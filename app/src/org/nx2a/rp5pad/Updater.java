package org.nx2a.rp5pad;

import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageInstaller;
import android.net.Uri;
import android.provider.Settings;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import org.json.JSONArray;
import org.json.JSONObject;

/** Looks for a newer APK in the GitHub releases when the app opens. Shows it in the app, and installs only after a tap on Update and Android's own question. Failing to check is silent: no network is normal here. */
final class Updater {
    static final String API = "https://api.github.com/repos/kieusonlam/rp5pad/releases/latest";
    static final String DONE = "org.nx2a.rp5pad.INSTALL_DONE";
    final PadActivity a;
    String version, url, sha;
    long size;
    volatile boolean busy;

    Updater(PadActivity a) { this.a = a; }

    static HttpURLConnection open(String u) throws IOException {
        HttpURLConnection c = (HttpURLConnection) new URL(u).openConnection();
        c.setConnectTimeout(15000);
        c.setReadTimeout(30000);
        c.setRequestProperty("User-Agent", "RP5Pad-Android");
        return c;
    }

    void check() {
        new Thread(() -> {
            try {
                apk().delete();
                String me = a.getPackageManager().getPackageInfo(a.getPackageName(), 0).versionName;
                HttpURLConnection c = open(API);
                c.setRequestProperty("Accept", "application/vnd.github+json");
                ByteArrayOutputStream body = new ByteArrayOutputStream();
                try (InputStream in = c.getInputStream()) {
                    byte[] b = new byte[8192];
                    for (int n; (n = in.read(b)) > 0 && body.size() < 2_000_000; ) body.write(b, 0, n);
                }
                JSONArray assets = new JSONObject(body.toString("UTF-8")).getJSONArray("assets");
                for (int i = 0; i < assets.length(); i++) {
                    JSONObject o = assets.getJSONObject(i);
                    String v = UpdateRules.apkVersion(o.optString("name"));
                    String s = UpdateRules.sha256(o.optString("digest"));
                    String u = o.optString("browser_download_url");
                    long z = o.optLong("size");
                    if (v != null && s != null && UpdateRules.allowed(u, z) && UpdateRules.newer(v, me)) {
                        version = v;
                        url = u;
                        sha = s;
                        size = z;
                        a.showUpdate("Update " + v + " available", "Update", this::start);
                        return;
                    }
                }
            } catch (Exception e) { /* offline, or nothing readable: try again next time */ }
        }, "update-check").start();
    }

    File apk() { return new File(a.getCacheDir(), "update.apk"); }

    void start() {
        if (busy || version == null) return;
        if (!a.getPackageManager().canRequestPackageInstalls()) {
            a.showUpdate("Allow installs from RP5 Pad, then tap Update again", "Update", this::start);
            a.startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + a.getPackageName())));
            return;
        }
        busy = true;
        a.showUpdate("Downloading " + version + "…", null, null);
        new Thread(() -> {
            try {
                download();
                install();
            } catch (Exception e) {
                failed("The update failed. Try again later.");
            }
        }, "update-install").start();
    }

    void failed(String why) {
        busy = false;
        apk().delete();
        a.showUpdate(why, "Update", this::start);
    }

    void download() throws Exception {
        MessageDigest h = MessageDigest.getInstance("SHA-256");
        long total = 0;
        try (InputStream in = open(url).getInputStream(); OutputStream out = new FileOutputStream(apk())) {
            byte[] b = new byte[65536];
            for (int n; (n = in.read(b)) > 0; ) {
                total += n;
                if (total > UpdateRules.MAX_SIZE) throw new IOException("too large");
                h.update(b, 0, n);
                out.write(b, 0, n);
            }
        }
        StringBuilder hex = new StringBuilder();
        for (byte x : h.digest()) hex.append(String.format("%02x", x));
        if (!hex.toString().equals(sha)) throw new IOException("checksum");
    }

    /** A session, not an intent to a file: this needs no FileProvider. Android asks the person before anything is installed. */
    void install() throws Exception {
        PackageInstaller pi = a.getPackageManager().getPackageInstaller();
        PackageInstaller.SessionParams p = new PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL);
        p.setAppPackageName(a.getPackageName());
        int id = pi.createSession(p);
        try (PackageInstaller.Session s = pi.openSession(id)) {
            try (InputStream in = new FileInputStream(apk()); OutputStream out = s.openWrite("update.apk", 0, apk().length())) {
                byte[] b = new byte[65536];
                for (int n; (n = in.read(b)) > 0; ) out.write(b, 0, n);
                s.fsync(out);
            }
            a.registerReceiver(new BroadcastReceiver() {
                @Override public void onReceive(Context c, Intent i) {
                    int st = i.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE);
                    if (st == PackageInstaller.STATUS_PENDING_USER_ACTION) {
                        Intent ask = i.getParcelableExtra(Intent.EXTRA_INTENT);
                        if (ask != null) a.startActivity(ask.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
                        return;
                    }
                    a.unregisterReceiver(this);
                    if (st == PackageInstaller.STATUS_SUCCESS) return;   // Android has already replaced this app
                    if (st == PackageInstaller.STATUS_FAILURE_ABORTED) failed("Update " + version + " available");
                    else if (st == PackageInstaller.STATUS_FAILURE_CONFLICT || st == PackageInstaller.STATUS_FAILURE_INCOMPATIBLE) failed("Cannot update over this copy: uninstall RP5 Pad, then install the new one.");
                    else failed("The update failed. Try again later.");
                }
            }, new IntentFilter(DONE));
            Intent done = new Intent(DONE).setPackage(a.getPackageName());
            s.commit(PendingIntent.getBroadcast(a, id, done, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_MUTABLE).getIntentSender());
        }
    }
}
