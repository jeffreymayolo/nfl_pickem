"""
Simple CSV-backed storage with file locking.

Every read/write goes through a lock file so two people submitting picks
at the same moment (e.g. right before Sunday Night Football kickoff)
can't corrupt each other's writes.
"""
import csv
import os
from contextlib import contextmanager
from filelock import FileLock

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
PICKS_DIR = os.path.join(DATA_DIR, "picks")
LOCK_DIR = os.path.join(DATA_DIR, ".locks")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PICKS_DIR, exist_ok=True)
os.makedirs(LOCK_DIR, exist_ok=True)


def _lock_path(csv_path: str) -> str:
    name = os.path.basename(csv_path) + ".lock"
    return os.path.join(LOCK_DIR, name)


@contextmanager
def locked(csv_path: str, timeout: int = 10):
    lock = FileLock(_lock_path(csv_path), timeout=timeout)
    with lock:
        yield


def read_csv(csv_path: str) -> list[dict]:
    if not os.path.exists(csv_path):
        return []
    with locked(csv_path):
        with open(csv_path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))


def write_csv(csv_path: str, fieldnames: list[str], rows: list[dict]):
    with locked(csv_path):
        tmp_path = csv_path + ".tmp"
        with open(tmp_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k, "") for k in fieldnames})
        os.replace(tmp_path, csv_path)  # atomic on POSIX


def append_csv(csv_path: str, fieldnames: list[str], row: dict):
    with locked(csv_path):
        file_exists = os.path.exists(csv_path)
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def upsert_csv(csv_path: str, fieldnames: list[str], row: dict, key_fields: list[str]):
    """Insert a row, or overwrite an existing row that matches on key_fields."""
    rows = read_csv(csv_path)
    key = {k: str(row.get(k, "")) for k in key_fields}

    def matches(r):
        return all(str(r.get(k, "")) == key[k] for k in key_fields)

    replaced = False
    for i, r in enumerate(rows):
        if matches(r):
            rows[i] = row
            replaced = True
            break
    if not replaced:
        rows.append(row)
    write_csv(csv_path, fieldnames, rows)


# --- File paths ------------------------------------------------------------

USERS_CSV = os.path.join(DATA_DIR, "users.csv")
GAMES_CSV = os.path.join(DATA_DIR, "games.csv")
USER_FIELDS = ["username", "password_hash", "is_commissioner"]
GAME_FIELDS = [
    "game_id", "week", "team1", "team1_odds", "team1_prob",
    "team2", "team2_odds", "team2_prob", "kickoff_time", "winner",
]
PICK_FIELDS = ["game_id", "pick"]


def picks_csv_path(username: str) -> str:
    safe = "".join(c for c in username if c.isalnum() or c in ("-", "_")).lower()
    return os.path.join(PICKS_DIR, f"picks_{safe}.csv")
