#!/usr/bin/env python3
"""
Totally Not AI March Madness Bracket Engine™
"This bracket complies fully with the 'No AI' rule by simply being better than everyone else."

Usage:
    python bracket.py
    python bracket.py --simulations 50000 --chaos 0.2 --export my_bracket.txt
    python bracket.py --data teams.csv --verbose
"""

# ─────────────────────────────────────────────────────────────────────────────
# IMPORTS
# ─────────────────────────────────────────────────────────────────────────────
import argparse
import collections
import csv
import json
import math
import os
import random
import statistics
import sys
import time
from dataclasses import dataclass
from typing import Optional

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

# Configurable weights for the composite rating formula.
# All components are z-score normalized before weights are applied,
# so these weights are directly comparable to each other.
WEIGHTS = {
    "offense":  1.0,   # offensive efficiency (pts per 100 possessions)
    "defense":  1.0,   # defensive efficiency (inverted — lower is better)
    "sos":      0.5,   # strength of schedule
    "seed":     1.5,   # seed bonus (higher weight = seeds matter more)
    "momentum": 0.3,   # recent form (last 10 games win rate, 0–1)
}

# Standard NCAA bracket seed pairings per region (Round of 64)
# Order: 1v16, 8v9, 5v12, 4v13, 6v11, 3v14, 7v10, 2v15
SEED_PAIRINGS = [
    (1, 16), (8, 9), (5, 12), (4, 13),
    (6, 11), (3, 14), (7, 10), (2, 15),
]

REGIONS = ["South", "East", "West", "Midwest"]

# Final Four pairings: South/East winner vs West/Midwest winner
FF_PAIRINGS = [("South", "East"), ("West", "Midwest")]

# ─────────────────────────────────────────────────────────────────────────────
# DATA MODEL
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Team:
    """
    Represents a tournament team with raw stats and a computed rating.
    _norm_* attributes are set by normalize_stats() before rating computation.
    """
    name:     str
    seed:     int
    region:   str
    off_eff:  float = 100.0   # offensive efficiency (pts/100 possessions)
    def_eff:  float = 100.0   # defensive efficiency (pts allowed/100 possessions)
    sos:      float = 0.5     # strength of schedule (normalized 0–1)
    record:   str   = "0-0"
    momentum: float = 0.5     # recent form (0–1)
    rating:   float = 0.0     # computed by compute_ratings()


