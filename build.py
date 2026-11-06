"""build.py: builds app/ into rp5pad.apk with the SDK's tools directly (no Gradle)."""
import glob
import os
import shutil
import subprocess
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
SDK, JDK = os.environ.get("ANDROID_HOME", r"D:\dev\android-sdk"), os.environ.get("JAVA_HOME", r"D:\dev\jdk-21")
BT = os.path.join(SDK, "build-tools", "36.1.0")
JAR = os.path.join(SDK, "platforms", "android-36", "android.jar")
OUT = os.path.join(HERE, "build")
KS = os.path.join(HERE, "debug.keystore")   # local, throwaway: this app is only sideloaded


def run(*a):
    subprocess.run(a, check=True)


shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(os.path.join(OUT, "cls"))
app = os.path.join(HERE, "app")
flat = os.path.join(OUT, "res.zip")
run(os.path.join(BT, "aapt2.exe"), "compile", "--dir", os.path.join(app, "res"), "-o", flat)
raw = os.path.join(OUT, "raw.apk")
run(os.path.join(BT, "aapt2.exe"), "link", "-I", JAR, "--manifest", os.path.join(app, "AndroidManifest.xml"), "--min-sdk-version", "26", "--target-sdk-version", "33", "-o", raw, flat)
src = glob.glob(os.path.join(app, "src", "**", "*.java"), recursive=True)
run(os.path.join(JDK, "bin", "javac.exe"), "-encoding", "UTF-8", "--release", "11", "-classpath", JAR, "-d", os.path.join(OUT, "cls"), *src)
cls = glob.glob(os.path.join(OUT, "cls", "**", "*.class"), recursive=True)
run(os.path.join(BT, "d8.bat"), "--release", "--min-api", "26", "--lib", JAR, "--output", OUT, *cls)
with zipfile.ZipFile(raw, "a") as z:
    z.write(os.path.join(OUT, "classes.dex"), "classes.dex")
aligned = os.path.join(OUT, "aligned.apk")
run(os.path.join(BT, "zipalign.exe"), "-f", "4", raw, aligned)
if not os.path.exists(KS):
    run(os.path.join(JDK, "bin", "keytool.exe"), "-genkeypair", "-keystore", KS, "-storepass", "android", "-keypass", "android", "-alias", "rp5pad", "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000", "-dname", "CN=rp5pad")
apk = os.path.join(HERE, "rp5pad.apk")
run(os.path.join(BT, "apksigner.bat"), "sign", "--ks", KS, "--ks-pass", "pass:android", "--out", apk, aligned)
print("built", apk, os.path.getsize(apk), "bytes")
