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

### Setting up the Python environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Setting up cloudflared
Install cloudfare
```bash
brew install cloudflared
```

Login to cloudflare and approve access to your domain. This will open a browser
```bash
cloudflared tunnel login
```
Generate a named tunnel and credential keys
```bash
cloudflared tunnel create pickem
```
Create a DNS record so that hostname points at your tunnel instead of a normal IP address
```bash
cloudflared tunnel route dns pickem pickem.jeffreymayolo.com
```

Copy the config template and fill in its placeholders (tunnel ID from the
`create` command above, your macOS username, and the hostname):
```bash
cp config.yml ~/.cloudflared/config.yml
```
Then edit `~/.cloudflared/config.yml` directly — the `service:` line inside
it must point at the same port gunicorn will bind to below (`8000`).

Install cloudflared as a persistent background service, so the tunnel
survives reboots and doesn't depend on a terminal staying open:
```bash
sudo cloudflared service install
```

Once it's installed it can be started and stopped via 
```bash
sudo launchctl stop com.cloudflare.cloudflared
sudo launchctl start com.cloudflare.cloudflared
```

running in the foreground
```bash
cloudflared tunnel run pickem
```

### Setting up gunicorn (already installed via requirements.txt)

Generate a secret key — this signs login session cookies, used by
Flask/gunicorn, not by cloudflared:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Test-run gunicorn locally to confirm the key and app both work:
```bash
export SECRET_KEY=<paste the value>
gunicorn --bind 127.0.0.1:8000 app:app
```
Visit `pickem.jeffreymayolo.com` — if cloudflared is already running, this
confirms the whole chain works end to end. Stop this with Ctrl+C once confirmed.

Set up the persistent service:
```bash
mkdir -p logs
cp deploy/macos/com.mayolopickem.web.plist ~/Library/LaunchAgents/
```
Fill in the placeholders inside
`~/Library/LaunchAgents/com.mayolopickem.web.plist`:
- `{{PROJECT_PATH}}`
- `{{VENV_PATH}}`
- `{{SECRET_KEY}}`

Then load it:
```bash
launchctl load ~/Library/LaunchAgents/com.mayolopickem.web.plist
```

### Shutting everything down

```bash
launchctl unload ~/Library/LaunchAgents/com.mayolopickem.web.plist
sudo launchctl unload /Library/LaunchDaemons/com.cloudflare.cloudflared.plist

launchctl list | grep mayolopickem
sudo launchctl list | grep cloudflare
```
Both `list` commands returning nothing confirms everything is stopped.


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


## starting
Start the service
```
python3 app.py
```

Connect to Cloudflare tunnel
```
cloudflared tunnel run pickem
```

## Pulling odds automatically

1. Get a free API key at https://the-odds-api.com (free tier = 500 requests/month;
   one pull per week costs 1 request).
2. Set it as an environment variable: `export ODDS_API_KEY=your_key_here`
3. Run the weekly pull, naming games as `Away@Home`:

```bash
python scripts/fetch_odds.py --week 5 --games "Chiefs@Bills" "Cowboys@Eagles"
```

## TODO
  - Switch hosting to gunicorn.
  - Make the points automatically calculate after each game and show in the plot.
  - Once a game starts, display a pie chart for who chose what team.
  - Make it nore viewable on phone since that is the primary source for viewing
  - Get rid of $20/game.
  - Get it running on Nina's laptop

## Self-hosting on your own machine (Cloudflare Tunnel)

If you'd rather run this on a spare laptop than pay for hosting, Cloudflare
Tunnel exposes it to the internet with **no port forwarding and no open
ports on your router** — a small daemon (`cloudflared`) runs locally and
makes an outbound-only connection to Cloudflare's edge; visitors to your
domain get routed back through that tunnel to your machine.

You'll need a domain name pointed at Cloudflare's nameservers (a "named
tunnel" gives you a stable URL like `pickem.yourdomain.com` that survives
restarts, unlike the free ephemeral "quick tunnel" option).

**1. Run the app itself in production mode**, bound to localhost only:
```bash
gunicorn --bind 127.0.0.1:8000 app:app
```
Set a real `SECRET_KEY` env var too — the app falls back to an insecure
default (`dev-secret-change-me`) if it's not set.

**2. Set up cloudflared** (macOS: `brew install cloudflared`):
```bash
cloudflared tunnel login                              # authorize your domain
cloudflared tunnel create pickem                       # creates a named tunnel
cloudflared tunnel route dns pickem pickem.yourdomain.com
```
Then create `~/.cloudflared/config.yml`:
```yaml
tunnel: <TUNNEL_ID>
credentials-file: /Users/yourname/.cloudflared/<TUNNEL_ID>.json
ingress:
  - hostname: pickem.yourdomain.com
    service: http://localhost:8000
  - service: http_status:404
```
Install it as a background service so it survives reboots:
```bash
sudo cloudflared service install
```

**3. Keep the app itself running as a background service too** — see
`deploy/macos/com.mayolopickem.web.plist`, a launchd template that runs
gunicorn via `launchctl` and restarts it automatically if it crashes or the
machine reboots. Fill in the placeholders in the file, then:
```bash
cp deploy/macos/com.mayolopickem.web.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.mayolopickem.web.plist
```

**4. Disable sleep** on the laptop (System Settings → Battery) while it's
plugged in — if it sleeps, both the tunnel and the app go down until
someone wakes the machine.

## Adding automatic pull to cron job
```
crontab /path/to/2026_nfl_primetime_odds_schedule.txt
```
verify with the following
```
crontab -l
```

## TODO
- Include ties in the standings calculations
- Automatically pull final scores on at midnight on Thursday, Sunday, and Monday.