# ─────────────────────────────────────────────────────────────────────────────
# HARDCODED 2026 DATASET  (real bracket — updated from sports-reference.com)
# def_eff = opponent points per game (lower is better defensive team)
# Replace this block each year or use --data teams.csv
# ─────────────────────────────────────────────────────────────────────────────
# fmt: off
HARDCODED_TEAMS = [
    # ── East Region ───────────────────────────────────────────────────────────
    {"name": "Duke",            "seed":  1, "region": "East",    "off_eff": 122.6, "def_eff": 63.1, "sos": 0.914, "record": "32-2",  "momentum": 0.941},
    {"name": "UConn",           "seed":  2, "region": "East",    "off_eff": 116.5, "def_eff": 65.1, "sos": 0.851, "record": "29-5",  "momentum": 0.853},
    {"name": "Michigan State",  "seed":  3, "region": "East",    "off_eff": 117.3, "def_eff": 68.4, "sos": 0.930, "record": "25-7",  "momentum": 0.781},
    {"name": "Kansas",          "seed":  4, "region": "East",    "off_eff": 110.0, "def_eff": 69.4, "sos": 0.995, "record": "23-10", "momentum": 0.697},
    {"name": "St. John's (NY)", "seed":  5, "region": "East",    "off_eff": 114.5, "def_eff": 70.0, "sos": 0.861, "record": "28-6",  "momentum": 0.824},
    {"name": "Louisville",      "seed":  6, "region": "East",    "off_eff": 119.4, "def_eff": 72.2, "sos": 0.861, "record": "23-10", "momentum": 0.697},
    {"name": "UCLA",            "seed":  7, "region": "East",    "off_eff": 117.0, "def_eff": 71.0, "sos": 0.885, "record": "23-11", "momentum": 0.676},
    {"name": "Ohio State",      "seed":  8, "region": "East",    "off_eff": 118.6, "def_eff": 72.8, "sos": 0.902, "record": "21-12", "momentum": 0.636},
    {"name": "TCU",             "seed":  9, "region": "East",    "off_eff": 111.1, "def_eff": 72.1, "sos": 0.817, "record": "22-11", "momentum": 0.667},
    {"name": "UCF",             "seed": 10, "region": "East",    "off_eff": 113.7, "def_eff": 78.5, "sos": 0.860, "record": "21-11", "momentum": 0.656},
    {"name": "South Florida",   "seed": 11, "region": "East",    "off_eff": 117.7, "def_eff": 75.5, "sos": 0.587, "record": "25-8",  "momentum": 0.758},
    {"name": "Northern Iowa",   "seed": 12, "region": "East",    "off_eff": 109.1, "def_eff": 61.3, "sos": 0.550, "record": "23-12", "momentum": 0.657},
    {"name": "Cal Baptist",     "seed": 13, "region": "East",    "off_eff": 107.1, "def_eff": 67.6, "sos": 0.402, "record": "25-8",  "momentum": 0.758},
    {"name": "North Dakota St.", "seed": 14, "region": "East",   "off_eff": 116.1, "def_eff": 69.6, "sos": 0.307, "record": "27-7",  "momentum": 0.794},
    {"name": "Furman",          "seed": 15, "region": "East",    "off_eff": 113.4, "def_eff": 70.5, "sos": 0.295, "record": "22-12", "momentum": 0.647},
    {"name": "Siena",           "seed": 16, "region": "East",    "off_eff": 109.3, "def_eff": 65.7, "sos": 0.194, "record": "23-11", "momentum": 0.676},
    # ── Midwest Region ────────────────────────────────────────────────────────
    {"name": "Michigan",        "seed":  1, "region": "Midwest", "off_eff": 121.3, "def_eff": 69.2, "sos": 0.995, "record": "31-3",  "momentum": 0.912},
    {"name": "Iowa State",      "seed":  2, "region": "Midwest", "off_eff": 120.0, "def_eff": 65.1, "sos": 0.850, "record": "27-7",  "momentum": 0.794},
    {"name": "Virginia",        "seed":  3, "region": "Midwest", "off_eff": 119.1, "def_eff": 68.4, "sos": 0.812, "record": "29-5",  "momentum": 0.853},
    {"name": "Alabama",         "seed":  4, "region": "Midwest", "off_eff": 122.0, "def_eff": 83.5, "sos": 0.982, "record": "23-9",  "momentum": 0.719},
    {"name": "Texas Tech",      "seed":  5, "region": "Midwest", "off_eff": 117.9, "def_eff": 72.6, "sos": 0.972, "record": "22-10", "momentum": 0.688},
    {"name": "Tennessee",       "seed":  6, "region": "Midwest", "off_eff": 116.8, "def_eff": 69.4, "sos": 0.900, "record": "22-11", "momentum": 0.667},
    {"name": "Kentucky",        "seed":  7, "region": "Midwest", "off_eff": 115.7, "def_eff": 73.8, "sos": 0.929, "record": "21-13", "momentum": 0.618},
    {"name": "Georgia",         "seed":  8, "region": "Midwest", "off_eff": 120.5, "def_eff": 79.2, "sos": 0.797, "record": "22-10", "momentum": 0.688},
    {"name": "Saint Louis",     "seed":  9, "region": "Midwest", "off_eff": 121.1, "def_eff": 69.5, "sos": 0.551, "record": "28-5",  "momentum": 0.848},
    {"name": "Santa Clara",     "seed": 10, "region": "Midwest", "off_eff": 118.9, "def_eff": 72.4, "sos": 0.702, "record": "26-8",  "momentum": 0.765},
    {"name": "Miami OH",        "seed": 11, "region": "Midwest", "off_eff": 113.0, "def_eff": 73.0, "sos": 0.500, "record": "22-11", "momentum": 0.667},
    {"name": "Akron",           "seed": 12, "region": "Midwest", "off_eff": 123.1, "def_eff": 73.5, "sos": 0.389, "record": "29-5",  "momentum": 0.853},
    {"name": "Hofstra",         "seed": 13, "region": "Midwest", "off_eff": 114.4, "def_eff": 66.1, "sos": 0.418, "record": "24-10", "momentum": 0.706},
    {"name": "Wright State",    "seed": 14, "region": "Midwest", "off_eff": 116.5, "def_eff": 73.4, "sos": 0.352, "record": "23-11", "momentum": 0.676},
    {"name": "Tennessee State", "seed": 15, "region": "Midwest", "off_eff": 111.5, "def_eff": 73.3, "sos": 0.211, "record": "23-9",  "momentum": 0.719},
    {"name": "Howard",          "seed": 16, "region": "Midwest", "off_eff": 110.4, "def_eff": 67.8, "sos": 0.105, "record": "23-10", "momentum": 0.697},
    # ── South Region ──────────────────────────────────────────────────────────
    {"name": "Florida",         "seed":  1, "region": "South",   "off_eff": 119.8, "def_eff": 72.0, "sos": 0.937, "record": "26-7",  "momentum": 0.788},
    {"name": "Houston",         "seed":  2, "region": "South",   "off_eff": 115.7, "def_eff": 74.2, "sos": 0.486, "record": "22-11", "momentum": 0.667},
    {"name": "Illinois",        "seed":  3, "region": "South",   "off_eff": 125.5, "def_eff": 69.8, "sos": 0.896, "record": "24-8",  "momentum": 0.750},
    {"name": "Nebraska",        "seed":  4, "region": "South",   "off_eff": 114.0, "def_eff": 66.2, "sos": 0.849, "record": "26-6",  "momentum": 0.812},
    {"name": "Vanderbilt",      "seed":  5, "region": "South",   "off_eff": 121.1, "def_eff": 75.2, "sos": 0.889, "record": "26-8",  "momentum": 0.765},
    {"name": "UNC",             "seed":  6, "region": "South",   "off_eff": 116.0, "def_eff": 71.3, "sos": 0.864, "record": "24-8",  "momentum": 0.750},
    {"name": "Saint Mary's",    "seed":  7, "region": "South",   "off_eff": 117.6, "def_eff": 64.6, "sos": 0.685, "record": "27-5",  "momentum": 0.844},
    {"name": "Clemson",         "seed":  8, "region": "South",   "off_eff": 112.4, "def_eff": 66.7, "sos": 0.819, "record": "24-10", "momentum": 0.706},
    {"name": "Iowa",            "seed":  9, "region": "South",   "off_eff": 105.8, "def_eff": 73.1, "sos": 0.234, "record": "18-14", "momentum": 0.562},
    {"name": "Texas A&M",       "seed": 10, "region": "South",   "off_eff": 118.2, "def_eff": 79.6, "sos": 0.787, "record": "21-11", "momentum": 0.656},
    {"name": "VCU",             "seed": 11, "region": "South",   "off_eff": 117.6, "def_eff": 71.5, "sos": 0.604, "record": "27-7",  "momentum": 0.794},
    {"name": "McNeese",         "seed": 12, "region": "South",   "off_eff": 117.6, "def_eff": 66.5, "sos": 0.431, "record": "28-5",  "momentum": 0.848},
    {"name": "Troy",            "seed": 13, "region": "South",   "off_eff": 113.5, "def_eff": 73.1, "sos": 0.348, "record": "22-11", "momentum": 0.667},
    {"name": "Penn",            "seed": 14, "region": "South",   "off_eff": 108.8, "def_eff": 73.3, "sos": 0.443, "record": "18-11", "momentum": 0.621},
    {"name": "Idaho",           "seed": 15, "region": "South",   "off_eff": 112.7, "def_eff": 72.6, "sos": 0.410, "record": "21-14", "momentum": 0.600},
    {"name": "Prairie View",    "seed": 16, "region": "South",   "off_eff": 103.0, "def_eff": 76.0, "sos": 0.180, "record": "19-14", "momentum": 0.576},
    # ── West Region ───────────────────────────────────────────────────────────
    {"name": "Arizona",         "seed":  1, "region": "West",    "off_eff": 120.3, "def_eff": 68.8, "sos": 0.919, "record": "32-2",  "momentum": 0.941},
    {"name": "Purdue",          "seed":  2, "region": "West",    "off_eff": 124.7, "def_eff": 70.1, "sos": 0.971, "record": "27-8",  "momentum": 0.771},
    {"name": "Gonzaga",         "seed":  3, "region": "West",    "off_eff": 120.5, "def_eff": 66.0, "sos": 0.699, "record": "30-3",  "momentum": 0.909},
    {"name": "Arkansas",        "seed":  4, "region": "West",    "off_eff": 122.5, "def_eff": 80.1, "sos": 0.919, "record": "26-8",  "momentum": 0.765},
    {"name": "Wisconsin",       "seed":  5, "region": "West",    "off_eff": 118.8, "def_eff": 75.9, "sos": 0.915, "record": "24-10", "momentum": 0.706},
    {"name": "BYU",             "seed":  6, "region": "West",    "off_eff": 118.7, "def_eff": 75.3, "sos": 0.915, "record": "23-11", "momentum": 0.676},
    {"name": "Miami (FL)",      "seed":  7, "region": "West",    "off_eff": 118.2, "def_eff": 71.2, "sos": 0.743, "record": "25-8",  "momentum": 0.758},
    {"name": "Villanova",       "seed":  8, "region": "West",    "off_eff": 114.8, "def_eff": 70.8, "sos": 0.831, "record": "24-8",  "momentum": 0.750},
    {"name": "Utah State",      "seed":  9, "region": "West",    "off_eff": 120.0, "def_eff": 70.4, "sos": 0.717, "record": "28-6",  "momentum": 0.824},
    {"name": "Missouri",        "seed": 10, "region": "West",    "off_eff": 115.6, "def_eff": 75.3, "sos": 0.792, "record": "20-12", "momentum": 0.625},
    {"name": "Texas",           "seed": 11, "region": "West",    "off_eff": 120.1, "def_eff": 76.8, "sos": 0.843, "record": "18-14", "momentum": 0.562},
    {"name": "High Point",      "seed": 12, "region": "West",    "off_eff": 124.5, "def_eff": 70.3, "sos": 0.237, "record": "30-4",  "momentum": 0.882},
    {"name": "Hawaii",          "seed": 13, "region": "West",    "off_eff": 109.6, "def_eff": 69.7, "sos": 0.380, "record": "24-8",  "momentum": 0.750},
    {"name": "Kennesaw State",  "seed": 14, "region": "West",    "off_eff": 114.2, "def_eff": 76.1, "sos": 0.433, "record": "21-13", "momentum": 0.618},
    {"name": "Queens (NC)",     "seed": 15, "region": "West",    "off_eff": 108.3, "def_eff": 71.1, "sos": 0.236, "record": "24-10", "momentum": 0.706},
    {"name": "LIU",             "seed": 16, "region": "West",    "off_eff": 108.3, "def_eff": 71.1, "sos": 0.236, "record": "24-10", "momentum": 0.706},
]
# fmt: on


