package org.nx2a.rp5pad;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** What the updater may accept. No Android classes here, so test_android/RulesTest.java can run it on the PC. */
final class UpdateRules {
    static final String DOWNLOADS = "https://github.com/kieusonlam/rp5pad/releases/download/";
    static final long MAX_SIZE = 50_000_000;
    private static final Pattern APK = Pattern.compile("rp5pad-(\\d+\\.\\d+\\.\\d+)\\.apk");
    private static final Pattern DIGEST = Pattern.compile("sha256:([0-9a-f]{64})");

    private UpdateRules() { }

    /** a > b, both "x.y.z"; anything else is not newer. */
    static boolean newer(String a, String b) {
        int[] x = parse(a), y = parse(b);
        if (x == null || y == null) return false;
        for (int i = 0; i < 3; i++) if (x[i] != y[i]) return x[i] > y[i];
        return false;
    }

    static int[] parse(String v) {
        if (v == null || !v.matches("\\d{1,6}\\.\\d{1,6}\\.\\d{1,6}")) return null;
        String[] p = v.split("\\.");
        return new int[] {Integer.parseInt(p[0]), Integer.parseInt(p[1]), Integer.parseInt(p[2])};
    }

    /** The version in an APK's file name: a release can change only the PC app, so its tag says nothing about the APK. Null when this is not our APK. */
    static String apkVersion(String name) {
        Matcher m = APK.matcher(name == null ? "" : name);
        return m.matches() ? m.group(1) : null;
    }

    /** The SHA-256 from GitHub's "digest" field, or null. */
    static String sha256(String digest) {
        Matcher m = DIGEST.matcher(digest == null ? "" : digest);
        return m.matches() ? m.group(1) : null;
    }

    static boolean allowed(String url, long size) {
        return url != null && url.startsWith(DOWNLOADS) && size > 0 && size <= MAX_SIZE;
    }
}
