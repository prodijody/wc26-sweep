# WC 2026 Office Sweep

A live World Cup 2026 dashboard for an office sweepstake. Shows who's **still in**
(last team standing), a **leaderboard**, **live/recent results** and **upcoming fixtures** —
designed to look good on a wall-mounted office TV, a laptop, or a phone.

![layout](https://img.shields.io/badge/layout-TV%20wall%20(light)-2f6df6) data from
[football-data.org](https://www.football-data.org/).

## How it works

```
football-data.org ──(your key, server-side)──> update.py ──> data.js ──> index.html (auto-refresh 60s)
                         sweep.json (your list) ──┘
```

- **`sweep.json`** — your players and their teams (edit this freely).
- **`update.py`** — fetches live results, works out standings / knockout progression /
  who's eliminated / each player's status, and writes **`data.js`**. No third-party
  packages — just Python 3.
- **`index.html`** — the page. Reads `data.js`, refreshes itself every 60 seconds.

The page never talks to the API directly, so your API key stays server-side and there
are no browser/CORS problems. Works the same on GitHub Pages or your Flask server.

## One-time setup

1. **Your API key** is read from an environment variable (so it never gets committed
   into a public repo). Set it:

   **PowerShell**
   ```powershell
   $env:FOOTBALL_DATA_KEY = "your-key-here"
   ```
   **bash / Linux / macOS**
   ```bash
   export FOOTBALL_DATA_KEY=your-key-here
   ```

2. **Generate the data:**
   ```bash
   python update.py
   ```
   This writes `data.js` and prints a summary (phase, players still in, any data flags).

3. **View it:**
   - Quick look: just open `index.html` in a browser.
   - Proper (with auto-refresh): serve the folder over HTTP, e.g.
     ```bash
     python -m http.server 8000
     ```
     then open <http://127.0.0.1:8000/index.html>.

## Keeping it fresh (pick one)

`update.py` is safe to run as often as you like (it makes 2 API calls per run; the
free tier allows 10/minute). Run it every ~10–15 minutes during the tournament.

**Windows Task Scheduler** — run `python C:\...\WC26Sweep\update.py` on a 15-min trigger,
with `FOOTBALL_DATA_KEY` set as a system/user environment variable.

**cron (Linux/macOS)**
```cron
*/15 * * * * cd /path/to/WC26Sweep && FOOTBALL_DATA_KEY=your-key /usr/bin/python3 update.py
```

**Flask (recommended)** — run the included **`app.py`**: it serves the page *and*
re-runs `update.py` every `REFRESH_SECONDS` (default 600) in a background thread, so
there's only one thing to run.
```bash
pip install flask
export FOOTBALL_DATA_KEY=your-key
python app.py            # serves http://<server>:8080/
```
Keep it alive with systemd / NSSM / Task Scheduler. For a sturdier server,
`pip install waitress && waitress-serve --port=8080 app:app` (then schedule `update.py`
separately, e.g. cron, since waitress doesn't run app.py's `__main__` refresh loop).

**GitHub Actions + GitHub Pages (fully free, no server)** — a workflow is included at
`.github/workflows/update.yml`. It runs `update.py` on a schedule and commits the new
`data.js`; GitHub Pages serves the folder. You must add your key as a repo secret:
**Settings → Secrets and variables → Actions → New repository secret**, name
`FOOTBALL_DATA_KEY`. Then enable Pages (**Settings → Pages → deploy from branch**).

## Editing the sweep

Everything is in **`sweep.json`**:

- Add/rename players or change their teams under `"players"`.
- `"aliases"` maps your spelling to the official team name. Current aliases:
  Bosnia→Bosnia-Herzegovina, America→United States, Cape Verde→Cape Verde Islands,
  Congo→Congo DR, **Beckistan→Uzbekistan** (best guess — change if wrong).
- Any team that doesn't match a real WC 2026 team is shown as "Not in tournament" and
  listed in the page's data flags.

Re-run `update.py` after editing.

## Notes on your list (auto-flagged)

- **Beckistan(?) → Uzbekistan** — assumed; it's the only "-stan" in the tournament.
- **Portugal** is listed for both Louise and Laura H, and **Croatia** for both Paul Mc
  and Johnny. The page flags shared teams — resolve in `sweep.json` if needed.
- Two **Brandon** lines are kept as `Brandon` (Australia) and `Brandon B`
  (Netherlands, Switzerland). Rename if they're the same person.

## Scoring

**Last team standing.** A player is *in* until all their teams are knocked out.
Elimination is taken from the bracket itself: once knockout fixtures exist, group teams
not in them are out; in the knockouts, the loser of any played match is out. During the
group stage the leaderboard ranks by furthest stage, then total group points, then goal
difference, then teams still alive.
