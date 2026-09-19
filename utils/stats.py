"""
Computes everything shown on the standings page:
  - per-user totals: points, percent correct, perfect weeks, zero-win weeks,
    $20/game season net
  - a cumulative-points-by-game series per user, for the line chart

A game only counts once it has a recorded winner (set by the commissioner
on the admin page after the game finishes). A "perfect week" means the user
picked every graded game that week and got all of them right. A "zero-win
week" means they picked at least one graded game that week and got none
right.
"""
from collections import defaultdict
# import pandas as pd
# import seaborn as sns
# import matplotlib.pyplot as plt

from utils.csv_store import GAMES_CSV, USERS_CSV, read_csv, picks_csv_path
from utils.games import week_is_locked
from utils.odds import normalize_pair, points_for_pick, payout_on_20


def _graded_games():
    """Games that have a winner recorded, in kickoff-time order."""
    games = read_csv(GAMES_CSV)
    graded = [g for g in games if g.get("winner")]
    graded.sort(key=lambda g: g.get("kickoff_time", ""))
    return graded


def compute_standings():
    users = read_csv(USERS_CSV)
    graded_games = _graded_games()
    game_order = [g["game_id"] for g in graded_games]

    games_by_week = defaultdict(list)
    for g in graded_games:
        games_by_week[g["week"]].append(g)

    results = []
    series = {}  # username -> [{game_id, cumulative_points}, ...]

    for user in users:
        username = user["username"]
        picks = {p["game_id"]: p["pick"] for p in read_csv(picks_csv_path(username))}

        total_points = 0.0
        total_dollars = 0.0
        picked_count = 0
        correct_count = 0
        cumulative = []

        for game in graded_games:
            game_id = game["game_id"]
            pick = picks.get(game_id)
            if pick:
                picked_count += 1
                prob1, prob2 = float(game["team1_prob"]), float(game["team2_prob"])
                norm1, norm2 = normalize_pair(prob1, prob2)
                if pick == game["team1"]:
                    picked_odds, picked_prob = game["team1_odds"], norm1
                else:
                    picked_odds, picked_prob = game["team2_odds"], norm2

                if pick == game["winner"]:
                    pts = points_for_pick(picked_prob)
                    total_points += pts
                    total_dollars += payout_on_20(picked_odds)
                    correct_count += 1
                else:
                    # total_dollars -= 20
                    pass

            cumulative.append({"game_id": game_id, "cumulative_points": round(total_points, 2)})

        perfect_weeks = 0
        zero_win_weeks = 0
        for week, week_games in games_by_week.items():
            week_ids = {g["game_id"] for g in week_games}
            picked_this_week = [gid for gid in week_ids if picks.get(gid)]
            correct_this_week = [
                gid for gid in picked_this_week
                if picks[gid] == next(g["winner"] for g in week_games if g["game_id"] == gid)
            ]
            if not picked_this_week:
                continue
            if len(picked_this_week) == len(week_ids) and len(correct_this_week) == len(week_ids):
                perfect_weeks += 1
            if len(correct_this_week) == 0:
                zero_win_weeks += 1

        pct_correct = round(100 * correct_count / picked_count, 1) if picked_count else 0.0

        results.append({
            "username": username,
            "points": round(total_points, 2),
            "percent_correct": pct_correct,
            "perfect_weeks": perfect_weeks,
            "zero_win_weeks": zero_win_weeks,
            # "dollar_net": round(total_dollars, 2),
            "games_picked": picked_count,
        })
        series[username] = cumulative

    # Sort by points desc, tiebreak by percent correct desc (per league rules)
    # create_standings_plot(series)
    results.sort(key=lambda r: (-r["points"], -r["percent_correct"]))
    return results, series, game_order


def compute_pick_distribution():
    """
    Once a week's first game kicks off, the whole week locks at once -
    every game in that week becomes safe to reveal, not just the individual
    games whose own kickoff has passed. Excludes games already graded (those
    show up in the standings table itself). Used for the "who picked what"
    section on the standings page.
    """
    games = read_csv(GAMES_CSV)
    current = [g for g in games if week_is_locked(g.get("week", ""), games) and not g.get("winner")]
    current.sort(key=lambda g: (g.get("week", ""), g.get("kickoff_time", "")))
 
    usernames = [u["username"] for u in read_csv(USERS_CSV)]
    picks_by_user = {
        u: {p["game_id"]: p["pick"] for p in read_csv(picks_csv_path(u))}
        for u in usernames
    }
 
    distribution = []
    for game in current:
        gid = game["game_id"]
        team1_pickers = [u for u in usernames if picks_by_user[u].get(gid) == game["team1"]]
        team2_pickers = [u for u in usernames if picks_by_user[u].get(gid) == game["team2"]]
        distribution.append({
            "game_id": gid,
            "week": game["week"],
            "team1": game["team1"],
            "team2": game["team2"],
            "team1_pickers": team1_pickers,
            "team2_pickers": team2_pickers,
        })
    return distribution
