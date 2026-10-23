#!/usr/bin/env python3
"""Hand log + progress sync for the Basic Strategy Drill. Python stdlib only.

Every answered hand is appended to a SQLite log with a server-assigned seq.
A device's progress is a fold: the baseline state (legacy progress, a restored
backup, or a reset) plus every hand with seq > baseline.from_seq, so devices
converge without overwriting each other. The browser does the folding; this
server only stores and serves.

  GET  /api/healthz             {"ok": true, "hands": N}
  POST /api/hands               {"hands": [...]}  idempotent on hand id
  GET  /api/hands?after=S       {"rev", "fromSeq", "hands": [...], "more"}
  GET  /api/hands.csv           the whole log, for spreadsheets
  GET  /api/baseline            {"rev", "fromSeq", "state"}  rev 0 = none yet
  PUT  /api/baseline            {"state", "reset", "expectRev"?}
                                reset=true starts the fold after the current
                                last hand; expectRev mismatch answers 409.

No auth: it binds to loopback behind nginx on a tailnet-only vhost.
Config: BJ_DB (sqlite path), BJ_HOST, BJ_PORT.
"""
import csv
import io
import json
import os
import re
import sqlite3
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

DB = os.environ.get("BJ_DB", "bj-drill.db")
HOST = os.environ.get("BJ_HOST", "127.0.0.1")
PORT = int(os.environ.get("BJ_PORT", "8091"))
MAX_BODY = 4 * 1024 * 1024
MAX_BATCH = 1000
PAGE = 5000

