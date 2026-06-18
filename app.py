#!/usr/bin/env python3
"""
All-in-one host for the WC 2026 Office Sweep.

Serves the static page AND refreshes data.js on a timer in the background, so
there's only ONE thing to run — no separate cron job needed.

  pip install flask
  export FOOTBALL_DATA_KEY=your-key       # PowerShell: $env:FOOTBALL_DATA_KEY="your-key"
  python app.py

Then open http://<this-machine>:8080/  (the office TV, phones, laptops).

The data refreshes every REFRESH_SECONDS (default 600 = 10 min). The browser page
also re-fetches data.js every 60s, so screens update themselves with no reload.
"""

import os
import sys
import time
import threading
import subprocess

from flask import Flask, send_from_directory

HERE = os.path.dirname(os.path.abspath(__file__))
REFRESH_SECONDS = int(os.environ.get("REFRESH_SECONDS", "600"))
PORT = int(os.environ.get("PORT", "8080"))

app = Flask(__name__, static_folder=HERE, static_url_path="")


@app.route("/")
def index():
    return send_from_directory(HERE, "index.html")


def run_update():
    """Run update.py once as a subprocess so a failure can't crash the server."""
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, "update.py")],
                           capture_output=True, text=True, timeout=60)
        print(r.stdout.strip() or r.stderr.strip(), flush=True)
    except Exception as e:  # noqa: BLE001
        print("update.py failed: %s" % e, flush=True)


def updater_loop():
    while True:
        run_update()
        time.sleep(REFRESH_SECONDS)


if __name__ == "__main__":
    if not os.environ.get("FOOTBALL_DATA_KEY"):
        sys.exit("Set FOOTBALL_DATA_KEY before starting (see README).")
    # refresh data in the background; daemon so it dies with the server
    threading.Thread(target=updater_loop, daemon=True).start()
    print("Serving on http://0.0.0.0:%d  (refresh every %ds)" % (PORT, REFRESH_SECONDS), flush=True)
    # use_reloader=False so the background thread isn't started twice
    app.run(host="0.0.0.0", port=PORT, use_reloader=False)
