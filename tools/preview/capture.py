#!/usr/bin/env python3
"""Render preview images of the built character GLB assets.

Serves the repository over HTTP, loads tools/preview/preview.html in headless
Chromium and captures a set of camera angles per character.

Usage:
    python3 tools/preview/capture.py --model hitori-gotoh.glb --out ../output/preview
"""

from __future__ import annotations

import argparse
import functools
import http.server
import os
import socket
import socketserver
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

VIEWS = [
    ("front", 0, 6, 5.2, 0.0),
    ("three_quarter", 32, 10, 5.0, 0.0),
    ("side", 88, 4, 5.0, 0.0),
    ("back", 180, 8, 5.2, 0.0),
    ("head_front", 8, 4, 2.5, 0.95),
    ("head_three_quarter", 38, 8, 2.6, 0.95),
]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve(directory: str):
    handler = functools.partial(QuietHandler, directory=directory)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, httpd.server_address[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="hitori-gotoh.glb")
    parser.add_argument("--out", default=os.path.join(ROOT, "..", "output", "preview"))
    parser.add_argument("--size", type=int, default=900)
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    httpd, port = serve(ROOT)
    base = f"http://127.0.0.1:{port}/tools/preview/preview.html"
    print(f"serving {ROOT} on {port}")

    from playwright.sync_api import sync_playwright

    written = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="/usr/local/bin/chromium",
            args=["--no-sandbox", "--use-gl=swiftshader", "--enable-unsafe-swiftshader"],
        )
        page = browser.new_page(viewport={"width": args.size, "height": args.size})
        page.on("console", lambda m: print(f"  [console:{m.type}] {m.text}")
                if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: print(f"  [pageerror] {e}"))

        url = f"{base}?model={args.model}&size={args.size}"
        print(f"loading {url}")
        page.goto(url, wait_until="load", timeout=60000)
        page.wait_for_function("window.modelReady === true || window.modelError", timeout=60000)

        if page.evaluate("window.modelError"):
            print("MODEL FAILED TO LOAD:", page.evaluate("window.modelError"))
            browser.close()
            httpd.shutdown()
            return 1

        stem = os.path.splitext(args.model)[0]
        for name, az, el, dist, ty in VIEWS:
            page.evaluate(f"window.setView({az}, {el}, {dist}, {ty})")
            time.sleep(0.25)
            path = os.path.join(args.out, f"{stem}_{name}.png")
            page.locator("canvas").screenshot(path=path)
            written.append(path)
            print(f"  wrote {path}")

        browser.close()
    httpd.shutdown()

    print(f"\n{len(written)} previews in {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
