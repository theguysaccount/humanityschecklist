#!/usr/bin/env python3
"""Renders the site's images and video into static/ with headless Google Chrome.

  python3 tools/render.py icons   favicon set (favicon.ico, favicon.svg, apple-touch-icon, 192, 512, maskable)
  python3 tools/render.py cards   a 1200x630 share card for every page (static/og/*.png)
  python3 tools/render.py video   the 8-second og:video (static/og/humanitys-checklist.mp4), via tools/encode_mp4.swift
  python3 tools/render.py all

Needs Google Chrome and, for video, Swift (macOS). Outputs are committed, so the
GitHub build never needs either. New posts without a card fall back to the home card.
Talks to Chrome over --remote-debugging-pipe using the standard library only.
"""
import base64
import fcntl
import json
import os
import pathlib
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "tools" / "assets"
STATIC = ROOT / "static"
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
sys.path.insert(0, str(ROOT))
import build  # noqa: E402  (reuses the post loader so cards match the site)


class Chrome:
    """A minimal Chrome DevTools Protocol client over the debugging pipe (fds 3 and 4)."""

    def __init__(self):
        to_chrome_r, self._w = os.pipe()
        self._r, from_chrome_w = os.pipe()
        a = fcntl.fcntl(to_chrome_r, fcntl.F_DUPFD, 10)
        b = fcntl.fcntl(from_chrome_w, fcntl.F_DUPFD, 10)

        def wire_pipes():
            os.dup2(a, 3)
            os.dup2(b, 4)

        self._profile = tempfile.mkdtemp(prefix="hc-chrome-")
        self.proc = subprocess.Popen(
            [CHROME, "--headless=new", "--remote-debugging-pipe", "--disable-gpu", "--hide-scrollbars",
             "--no-first-run", "--no-default-browser-check", "--allow-file-access-from-files",
             "--force-color-profile=srgb", f"--user-data-dir={self._profile}", "about:blank"],
            preexec_fn=wire_pipes, close_fds=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for fd in (to_chrome_r, from_chrome_w, a, b):
            os.close(fd)
        self._buf, self._id, self.events = b"", 0, []
        target = self.send("Target.createTarget", {"url": "about:blank"})["targetId"]
        self.session = self.send("Target.attachToTarget", {"targetId": target, "flatten": True})["sessionId"]
        self.send("Page.enable", session=True)

    def _message(self):
        while b"\0" not in self._buf:
            chunk = os.read(self._r, 1 << 20)
            if not chunk:
                raise RuntimeError("Chrome closed the debugging pipe")
            self._buf += chunk
        raw, self._buf = self._buf.split(b"\0", 1)
        return json.loads(raw)

    def send(self, method, params=None, session=False):
        self._id += 1
        msg = {"id": self._id, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = self.session
        os.write(self._w, json.dumps(msg).encode() + b"\0")
        while True:
            m = self._message()
            if m.get("id") == self._id:
                if "error" in m:
                    raise RuntimeError(f"{method}: {m['error']}")
                return m.get("result", {})
            self.events.append(m)

    def wait_event(self, name):
        while True:
            for i, e in enumerate(self.events):
                if e.get("method") == name:
                    del self.events[i]
                    return e
            self.events.append(self._message())

    def open(self, url, width, height, transparent=False):
        self.send("Emulation.setDeviceMetricsOverride",
                  {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False}, session=True)
        color = {"r": 0, "g": 0, "b": 0, "a": 0} if transparent else None
        self.send("Emulation.setDefaultBackgroundColorOverride", {"color": color} if color else {}, session=True)
        self.events.clear()
        self.send("Page.navigate", {"url": url}, session=True)
        self.wait_event("Page.loadEventFired")
        return self.eval("Promise.resolve(window.ready).then(r => r ?? true)")

    def eval(self, expr):
        res = self.send("Runtime.evaluate", {"expression": expr, "awaitPromise": True, "returnByValue": True}, session=True)
        if "exceptionDetails" in res:
            raise RuntimeError(res["exceptionDetails"])
        return res["result"].get("value")

    def shot(self, path):
        data = self.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False}, session=True)["data"]
        pathlib.Path(path).write_bytes(base64.b64decode(data))

    def close(self):
        try:
            self.send("Browser.close")
        except Exception:
            pass
        self.proc.wait(timeout=10)
        shutil.rmtree(self._profile, ignore_errors=True)


def asset(name, **params):
    return (ASSETS / name).as_uri() + ("?" + urllib.parse.urlencode(params) if params else "")


def write_ico(path, pngs):
    """An .ico file that embeds PNG images (supported by every current browser)."""
    header = struct.pack("<HHH", 0, 1, len(pngs))
    entries, data, offset = b"", b"", 6 + 16 * len(pngs)
    for size, blob in pngs:
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(blob), offset)
        data += blob
        offset += len(blob)
    pathlib.Path(path).write_bytes(header + entries + data)


