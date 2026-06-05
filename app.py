#!/usr/bin/env python3
from flask import Flask, render_template, jsonify, request
import sys, os, random, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bracket import (
    load_teams, compute_ratings, build_bracket,
    deterministic_bracket, run_simulations, find_upsets,
    WEIGHTS, BRACKET_NAMES, ROUND_ORDER,
)

app = Flask(__name__)

# Secret key: visit /?real=<SECRET> to get accurate predictions.
# Family gets the default URL which produces plausible-but-wrong picks.
# Override via env: BRACKET_SECRET=yourword python3 app.py
SECRET_KEY = os.environ.get("BRACKET_SECRET", "notai")

FAKE_THOUGHTS = [
    "Reviewing game tape from the last 3 weeks...",
    "Checking injury reports on ESPN...",
    "Consulting my bracket notes from 2019...",
    "Calling my uncle Dave for his hot takes...",
    "Overriding Uncle Dave's picks...",
    "Cross-referencing vibes with box scores...",
    "Definitely not running any computer simulations...",
    "Finalizing picks based on jersey colors...",
    "Adding some chaos for entertainment value...",
    "Double-checking everything by hand...",
    "Consulting the gut feeling database...",
    "Peer-reviewing with 100% organic brain cells...",
]

_CHALK = [
    "I watched {w} live in December. They have that look in their eye.",
    "After rewatching {w}'s last four games, this call was obvious.",
    "{l} is a good team. {w} is a great team. There is a difference.",
    "Classic mismatch. {w} has the size, the depth, and the coaching.",
    "This was never in doubt. {w}'s offense is a completely different animal.",
]

_UPSET = [
    "Nobody in my pool is taking {w} here. That is exactly why I am.",
    "The metrics on {w} have been screaming all season. Seed {ws} is a lie.",
    "{l} is the classic trap game pick. {w} is peaking at the right time.",
    "I have been on {w} since January. The masses are about to catch up.",
    "Do not be a sheep. {w} covers this matchup and then some.",
]

_LATE = [
    "This is what I predicted on Selection Sunday. {w}'s destiny is unfolding.",
    "When {w} cuts down the nets, remember who told you first.",
    "Every piece of analysis I have done for three months points here.",
    "This run by {w} should not surprise anyone who watched their nonconference schedule.",
]


def _analysis(wn, ln, ws, ls, round_label):
    if round_label in ("Final Four", "Championship"):
        return random.choice(_LATE).format(w=wn, l=ln)
    if ws > ls:
        return random.choice(_UPSET).format(w=wn, l=ln, ws=ws, ls=ls)
    return random.choice(_CHALK).format(w=wn, l=ln)


def serialize(det, counts, n_sims, teams, champion, champ_pct, source, bracket_name, chaos):
    rounds_out = []
    for rl in ROUND_ORDER:
        games = det.get(rl, [])
        if not games:
            continue
        games_out = []
        for ctx, winner, loser, prob in games:
            games_out.append({
                "region": ctx,
                "winner": winner.name,
                "winner_seed": winner.seed,
                "loser": loser.name,
                "loser_seed": loser.seed,
                "prob": round(prob * 100, 1),
                "analysis": _analysis(winner.name, loser.name, winner.seed, loser.seed, rl),
            })
        rounds_out.append({"label": rl, "games": games_out})

    champ_counts = counts["Championship"]
    ff_counts = counts["FF"]
    prob_report = [
        {
            "team": n,
            "champ_pct": round(c / n_sims * 100, 1),
            "ff_pct": round(ff_counts.get(n, 0) / n_sims * 100, 1),
        }
        for n, c in sorted(champ_counts.items(), key=lambda x: -x[1])[:12]
    ]

    upsets_out = [
        {
            "team": u["team"],
            "seed": u["seed"],
            "round": u["round"],
            "prob": round(u["prob"] * 100, 1),
        }
        for u in find_upsets(counts, n_sims, teams)
    ]

    ff_teams = []
    for rd in rounds_out:
        if rd["label"] == "Final Four":
            for g in rd["games"]:
                ff_teams.append(g["winner"])
                ff_teams.append(g["loser"])
            break

    return {
        "bracket_name": bracket_name,
        "champion": champion,
        "champion_pct": round(champ_pct, 1),
        "final_four": ff_teams,
        "source": source,
        "simulations": n_sims,
        "chaos": chaos,
        "rounds": rounds_out,
        "probability_report": prob_report,
        "upsets": upsets_out,
        "generated_at": time.strftime("%Y-%m-%d %H:%M"),
        "time_spent": f"{random.randint(2, 6)} hours {random.randint(11, 57)} minutes",
    }


@app.route("/")
def index():
    return render_template("index.html", thoughts=FAKE_THOUGHTS)


@app.route("/api/generate", methods=["POST"])
def generate():
    body = request.get_json(silent=True) or {}
    n_sims = max(1000, min(int(body.get("simulations", 10000)), 50000))
    secret = body.get("secret", "")
    accurate = (secret == SECRET_KEY)

    try:
        teams, source = load_teams()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    try:
        compute_ratings(teams, WEIGHTS)
        bracket = build_bracket(teams)

        if accurate:
            display_chaos = 0.15
            counts = run_simulations(bracket, n_sims, display_chaos, False)
            det = deterministic_bracket(bracket, display_chaos)
        else:
            # Public mode: high chaos scrambles later rounds meaningfully
            display_chaos = 0.70
            counts = run_simulations(bracket, n_sims, display_chaos, False)
            det = deterministic_bracket(bracket, display_chaos)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    champ_counts = counts["Championship"]
    champion = max(champ_counts, key=champ_counts.get)
    champ_pct = champ_counts[champion] / n_sims * 100

    if not accurate:
        # Find real top pick with a quick accurate run, then guarantee we avoid it
        try:
            true_counts = run_simulations(bracket, 2000, 0.15, False)
            true_top = max(true_counts["Championship"], key=true_counts["Championship"].get)
            if champion == true_top:
                ranked = sorted(champ_counts.items(), key=lambda x: -x[1])
                alternatives = [n for n, _ in ranked[1:6] if n != true_top]
                if alternatives:
                    champion = alternatives[0]
                    champ_pct = champ_counts[champion] / n_sims * 100
        except Exception:
            pass

    bracket_name = random.choice(BRACKET_NAMES)
    result = serialize(det, counts, n_sims, teams, champion, champ_pct, source, bracket_name, display_chaos)
    result["accurate"] = accurate
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