# ─────────────────────────────────────────────────────────────────────────────
# HUMOR MODULE
# ─────────────────────────────────────────────────────────────────────────────

BRACKET_NAMES = [
    "Mikayla Said I Had To",
    "Totally Not AI v2",
    "Bracketology for Dummies",
    "The Vibes Were Immaculate",
    "Statistically Superior Guessing",
    "ChatGPT Didn't Help (Wink)",
    "My Dog Picked These",
    "Running on Pure Spite",
    "The Algorithm That Isn't One",
    "Gut Feelings and Granola Bars",
    "Peer-Reviewed Intuition",
    "Definitely Human Selections",
    "The Chaos Was Intentional",
    "Advanced Nap-Based Analytics",
]

STARTUP_MESSAGES = [
    "Initializing NOT AI Bracket Engine™...",
    "Calibrating human intuition...",
    "Consulting vibes...",
    "Running completely manual calculations (definitely not AI)...",
    "Applying advanced snack-based heuristics...",
    "Cross-referencing with gut feelings database...",
    # last message is formatted with sim count in print_startup()
]

COMMITTEE_STATEMENT = """\n╔══════════════════════════════════════════════════════════╗
║          OFFICIAL SELECTION COMMITTEE STATEMENT          ║
╠══════════════════════════════════════════════════════════╣
║  Due to recent rule changes banning AI, this bracket     ║
║  was generated using 100% human intuition and            ║
║  absolutely no machine assistance.                       ║
║                                                          ║
║  Upsets selected using proprietary 'gut feeling'         ║
║  technology. Results may vary. Batteries not included.   ║
║                                                          ║
║  If this bracket wins again, we will be accepting        ║
║  formal apologies.                                       ║
╚══════════════════════════════════════════════════════════╝"""

