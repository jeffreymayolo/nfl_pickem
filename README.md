# Mayolo Family Pick 'Em

A small Flask app for running your family's weekly NFL pick-em league.

## How it works

- Each week the **commissioner** (the first person to register becomes commissioner)
  adds that week's games on the **Admin** page — normally the odds are filled in
  automatically by the Tuesday-morning odds pull, but you can also add a game by
  hand there (e.g. for the one bonus game chosen manually each week).
- Everyone picks winners on the **Picks** page. A game locks automatically once
  its kickoff time passes.
- After games finish, the commissioner records the winner on the **Admin** page.
- The **Standings** page recalculates automatically: points (inversely
  proportional to the picked team's win probability), percent correct, perfect
  weeks, zero-win weeks, and season net if you'd bet $20 on every pick — plus a
  cumulative points line chart. Ties are broken by percent correct.

## Local setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Visit http://localhost:5001 — register the first account (that becomes the
commissioner), then add a game from the Admin page to try it out.

## Pulling odds automatically

1. Get a free API key at https://the-odds-api.com (free tier = 500 requests/month;
   one pull per week costs 1 request).
2. Set it as an environment variable: `export ODDS_API_KEY=your_key_here`
3. Run the weekly pull, naming games as `Away@Home`:

```bash
python scripts/fetch_odds.py --week 5 --games "Chiefs@Bills" "Cowboys@Eagles"
```

This writes/updates rows in `data/games.csv` with the averaged moneyline odds
across books and the resulting implied win probabilities. Team-name matching
is a loose substring match (e.g. "Chiefs" matches "Kansas City Chiefs"), so
short nicknames work fine.

## Deploying to Render

`render.yaml` is included and defines two services:

1. **mayolo-pickem** — the web app itself (free plan, gunicorn).
2. **fetch-odds-tuesday** — an optional cron job that runs the odds pull every
   Tuesday at 9am ET. You'll need to edit the `--week`/`--games` args in
   `render.yaml` each week (or point it at a small wrapper script that reads
   the week's games from a file the commissioner maintains).

Steps:
1. Push this project to a GitHub repo.
2. In Render, choose "New > Blueprint" and point it at the repo — it will
   read `render.yaml` and set up both services.
3. Set the `ODDS_API_KEY` environment variable on both services in the Render
   dashboard (it's marked `sync: false` so it's not stored in the repo).
4. Note: Render's **free** plan does not support persistent disks, so
   `data/` will reset on redeploy on the free tier. If you want the CSVs to
   survive redeploys, upgrade the web service to a paid plan (enables the
   `disk:` block already in `render.yaml`), or swap in Render's free
   PostgreSQL/S3-compatible storage down the line.

## Data files

- `data/users.csv` — username, hashed password, commissioner flag
- `data/games.csv` — one row per game: game_id, week, team1, team1_odds,
  team1_prob, team2, team2_odds, team2_prob, kickoff_time, winner
- `data/picks/picks_<username>.csv` — one row per pick: game_id, pick

All writes go through a file lock (see `utils/csv_store.py`) so simultaneous
submissions right before kickoff can't corrupt a file.

## Notes on the scoring math

- **Points**: implied win probabilities from the odds are normalized so each
  matchup's two probabilities sum to 1 (removing the sportsbook's vig), then
  points for a correct pick = `100 * (1 - normalized_probability)`. A big
  favorite is worth few points; a big underdog is worth a lot.

- **20/game net**: uses the *actual* American odds (not normalized) of the
  team you picked — a win pays out what a real 20 bet would at those odds; a
  loss costs 20. This can rank differently than the points column, since
  points reward beating the odds while the dollar column pays out more for
  underdog wins regardless of how big the upset was.
