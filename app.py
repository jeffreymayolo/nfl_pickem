import os

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash

from utils.csv_store import (
    USERS_CSV, USER_FIELDS, GAMES_CSV, GAME_FIELDS, PICK_FIELDS,
    read_csv, write_csv, upsert_csv, picks_csv_path,
)
from utils.games import week_is_locked
from utils.stats import compute_standings, compute_pick_distribution, normalize_pair

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

login_manager = LoginManager(app)
login_manager.login_view = "login"


class User(UserMixin):
    def __init__(self, username, is_commissioner):
        self.id = username
        self.is_commissioner = is_commissioner == "true"


def _find_user_row(username):
    for row in read_csv(USERS_CSV):
        if row["username"].lower() == username.lower():
            return row
    return None


@login_manager.user_loader
def load_user(username):
    row = _find_user_row(username)
    if not row:
        return None
    return User(row["username"], row["is_commissioner"])


# --- Auth --------------------------------------------------------------

@app.route("/", methods=["GET"])
def index():
    if current_user.is_authenticated:
        return redirect(url_for("standings"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        row = _find_user_row(username)
        if row and check_password_hash(row["password_hash"], password):
            login_user(User(row["username"], row["is_commissioner"]))
            return redirect(url_for("standings"))
        flash("Wrong username or password.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template("register.html")
        if _find_user_row(username):
            flash("That username is already taken.", "error")
            return render_template("register.html")

        users = read_csv(USERS_CSV)
        is_commissioner = "true" if len(users) == 0 else "false"  # first user = commissioner
        users.append({
            "username": username,
            "password_hash": generate_password_hash(password),
            "is_commissioner": is_commissioner,
        })
        write_csv(USERS_CSV, USER_FIELDS, users)
        login_user(User(username, is_commissioner))
        return redirect(url_for("standings"))
    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# --- Standings -----------------------------------------------------------

@app.route("/standings")
@login_required
def standings():
    results, series, game_order = compute_standings()
    pick_distribution = compute_pick_distribution()
    return render_template(
        "standings.html", results=results, series=series, game_order=game_order,
        pick_distribution=pick_distribution,
    )


# --- Picks -----------------------------------------------------------------

def _upcoming_games():
    """Games available for picking. Once a week's first game kicks off,
    the entire week locks at once - not just each game individually."""
    games = read_csv(GAMES_CSV)
    upcoming = [g for g in games if not week_is_locked(g.get("week", ""), games)]
    upcoming.sort(key=lambda g: (g.get("week", ""), g.get("kickoff_time", "")))
    return upcoming


@app.route("/picks", methods=["GET", "POST"])
@login_required
def picks():
    games = _upcoming_games()
    my_picks = {p["game_id"]: p["pick"] for p in read_csv(picks_csv_path(current_user.id))}

    if request.method == "POST":
        for game in games:
            selected = request.form.get(f"pick_{game['game_id']}")
            if selected:
                upsert_csv(
                    picks_csv_path(current_user.id),
                    PICK_FIELDS,
                    {"game_id": game["game_id"], "pick": selected},
                    key_fields=["game_id"],
                )
        flash("Picks saved.", "success")
        my_picks = {p["game_id"]: p["pick"] for p in read_csv(picks_csv_path(current_user.id))}

    return render_template("picks.html", games=games, my_picks=my_picks)


# --- Admin -----------------------------------------------------------------

def _require_commissioner():
    if not current_user.is_commissioner:
        flash("Only the commissioner can do that.", "error")
        return False
    return True


@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin():
    if not _require_commissioner():
        return redirect(url_for("standings"))

    games = read_csv(GAMES_CSV)

    if request.method == "POST":
        action = request.form.get("action")

        if action == "set_winner":
            game_id = request.form["game_id"]
            winner = request.form["winner"]
            for g in games:
                if g["game_id"] == game_id:
                    g["winner"] = winner
            write_csv(GAMES_CSV, GAME_FIELDS, games)
            flash(f"Winner recorded for {game_id}.", "success")

        elif action == "add_game":
            new_row = {
                "game_id": request.form["game_id"].strip(),
                "week": request.form["week"].strip(),
                "team1": request.form["team1"].strip(),
                "team1_odds": request.form["team1_odds"].strip(),
                "team1_prob": request.form.get("team1_prob", "").strip(),
                "team2": request.form["team2"].strip(),
                "team2_odds": request.form["team2_odds"].strip(),
                "team2_prob": request.form.get("team2_prob", "").strip(),
                "kickoff_time": request.form.get("kickoff_time", "").strip(),
                "winner": "",
            }

            #normalize the odds
            prob1, prob2 = float(new_row["team1_prob"]), float(new_row["team2_prob"])
            norm1, norm2 = normalize_pair(prob1, prob2)
            new_row["team1_prob"] = str(norm1)
            new_row["team2_prob"] = str(norm2)
            
            games.append(new_row)
            write_csv(GAMES_CSV, GAME_FIELDS, games)
            flash(f"Added game {new_row['game_id']}.", "success")

        games = read_csv(GAMES_CSV)

    games.sort(key=lambda g: (g.get("week", ""), g.get("game_id", "")))
    return render_template("admin.html", games=games)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