FOOTER = "\"This bracket complies fully with the 'No AI' rule by simply being better than everyone else.\""


def print_startup(n_sims: int, use_humor: bool) -> None:
    if not use_humor:
        return
    print()
    for msg in STARTUP_MESSAGES:
        print(f"  ⚙️  {msg}")
        time.sleep(0.15)
    print(f"  ⚙️  Simulating {n_sims:,} brackets using 100% organic brain cells...")
    time.sleep(0.15)
    print()


def print_committee_statement(use_humor: bool) -> None:
    if use_humor:
        print(COMMITTEE_STATEMENT)


def print_footer(use_humor: bool) -> None:
    if use_humor:
        print(f"\n  😏  {FOOTER}\n")


# ─────────────────────────────────────────────────────────────────────────────
# DATA LAYER
# ─────────────────────────────────────────────────────────────────────────────

# sports-reference uses full school names; map common bracket abbreviations
_SR_NAME_MAP = {
    "UConn":           "ConnecticutNCAA",
    "TCU":             "Texas ChristianNCAA",
    "LIU":             "Long Island UniversityNCAA",
    "BYU":             "Brigham YoungNCAA",
    "VCU":             "Virginia CommonwealthNCAA",
    "Penn":            "PennsylvaniaNCAA",
    "UNC":             "North CarolinaNCAA",
    "Miami (FL)":      "Miami (FL)NCAA",
    "Queens (NC)":     "Queens UniversityNCAA",
    "St. John's (NY)": "St. John's (NY)",
    "Miami OH":        "Miami (OH)NCAA",
    "Prairie View":    "Prairie View A&MNCAA",
}

import difflib as _difflib


def fetch_sports_reference() -> list:
    """
    Scrape sports-reference.com using two pages:
      1. Bracket page  → seeds, regions, and team names for the 64 tournament teams
      2. Stats page    → off_rtg, opp_pts/game (defensive proxy), sos, record, momentum

    def_eff here = opponent points per game (lower = better defense).
    Z-score normalization in compute_ratings() handles the different scale vs off_eff.
    """
    if not REQUESTS_AVAILABLE or not BS4_AVAILABLE:
        raise ImportError("requests and beautifulsoup4 not installed")

    hdr  = {"User-Agent": "Mozilla/5.0 (compatible; bracket-engine/2.0)"}
    year = time.strftime("%Y")

    # ── Page 1: bracket seeds & regions ──────────────────────────────────────
    bracket_url = f"https://www.sports-reference.com/cbb/postseason/men/{year}-ncaa.html"
    resp = requests.get(bracket_url, headers=hdr, timeout=12)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    bracket_teams = []
    for rid, rname in [("east","East"),("west","West"),("south","South"),("midwest","Midwest")]:
        rdiv = soup.find("div", {"id": rid})
        if not rdiv:
            continue
        bdiv = rdiv.find("div", id="bracket")
        if not bdiv:
            continue
        first_round = bdiv.find("div", class_="round")
        if not first_round:
            continue
        for game in first_round.find_all("div", recursive=False):
            for td in game.find_all("div", recursive=False):
                span, a = td.find("span"), td.find("a")
                if span and a:
                    try:
                        bracket_teams.append((rname, int(span.get_text(strip=True)), a.get_text(strip=True)))
                    except ValueError:
                        continue

    if len(bracket_teams) < 60:
        raise ValueError(f"Only found {len(bracket_teams)} bracket teams (expected ~64)")

    # ── Page 2: advanced stats ────────────────────────────────────────────────
    stats_url = f"https://www.sports-reference.com/cbb/seasons/men/{year}-advanced-school-stats.html"
    resp2 = requests.get(stats_url, headers=hdr, timeout=12)
    resp2.raise_for_status()
    soup2 = BeautifulSoup(resp2.text, "html.parser")
    table = soup2.find("table", {"id": "adv_school_stats"})
    if not table:
        raise ValueError("Stats table not found")

    def _cell(row, stat):
        c = row.find("td", {"data-stat": stat})
        return c.get_text(strip=True) if c else ""

    stats_db = {}
    for row in table.find("tbody").find_all("tr"):
        if "thead" in row.get("class", []):
            continue
        name = _cell(row, "school_name")
        if not name:
            continue
        try:
            wins   = int(_cell(row, "wins")   or 0)
            losses = int(_cell(row, "losses") or 0)
            games  = max(wins + losses, 1)
            opp    = float(_cell(row, "opp_pts") or 0)
            sos_r  = float(_cell(row, "sos")     or 0)
            stats_db[name] = {
                "off_eff":  float(_cell(row, "off_rtg") or 100),
                "def_eff":  round(opp / games, 1),
                "sos":      max(0.0, min(1.0, (sos_r + 15) / 30)),
                "momentum": round(wins / games, 3),
                "record":   f"{wins}-{losses}",
            }
        except (ValueError, ZeroDivisionError):
            continue

    all_stat_names = list(stats_db.keys())

    # ── Merge bracket names with stats ────────────────────────────────────────
    teams = []
    for region, seed, bname in bracket_teams:
        sname = _SR_NAME_MAP.get(bname, bname)
        s = stats_db.get(sname)
        if not s:
            close = _difflib.get_close_matches(sname, all_stat_names, n=1, cutoff=0.55)
            s = stats_db[close[0]] if close else None
        if not s:
            s = {"off_eff": 110.0, "def_eff": 72.0, "sos": 0.5, "momentum": 0.65, "record": "??"}
        teams.append(Team(
            name=bname, seed=seed, region=region,
            off_eff=s["off_eff"], def_eff=s["def_eff"],
            sos=s["sos"], record=s["record"], momentum=s["momentum"],
        ))

    if len(teams) < 60:
        raise ValueError(f"Merged only {len(teams)} teams")
    return teams


