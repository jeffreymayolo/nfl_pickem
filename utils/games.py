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
