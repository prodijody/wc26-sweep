#!/usr/bin/env python3
"""
WC 2026 Office Sweep — data updater.

Fetches live World Cup 2026 matches + standings from football-data.org,
computes group tables, knockout progression, team elimination and each
player's "last team standing" status, then writes data.js (window.DATA = {...}).

The page (index.html) reads data.js. Run this on whatever schedule you like:
  - manually:        python update.py
  - cron / Task Sched / Flask timer / GitHub Action

The API key is read from the FOOTBALL_DATA_KEY environment variable so it never
gets committed into a (public) repo. Set it first, e.g.:
  PowerShell:  $env:FOOTBALL_DATA_KEY = "your-key"
  bash:        export FOOTBALL_DATA_KEY=your-key

Zero third-party dependencies — standard library only.
"""

import os
import sys
import io
import json
import datetime
import urllib.request
import urllib.error

API_BASE = "https://api.football-data.org/v4/competitions/WC"
HERE = os.path.dirname(os.path.abspath(__file__))

# Stage ranking — higher = further in the tournament.
STAGE_RANK = {
    "GROUP": 0, "LAST_32": 1, "LAST_16": 2, "QUARTER_FINALS": 3,
    "SEMI_FINALS": 4, "THIRD_PLACE": 4, "FINAL": 5, "CHAMPION": 6,
}
RANK_LABEL = {
    0: "Group stage", 1: "Round of 32", 2: "Round of 16", 3: "Quarter-final",
    4: "Semi-final", 5: "Final", 6: "Champion \U0001F3C6",
}
KO_STAGES = {"LAST_32", "LAST_16", "QUARTER_FINALS", "SEMI_FINALS", "THIRD_PLACE", "FINAL"}
DURATION_NOTE = {"REGULAR": "FT", "EXTRA_TIME": "AET", "PENALTY_SHOOTOUT": "PENS"}


def fetch(path):
    key = os.environ.get("FOOTBALL_DATA_KEY")
    if not key:
        sys.exit("ERROR: set the FOOTBALL_DATA_KEY environment variable to your "
                 "football-data.org API key before running update.py.")
    req = urllib.request.Request(API_BASE + path, headers={"X-Auth-Token": key})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        sys.exit("ERROR: football-data.org returned HTTP %s for %s\n%s"
                 % (e.code, path, e.read().decode("utf-8", "replace")[:300]))
    except Exception as e:  # noqa: BLE001
        sys.exit("ERROR: could not reach football-data.org (%s)" % e)


def team_mini(t):
    return {"name": t.get("name"), "tla": t.get("tla"), "crest": t.get("crest")}


