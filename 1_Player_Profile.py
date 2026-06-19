"""
Module 1 — Player Profile
Endpoints used:
  - PlayerCareerStats         → career totals + per-season
  - PlayerEstimatedMetrics    → E_OFF_RATING, E_DEF_RATING, E_NET_RATING, USG%, etc.
  - PlayerDashboardByClutch   → clutch performance (last 5 min, ≤5 pts)
  - LeagueDashPlayerStats     → MeasureType=Advanced → TS%, eFG%, PIE, POSS
  - PlayerDashboardByShootingSplits → shot quality splits
"""
import time
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from nba_api.stats.static import players
from nba_api.stats.endpoints import (
    playercareerstats,
    playerestimatedmetrics,
    playerdashboardbyclutch,
    leaguedashplayerstats,
    commonplayerinfo,
)

st.set_page_config(page_title="Player Profile | NBA Analytics", page_icon="🎯", layout="wide")

# ── Shared style ─────────────────────────────────────────────────────────────
st.markdown(
    """<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    html,body,[class*="css"]{font-family:'Inter',sans-serif;}
    [data-testid="stSidebar"]{background:linear-gradient(180deg,#0d0d0d,#1a1a2e);}
    [data-testid="stSidebar"] *{color:#e0e0e0!important;}
    .metric-box{background:#16213e;border:1px solid #0f3460;border-radius:10px;padding:1rem;text-align:center;}
    .metric-box h2{color:#e94560;font-size:1.6rem;margin:0;}
    .metric-box p{color:#8a8a9a;font-size:0.7rem;text-transform:uppercase;letter-spacing:.07em;margin:.2rem 0 0;}
    .section-header{color:#e94560;font-size:0.7rem;font-weight:700;text-transform:uppercase;
                    letter-spacing:.12em;margin:1.4rem 0 .4rem;}
    </style>""",
    unsafe_allow_html=True,
)

SEASON = "2025-26"
HEADERS = {
    "Host": "stats.nba.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
    "Referer": "https://stats.nba.com/",
}

# ── Sidebar: player selector ──────────────────────────────────────────────────
st.sidebar.title("🎯 Player Profile")
st.sidebar.markdown("Select any active NBA player.")

@st.cache_data(ttl=86400, show_spinner=False)
def load_active_players():
    return sorted([p for p in players.get_players() if p["is_active"]], key=lambda x: x["full_name"])

active = load_active_players()
names = [p["full_name"] for p in active]
default_idx = names.index("LeBron James") if "LeBron James" in names else 0
selected_name = st.sidebar.selectbox("Player", names, index=default_idx)
player_id = next(p["id"] for p in active if p["full_name"] == selected_name)

st.title(f"🎯 {selected_name}")
st.caption(f"2025–26 Season · Player ID: {player_id}")

# ── Helper: safe API call ────────────────────────────────────────────────────
def fetch(func, **kwargs):
    for attempt in range(3):
        try:
            time.sleep(0.7)
            return func(headers=HEADERS, timeout=60, **kwargs)
        except Exception as e:
            if attempt == 2:
                st.warning(f"Could not load data: {e}")
                return None
            time.sleep(2 ** attempt)

# ── Load data ────────────────────────────────────────────────────────────────
with st.spinner("Loading player data…"):
    career_resp    = fetch(playercareerstats.PlayerCareerStats, player_id=player_id, per_mode36="PerGame")
    est_resp       = fetch(playerestimatedmetrics.PlayerEstimatedMetrics, season=SEASON)
    adv_resp       = fetch(leaguedashplayerstats.LeagueDashPlayerStats, season=SEASON,
                           measure_type_detailed_defense="Advanced", per_mode_detailed="PerGame")
    clutch_resp    = fetch(playerdashboardbyclutch.PlayerDashboardByClutch,
                           player_id=player_id, season=SEASON, per_mode_simple="PerGame")
    info_resp      = fetch(commonplayerinfo.CommonPlayerInfo, player_id=player_id)

# ── Parse data ────────────────────────────────────────────────────────────────
def resp_to_df(resp, dataset_key):
    try:
        ds = resp.get_data_frames()
        if isinstance(dataset_key, int):
            return ds[dataset_key]
        for i, name in enumerate(resp.get_normalized_dict().keys()):
            if name == dataset_key:
                return ds[i]
        return ds[0]
    except Exception:
        return pd.DataFrame()

career_df = resp_to_df(career_resp, 0) if career_resp else pd.DataFrame()
est_df    = resp_to_df(est_resp, 0)    if est_resp    else pd.DataFrame()
adv_df    = resp_to_df(adv_resp, 0)    if adv_resp    else pd.DataFrame()
clutch_df = resp_to_df(clutch_resp, 1) if clutch_resp else pd.DataFrame()
info_df   = resp_to_df(info_resp, 0)   if info_resp   else pd.DataFrame()

# Filter advanced stats to this player
if not adv_df.empty and "PLAYER_ID" in adv_df.columns:
    adv_row = adv_df[adv_df["PLAYER_ID"] == player_id]
else:
    adv_row = pd.DataFrame()

if not est_df.empty and "PLAYER_ID" in est_df.columns:
    est_row = est_df[est_df["PLAYER_ID"] == player_id]
else:
    est_row = pd.DataFrame()

# ── Player info header ────────────────────────────────────────────────────────
if not info_df.empty:
    c1, c2, c3, c4 = st.columns(4)
    info_fields = {
        "Position":      info_df.get("POSITION", pd.Series(["—"])).iloc[0],
        "Team":          info_df.get("TEAM_NAME", pd.Series(["—"])).iloc[0],
        "Height":        info_df.get("HEIGHT",    pd.Series(["—"])).iloc[0],
        "Draft Year":    info_df.get("DRAFT_YEAR",pd.Series(["—"])).iloc[0],
    }
    for col, (label, val) in zip([c1, c2, c3, c4], info_fields.items()):
        col.markdown(f'<div class="metric-box"><h2>{val}</h2><p>{label}</p></div>', unsafe_allow_html=True)