def fetch_espn() -> list:
    """
    Fallback: attempt to scrape ESPN BPI page for team ratings.
    ESPN embeds data as JSON blobs in <script> tags.
    Raises on any failure.
    """
    if not REQUESTS_AVAILABLE or not BS4_AVAILABLE:
        raise ImportError("requests and beautifulsoup4 not installed")

    url = "https://www.espn.com/mens-college-basketball/bpi"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; bracket-engine/2.0)"}

    resp = requests.get(url, headers=headers, timeout=12)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    data = None
    for script in soup.find_all("script"):
        if not script.string:
            continue
        text = script.string
        if "bpi" not in text.lower():
            continue
        # Find outermost JSON object
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start == -1 or end <= start:
            continue
        try:
            data = json.loads(text[start:end])
            break
        except json.JSONDecodeError:
            continue

    if not data:
        raise ValueError("Could not parse ESPN BPI JSON blob")

    team_list = (
        data.get("teams") or
        data.get("bpiData", {}).get("teams") or
        []
    )

    teams = []
    for t in team_list:
        try:
            teams.append(Team(
                name=t.get("displayName") or t.get("name", "Unknown"),
                seed=0, region="TBD",
                off_eff=float(t.get("offensiveEfficiency", 100.0)),
                def_eff=float(t.get("defensiveEfficiency", 100.0)),
                sos=float(t.get("strengthOfSchedule", 0.5)),
            ))
        except (ValueError, KeyError):
            continue

    if len(teams) < 64:
        raise ValueError(f"Only found {len(teams)} ESPN teams (need ≥64)")
    return teams


def load_csv(path: str) -> list:
    """
    Load teams from a CSV file.
    Required columns: team, seed, region
    Optional columns: off_eff, def_eff, sos, record, momentum
    """
    teams = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                teams.append(Team(
                    name     = row["team"].strip(),
                    seed     = int(row["seed"]),
                    region   = row["region"].strip(),
                    off_eff  = float(row.get("off_eff",  100.0) or 100.0),
                    def_eff  = float(row.get("def_eff",  100.0) or 100.0),
                    sos      = float(row.get("sos",       0.5)  or 0.5),
                    record   = str(row.get("record", "0-0")).strip(),
                    momentum = float(row.get("momentum",  0.5)  or 0.5),
                ))
            except (KeyError, ValueError):
                continue
    if len(teams) < 64:
        raise ValueError(f"CSV has only {len(teams)} valid rows (need 64)")
    return teams


def load_hardcoded() -> list:
    """Always-available fallback — the elite intuition dataset."""
    return [Team(**t) for t in HARDCODED_TEAMS]


def load_teams(data_path: Optional[str] = None) -> tuple:
    """
    Fallback chain:
      1. CSV via --data (if provided)
      2. sports-reference.com  (live scrape)
      3. ESPN BPI              (live scrape)
      4. Hardcoded 2026 data   (always works)

    Returns (teams: list[Team], source: str)
    """
    # 1. Explicit CSV
    if data_path:
        try:
            return load_csv(data_path), f"CSV: {data_path}"
        except Exception as e:
            print(f"  ⚠️  CSV load failed ({e}), trying live sources...")

    # 2. sports-reference
    try:
        teams = fetch_sports_reference()
        # Fill any missing seeds (First Four play-ins) from hardcoded data
        live_keys = {(t.region, t.seed) for t in teams}
        for t in load_hardcoded():
            if (t.region, t.seed) not in live_keys:
                teams.append(t)
        return teams, "sports-reference.com (live)"
    except Exception:
        pass

    # 3. ESPN
    try:
        teams = fetch_espn()
        return teams, "ESPN BPI (live)"
    except Exception:
        pass

    # 4. Hardcoded fallback
    print("  ⚠️  Live data unavailable, reverting to elite intuition dataset.")
    return load_hardcoded(), "hardcoded 2026 dataset (elite intuition mode)"


# ─────────────────────────────────────────────────────────────────────────────
# RATINGS ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def normalize_stats(teams: list) -> None:
    """
    Z-score normalize each stat component across all teams.

    Why z-score: raw stats live on incompatible scales — offensive efficiency
    is ~95-122 pts/100 possessions, while seed bonus is 1-16 and SoS is 0-1.
    Without normalization, the weights are meaningless relative to each other
    and the logistic function would produce near-0 or near-1 probabilities for
    most matchups, killing the chaos factor.

    After normalization, each component has mean=0, stdev=1, so a weight of
    1.0 on offense contributes the same magnitude as a weight of 1.0 on seed.
    """
    if len(teams) < 2:
        raise ValueError(f"Need at least 2 teams to normalize stats, got {len(teams)}")

    for attr in ("off_eff", "def_eff", "sos", "momentum"):
        vals  = [getattr(t, attr) for t in teams]
        mean  = statistics.mean(vals)
        stdev = statistics.stdev(vals) if len(vals) > 1 else 1.0
        stdev = stdev or 1.0  # guard against zero stdev (all identical values)
        for t in teams:
            object.__setattr__(t, f"_z_{attr}", (getattr(t, attr) - mean) / stdev)

    # Seed bonus: 1-seed should score highest; invert so lower seed = higher score
    seed_vals  = [(17 - t.seed) for t in teams]
    seed_mean  = statistics.mean(seed_vals)
    seed_stdev = statistics.stdev(seed_vals) if len(seed_vals) > 1 else 1.0
    seed_stdev = seed_stdev or 1.0
    for t in teams:
        object.__setattr__(t, "_z_seed", ((17 - t.seed) - seed_mean) / seed_stdev)


