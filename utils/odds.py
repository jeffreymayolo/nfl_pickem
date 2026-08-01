"""
American-odds math.

Odds are stored as American odds, e.g. -150 (favorite) or +130 (underdog).
"""


def implied_probability(american_odds: float) -> float:
    """Convert American odds to implied win probability (0-1), including vig."""
    odds = float(american_odds)
    if odds < 0:
        return -odds / (-odds + 100)
    return 100 / (odds + 100)


def normalize_pair(prob1: float, prob2: float) -> tuple[float, float]:
    """
    Sportsbook implied probabilities sum to > 1 (that's the vig / house edge).
    Normalize so the two team probabilities sum to exactly 1, which is what
    we use for point allocation.
    """
    total = prob1 + prob2
    if total == 0:
        return 0.5, 0.5
    return prob1 / total, prob2 / total


def points_for_pick(picked_team_prob: float) -> float:
    """
    Points for correctly picking a team = 100 * (1 - that team's normalized
    win probability). A heavy favorite (prob 0.8) is worth 20 points;
    a big underdog (prob 0.2) is worth 80 points.
    """
    return round(100 * (1 - picked_team_prob), 2)


def payout_on_20(american_odds: float) -> float:
    """Net profit on a winning $20 bet at the given American odds."""
    odds = float(american_odds)
    if odds > 0:
        return round(20 * (odds / 100), 2)
    return round(20 * (100 / abs(odds)), 2)