ACTIONS = {"hit", "stand", "double", "split"}
UPS = {"2", "3", "4", "5", "6", "7", "8", "9", "10", "A"}
MODES = {"spaced", "random", "hard", "soft", "pair"}
RE_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")
RE_ROW = re.compile(r"^[HSP]\d{1,2}$")
RE_TAG = re.compile(r"^[A-Za-z0-9-]{1,64}$")
FIELDS = ["seq", "id", "ts", "dev", "sid", "mode", "row", "up", "cards", "chosen", "best", "ok"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS hands (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  id TEXT NOT NULL UNIQUE,
  ts INTEGER NOT NULL,          -- ms since epoch, client clock
  dev TEXT NOT NULL,            -- device tag, e.g. iphone-3fa2c1
  sid TEXT NOT NULL,            -- drill session (one app visit)
  mode TEXT NOT NULL,
  row TEXT NOT NULL,            -- chart row key: H16, S18, P8...
  up TEXT NOT NULL,             -- dealer up card
  cards TEXT NOT NULL,          -- e.g. "K♠ 6♥ v 10♣"
  chosen TEXT NOT NULL,
  best TEXT NOT NULL,
  ok INTEGER NOT NULL,
  received INTEGER NOT NULL     -- ms since epoch, server clock
);
CREATE TABLE IF NOT EXISTS baseline (
  k INTEGER PRIMARY KEY CHECK (k = 1),
  rev INTEGER NOT NULL,
  from_seq INTEGER NOT NULL,
  state TEXT NOT NULL,
  updated INTEGER NOT NULL
);
"""


@contextmanager
def db():
    """One connection per request: commit on success, roll back on error, always close."""
    c = sqlite3.connect(DB, timeout=10)
    try:
        c.execute("PRAGMA journal_mode=WAL")
        with c:
            yield c
    finally:
        c.close()


def baseline(c):
    r = c.execute("SELECT rev, from_seq, state FROM baseline WHERE k = 1").fetchone()
    return (r[0], r[1], json.loads(r[2])) if r else (0, 0, None)


def clean_hand(h, now):
    """Validated row tuple, or None to drop the hand."""
    if not isinstance(h, dict):
        return None
    hid, dev, sid = h.get("id"), h.get("dev"), h.get("sid")
    row, up, chosen, best = h.get("row"), h.get("up"), h.get("chosen"), h.get("best")
    ts, mode, cards = h.get("ts"), h.get("mode"), h.get("cards", "")
    if not (isinstance(hid, str) and RE_ID.match(hid)):
        return None
    if not (isinstance(dev, str) and RE_TAG.match(dev) and isinstance(sid, str) and RE_TAG.match(sid)):
        return None
    if not (isinstance(row, str) and RE_ROW.match(row) and up in UPS and chosen in ACTIONS and best in ACTIONS):
        return None
    if not (isinstance(ts, int) and not isinstance(ts, bool) and 0 < ts < 10**14):
        return None
    if mode not in MODES:
        mode = "spaced"
    cards = cards[:40] if isinstance(cards, str) else ""
    return (hid, ts, dev, sid, mode, row, up, cards, chosen, best, int(chosen == best), now)


class Handler(BaseHTTPRequestHandler):
    server_version = "bj-drill/1"

    def log_message(self, fmt, *args):  # journal gets errors only
        pass

    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_BODY:
            raise ValueError("body size")
        return json.loads(self.rfile.read(n))

    def route(self):
        u = urlparse(self.path)
        return u.path.rstrip("/"), {k: v[-1] for k, v in parse_qs(u.query).items()}

    def do_GET(self):
        path, q = self.route()
        with db() as c:
            if path == "/api/healthz":
                return self.send(200, {"ok": True, "hands": c.execute("SELECT COUNT(*) FROM hands").fetchone()[0]})
            if path == "/api/baseline":
                rev, from_seq, state = baseline(c)
                return self.send(200, {"rev": rev, "fromSeq": from_seq, "state": state})
            if path == "/api/hands":
                try:
                    after = max(0, int(q.get("after", 0)))
                    limit = min(PAGE, max(1, int(q.get("limit", PAGE))))
                except ValueError:
                    return self.send(400, {"error": "after/limit must be integers"})
                rev, from_seq, _ = baseline(c)
                rows = c.execute(f"SELECT {','.join(FIELDS)} FROM hands WHERE seq > ? ORDER BY seq LIMIT ?", (after, limit + 1)).fetchall()
                hands = [dict(zip(FIELDS, r)) for r in rows[:limit]]
                for h in hands:
                    h["ok"] = bool(h["ok"])
                return self.send(200, {"rev": rev, "fromSeq": from_seq, "hands": hands, "more": len(rows) > limit})
            if path == "/api/hands.csv":
                buf = io.StringIO()
                w = csv.writer(buf)
                w.writerow(["seq", "time_utc", *FIELDS[2:]])
                for r in c.execute(f"SELECT {','.join(FIELDS)} FROM hands ORDER BY seq"):
                    w.writerow([r[0], time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(r[2] / 1000)), *r[2:]])
                return self.send(200, buf.getvalue().encode(), "text/csv; charset=utf-8")
        self.send(404, {"error": "not found"})

    def do_POST(self):
        path, _ = self.route()
        if path != "/api/hands":
            return self.send(404, {"error": "not found"})
        try:
            hands = self.body().get("hands")
            if not isinstance(hands, list) or len(hands) > MAX_BATCH:
                raise ValueError("hands")
        except (ValueError, AttributeError):
            return self.send(400, {"error": f"expected {{\"hands\": [...]}} with at most {MAX_BATCH}"})
        now = int(time.time() * 1000)
        rows = [r for r in (clean_hand(h, now) for h in hands) if r]
        with db() as c:
            before = c.total_changes
            c.executemany("INSERT OR IGNORE INTO hands (id,ts,dev,sid,mode,row,up,cards,chosen,best,ok,received) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
            added = c.total_changes - before
        # Dropped (invalid) hands are acknowledged too: resending them can never succeed.
        self.send(200, {"accepted": len(rows), "added": added, "dropped": len(hands) - len(rows)})

    def do_PUT(self):
        path, _ = self.route()
        if path != "/api/baseline":
            return self.send(404, {"error": "not found"})
        try:
            b = self.body()
            state = b["state"]
            if not isinstance(state, dict):
                raise ValueError("state")
        except (ValueError, KeyError, TypeError, AttributeError):
            return self.send(400, {"error": "expected {\"state\": {...}}"})
        with db() as c:
            c.execute("BEGIN IMMEDIATE")
            rev, from_seq, _ = baseline(c)
            if b.get("expectRev") is not None and b["expectRev"] != rev:
                return self.send(409, {"error": "baseline changed", "rev": rev})
            if b.get("reset"):
                from_seq = c.execute("SELECT COALESCE(MAX(seq), 0) FROM hands").fetchone()[0]
            c.execute(
                "INSERT INTO baseline (k, rev, from_seq, state, updated) VALUES (1, ?, ?, ?, ?) "
                "ON CONFLICT(k) DO UPDATE SET rev=excluded.rev, from_seq=excluded.from_seq, state=excluded.state, updated=excluded.updated",
                (rev + 1, from_seq, json.dumps(state, separators=(",", ":")), int(time.time() * 1000)),
            )
        self.send(200, {"rev": rev + 1, "fromSeq": from_seq})


def main():
    with db() as c:
        c.executescript(SCHEMA)
    print(f"bj-drill api on {HOST}:{PORT}, db {DB}", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