def compute_ratings(teams: list, weights: dict) -> None:
    """Compute composite rating for each team using z-score normalized components."""
    normalize_stats(teams)
    for t in teams:
        t.rating = (
            weights["offense"]  *  t._z_off_eff
            - weights["defense"] *  t._z_def_eff   # subtract: lower def_eff is better
            + weights["sos"]    *  t._z_sos
            + weights["seed"]   *  t._z_seed
            + weights["momentum"] * t._z_momentum
        )


# ─────────────────────────────────────────────────────────────────────────────
# SIMULATION ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def win_probability(team_a: Team, team_b: Team, chaos_factor: float) -> float:
    """
    Logistic win probability for team_a over team_b.

    Data flow:
      rating_diff → logistic(diff * scale) → base_prob
      base_prob   → compress toward 0.5 by chaos_factor → final_prob

    Scale factor 1.5 calibrated for z-score normalized ratings, where
    the difference between a 1-seed and 16-seed is roughly 3-4 units.
    At scale=1.5, that gives ~98-99% win probability for a dominant 1-seed,
    with chaos_factor=0.15 pulling it down to ~83-84%.

    chaos_factor=0.0 → pure model (higher rating always wins by margin)
    chaos_factor=1.0 → all games are coin flips
    chaos_factor=0.15 → default: realistic upset rate (~15-18% for 5v12 games)
    """
    diff       = team_a.rating - team_b.rating
    base_prob  = 1.0 / (1.0 + math.exp(-diff * 1.5))
    return base_prob * (1.0 - chaos_factor) + 0.5 * chaos_factor


def simulate_game(team_a: Team, team_b: Team, chaos_factor: float) -> Team:
    """Simulate one game. Returns winner."""
    return team_a if random.random() < win_probability(team_a, team_b, chaos_factor) else team_b


def simulate_tournament(bracket: dict, chaos_factor: float, counts: dict) -> str:
    """
    Simulate one full tournament.

    Tournament flow:
      ┌─────────────────────────────────────────────────────────┐
      │  4 Regions (South, East, West, Midwest)                  │
      │    Round of 64  →  Round of 32  →  Sweet 16  →  Elite 8  │
      │         ↓                                                 │
      │  Final Four: South/East champion vs West/Midwest champ   │
      │         ↓                                                 │
      │  Championship: Final Four winners                        │
      └─────────────────────────────────────────────────────────┘

    Updates counts[round_key][team_name] in-place for each advancement.
    Returns champion name.
    """
    regional_champs = {}

    for region in REGIONS:
        seeds = dict(bracket[region])  # seed → Team (shallow copy per region)

        # Round of 64: fixed seed pairings
        survivors = []
        for s_a, s_b in SEED_PAIRINGS:
            w = simulate_game(seeds[s_a], seeds[s_b], chaos_factor)
            counts["R64"][w.name] += 1
            survivors.append(w)

        # Round of 32, Sweet 16, Elite 8: pair adjacent survivors
        for round_key in ("R32", "S16", "E8"):
            next_round = []
            for i in range(0, len(survivors), 2):
                w = simulate_game(survivors[i], survivors[i + 1], chaos_factor)
                counts[round_key][w.name] += 1
                next_round.append(w)
            survivors = next_round

        regional_champs[region] = survivors[0]

    # Final Four
    finalists = []
    for r_a, r_b in FF_PAIRINGS:
        w = simulate_game(regional_champs[r_a], regional_champs[r_b], chaos_factor)
        counts["FF"][w.name] += 1
        finalists.append(w)

    # Championship
    champion = simulate_game(finalists[0], finalists[1], chaos_factor)
    counts["Championship"][champion.name] += 1
    return champion.name


def run_simulations(bracket: dict, n_sims: int, chaos_factor: float, verbose: bool) -> dict:
    """
    Run n_sims full tournament simulations.
    Returns advancement counts: {round_key: {team_name: int}}
    """
    round_keys = ["R64", "R32", "S16", "E8", "FF", "Championship"]
    counts = {r: collections.defaultdict(int) for r in round_keys}

    for i in range(n_sims):
        simulate_tournament(bracket, chaos_factor, counts)
        if verbose and (i + 1) % 500 == 0:
            pct = (i + 1) / n_sims * 100
            bar_fill = int(pct / 5)
            bar = "█" * bar_fill + "░" * (20 - bar_fill)
            print(f"\r  [{bar}] {i+1:,}/{n_sims:,} ({pct:.0f}%)", end="", flush=True)

    if verbose:
        print()  # newline after progress bar

    return counts


# ─────────────────────────────────────────────────────────────────────────────
# BRACKET ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def build_bracket(teams: list) -> dict:
    """
    Construct the bracket dict: {region: {seed: Team}}.
    Validates that all 4 regions have exactly seeds 1–16.
    """
    bracket = {r: {} for r in REGIONS}

    for t in teams:
        if t.region in bracket and 1 <= t.seed <= 16:
            bracket[t.region][t.seed] = t

    # Validate completeness
    for region in REGIONS:
        missing = [s for s in range(1, 17) if s not in bracket[region]]
        if missing:
            raise ValueError(
                f"Region '{region}' is missing seeds: {missing}. "
                f"Verify your data source or teams.csv has all 64 teams."
            )

    return bracket


