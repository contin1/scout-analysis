"""
NBA API helper utilities — caching, rate limiting, error handling.
"""
import time
import streamlit as st
from nba_api.stats.static import players, teams


SEASON = "2025-26"
HEADERS = {
    "Host": "stats.nba.com",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
    "Connection": "keep-alive",
    "Referer": "https://stats.nba.com/",
    "Origin": "https://www.nba.com",
}
TIMEOUT = 60


@st.cache_data(ttl=3600, show_spinner=False)
def get_all_players_2026():
    """Return active players list."""
    all_players = players.get_players()
    active = [p for p in all_players if p["is_active"]]
    return sorted(active, key=lambda x: x["full_name"])


@st.cache_data(ttl=3600, show_spinner=False)
def get_all_teams():
    return sorted(teams.get_teams(), key=lambda x: x["full_name"])


def player_name_to_id(name: str) -> int | None:
    plist = get_all_players_2026()
    for p in plist:
        if p["full_name"].lower() == name.lower():
            return p["id"]
    return None


def safe_fetch(func, *args, **kwargs):
    """Wrap API call with retry + rate limit handling."""
    for attempt in range(3):
        try:
            time.sleep(0.6)
            return func(*args, **kwargs)
        except Exception as e:
            if attempt == 2:
                st.error(f"API error after 3 attempts: {e}")
                return None
            time.sleep(2 ** attempt)
    return None
