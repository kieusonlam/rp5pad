"""test_update_rules.py: what pad_update may accept. Run with any Python 3.13."""
import os
import pad_update as p
os.environ.pop("RP5PAD_UPDATE_API", None)
good = "https://github.com/kieusonlam/rp5pad/releases/download/v9.0.0/RP5Pad-Setup-9.0.0.exe"
d = "sha256:" + "a" * 64


def rel(tag="v9.0.0", name="RP5Pad-Setup-9.0.0.exe", digest=d, url=good, size=1000):
    return {"tag_name": tag, "assets": [{"name": "rp5pad-1.apk", "digest": d, "browser_download_url": good, "size": 5}, {"name": name, "digest": digest, "browser_download_url": url, "size": size}]}


cases = {
    "good": (rel(), True),
    "no digest": (rel(digest=None), False),
    "md5 digest": (rel(digest="md5:" + "a" * 32), False),
    "other site": (rel(url="https://evil.example/RP5Pad-Setup-9.0.0.exe"), False),
    "http": (rel(url=good.replace("https", "http")), False),
    "same-looking host": (rel(url="https://github.com.evil.example/kieusonlam/rp5pad/releases/download/x.exe"), False),
    "too big": (rel(size=10 ** 9), False),
    "odd tag": (rel(tag="latest"), False),
    "no installer": ({"tag_name": "v9.0.0", "assets": []}, False),
}
bad = 0
for name, (data, want) in cases.items():
    got = p.read_release(data) is not None
    bad += got != want
    print("ok " if got == want else "BAD", name)
print("order:", p.parse("0.1.10") > p.parse("0.1.9"), p.parse("v1.0.0") > p.parse("0.9.9"))
print("failed:", bad)