def main():
    sweep = json.load(io.open(os.path.join(HERE, "sweep.json"), encoding="utf-8"))
    aliases = sweep.get("aliases", {})

    # Teams forced OUT regardless of what the bracket says (withdrawals,
    # expulsions, disqualifications). Resolve through aliases and also keep the
    # raw spelling so either form in sweep.json matches.
    withdrawn = set()
    for w in sweep.get("withdrawn", []):
        withdrawn.add(w)
        withdrawn.add(aliases.get(w, w))

    matches = fetch("/matches").get("matches", [])
    standings = fetch("/standings").get("standings", [])

    # ---- team meta + group standings (from the standings tables) ----
    teams = {}          # name -> meta dict
    groups = []         # compact group tables for optional display
    for g in standings:
        if g.get("type") != "TOTAL":
            continue
        grp = (g.get("group") or "").replace("Group ", "").strip()
        rows = []
        for row in g.get("table", []):
            t = row["team"]
            name = t["name"]
            teams[name] = {
                "name": name, "tla": t.get("tla"), "crest": t.get("crest"),
                "group": grp, "position": row.get("position"),
                "points": row.get("points", 0), "played": row.get("playedGames", 0),
                "gd": row.get("goalDifference", 0), "gf": row.get("goalsFor", 0),
            }
            rows.append({"pos": row.get("position"), "team": team_mini(t),
                         "p": row.get("playedGames", 0), "w": row.get("won", 0),
                         "d": row.get("draw", 0), "l": row.get("lost", 0),
                         "gd": row.get("goalDifference", 0), "pts": row.get("points", 0)})
        groups.append({"group": grp, "table": rows})
    groups.sort(key=lambda x: x["group"])

    def meta(name):
        if name not in teams:
            teams[name] = {"name": name, "tla": None, "crest": None, "group": None,
                           "position": None, "points": 0, "played": 0, "gd": 0, "gf": 0}
        return teams[name]

    # ---- walk matches: furthest stage, knockout losers, qualified set ----
    group_total = sum(1 for m in matches if m["stage"] == "GROUP_STAGE")
    group_done = sum(1 for m in matches if m["stage"] == "GROUP_STAGE" and m["status"] == "FINISHED")
    group_complete = group_total > 0 and group_done == group_total

    furthest = {}       # name -> stage rank reached
    ko_losers = set()   # eliminated in a played knockout match
    qualified = set()   # appears (named) in any knockout match -> survived the group
    champion = None
    runner_up = None

    def bump(name, rank):
        if name:
            furthest[name] = max(furthest.get(name, 0), rank)

    for m in matches:
        stage = m["stage"]
        h = m["homeTeam"].get("name")
        a = m["awayTeam"].get("name")
        if stage == "GROUP_STAGE":
            bump(h, 0); bump(a, 0)
            continue
        # knockout match
        for nm in (h, a):
            if nm:
                qualified.add(nm)
                bump(nm, STAGE_RANK[stage])
        if m["status"] == "FINISHED" and h and a:
            w = m.get("score", {}).get("winner")
            loser = a if w == "HOME_TEAM" else (h if w == "AWAY_TEAM" else None)
            if loser:
                ko_losers.add(loser)
            if stage == "FINAL":
                champion = h if w == "HOME_TEAM" else (a if w == "AWAY_TEAM" else None)
                runner_up = loser
    if champion:
        furthest[champion] = STAGE_RANK["CHAMPION"]

    # ---- group-stage elimination (worked out, not waited-for) ----
    # Count each team's and each group's *unplayed* group games so we can tell
    # the most points a team can still reach, and whether its group is done.
    team_remaining = {}     # team name -> unplayed group games
    group_remaining = {}    # group letter -> unplayed group games
    for m in matches:
        if m["stage"] != "GROUP_STAGE" or m["status"] == "FINISHED":
            continue
        grp = (m.get("group") or "").replace("GROUP_", "").strip()
        group_remaining[grp] = group_remaining.get(grp, 0) + 1
        for nm in (m["homeTeam"].get("name"), m["awayTeam"].get("name")):
            if nm:
                team_remaining[nm] = team_remaining.get(nm, 0) + 1

    def group_eliminated(name):
        """True if a team can no longer reach the Round of 32.

        WC2026: top 2 of each group + the 8 best 3rd-placed teams advance, so a
        team is out once it can't even finish 3rd. Sound (no false positives):
          - its group has finished and it placed 4th (last), OR
          - at least 3 group rivals already have more points than this team can
            still reach (current points + 3 per game left) -> it lands 4th.
        Best-3rd qualification across groups is left to the bracket itself."""
        meta = teams.get(name)
        if not meta or not meta.get("group"):
            return False
        g = meta["group"]
        if group_remaining.get(g, 0) == 0 and meta.get("position") and meta["position"] >= 4:
            return True
        ceiling = meta["points"] + 3 * team_remaining.get(name, 0)
        rivals_above = sum(1 for o, mt in teams.items()
                           if o != name and mt.get("group") == g and mt["points"] > ceiling)
        return rivals_above >= 3

    def team_status(name):
        """Return (is_in, rank, label)."""
        rank = furthest.get(name, 0)
        if name in withdrawn:
            return False, rank, "Withdrawn"
        if champion == name:
            return True, STAGE_RANK["CHAMPION"], RANK_LABEL[6]
        if name in ko_losers:
            return False, rank, RANK_LABEL.get(rank, "Group stage")
        if group_complete and name not in qualified:
            return False, rank, "Eliminated"
        if rank == 0 and group_eliminated(name):
            return False, rank, "Eliminated"
        return True, rank, RANK_LABEL.get(rank, "Group stage")

    # ---- build players ----
    players = []
    matched_names = set()
    for p in sweep["players"]:
        tobjs = []
        for disp in p["teams"]:
            resolved = aliases.get(disp, disp)
            mt = teams.get(resolved)
            if mt is None:
                tobjs.append({"display": disp, "name": resolved, "matched": False,
                              "tla": None, "crest": None, "group": None,
                              "stage": None, "stageLabel": "Not in tournament",
                              "position": None, "points": 0, "gd": 0, "played": 0, "in": False})
                continue
            matched_names.add(resolved)
            is_in, rank, label = team_status(resolved)
            tobjs.append({"display": disp, "name": resolved, "matched": True,
                          "tla": mt["tla"], "crest": mt["crest"], "group": mt["group"],
                          "stage": rank, "stageLabel": label, "position": mt["position"],
                          "points": mt["points"], "gd": mt["gd"], "played": mt["played"],
                          "in": is_in})
        valid = [t for t in tobjs if t["matched"]]
        best = max((t["stage"] for t in valid), default=0) if valid else -1
        players.append({
            "name": p["name"], "teams": tobjs,
            "in": any(t["in"] for t in tobjs),
            "bestStage": best, "bestStageLabel": RANK_LABEL.get(best, "—") if best >= 0 else "—",
            "aliveCount": sum(1 for t in tobjs if t["in"]),
            "totalPoints": sum(t["points"] for t in valid),
            "totalGd": sum(t["gd"] for t in valid),
        })

    # Rank: still-in first, then furthest stage reached, then overall form
    # (points sum already rewards having several well-performing teams), then
    # goal difference, then teams-still-alive, then name.
    leaderboard = sorted(
        players,
        key=lambda p: (-int(p["in"]), -p["bestStage"], -p["totalPoints"],
                       -p["totalGd"], -p["aliveCount"], p["name"]),
    )

    # ---- results, fixtures, live ----
    def match_row(m, with_score):
        h, a = m["homeTeam"], m["awayTeam"]
        sc = m.get("score", {}).get("fullTime", {}) or {}
        sweep_match = (h.get("name") in matched_names) or (a.get("name") in matched_names)
        stg = "Group " + (m.get("group") or "").replace("GROUP_", "") if m["stage"] == "GROUP_STAGE" \
            else RANK_LABEL.get(STAGE_RANK.get(m["stage"], 0), m["stage"].replace("_", " ").title())
        row = {"stage": stg, "home": team_mini(h), "away": team_mini(a),
               "utc": m.get("utcDate"), "sweep": sweep_match, "status": m["status"]}
        if with_score:
            row["hs"] = sc.get("home") if sc.get("home") is not None else 0
            row["as"] = sc.get("away") if sc.get("away") is not None else 0
            row["note"] = DURATION_NOTE.get(m.get("score", {}).get("duration"), "FT")
        return row

    finished = [m for m in matches if m["status"] == "FINISHED"]
    finished.sort(key=lambda m: m.get("utcDate") or "", reverse=True)
    recent = [match_row(m, True) for m in finished[:12]]

    upcoming = [m for m in matches if m["status"] in ("SCHEDULED", "TIMED")]
    upcoming.sort(key=lambda m: m.get("utcDate") or "")
    fixtures = [match_row(m, False) for m in upcoming[:12]]

    live = [match_row(m, True) for m in matches if m["status"] in ("IN_PLAY", "PAUSED")]

    # ---- data-quality flags ----
    flags = {}
    for p in sweep["players"]:
        for disp in p["teams"]:
            resolved = aliases.get(disp, disp)
            if resolved not in teams:
                flags["%s (%s)" % (disp, p["name"])] = "Not found in WC 2026 — check spelling/alias in sweep.json"
    owner_of = {}
    for p in sweep["players"]:
        for disp in p["teams"]:
            resolved = aliases.get(disp, disp)
            owner_of.setdefault(resolved, []).append(p["name"])
    for tname, owners in owner_of.items():
        if len(owners) > 1:
            flags["%s" % tname] = "Owned by more than one player: " + ", ".join(owners)
    for w in sorted(withdrawn):
        if w in owner_of:
            flags["%s (withdrawn)" % w] = "Forced out via sweep.json 'withdrawn' — owner(s): " + ", ".join(owner_of[w])

    # ---- phase label ----
    if champion:
        phase = "Tournament complete"
    elif any(m["stage"] == "FINAL" for m in matches if m["status"] in ("SCHEDULED", "TIMED")) and group_complete:
        phase = "Final to come"
    elif group_complete:
        phase = "Knockout stage"
    else:
        md = next((m.get("matchday") for m in matches if m["status"] in ("SCHEDULED", "TIMED", "IN_PLAY")), None)
        phase = "Group stage" + (" · matchday %s" % md if md else "")

    # ---- knockout bracket (symmetric tree, ready for the KO rounds) ----
    # Each round's matches are emitted in chronological/id order; the page lays
    # the first half down the left, the second half down the right, and the
    # final in the middle. Until the draw is made these rounds are empty and the
    # bracket page shows a "waiting for the knockouts" placeholder.
    KO_ORDER = ["LAST_32", "LAST_16", "QUARTER_FINALS", "SEMI_FINALS", "FINAL"]

    def bracket_row(m):
        h, a = m["homeTeam"], m["awayTeam"]
        sc = m.get("score", {}).get("fullTime", {}) or {}
        is_fin = m["status"] == "FINISHED"
        return {
            "home": team_mini(h), "away": team_mini(a),
            "hs": sc.get("home"), "as": sc.get("away"),
            "winner": m.get("score", {}).get("winner"),  # HOME_TEAM/AWAY_TEAM/DRAW/None
            "status": m["status"], "utc": m.get("utcDate"),
            "note": DURATION_NOTE.get(m.get("score", {}).get("duration")) if is_fin else None,
            "sweep": (h.get("name") in matched_names) or (a.get("name") in matched_names),
        }

    bracket = {
        "order": KO_ORDER,
        "labels": {s: RANK_LABEL[STAGE_RANK[s]] for s in KO_ORDER},
        "rounds": {},
        "hasData": False,
        "thirdPlaceLabel": "Third-place play-off",
    }
    for s in KO_ORDER + ["THIRD_PLACE"]:
        ms = [m for m in matches if m["stage"] == s]
        ms.sort(key=lambda m: (m.get("utcDate") or "", m.get("id") or 0))
        bracket["rounds"][s] = [bracket_row(m) for m in ms]
        if s in KO_ORDER and ms:
            bracket["hasData"] = True

    data = {
        "demo": False,
        "title": sweep.get("title", "WC 2026 Office Sweep"),
        "updated": datetime.datetime.now().isoformat(timespec="seconds"),
        "phase": phase,
        "champion": champion,
        "runnerUp": runner_up,
        "playersIn": sum(1 for p in players if p["in"]),
        "playersTotal": len(players),
        "players": players,
        "leaderboard": leaderboard,
        "recent": recent,
        "fixtures": fixtures,
        "live": live,
        "groups": groups,
        "bracket": bracket,
        "flags": flags,
    }

    out = os.path.join(HERE, "data.js")
    with io.open(out, "w", encoding="utf-8") as f:
        f.write("window.DATA = " + json.dumps(data, ensure_ascii=False, indent=1) + ";\n")

    print("Wrote %s" % out)
    print("  phase: %s | players in: %d/%d | live: %d | flags: %d"
          % (phase, data["playersIn"], data["playersTotal"], len(live), len(flags)))
    if withdrawn:
        print("  withdrawn (forced out): %s" % ", ".join(sorted(withdrawn)))
    print("  bracket: %s" % ("populated" if bracket["hasData"] else "waiting for knockout draw"))
    if flags:
        for k, v in flags.items():
            print("  flag: %s -> %s" % (k, v))


if __name__ == "__main__":
    main()