st.markdown("---")

# ── Section 1: Cutting-Edge Advanced Stats ───────────────────────────────────
st.markdown('<p class="section-header">⚡ Advanced Metrics — 2025-26</p>', unsafe_allow_html=True)

adv_metrics = [
    ("TS_PCT",    "True Shooting %",      ".1%"),
    ("EFG_PCT",   "Effective FG %",       ".1%"),
    ("USG_PCT",   "Usage Rate",           ".1%"),
    ("NET_RATING","Net Rating",           "+.1f"),
    ("OFF_RATING","Offensive Rating",     ".1f"),
    ("DEF_RATING","Defensive Rating",     ".1f"),
    ("AST_PCT",   "Assist %",             ".1%"),
    ("REB_PCT",   "Rebound %",            ".1%"),
    ("PIE",       "Player Impact Est.",   ".3f"),
]

if not adv_row.empty:
    cols = st.columns(len(adv_metrics))
    for col, (field, label, fmt) in zip(cols, adv_metrics):
        val = adv_row[field].iloc[0] if field in adv_row.columns else None
        if val is not None and pd.notna(val):
            try:
                display = f"{val:{fmt}}" if fmt else str(val)
            except Exception:
                display = str(val)
        else:
            display = "—"
        col.markdown(f'<div class="metric-box"><h2>{display}</h2><p>{label}</p></div>', unsafe_allow_html=True)
else:
    st.info("Advanced stats unavailable — API may be rate-limiting. Refresh in a moment.")

# ── Section 2: Estimated Ratings (RAPM-adjacent) ─────────────────────────────
st.markdown('<p class="section-header">🧠 Estimated Impact Ratings (RAPTOR-style)</p>', unsafe_allow_html=True)

est_fields = [
    ("E_OFF_RATING", "Est. Off Rating"),
    ("E_DEF_RATING", "Est. Def Rating"),
    ("E_NET_RATING", "Est. Net Rating"),
    ("E_USG_PCT",    "Est. Usage %"),
    ("E_AST_RATIO",  "Est. AST Ratio"),
    ("E_REB_PCT",    "Est. Reb %"),
    ("E_TOV_PCT",    "Est. TOV %"),
    ("E_PACE",       "Est. Pace"),
]
if not est_row.empty:
    cols = st.columns(len(est_fields))
    for col, (field, label) in zip(cols, est_fields):
        val = est_row[field].iloc[0] if field in est_row.columns else None
        display = f"{val:.2f}" if val is not None and pd.notna(val) else "—"
        col.markdown(f'<div class="metric-box"><h2>{display}</h2><p>{label}</p></div>', unsafe_allow_html=True)
else:
    st.info("Estimated metrics unavailable.")

st.markdown("---")

# ── Section 3: Career Season-by-Season chart ─────────────────────────────────
st.markdown('<p class="section-header">📈 Career Scoring Trend (Per Game)</p>', unsafe_allow_html=True)

if not career_df.empty:
    req_cols = {"SEASON_ID", "PTS", "AST", "REB"}
    if req_cols.issubset(career_df.columns):
        reg = career_df[career_df.get("TEAM_ID", pd.Series([0])) != 0].copy() if "TEAM_ID" in career_df.columns else career_df.copy()
        # Drop All-Star / TOT duplicate rows
        if "TEAM_ABBREVIATION" in reg.columns:
            reg = reg[reg["TEAM_ABBREVIATION"] != "TOT"]
        reg = reg.sort_values("SEASON_ID")

        fig = go.Figure()
        for stat, color, name in [("PTS","#e94560","Points"), ("AST","#0f3460","Assists"), ("REB","#16213e","Rebounds")]:
            if stat in reg.columns:
                fig.add_trace(go.Scatter(
                    x=reg["SEASON_ID"], y=reg[stat],
                    mode="lines+markers", name=name,
                    line=dict(color=color, width=2.5),
                    marker=dict(size=6),
                ))
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0d0d0d",
            plot_bgcolor="#0d0d0d",
            height=380,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(title="Season", tickangle=-45),
            yaxis=dict(title="Per Game"),
            margin=dict(l=40, r=20, t=30, b=60),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Career data columns not as expected.")
else:
    st.info("Career data not available.")

# ── Section 4: Clutch Stats ───────────────────────────────────────────────────
st.markdown('<p class="section-header">🔥 Clutch Performance (Last 5 min, ≤5 pts)</p>', unsafe_allow_html=True)

if not clutch_df.empty:
    clutch_show = ["GROUP_VALUE","GP","W","L","W_PCT","MIN","PTS","AST","REB","FG_PCT","FG3_PCT","PLUS_MINUS"]
    cols_present = [c for c in clutch_show if c in clutch_df.columns]
    st.dataframe(
        clutch_df[cols_present].rename(columns={
            "GROUP_VALUE":"Clutch Bucket","GP":"GP","W":"W","L":"L","W_PCT":"W%",
            "MIN":"MIN","PTS":"PTS","AST":"AST","REB":"REB",
            "FG_PCT":"FG%","FG3_PCT":"3P%","PLUS_MINUS":"+/-",
        }),
        use_container_width=True, hide_index=True,
    )
else:
    st.info("Clutch data not available.")

st.markdown("---")
st.caption("Data via NBA Stats API · Season 2025-26 · Cached 1 hr")
