"""Shared helpers for reasoning about game kickoff times."""
from datetime import datetime, timezone


def kickoff_passed(game: dict) -> bool:
    """True if this game's kickoff time is in the past (or malformed/missing,
    in which case we conservatively treat it as not yet locked)."""
    kickoff = game.get("kickoff_time")
    if not kickoff:
        return False
    try:
        kt = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
    except ValueError:
        return False
    return kt <= datetime.now(timezone.utc)

def week_is_locked(week: str, games: list) -> bool:
    """
    A week locks all at once, as soon as its earliest game (by kickoff_time)
    has kicked off - not each game individually. Games in that week with no
    kickoff_time set are ignored when finding the earliest one, so a week
    never locks early just because one game hasn't been scheduled yet.
    """
    week_games = [g for g in games if g.get("week") == week and g.get("kickoff_time")]
    if not week_games:
        return False
    earliest = min(week_games, key=lambda g: g["kickoff_time"])
    return kickoff_passed(earliest)
