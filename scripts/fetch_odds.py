"""
Pulls current NFL moneyline odds from The Odds API and writes/updates rows
in data/games.csv for a given week's selected games.

Usage:
    python scripts/fetch_odds.py --week 5 --games "Chiefs@Bills" "Cowboys@Eagles"

Set the ODDS_API_KEY environment variable (get a free key at the-odds-api.com,
free tier = 500 requests/month, one pull per week uses 1 request).

This is meant to be run manually or via a scheduled job (Render Cron Job,
cron, APScheduler, etc.) on Tuesday mornings once the commissioner has
picked the week's games in the admin page.
"""
import argparse
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.csv_store import GAMES_CSV, GAME_FIELDS, read_csv, write_csv
from utils.odds import implied_probability

ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"


def fetch_current_odds(api_key: str):
    """Returns a list of games with moneyline odds from The Odds API."""
    params = {
        "apiKey": api_key,
        "regions": "us",
        "markets": "h2h",
        "oddsFormat": "american",
    }
    resp = requests.get(ODDS_API_URL, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def find_game_odds(api_games, home_team: str, away_team: str):
    """
    Find a game in the API response matching the two team names (loose
    substring match since franchise names vary, e.g. "Chiefs" vs
    "Kansas City Chiefs").
    """
    for game in api_games:
        teams = {game.get("home_team", ""), game.get("away_team", "")}
        if any(home_team.lower() in t.lower() for t in teams) and \
           any(away_team.lower() in t.lower() for t in teams):
            return game
    return None


def extract_moneylines(game: dict, team1: str, team2: str):
    """Average the moneyline across all books that list both teams."""
    odds1, odds2 = [], []
    for bookmaker in game.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            if market["key"] != "h2h":
                continue
            outcomes = {o["name"]: o["price"] for o in market["outcomes"]}
            for name, price in outcomes.items():
                if team1.lower() in name.lower():
                    odds1.append(price)
                elif team2.lower() in name.lower():
                    odds2.append(price)
    if not odds1 or not odds2:
        return None, None
    return round(sum(odds1) / len(odds1)), round(sum(odds2) / len(odds2))


def build_game_row(game_id: str, week: str, team1: str, team2: str, odds1: int, odds2: int, kickoff: str):
    return {
        "game_id": game_id,
        "week": week,
        "team1": team1,
        "team1_odds": odds1,
        "team1_prob": round(implied_probability(odds1), 4),
        "team2": team2,
        "team2_odds": odds2,
        "team2_prob": round(implied_probability(odds2), 4),
        "kickoff_time": kickoff,
        "winner": "",
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch NFL odds and update games.csv")
    parser.add_argument("--week", required=True, help="Week number, e.g. 5")
    parser.add_argument(
        "--games", nargs="+", required=True,
        help='Games as "Away@Home", e.g. "Chiefs@Bills" "Cowboys@Eagles"',
    )
    args = parser.parse_args()

    api_key = os.environ.get("ODDS_API_KEY")
    if not api_key:
        print("ERROR: set the ODDS_API_KEY environment variable.", file=sys.stderr)
        sys.exit(1)

    api_games = fetch_current_odds(api_key)
    existing_rows = read_csv(GAMES_CSV)
    existing_by_id = {r["game_id"]: r for r in existing_rows}

    for matchup in args.games:
        away, home = matchup.split("@")
        api_game = find_game_odds(api_games, home.strip(), away.strip())
        if not api_game:
            print(f"WARNING: no odds found for {matchup}, skipping.", file=sys.stderr)
            continue

        odds1, odds2 = extract_moneylines(api_game, home.strip(), away.strip())
        if odds1 is None:
            print(f"WARNING: no moneyline market for {matchup}, skipping.", file=sys.stderr)
            continue

        game_id = f"w{args.week}_{home.strip()}_{away.strip()}".replace(" ", "")
        row = build_game_row(
            game_id=game_id,
            week=args.week,
            team1=home.strip(),
            team2=away.strip(),
            odds1=odds1,
            odds2=odds2,
            kickoff=api_game.get("commence_time", ""),
        )
        existing_by_id[game_id] = row
        print(f"Saved {matchup}: {home}={odds1} ({row['team1_prob']*100:.1f}%), "
              f"{away}={odds2} ({row['team2_prob']*100:.1f}%)")

    write_csv(GAMES_CSV, GAME_FIELDS, list(existing_by_id.values()))
    print(f"\nWrote {len(existing_by_id)} total games to {GAMES_CSV}")


if __name__ == "__main__":
    main()
