package org.nx2a.rp5pad;

import android.app.Activity;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.Gravity;
import android.view.InputDevice;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.view.inputmethod.EditorInfo;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.io.DataInputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.InterfaceAddress;
import java.net.NetworkInterface;
import java.net.Socket;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.security.SecureRandom;
import java.util.Collections;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

/** Reads the handheld's buttons and sticks while in front and sends them to the PC over TCP (16 bytes, see fill()). The screen dims while connected and untouched. */
public class PadActivity extends Activity {
    static final int PORT = 7878, DIM_MS = 8000;
    static final int AUTO = 0, USB = 1, WIFI = 2;
    static final int BG = 0xFF0B0F14, CARD = 0xFF141A22, TEXT = 0xFFE6EBF0, MUTED = 0xFF8A97A6, ACCENT = 0xFF22D3EE, WAIT = 0xFFF5B83D;
    // XInput button bits, so the server passes them on as they are
    static final int UP = 1, DOWN = 2, LEFT = 4, RIGHT = 8, START = 0x10, BACK = 0x20, L3 = 0x40, R3 = 0x80, LB = 0x100, RB = 0x200, GUIDE = 0x400, A = 0x1000, B = 0x2000, X = 0x4000, Y = 0x8000;

    final Object lock = new Object();
    int keys, hat, seq;
    volatile int echo;   // the last byte the PC sent: back to it for the round trip it shows
    float lx, ly, rx, ry, lta, rta;
    boolean l2, r2, dirty;
    volatile boolean running, connected;
    volatile String host = "";
    volatile int mode = AUTO, gen;   // gen: bumped when the connection choice changes
    volatile int declinedGen = -1;   // the PC said no: no more asking until the choice is touched again
    volatile Socket pairing;   // closed when waiting for an answer is abandoned
    final Handler ui = new Handler(Looper.getMainLooper());
    final Runnable dim = () -> { if (connected) brightness(0.01f); };
    SharedPreferences prefs;
    TextView title, subtitle;
    View dot;
    PadView padView;
    EditText ipField;
    TextView[] seg = new TextView[3];
    LinearLayout updateCard;
    TextView updateText, updateButton;

    int dp(float v) { return Math.round(v * getResources().getDisplayMetrics().density); }

