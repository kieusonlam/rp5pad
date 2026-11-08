package org.nx2a.rp5pad;

/** Run on the PC: javac and java with app/src/.../UpdateRules.java. Prints failures and exits 1 if any. */
public class RulesTest {
    static int bad;

    static void is(String what, Object got, Object want) {
        boolean ok = want == null ? got == null : want.equals(got);
        if (!ok) bad++;
        System.out.println((ok ? "ok  " : "BAD ") + what + (ok ? "" : ": got " + got));
    }

    public static void main(String[] a) {
        String good = UpdateRules.DOWNLOADS + "v9.0.0/rp5pad-9.0.0.apk", d = "a".repeat(64);
        is("newer minor", UpdateRules.newer("0.1.10", "0.1.9"), true);
        is("newer major", UpdateRules.newer("1.0.0", "0.9.9"), true);
        is("same", UpdateRules.newer("0.1.3", "0.1.3"), false);
        is("older", UpdateRules.newer("0.1.2", "0.1.3"), false);
        is("bad new", UpdateRules.newer("latest", "0.1.3"), false);
        is("bad current", UpdateRules.newer("0.1.4", "dev"), false);
        is("null", UpdateRules.newer(null, "0.1.3"), false);
        is("huge number", UpdateRules.newer("99999999999.0.0", "0.1.3"), false);
        is("apk name", UpdateRules.apkVersion("rp5pad-0.1.3.apk"), "0.1.3");
        is("not the setup", UpdateRules.apkVersion("RP5Pad-Setup-0.1.3.exe"), null);
        is("old build's output name", UpdateRules.apkVersion("rp5pad.apk"), null);
        is("path in name", UpdateRules.apkVersion("x/rp5pad-0.1.3.apk"), null);
        is("digest", UpdateRules.sha256("sha256:" + d), d);
        is("md5", UpdateRules.sha256("md5:" + d), null);
        is("no digest", UpdateRules.sha256(null), null);
        is("short digest", UpdateRules.sha256("sha256:abc"), null);
        is("good url", UpdateRules.allowed(good, 1000), true);
        is("other site", UpdateRules.allowed("https://evil.example/rp5pad-9.0.0.apk", 1000), false);
        is("same-looking host", UpdateRules.allowed("https://github.com.evil.example/kieusonlam/rp5pad/releases/download/x.apk", 1000), false);
        is("http", UpdateRules.allowed(good.replace("https", "http"), 1000), false);
        is("too big", UpdateRules.allowed(good, 60_000_000), false);
        is("empty", UpdateRules.allowed(good, 0), false);
        System.out.println("failed: " + bad);
        System.exit(bad == 0 ? 0 : 1);
    }
}