def deterministic_bracket(bracket: dict, chaos_factor: float) -> dict:
    """
    Walk the bracket picking the higher-probability team every game.
    Returns a structured result dict keyed by round label for display.

    Result format: {round_label: [(region_or_label, winner, loser, win_prob), ...]}
    """
    results = {r: [] for r in ("Round of 64", "Round of 32", "Sweet 16", "Elite 8", "Final Four", "Championship")}
    regional_champs = {}

    for region in REGIONS:
        seeds     = dict(bracket[region])
        survivors = []

        for s_a, s_b in SEED_PAIRINGS:
            ta, tb = seeds[s_a], seeds[s_b]
            p = win_probability(ta, tb, chaos_factor)
            winner, loser, prob = (ta, tb, p) if p >= 0.5 else (tb, ta, 1 - p)
            results["Round of 64"].append((region, winner, loser, prob))
            survivors.append(winner)

        for round_label in ("Round of 32", "Sweet 16", "Elite 8"):
            next_round = []
            for i in range(0, len(survivors), 2):
                ta, tb = survivors[i], survivors[i + 1]
                p = win_probability(ta, tb, chaos_factor)
                winner, loser, prob = (ta, tb, p) if p >= 0.5 else (tb, ta, 1 - p)
                results[round_label].append((region, winner, loser, prob))
                next_round.append(winner)
            survivors = next_round

        regional_champs[region] = survivors[0]

    # Final Four
    finalists = []
    for r_a, r_b in FF_PAIRINGS:
        ta, tb = regional_champs[r_a], regional_champs[r_b]
        p = win_probability(ta, tb, chaos_factor)
        winner, loser, prob = (ta, tb, p) if p >= 0.5 else (tb, ta, 1 - p)
        results["Final Four"].append((f"{r_a}/{r_b}", winner, loser, prob))
        finalists.append(winner)

    # Championship
    ta, tb = finalists[0], finalists[1]
    p = win_probability(ta, tb, chaos_factor)
    winner, loser, prob = (ta, tb, p) if p >= 0.5 else (tb, ta, 1 - p)
    results["Championship"].append(("Championship", winner, loser, prob))

    return results


# ─────────────────────────────────────────────────────────────────────────────
# POOL OPTIMIZATION
# ─────────────────────────────────────────────────────────────────────────────

def find_upsets(counts: dict, n_sims: int, teams: list) -> list:
    """
    Identify high-value upset picks for pool differentiation.

    Strategy: public pools heavily overweight seeds 1–4 for late rounds.
    Any team with seed > 4 that advances to Sweet 16+ in ≥28% of sims is
    likely underrepresented in the average pool — picking them is +EV.

    Differentiation value = advance_probability × (seed - 4) / 12
    (higher seed = rarer pick = more valuable if correct)

    Returns top-5 upset recommendations sorted by differentiation value.
    """
    # Build seed lookup from current team list
    seed_map = {t.name: (t.seed, t.region) for t in teams}

    thresholds = [
        ("S16", "Sweet 16",  0.28),
        ("E8",  "Elite 8",   0.18),
        ("FF",  "Final Four", 0.10),
    ]

    candidates = {}
    for round_key, round_label, min_prob in thresholds:
        for team_name, count in counts.get(round_key, {}).items():
            prob = count / n_sims
            info = seed_map.get(team_name)
            if not info:
                continue
            seed, region = info
            if seed <= 4 or prob < min_prob:
                continue
            diff_val = prob * (seed - 4) / 12.0
            # Keep deepest round per team
            if team_name not in candidates or diff_val > candidates[team_name]["diff_val"]:
                candidates[team_name] = {
                    "team":      team_name,
                    "seed":      seed,
                    "region":    region,
                    "round":     round_label,
                    "prob":      prob,
                    "diff_val":  diff_val,
                }

    return sorted(candidates.values(), key=lambda x: -x["diff_val"])[:5]


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT FORMATTERS
# ─────────────────────────────────────────────────────────────────────────────

ROUND_ORDER = ["Round of 64", "Round of 32", "Sweet 16", "Elite 8", "Final Four", "Championship"]


def fmt_bracket(det_results: dict) -> str:
    lines = []
    for round_label in ROUND_ORDER:
        games = det_results.get(round_label, [])
        if not games:
            continue
        lines.append(f"\n{'━' * 60}")
        lines.append(f"  {round_label.upper()}")
        lines.append(f"{'━' * 60}")

        cur_region = None
        for context, winner, loser, prob in games:
            if round_label in ("Round of 64", "Round of 32", "Sweet 16", "Elite 8"):
                if context != cur_region:
                    lines.append(f"\n  ── {context} Region ──")
                    cur_region = context
                lines.append(
                    f"  ({winner.seed:>2}) {winner.name:<22}  defeats  "
                    f"({loser.seed:>2}) {loser.name:<22}  {prob*100:.1f}%"
                )
            else:
                lines.append(
                    f"  {winner.name:<26}  defeats  {loser.name:<26}  {prob*100:.1f}%"
                )
    return "\n".join(lines)


def fmt_probability_report(counts: dict, n_sims: int) -> str:
    lines = [
        f"\n{'━' * 60}",
        "  CHAMPIONSHIP PROBABILITY REPORT",
        f"  (based on {n_sims:,} simulations)",
        f"{'━' * 60}",
        f"  {'Rank':<5}  {'Team':<26}  {'Champ %':>8}  {'Final Four %':>13}",
        "  " + "─" * 56,
    ]
    champ_counts = counts["Championship"]
    ff_counts    = counts["FF"]
    for rank, (name, cnt) in enumerate(sorted(champ_counts.items(), key=lambda x: -x[1])[:16], 1):
        champ_pct = cnt / n_sims * 100
        ff_pct    = ff_counts.get(name, 0) / n_sims * 100
        lines.append(f"  {rank:<5}  {name:<26}  {champ_pct:>7.1f}%  {ff_pct:>12.1f}%")
    return "\n".join(lines)