    GradientDrawable round(int color, float radius) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(color);
        d.setCornerRadius(dp(radius));
        return d;
    }

    TextView text(String s, float size, int color, boolean medium) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(size);
        t.setTextColor(color);
        if (medium) t.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        return t;
    }

    LinearLayout card(int orientation) {
        LinearLayout c = new LinearLayout(this);
        c.setOrientation(orientation);
        c.setBackground(round(CARD, 16));
        c.setPadding(dp(16), dp(14), dp(16), dp(14));
        return c;
    }

    LinearLayout.LayoutParams wrap(int top) {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        p.topMargin = dp(top);
        return p;
    }

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        getWindow().getDecorView().setBackgroundColor(BG);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        prefs = getPreferences(MODE_PRIVATE);
        host = prefs.getString("host", "");
        mode = prefs.getInt("mode", AUTO);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.HORIZONTAL);
        root.setBackgroundColor(BG);
        root.setPadding(dp(20), dp(16), dp(20), dp(16));
        root.setFocusableInTouchMode(true);

        LinearLayout left = new LinearLayout(this);
        left.setOrientation(LinearLayout.VERTICAL);
        left.setGravity(Gravity.CENTER_VERTICAL);
        root.addView(left, new LinearLayout.LayoutParams(dp(300), LinearLayout.LayoutParams.MATCH_PARENT));

        LinearLayout brand = new LinearLayout(this);
        brand.setGravity(Gravity.CENTER_VERTICAL);
        ImageView logo = new ImageView(this);
        logo.setImageDrawable(getDrawable(getApplicationInfo().icon));
        logo.setClipToOutline(true);
        logo.setBackground(round(Color.TRANSPARENT, 10));
        brand.addView(logo, new LinearLayout.LayoutParams(dp(40), dp(40)));
        TextView name = text("RP5 Pad", 20, TEXT, true);
        name.setPadding(dp(12), 0, 0, 0);
        brand.addView(name);
        left.addView(brand);

        LinearLayout st = card(LinearLayout.HORIZONTAL);
        st.setGravity(Gravity.CENTER_VERTICAL);
        dot = new View(this);
        LinearLayout.LayoutParams dl = new LinearLayout.LayoutParams(dp(10), dp(10));
        dl.rightMargin = dp(12);
        st.addView(dot, dl);
        LinearLayout tx = new LinearLayout(this);
        tx.setOrientation(LinearLayout.VERTICAL);
        title = text("", 15, TEXT, true);
        subtitle = text("", 12, MUTED, false);
        subtitle.setPadding(0, dp(2), 0, 0);
        tx.addView(title);
        tx.addView(subtitle);
        st.addView(tx, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        left.addView(st, wrap(16));

        TextView connect = text("Connection", 12, MUTED, true);
        connect.setPadding(dp(4), 0, 0, 0);
        left.addView(connect, wrap(16));
        LinearLayout segs = new LinearLayout(this);
        segs.setBackground(round(CARD, 12));
        segs.setPadding(dp(4), dp(4), dp(4), dp(4));
        String[] names = {"Auto", "USB", "WiFi"};
        for (int i = 0; i < 3; i++) {
            final int m = i;
            TextView t = text(names[i], 14, TEXT, true);
            t.setGravity(Gravity.CENTER);
            t.setPadding(0, dp(9), 0, dp(9));
            t.setOnClickListener(v -> choose(m));
            seg[i] = t;
            segs.addView(t, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        }
        left.addView(segs, wrap(6));

        ipField = new EditText(this);
        ipField.setText(host);
        ipField.setHint("PC address: find automatically");
        ipField.setHintTextColor(MUTED);
        ipField.setTextColor(TEXT);
        ipField.setTextSize(14);
        ipField.setSingleLine();
        ipField.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        ipField.setImeOptions(EditorInfo.IME_ACTION_DONE | EditorInfo.IME_FLAG_NO_EXTRACT_UI);
        ipField.setBackground(round(CARD, 12));
        ipField.setPadding(dp(14), dp(11), dp(14), dp(11));
        ipField.setOnEditorActionListener((v, id, ev) -> {
            host = v.getText().toString().trim();
            prefs.edit().putString("host", host).apply();
            gen++;
            v.clearFocus();
            root.requestFocus();
            return false;
        });
        left.addView(ipField, wrap(8));

        updateCard = card(LinearLayout.HORIZONTAL);
        updateCard.setGravity(Gravity.CENTER_VERTICAL);
        updateCard.setVisibility(View.GONE);
        updateText = text("", 13, TEXT, false);
        updateCard.addView(updateText, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        updateButton = text("", 13, BG, true);
        updateButton.setBackground(round(ACCENT, 9));
        updateButton.setPadding(dp(14), dp(7), dp(14), dp(7));
        LinearLayout.LayoutParams ub = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        ub.leftMargin = dp(10);
        updateCard.addView(updateButton, ub);
        left.addView(updateCard, wrap(12));

        padView = new PadView(this, this);
        LinearLayout.LayoutParams pl = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.MATCH_PARENT, 1);
        pl.leftMargin = dp(16);
        root.addView(padView, pl);

        setContentView(root);
        root.requestFocus();
        paintChoice();
        waiting();
        new Updater(this).check();
    }

    /** The update card; no button while something is under way. From any thread. */
    void showUpdate(String s, String button, Runnable tap) {
        ui.post(() -> {
            updateText.setText(s);
            updateButton.setText(button == null ? "" : button);
            updateButton.setVisibility(button == null ? View.GONE : View.VISIBLE);
            updateButton.setOnClickListener(tap == null ? null : v -> tap.run());
            updateCard.setVisibility(View.VISIBLE);
        });
    }

    void choose(int m) {
        mode = m;
        prefs.edit().putInt("mode", m).apply();
        gen++;
        dropPairing();
        paintChoice();
        wake();
    }

    void paintChoice() {
        for (int i = 0; i < 3; i++) {
            boolean on = i == mode;
            seg[i].setBackground(on ? round(ACCENT, 9) : null);
            seg[i].setTextColor(on ? BG : TEXT);
        }
        ipField.setVisibility(mode == WIFI ? View.VISIBLE : View.GONE);
    }

    void status(boolean on, String t, String s) {
        ui.post(() -> {
            boolean was = connected;
            connected = on;
            GradientDrawable d = new GradientDrawable();
            d.setShape(GradientDrawable.OVAL);
            d.setColor(on ? ACCENT : WAIT);
            dot.setBackground(d);
            title.setText(t);
            subtitle.setText(s);
            if (on != was) wake();
        });
    }

    void dropPairing() {
        Socket p = pairing;
        if (p != null) new Thread(() -> { try { p.close(); } catch (IOException e) { /* gone already */ } }).start();
    }

    void waiting() {
        if (declinedGen == gen) {
            status(false, "Not allowed on the PC", "Tap Auto, USB or WiFi to ask again, after 30 seconds.");
            return;
        }
        String s = mode == USB ? "Plug in the USB cable and start RP5 Pad on the PC."
                : mode == WIFI ? "On the PC, turn on Allow WiFi connections in the RP5 Pad tray menu."
                : "Start RP5 Pad on the PC. Connects over USB, or WiFi if allowed in its tray menu.";
        status(false, "Looking for your PC…", s);
    }

    void brightness(float v) {
        WindowManager.LayoutParams a = getWindow().getAttributes();
        a.screenBrightness = v;
        getWindow().setAttributes(a);
    }

    void wake() {
        brightness(WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE);
        ui.removeCallbacks(dim);
        ui.postDelayed(dim, DIM_MS);
    }

    void release() {
        synchronized (lock) { keys = hat = 0; lx = ly = rx = ry = lta = rta = 0; l2 = r2 = false; dirty = true; lock.notifyAll(); }
        padView.invalidate();
    }

    @Override public void onWindowFocusChanged(boolean has) {
        super.onWindowFocusChanged(has);
        if (has) getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_LAYOUT_STABLE | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION);
    }

    @Override protected void onResume() {
        super.onResume();
        running = true;
        wake();
        new Thread(this::sendLoop, "pad-send").start();
    }

    @Override protected void onPause() {   // nothing stays held on the PC when this leaves the front
        super.onPause();
        running = false;
        dropPairing();
        ui.removeCallbacks(dim);
        release();
    }

    @Override public boolean dispatchTouchEvent(MotionEvent ev) { wake(); return super.dispatchTouchEvent(ev); }

    static boolean pad(int source) {
        return (source & InputDevice.SOURCE_GAMEPAD) == InputDevice.SOURCE_GAMEPAD || (source & InputDevice.SOURCE_JOYSTICK) == InputDevice.SOURCE_JOYSTICK || (source & InputDevice.SOURCE_DPAD) == InputDevice.SOURCE_DPAD;
    }

    static int bit(int code) {
        switch (code) {
            case KeyEvent.KEYCODE_BUTTON_A: return A;
            case KeyEvent.KEYCODE_BUTTON_B: return B;
            case KeyEvent.KEYCODE_BUTTON_X: return X;
            case KeyEvent.KEYCODE_BUTTON_Y: return Y;
            case KeyEvent.KEYCODE_BUTTON_L1: return LB;
            case KeyEvent.KEYCODE_BUTTON_R1: return RB;
            case KeyEvent.KEYCODE_BUTTON_THUMBL: return L3;
            case KeyEvent.KEYCODE_BUTTON_THUMBR: return R3;
            case KeyEvent.KEYCODE_BUTTON_START: return START;
            case KeyEvent.KEYCODE_BUTTON_SELECT: return BACK;
            case KeyEvent.KEYCODE_BUTTON_MODE: return GUIDE;
            case KeyEvent.KEYCODE_DPAD_UP: return UP;
            case KeyEvent.KEYCODE_DPAD_DOWN: return DOWN;
            case KeyEvent.KEYCODE_DPAD_LEFT: return LEFT;
            case KeyEvent.KEYCODE_DPAD_RIGHT: return RIGHT;
            default: return 0;
        }
    }

    @Override public boolean dispatchKeyEvent(KeyEvent ev) {
        int code = ev.getKeyCode(), a = ev.getAction();
        if (!pad(ev.getSource()) || code == KeyEvent.KEYCODE_VOLUME_UP || code == KeyEvent.KEYCODE_VOLUME_DOWN) return super.dispatchKeyEvent(ev);
        if (a != KeyEvent.ACTION_DOWN && a != KeyEvent.ACTION_UP) return true;
        boolean down = a == KeyEvent.ACTION_DOWN;
        synchronized (lock) {
            if (code == KeyEvent.KEYCODE_BUTTON_L2) l2 = down;
            else if (code == KeyEvent.KEYCODE_BUTTON_R2) r2 = down;
            else { int m = bit(code); keys = down ? keys | m : keys & ~m; }
            dirty = true;
            lock.notifyAll();
        }
        padView.invalidate();
        return true;
    }

    @Override public boolean dispatchGenericMotionEvent(MotionEvent ev) {
        if ((ev.getSource() & InputDevice.SOURCE_JOYSTICK) != InputDevice.SOURCE_JOYSTICK || ev.getAction() != MotionEvent.ACTION_MOVE) return super.dispatchGenericMotionEvent(ev);
        synchronized (lock) {
            lx = ev.getAxisValue(MotionEvent.AXIS_X);
            ly = ev.getAxisValue(MotionEvent.AXIS_Y);
            rx = ev.getAxisValue(MotionEvent.AXIS_Z);
            ry = ev.getAxisValue(MotionEvent.AXIS_RZ);
            lta = Math.max(ev.getAxisValue(MotionEvent.AXIS_LTRIGGER), ev.getAxisValue(MotionEvent.AXIS_BRAKE));
            rta = Math.max(ev.getAxisValue(MotionEvent.AXIS_RTRIGGER), ev.getAxisValue(MotionEvent.AXIS_GAS));
            float hx = ev.getAxisValue(MotionEvent.AXIS_HAT_X), hy = ev.getAxisValue(MotionEvent.AXIS_HAT_Y);
            hat = (hx < -0.5f ? LEFT : 0) | (hx > 0.5f ? RIGHT : 0) | (hy < -0.5f ? UP : 0) | (hy > 0.5f ? DOWN : 0);
            dirty = true;
            lock.notifyAll();
        }
        padView.invalidate();
        return true;
    }

    static short stick(float v) { return (short) Math.round(Math.max(-1f, Math.min(1f, v)) * 32767f); }
    static int trig(float v, boolean digital) { return digital ? 255 : Math.round(Math.max(0f, Math.min(1f, v)) * 255f); }

    /** The packet: "R5", u16 buttons (XInput bits), i16 lx ly rx ry (Android's sign: up is negative), u8 lt rt, u8 sequence, u8 echo; little endian. */
    void fill(ByteBuffer o) {
        o.clear();
        o.put((byte) 'R').put((byte) '5');
        o.putShort((short) (keys | hat));
        o.putShort(stick(lx)).putShort(stick(ly)).putShort(stick(rx)).putShort(stick(ry));
        o.put((byte) trig(lta, l2)).put((byte) trig(rta, r2));
        o.putShort((short) ((echo << 8) | (seq++ & 0xff)));
    }

    /** Asks the WiFi network for the PC; its address, or null. */
    static String discover() {
        try (DatagramSocket u = new DatagramSocket()) {
            u.setBroadcast(true);
            u.setSoTimeout(500);
            byte[] ask = "RP5PAD?".getBytes("US-ASCII");
            for (int i = 0; i < 3; i++) {   // a broadcast is easily lost on WiFi
                for (NetworkInterface n : Collections.list(NetworkInterface.getNetworkInterfaces())) {
                    if (!n.isUp() || n.isLoopback()) continue;
                    for (InterfaceAddress a : n.getInterfaceAddresses()) {
                        InetAddress b = a.getBroadcast();
                        if (b != null) u.send(new DatagramPacket(ask, ask.length, b, PORT));
                    }
                }
                Thread.sleep(60);
            }
            byte[] got = new byte[16];
            DatagramPacket r = new DatagramPacket(got, got.length);
            u.receive(r);
            return new String(got, 0, r.getLength(), "US-ASCII").equals("RP5PAD!") ? r.getAddress().getHostAddress() : null;
        } catch (Exception e) {
            return null;
        }
    }

    /** One connection, until the choice changes or this leaves the front: false when nothing of ours answered. The server greets with "R5": with adb reverse set up, a connection succeeds even when no server runs. */
    boolean session(String h, int g, ByteBuffer o) throws InterruptedException {
        try (Socket s = new Socket()) {
            s.setTcpNoDelay(true);
            s.connect(new InetSocketAddress(h, PORT), 500);
            s.setSoTimeout(500);
            DataInputStream in = new DataInputStream(s.getInputStream());
            OutputStream out = s.getOutputStream();
            if (in.read() != 'R' || in.read() != '5') return false;
            int how = in.read();
            if (how == 'A' && !authorize(s, in, out, g)) return false;
            if (how != 'A' && how != 'U') return false;
            if (!h.equals("127.0.0.1")) prefs.edit().putString("last", h).apply();
            status(true, "Connected", h.equals("127.0.0.1") ? "Over USB. Your PC sees an Xbox controller." : "Over WiFi (" + h + "). Your PC sees an Xbox controller.");
            Thread reader = new Thread(() -> {
                while (true) {
                    try {
                        int v = in.read();
                        if (v < 0) return;
                        synchronized (lock) { echo = v; dirty = true; lock.notifyAll(); }
                    } catch (java.net.SocketTimeoutException e) {
                        // nothing yet
                    } catch (IOException e) {
                        return;
                    }
                }
            }, "pad-echo");
            reader.setDaemon(true);
            reader.start();
            boolean last = false;
            while (!last) {
                last = !running || g != gen;   // one packet after leaving the front: the released state
                synchronized (lock) {
                    if (!dirty && !last) lock.wait(100);   // also a heartbeat: the server lets go of everything after 1 s of silence
                    dirty = false;
                    fill(o);
                }
                out.write(o.array(), 0, 16);
            }
            return true;
        } catch (IOException e) {
            return false;
        }
    }

    static String hex(byte[] b) {
        StringBuilder t = new StringBuilder();
        for (byte v : b) t.append(String.format("%02x", v));
        return t.toString();
    }

    static byte[] unhex(String s) {
        byte[] b = new byte[s.length() / 2];
        for (int i = 0; i < b.length; i++) b[i] = (byte) Integer.parseInt(s.substring(2 * i, 2 * i + 2), 16);
        return b;
    }

    byte[] deviceId() {
        String v = prefs.getString("device", null);
        if (v == null) {
            byte[] b = new byte[16];
            new SecureRandom().nextBytes(b);
            v = hex(b);
            prefs.edit().putString("device", v).apply();
        }
        return unhex(v);
    }

    /** The WiFi handshake (pad_server.py handshake): true when the PC accepts this device. */
    boolean authorize(Socket s, DataInputStream in, OutputStream out, int g) throws IOException {
        byte[] pc = new byte[16], nonce = new byte[16], id = deviceId();
        in.readFully(pc);
        in.readFully(nonce);
        String slot = "key_" + hex(pc), key = prefs.getString(slot, null);
        if (key != null) {
            try {
                Mac mac = Mac.getInstance("HmacSHA256");
                mac.init(new SecretKeySpec(unhex(key), "HmacSHA256"));
                mac.update(nonce);
                byte[] sig = mac.doFinal(id);
                ByteBuffer o = ByteBuffer.allocate(1 + 16 + 32);
                o.put((byte) 'H').put(id).put(sig);
                out.write(o.array());
            } catch (java.security.GeneralSecurityException e) {
                return false;
            }
            if (in.read() == 'K') return true;
            prefs.edit().remove(slot).apply();   // this PC forgot this device: pair again on the next try
            return false;
        }
        if (declinedGen == g) return false;
        byte[] name = (Build.MODEL == null ? "Android" : Build.MODEL).getBytes("UTF-8");
        int n = Math.min(name.length, 40);
        ByteBuffer o = ByteBuffer.allocate(1 + 16 + 1 + n);
        o.put((byte) 'P').put(id).put((byte) n).put(name, 0, n);
        out.write(o.array());
        s.setSoTimeout(70000);   // the question stays up for a minute on the PC
        pairing = s;
        try {
            int r = in.read();
            if (r == 'C') {
                byte[] code = new byte[6];
                in.readFully(code);
                String c = new String(code, "US-ASCII");
                status(false, "Pair with this PC: " + c.substring(0, 3) + " " + c.substring(3), "Check that the PC shows the same code, then choose Yes there.");
                r = in.read();
            }
            if (r == 'Y') {
                byte[] k = new byte[32];
                in.readFully(k);
                prefs.edit().putString(slot, hex(k)).apply();
                return true;
            }
            if (r == 'D' || r == 'B') declinedGen = g;
            return false;
        } finally {
            pairing = null;
            s.setSoTimeout(500);
        }
    }

    void sendLoop() {
        ByteBuffer o = ByteBuffer.allocate(16).order(ByteOrder.LITTLE_ENDIAN);
        try {
            while (running) {
                int g = gen, m = mode;
                String ip = host;
                boolean ok = false;
                if (m != WIFI) ok = session("127.0.0.1", g, o);
                if (!ok && running && g == gen && m != USB) {
                    String last = prefs.getString("last", "");
                    boolean manual = m == WIFI && !ip.isEmpty();
                    if (manual) ok = session(ip, g, o);
                    else {
                        if (!last.isEmpty()) ok = session(last, g, o);   // the PC usually keeps its address: no need to wait for a broadcast
                        if (!ok && running && g == gen) {
                            String h = discover();
                            ok = h != null && session(h, g, o);
                        }
                    }
                }
                if (running && g == gen) waiting();
                if (!ok && running && g == gen) Thread.sleep(800);
            }
        } catch (InterruptedException e) {
            // leaving
        }
    }
}
