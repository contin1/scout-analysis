"""
Module 4 — League Leaderboard
Endpoints used:
  - LeagueDashPlayerStats (MeasureType=Base)      → traditional stats
  - LeagueDashPlayerStats (MeasureType=Advanced)  → TS%, eFG%, USG%, NET_RATING, PIE
  - LeagueDashPlayerStats (MeasureType=Misc)      → PTS_OFF_TOV, PTS_2ND_CHANCE, FBPS, etc.
  - LeagueDashPlayerStats (MeasureType=Scoring)   → PCT_FGA by shot type
  - LeagueDashPlayerClutch                        → clutch leaders
"""
import time
import pandas as pd
import streamlit as st
import plotly.express as px

from nba_api.stats.endpoints import leaguedashplayerstats, leaguedashplayerclutch

st.set_page_config(page_title="League Leaderboard | NBA Analytics", page_icon="📊", layout="wide")

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0d0d0d,#1a1a2e);}
[data-testid="stSidebar"] *{color:#e0e0e0!important;}
</style>""", unsafe_allow_html=True)

SEASON = "2025-26"
HEADERS = {
    "Host": "stats.nba.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
    "Referer": "https://stats.nba.com/",
}

def fetch(func, **kwargs):
    for attempt in range(3):
        try:
            time.sleep(0.7)
            return func(headers=HEADERS, timeout=60, **kwargs)
        except Exception as e:
            if attempt == 2:
                return None
            time.sleep(2 ** attempt)

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("📊 League Leaderboard")
stat_mode = st.sidebar.selectbox(
    "Stat Category",
    ["Base (Traditional)", "Advanced", "Misc (Secondary Scoring)", "Scoring (Shot Zones)", "Clutch"],
    index=1,
)
per_mode = st.sidebar.selectbox("Per Mode", ["PerGame","Per36","Totals"], index=0)
min_gp   = st.sidebar.slider("Min Games Played", 1, 50, 20)
top_n    = st.sidebar.slider("Rows to Display", 10, 100, 25)
position_filter = st.sidebar.selectbox("Position Filter", ["All","G","F","C"], index=0)
season_type = st.sidebar.selectbox("Season Type", ["Regular Season","Playoffs"], index=0)

st.title("📊 League Leaderboard — 2025-26")

# ── Stat mode config ──────────────────────────────────────────────────────────
MODE_CONFIG = {
    "Base (Traditional)": {
        "measure_type": "Base",
        "cols": ["PLAYER_NAME","TEAM_ABBREVIATION","GP","MIN","PTS","AST","REB","STL","BLK","TOV","FG_PCT","FG3_PCT","FT_PCT","PLUS_MINUS"],
        "default_sort": "PTS",
        "sort_asc": False,
    },
    "Advanced": {
        "measure_type": "Advanced",
        "cols": ["PLAYER_NAME","TEAM_ABBREVIATION","GP","MIN",
                 "OFF_RATING","DEF_RATING","NET_RATING",
                 "TS_PCT","EFG_PCT","USG_PCT",
                 "AST_PCT","REB_PCT","AST_TO","TO_PCT","PIE"],
        "default_sort": "NET_RATING",
        "sort_asc": False,
    },
    "Misc (Secondary Scoring)": {
        "measure_type": "Misc",
        "cols": ["PLAYER_NAME","TEAM_ABBREVIATION","GP","MIN",
                 "PTS_OFF_TOV","PTS_2ND_CHANCE","PTS_FB","PTS_PAINT",
                 "OPP_PTS_OFF_TOV","OPP_PTS_2ND_CHANCE","OPP_PTS_FB","OPP_PTS_PAINT"],
        "default_sort": "PTS_PAINT",
        "sort_asc": False,
    },
    "Scoring (Shot Zones)": {
        "measure_type": "Scoring",
        "cols": ["PLAYER_NAME","TEAM_ABBREVIATION","GP","PCT_FGA_2PT","PCT_FGA_3PT",
                 "PCT_PTS_2PT","PCT_PTS_3PT","PCT_PTS_FT","PCT_PTS_PAINT",
                 "PCT_PTS_MID_RANGE","PCT_PTS_OFF_TOV","PCT_AST_2PM","PCT_UAST_2PM",
                 "PCT_AST_3PM","PCT_UAST_3PM"],
        "default_sort": "PCT_PTS_3PT",
        "sort_asc": False,
    },
    "Clutch": {
        "measure_type": "Clutch",
        "cols": None,  # handled separately
        "default_sort": "PTS",
        "sort_asc": False,
    },
}

config = MODE_CONFIG[stat_mode]

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def load_league(measure_type, per_mode, season_type):
    if measure_type == "Clutch":
        r = fetch(leaguedashplayerclutch.LeagueDashPlayerClutch,
                  season=SEASON, per_mode_simple=per_mode,
                  season_type_all_star=season_type)
    else:
        r = fetch(leaguedashplayerstats.LeagueDashPlayerStats,
                  season=SEASON,
                  measure_type_detailed_defense=measure_type,
                  per_mode_detailed=per_mode,
                  season_type_all_star=season_type)
    if r:
        try:
            return r.get_data_frames()[0]
        except Exception:
            pass
    return pd.DataFrame()

with st.spinner(f"Loading {stat_mode} data…"):
    df = load_league(config["measure_type"], per_mode, season_type)

if df.empty:
    st.warning("Data unavailable — try again in a moment.")
    st.stop()

# ── Filter ────────────────────────────────────────────────────────────────────
if "GP" in df.columns:
    df = df[df["GP"] >= min_gp]

if position_filter != "All" and "PLAYER_POSITION" in df.columns:
    df = df[df["PLAYER_POSITION"].str.contains(position_filter, na=False)]

# ── Column selection ──────────────────────────────────────────────────────────
if config["cols"]:
    display_cols = [c for c in config["cols"] if c in df.columns]
else:
    priority = ["PLAYER_NAME","TEAM_ABBREVIATION","GP","MIN","PTS","AST","REB","STL","BLK","FG_PCT","FG3_PCT","PLUS_MINUS"]
    display_cols = [c for c in priority if c in df.columns]

sort_col = config["default_sort"] if config["default_sort"] in df.columns else display_cols[-1]
sort_col = st.selectbox("Sort By", [c for c in display_cols if c not in ["PLAYER_NAME","TEAM_ABBREVIATION"]], index=0)

df_sorted = df[display_cols].sort_values(sort_col, ascending=config["sort_asc"]).head(top_n).reset_index(drop=True)
df_sorted.index += 1  # rank starting from 1

# ── Bar chart: top 15 ─────────────────────────────────────────────────────────
top15 = df_sorted.head(15)
if "PLAYER_NAME" in top15.columns and sort_col in top15.columns:
    fig = px.bar(
        top15.sort_values(sort_col),
        x=sort_col, y="PLAYER_NAME",
        orientation="h",
        color=sort_col,
        color_continuous_scale="Reds",
        template="plotly_dark",
        title=f"Top 15 — {sort_col} ({per_mode} | {stat_mode})",
        text=sort_col,
    )
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    fig.update_layout(
        paper_bgcolor="#0d0d0d", plot_bgcolor="#0d0d0d",
        showlegend=False, height=420,
        yaxis=dict(autorange="reversed"),
        coloraxis_showscale=False,
        margin=dict(l=10, r=80, t=40, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Full sortable table ────────────────────────────────────────────────────────
st.subheader(f"Full Leaderboard — {stat_mode}")
# Format PCT columns
pct_cols = [c for c in df_sorted.columns if "_PCT" in c or c.startswith("PCT_")]
styled = df_sorted.copy()
for c in pct_cols:
    if styled[c].dtype in ["float64","float32"]:
        styled[c] = styled[c].map(lambda v: f"{v:.1%}" if pd.notna(v) else "—")

st.dataframe(styled, use_container_width=True)

# ── Scatter: Usage vs Efficiency ────────────────────────────────────────────────
if stat_mode == "Advanced" and "USG_PCT" in df.columns and "NET_RATING" in df.columns:
    st.markdown("---")
    st.subheader("Usage % vs Net Rating")
    scatter_df = df[["PLAYER_NAME","TEAM_ABBREVIATION","USG_PCT","NET_RATING","TS_PCT","GP"]].dropna()
    scatter_df = scatter_df[scatter_df["GP"] >= min_gp]
    fig2 = px.scatter(
        scatter_df,
        x="USG_PCT", y="NET_RATING",
        color="TS_PCT", size="GP",
        hover_name="PLAYER_NAME",
        hover_data=["TEAM_ABBREVIATION","TS_PCT","GP"],
        color_continuous_scale="RdYlGn",
        labels={"USG_PCT":"Usage %","NET_RATING":"Net Rating","TS_PCT":"True Shooting %"},
        template="plotly_dark",
        title="Usage Rate vs Net Rating (bubble size = games played, color = TS%)",
    )
    fig2.update_layout(
        paper_bgcolor="#0d0d0d", plot_bgcolor="#0d0d0d",
        height=480,
        margin=dict(l=40, r=20, t=50, b=40),
    )
    fig2.add_hline(y=0, line_dash="dash", line_color="#555", annotation_text="League avg net rating ≈ 0")
    st.plotly_chart(fig2, use_container_width=True)

st.caption("Data via NBA Stats API · Season 2025-26 · Cached 1 hr")