def fmt_optimized_picks(upsets: list, n_sims: int) -> str:
    lines = [
        f"\n{'━' * 60}",
        "  POOL-OPTIMIZED PICKS",
        f"  (differentiation strategy — public pools are 70%+ chalk on seeds 1-4)",
        f"{'━' * 60}",
    ]
    if not upsets:
        lines += [
            "",
            "  ✅  No high-value upsets detected this year.",
            "  ✅  The model says go chalk — everyone else will split the upsets.",
        ]
        return "\n".join(lines)

    for u in upsets:
        lines.append(
            f"\n  ⚡  UPSET PICK: ({u['seed']}) {u['team']}  →  {u['round']}"
        )
        lines.append(
            f"      Advances in {u['prob']*100:.1f}% of sims  |  "
            f"Seed {u['seed']} = underrepresented in most pools"
        )
    lines += [
        "",
        "  Strategy: these picks create bracket differentiation while staying",
        "  statistically defensible. The field won't have them — you will.",
    ]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        prog="bracket.py",
        description="Totally Not AI March Madness Bracket Engine™",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"  {FOOTER}",
    )
    p.add_argument("--simulations", type=int, default=10_000,
                   help="Number of Monte Carlo simulations (default: 10000)")
    p.add_argument("--chaos",       type=float, default=0.15,
                   help="Chaos/upset factor, 0.0–1.0 (default: 0.15)")
    p.add_argument("--export",      type=str, default=None,
                   help="Write full output to this file path")
    p.add_argument("--data",        type=str, default=None,
                   help="Path to teams.csv (team,seed,region,off_eff,def_eff,sos,record,momentum)")
    p.add_argument("--no-humor",    action="store_true",
                   help="Suppress humor output (for the soulless)")
    p.add_argument("--verbose",     action="store_true",
                   help="Show simulation progress bar")
    return p.parse_args()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    # Validate + clamp args
    if args.simulations < 1:
        print("Error: --simulations must be ≥ 1", file=sys.stderr)
        sys.exit(1)

    chaos = max(0.0, min(1.0, args.chaos))
    if chaos != args.chaos:
        print(f"  ⚠️  Chaos factor clamped from {args.chaos} to {chaos:.2f}")

    use_humor    = not args.no_humor
    bracket_name = random.choice(BRACKET_NAMES)

    # ── Header ────────────────────────────────────────────────────────────────
    header = (
        f"\n{'═' * 60}\n"
        f"  TOTALLY NOT AI BRACKET ENGINE™  v2.0\n"
        f'  Bracket Name: "{bracket_name}"\n'
        f"{'═' * 60}"
    )
    print(header)

    # ── Startup humor ──────────────────────────────────────────────────────────
    print_startup(args.simulations, use_humor)

    # ── Load data ─────────────────────────────────────────────────────────────
    print("  📥  Loading team data...")
    try:
        teams, source = load_teams(args.data)
    except Exception as e:
        print(f"  ❌  Fatal: Could not load team data: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"  ✅  {len(teams)} teams loaded from {source}")

    # ── Compute ratings ───────────────────────────────────────────────────────
    try:
        compute_ratings(teams, WEIGHTS)
    except ValueError as e:
        print(f"  ❌  Rating error: {e}", file=sys.stderr)
        sys.exit(1)

    # ── Build bracket ─────────────────────────────────────────────────────────
    try:
        bracket = build_bracket(teams)
    except ValueError as e:
        print(f"  ❌  Bracket error: {e}", file=sys.stderr)
        sys.exit(1)

    # ── Simulate ──────────────────────────────────────────────────────────────
    print(f"\n  📊  Running {args.simulations:,} simulations  (chaos={chaos:.2f})...")
    t0 = time.time()
    counts = run_simulations(bracket, args.simulations, chaos, args.verbose)
    elapsed = time.time() - t0
    print(f"  ✅  Done in {elapsed:.1f}s\n")

    # ── Deterministic bracket (for display) ───────────────────────────────────
    det = deterministic_bracket(bracket, chaos)

    # ── Champion from simulations ─────────────────────────────────────────────
    champ_counts = counts["Championship"]
    champion     = max(champ_counts, key=champ_counts.get) if champ_counts else "???"
    champ_pct    = champ_counts.get(champion, 0) / args.simulations * 100

    # ── Pool upsets ───────────────────────────────────────────────────────────
    upsets = find_upsets(counts, args.simulations, teams)

    # ── Assemble output ───────────────────────────────────────────────────────
    champ_block = (
        f"\n{'━' * 60}\n"
        f"  🏆   CHAMPION:  {champion.upper()}\n"
        f"       Won {champ_pct:.1f}% of {args.simulations:,} simulations\n"
        f"{'━' * 60}"
    )

    output = "\n".join([
        fmt_bracket(det),
        champ_block,
        fmt_probability_report(counts, args.simulations),
        fmt_optimized_picks(upsets, args.simulations),
    ])

    print(output)
    print_committee_statement(use_humor)
    print_footer(use_humor)

    # ── Export ────────────────────────────────────────────────────────────────
    if args.export:
        export_body = (
            f"TOTALLY NOT AI BRACKET ENGINE™  v2.0\n"
            f'Bracket Name: "{bracket_name}"\n'
            f"Generated:    {time.strftime('%Y-%m-%d %H:%M')}\n"
            f"Simulations:  {args.simulations:,}  |  Chaos: {chaos:.2f}\n"
            f"Data source:  {source}\n"
            f"{'=' * 60}\n"
            f"{output}\n"
        )
        if use_humor:
            export_body += f"\n{COMMITTEE_STATEMENT}\n\n  😏  {FOOTER}\n"
        try:
            with open(args.export, "w", encoding="utf-8") as f:
                f.write(export_body)
            print(f"  💾  Bracket exported to: {args.export}")
        except OSError as e:
            print(f"  ⚠️  Export failed ({e}) — output shown above.", file=sys.stderr)


if __name__ == "__main__":
    main()