def render_icons(chrome):
    STATIC.mkdir(exist_ok=True)
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="hc-icons-"))
    plan = {
        "icon-512.png": dict(size=512, radius=0.22, pad=0.18),
        "icon-192.png": dict(size=192, radius=0.22, pad=0.18),
        "icon-maskable-512.png": dict(size=512, radius=0, pad=0.27),
        "apple-touch-icon.png": dict(size=180, radius=0, pad=0.2),
        "ico-48.png": dict(size=48, radius=0.2, pad=0.14),
        "ico-32.png": dict(size=32, radius=0.18, pad=0.12),
        "ico-16.png": dict(size=16, radius=0.15, pad=0.08),
    }
    for name, p in plan.items():
        chrome.open(asset("icon.html", **p), p["size"], p["size"], transparent=True)
        chrome.shot((tmp if name.startswith("ico-") else STATIC) / name)
    write_ico(STATIC / "favicon.ico", [(s, (tmp / f"ico-{s}.png").read_bytes()) for s in (16, 32, 48)])
    chrome.open(asset("icon.html", size=64, radius=0.22, pad=0.16), 64, 64, transparent=True)
    (STATIC / "favicon.svg").write_text(chrome.eval("svgSource()") + "\n")
    shutil.rmtree(tmp)
    print("icons: favicon.ico, favicon.svg, apple-touch-icon.png, icon-192.png, icon-512.png, icon-maskable-512.png")


def card_plan():
    """(file name, kicker, title, subtitle, bloomed items, heal) for every page."""
    wp = build.load_doc(build.CONTENT / "whitepaper.md")
    plan = [
        ("home", "What if $5 million was all it took?", "Six things to fix so we can fix everything else.",
         "", "story,status", 0.45),
        ("whitepaper", "Whitepaper", wp["title"], "The philosophy and method behind Humanity's Checklist.", "story", 0.3),
        ("blog", "Blog", "Fixing the world at the source", "Essays on systemic altruism, charity and the six sources.", "story,coordination", 0.3),
        ("questions", "Questions", "Fixing the world at the source, answered", "Plain answers to the questions people ask.", "story,vision", 0.3),
    ]
    for p in build.load_posts():
        plan.append((f"blog-{p['slug']}", "Blog", p["title"], "", p.get("item", "story"), 0.3))
    return plan


def render_cards(chrome):
    out = STATIC / "og"
    out.mkdir(parents=True, exist_ok=True)
    for name, kicker, title, sub, bloom, heal in card_plan():
        ok = chrome.open(asset("card.html", kicker=kicker, title=title, sub=sub, bloom=bloom, heal=heal), 1200, 630)
        if not ok:
            raise SystemExit("Fonts did not load for the share cards; check the network and try again.")
        chrome.shot(out / f"{name}.png")
    print(f"cards: {len(card_plan())} share cards in static/og/")


def encode_mp4(frames, out, fps):
    """Runs tools/encode_mp4.swift. Command Line Tools sometimes ship an SDK newer than
    their Swift compiler, so on failure retry with each installed SDK, newest first."""
    cmd = ["swift", str(ROOT / "tools" / "encode_mp4.swift"), str(frames), str(out), str(fps)]
    if subprocess.run(cmd, capture_output=True).returncode == 0:
        return
    for sdk in sorted(pathlib.Path("/Library/Developer/CommandLineTools/SDKs").glob("MacOSX*.sdk"), reverse=True):
        if subprocess.run(cmd, capture_output=True, env={**os.environ, "SDKROOT": str(sdk)}).returncode == 0:
            return
    raise SystemExit("Swift could not encode the video with any installed SDK.")


def render_video(chrome, fps=30, seconds=8):
    frames = pathlib.Path(tempfile.mkdtemp(prefix="hc-frames-"))
    if not chrome.open(asset("video.html"), 1280, 720):
        raise SystemExit("Fonts did not load for the video; check the network and try again.")
    total = fps * seconds
    for i in range(total):
        chrome.eval(f"renderFrame({i / fps})")
        chrome.shot(frames / f"{i:04d}.png")
    out = STATIC / "og" / "humanitys-checklist.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    encode_mp4(frames, out, fps)
    shutil.copy(frames / f"{int(fps * 6.6):04d}.png", STATIC / "og" / "video-poster.png")
    shutil.rmtree(frames)
    print(f"video: {total} frames -> {out.relative_to(ROOT)}")


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    chrome = Chrome()
    try:
        if what in ("icons", "all"):
            render_icons(chrome)
        if what in ("cards", "all"):
            render_cards(chrome)
        if what in ("video", "all"):
            render_video(chrome)
    finally:
        chrome.close()


if __name__ == "__main__":
    main()
