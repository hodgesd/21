# Basic Strategy Drill

A blackjack basic strategy trainer: one self-contained page you can install
to a phone's home screen. It deals a hand, you pick Hit, Stand, Double or
Split, and it tells you whether that was the right play, what each option
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
| Hit | ↑ or H | swipe up |
| Stand | ↓ or S | swipe down |
| Double | → or D | swipe right |
| Split | ← or P | swipe left |
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
pick up the new build.

Progress lives in the browser's localStorage, per device. Settings → Backup
copies it to the clipboard and restores it on another device. On iPhone,
Safari and the home-screen app keep separate storage.
