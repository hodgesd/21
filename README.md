# Basic Strategy Drill

A blackjack basic strategy trainer: one self-contained page you can install
to a phone's home screen. It deals a hand, you pick Split, Hit, Stand or
Double, and it tells you whether that was the right play, what each option
is worth in expected value, and why.

- **Rules:** 6 decks, dealer hits soft 17, double on any two cards, double
  after split, split to 4 hands, no resplitting aces, no surrender, dealer
  peeks for blackjack. EVs are per unit bet, from the exact shoe after the
  three visible cards are removed.
- **Drill modes:** spaced repetition (a spot comes back after 3 hands, then
  8, 20, 50, 120, 300 while you keep getting it right; a miss resets it),
  random, or hard totals / soft totals / pairs only.
- **Feedback:** EV bars for every option, close-call flags, dealer bust odds,
  your bust odds, and a plain-English explanation.
- **Stats:** session and lifetime accuracy, streaks, a colour-coded strategy
  chart of your accuracy per spot, your most common mistakes, and weakest
  spots.

## Controls

| Action | Keyboard | Touch |
|---|---|---|
| Split | ← or P | swipe left |
| Hit | ↑ or H | swipe up |
| Stand | ↓ or S | swipe down |
| Double | → or D | swipe right |
| Next hand | Enter, Space or N | tap or swipe anywhere |
| Close a panel | Esc | Back button |

## Running it

There is no build step. Serve the directory over HTTPS (the service worker
and home-screen install need it) with any static file server, or for local
use:

```sh
python3 -m http.server 8000   # then open http://localhost:8000
```

When you change `index.html`, bump `VERSION` in `sw.js` so installed copies
pick up the new build, and run the tests with `node --test` (no dependencies;
they load the page's script under a stub DOM).

The buttons sit left to right in the same order as the arrows and swipes:
← Split, ↑ Hit, ↓ Stand, → Double.

## Hand log and sync

`server/server.py` (Python stdlib + SQLite, no dependencies) logs every
answered hand and syncs progress between devices. The page calls it at the
relative path `api/`, so serve both from one origin with `/api/` proxied to
the server:

```sh
BJ_DB=./bj-drill.db python3 server/server.py   # listens on 127.0.0.1:8091
```

How it works:

- Each answer becomes a hand record (id, time, device, session, chart spot,
  cards, your play, the right play). It goes into a localStorage outbox
  and uploads within a couple of seconds, or later if the device is offline.
- Progress on every device is a fold: a **baseline** state plus every hand
  logged after it. The browser does the folding (`applyHand`), and the
  spaced-repetition jitter is seeded from the hand id, so phone and desktop
  converge on the same chart, streaks and review schedule.
- The first time a device with older local-only progress syncs, that
  progress is merged into the server baseline once.
- Settings → Backup: restore and reset start a new baseline on the server and
  apply to every device. The hand log is never deleted.
- Settings → Server sync shows the last sync time and any hands waiting to
  upload, and links the full log as CSV (`api/hands.csv`).

API: `GET api/healthz`, `POST api/hands`, `GET api/hands?after=SEQ`,
`GET api/hands.csv`, `GET|PUT api/baseline`. It has no auth. Run it only
where the network is private (it's tailnet-only at 21.hdgs.me).

Settings (sound, drill mode and the rest) stay per device. Without the server
the app still works: hands queue locally and the Settings panel says so.

The page makes no third-party requests: its fonts (Archivo and IBM Plex
Mono, Latin subsets) are served from `fonts/` and cached for offline use.

## License

MIT, see [LICENSE](LICENSE). The fonts in `fonts/` are under the SIL Open
Font License 1.1; their licenses are alongside them.
