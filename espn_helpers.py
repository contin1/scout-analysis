"""
ESPN API helpers for College Basketball + High School (MaxPreps via ESPN ecosystem).
All endpoints are free/public — no API key required.
"""
import time
import requests
import pandas as pd

ESPN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.espn.com/",
    "Origin": "https://www.espn.com",
}

BASE_SITE   = "https://site.api.espn.com/apis/site/v2"
BASE_WEB    = "https://site.web.api.espn.com/apis/common/v3"
BASE_SEARCH = "https://site.api.espn.com/apis/search/v2"

LEAGUE_SLUGS = {
    "nba":      ("nba",                     "s:40~l:46"),
    "college":  ("mens-college-basketball", "s:40~l:41"),
}

GAMELOG_LABELS = [
    "MIN", "FG", "FG%", "3PT", "3P%", "FT", "FT%",
    "REB", "AST", "BLK", "STL", "PF", "TO", "PTS",
]

GAMELOG_NAMES = [
    "minutes", "fg", "fg_pct", "3pt", "3pt_pct", "ft", "ft_pct",
    "reb", "ast", "blk", "stl", "pf", "tov", "pts",
]


def _get(url, params=None, retries=3):
    for attempt in range(retries):
        try:
            time.sleep(0.4)
            r = requests.get(url, headers=ESPN_HEADERS, params=params, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception:
            if attempt == retries - 1:
                return None
            time.sleep(1.5 ** attempt)
    return None


def search_player(query: str, limit: int = 8) -> list[dict]:
    """
    Search ESPN for a player by name. Returns list of dicts:
    {id, uid, displayName, description (league/team), imageUrl, league_slug}
    """
    data = _get(BASE_SEARCH, params={"query": query, "limit": limit, "lang": "en", "contenttype": "player"})
    if not data:
        return []
    results = []
    for group in data.get("results", []):
        if group.get("type") == "player":
            for c in group.get("contents", []):
                uid = c.get("uid", "")
                # uid format: s:40~l:46~a:12345  (l:46 = NBA, l:41 = NCAAM)
                league_slug = "nba" if "l:46" in uid else ("college" if "l:41" in uid else "other")
                # extract athlete id from uid  s:40~l:XX~a:ID
                aid = uid.split("~a:")[-1] if "~a:" in uid else c.get("id", "")
                results.append({
                    "id":          aid,
                    "uid":         uid,
                    "displayName": c.get("displayName", ""),
                    "description": c.get("description", ""),
                    "subtitle":    c.get("subtitle", ""),
                    "imageUrl":    c.get("image", {}).get("default", ""),
                    "league_slug": league_slug,
                    "webLink":     c.get("link", {}).get("web", ""),
                })
    return results


def get_college_gamelog(athlete_id: str, season: int = 2026) -> pd.DataFrame:
    """
    Fetch per-game stats for a college player.
    Returns DataFrame with columns: date, opponent, result, MIN, FG, FG%, 3PT, 3P%, FT, FT%, REB, AST, BLK, STL, PF, TO, PTS
    """
    # ESPN uses year-end convention: 2026 = 2025-26 season
    espn_season = season if season >= 2026 else season + 1
    url  = f"{BASE_WEB}/sports/basketball/mens-college-basketball/athletes/{athlete_id}/gamelog"
    data = _get(url, params={"season": espn_season})
    if not data:
        return pd.DataFrame()

    labels = data.get("labels", GAMELOG_LABELS)
    events_meta = data.get("events", {})
    season_types = data.get("seasonTypes", [])

    rows = []
    for stype in season_types:
        for cat in stype.get("categories", []):
            for ev in cat.get("events", []):
                event_id = ev.get("eventId", "")
                stats    = ev.get("stats", [])
                meta     = events_meta.get(event_id, {})

                row = {
                    "game_date": meta.get("gameDate", "")[:10],
                    "opponent":  meta.get("opponent", {}).get("displayName", ""),
                    "result":    meta.get("gameResult", ""),
                    "location":  meta.get("atVs", ""),
                }
                for i, label in enumerate(labels):
                    row[label] = stats[i] if i < len(stats) else None
                rows.append(row)

    df = pd.DataFrame(rows)
    return df


def get_college_season_totals(athlete_id: str, season: int = 2026) -> dict:
    """Return season totals dict for a college player."""
    espn_season = season if season >= 2026 else season + 1
    url  = f"{BASE_WEB}/sports/basketball/mens-college-basketball/athletes/{athlete_id}/gamelog"
    data = _get(url, params={"season": espn_season})
    if not data:
        return {}
    labels = data.get("labels", GAMELOG_LABELS)
    totals = data.get("totals", [])
    return {labels[i]: totals[i] for i in range(min(len(labels), len(totals)))}


def get_nba_player_gamelog_espn(athlete_id: str, season: int = 2026) -> pd.DataFrame:
    """Fetch per-game stats for an NBA player via ESPN gamelog endpoint."""
    espn_season = season if season >= 2026 else season + 1
    url  = f"{BASE_WEB}/sports/basketball/nba/athletes/{athlete_id}/gamelog"
    data = _get(url, params={"season": espn_season})
    if not data:
        return pd.DataFrame()

    labels      = data.get("labels", GAMELOG_LABELS)
    events_meta = data.get("events", {})
    season_types = data.get("seasonTypes", [])

    rows = []
    for stype in season_types:
        for cat in stype.get("categories", []):
            for ev in cat.get("events", []):
                event_id = ev.get("eventId", "")
                stats    = ev.get("stats", [])
                meta     = events_meta.get(event_id, {})
                row = {
                    "game_date": meta.get("gameDate", "")[:10],
                    "opponent":  meta.get("opponent", {}).get("displayName", ""),
                    "result":    meta.get("gameResult", ""),
                    "location":  meta.get("atVs", ""),
                }
                for i, label in enumerate(labels):
                    row[label] = stats[i] if i < len(stats) else None
                rows.append(row)
    return pd.DataFrame(rows)


def get_athlete_bio(athlete_id: str, league_slug: str = "mens-college-basketball") -> dict:
    """Fetch basic bio info for an athlete via ESPN."""
    url  = f"{BASE_SITE}/sports/basketball/{league_slug}/athletes/{athlete_id}"
    data = _get(url)
    if not data:
        return {}
    ath = data.get("athlete", data)
    return {
        "displayName":  ath.get("displayName", ""),
        "position":     ath.get("position", {}).get("abbreviation", ""),
        "team":         ath.get("team", {}).get("displayName", ""),
        "height":       ath.get("displayHeight", ""),
        "weight":       ath.get("displayWeight", ""),
        "birthDate":    ath.get("dateOfBirth", ""),
        "jersey":       ath.get("jersey", ""),
        "experience":   ath.get("experience", {}).get("displayValue", ""),
        "college":      ath.get("college", {}).get("name", ""),
        "imageUrl":     next((l["href"] for l in ath.get("links", [])
                              if "headshot" in str(l.get("rel", []))), ""),
    }


def parse_stat_float(val) -> float | None:
    """Convert '14-44' → None, '31.8' → 31.8, '0' → 0.0"""
    if val is None:
        return None
    s = str(val).strip()
    if "-" in s and s.count("-") == 1:
        # made-attempted
        parts = s.split("-")
        try:
            m, a = float(parts[0]), float(parts[1])
            return m / a * 100 if a > 0 else 0.0
        except ValueError:
            return None
    try:
        return float(s)
    except ValueError:
        return None


def gamelog_to_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Convert gamelog df string stats to numeric where possible."""
    skip = {"game_date", "opponent", "result", "location", "FG", "3PT", "FT"}
    for col in df.columns:
        if col in skip:
            continue
        df[col] = df[col].apply(parse_stat_float)
    return df
