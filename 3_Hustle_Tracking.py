"""
Module 3 — Hustle & Tracking Stats
Endpoints used:
  - LeagueHustleStatsPlayer → contested shots, deflections, charges drawn, screen assists, box-outs
  - LeagueDashPtStats (PlayerOrTeam=Player, PtMeasureType=SpeedDistance) → speed / distance
  - LeagueDashPtStats (PlayerOrTeam=Player, PtMeasureType=Hustle) → hustle
"""
import time
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from nba_api.stats.static import players
from nba_api.stats.endpoints import leaguehustlestatsplayer, leaguedashptstats

st.set_page_config(page_title="Hustle & Tracking | NBA Analytics", page_icon="💪", layout="wide")

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0d0d0d,#1a1a2e);}
[data-testid="stSidebar"] *{color:#e0e0e0!important;}
.metric-box{background:#16213e;border:1px solid #0f3460;border-radius:10px;padding:1rem;text-align:center;}
.metric-box h2{color:#e94560;font-size:1.6rem;margin:0;}
.metric-box p{color:#8a8a9a;font-size:0.7rem;text-transform:uppercase;letter-spacing:.07em;margin:.2rem 0 0;}
.section-header{color:#e94560;font-size:0.7rem;font-weight:700;text-transform:uppercase;
                letter-spacing:.12em;margin:1.4rem 0 .4rem;}
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

@st.cache_data(ttl=86400, show_spinner=False)
def load_active_players():
    return sorted([p for p in players.get_players() if p["is_active"]], key=lambda x: x["full_name"])

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("💪 Hustle & Tracking")
active = load_active_players()
names = [p["full_name"] for p in active]

view_mode = st.sidebar.radio("View Mode", ["Single Player Deep Dive", "League Leaders"])
selected_name = st.sidebar.selectbox("Player (for deep dive)", names,
                                     index=names.index("Draymond Green") if "Draymond Green" in names else 0)
player_id = next(p["id"] for p in active if p["full_name"] == selected_name)
top_n = st.sidebar.slider("League Leaders — Show Top N", 5, 30, 15)

st.title("💪 Hustle & Tracking Stats — 2025-26")
st.caption("The stats the box score ignores.")

# ── Load hustle data ─────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def load_hustle():
    r = fetch(leaguehustlestatsplayer.LeagueHustleStatsPlayer, season=SEASON, season_type_all_star="Regular Season")
    if r:
        try:
            return r.get_data_frames()[0]
        except Exception:
            pass
    return pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner=False)
def load_speed():
    r = fetch(leaguedashptstats.LeagueDashPtStats,
              season=SEASON, pt_measure_type="SpeedDistance",
              player_or_team="Player", per_mode_simple="PerGame")
    if r:
        try:
            return r.get_data_frames()[0]
        except Exception:
            pass
    return pd.DataFrame()

with st.spinner("Loading hustle + tracking data…"):
    hustle_df = load_hustle()
    speed_df  = load_speed()

if hustle_df.empty:
    st.warning("Hustle data unavailable. NBA API may be rate-limiting — refresh in 30 seconds.")
    st.stop()

# ── Normalize per-game ─────────────────────────────────────────────────────────
per_game_cols = [
    "CONTESTED_SHOTS","CONTESTED_SHOTS_2PT","CONTESTED_SHOTS_3PT",
    "DEFLECTIONS","CHARGES_DRAWN","SCREEN_ASSISTS","SCREEN_AST_PTS",
    "LOOSE_BALLS_RECOVERED","BOX_OUTS",
]
hustle_pg = hustle_df.copy()
for col in per_game_cols:
    if col in hustle_pg.columns and "G" in hustle_pg.columns:
        hustle_pg[col + "_PG"] = hustle_pg[col] / hustle_pg["G"].replace(0, 1)

# ── View: Single Player Deep Dive ────────────────────────────────────────────
if view_mode == "Single Player Deep Dive":
    st.subheader(f"🔍 {selected_name} — Hustle Profile")
    row = hustle_df[hustle_df["PLAYER_ID"] == player_id]

    if row.empty:
        st.info("No hustle data for this player (may not have enough games played).")
    else:
        r = row.iloc[0]
        games = r.get("G", 1) or 1

        metrics = [
            ("CONTESTED_SHOTS",    "Contested Shots/G"),
            ("DEFLECTIONS",        "Deflections/G"),
            ("CHARGES_DRAWN",      "Charges Drawn/G"),
            ("SCREEN_ASSISTS",     "Screen Assists/G"),
            ("SCREEN_AST_PTS",     "Screen Ast Pts/G"),
            ("LOOSE_BALLS_RECOVERED","Loose Balls Rec/G"),
            ("BOX_OUTS",           "Box Outs/G"),
        ]
        cols = st.columns(len(metrics))
        for col, (field, label) in zip(cols, metrics):
            val = r.get(field, None)
            if val is not None and pd.notna(val):
                pg = val / games
                display = f"{pg:.1f}"
            else:
                display = "—"
            col.markdown(f'<div class="metric-box"><h2>{display}</h2><p>{label}</p></div>', unsafe_allow_html=True)

        # Radar chart — compare vs league average
        st.markdown('<p class="section-header">📡 Hustle Radar vs League Average</p>', unsafe_allow_html=True)

        radar_fields = ["CONTESTED_SHOTS","DEFLECTIONS","CHARGES_DRAWN",
                        "SCREEN_ASSISTS","LOOSE_BALLS_RECOVERED","BOX_OUTS"]
        radar_labels = ["Contested\nShots","Deflections","Charges\nDrawn",
                        "Screen\nAssists","Loose Balls\nRec","Box\nOuts"]
        rf = [f for f in radar_fields if f in hustle_df.columns]

        if rf:
            league_avg = hustle_df[rf].mean()
            player_vals = [r.get(f, 0) / games for f in rf]
            league_vals = [(league_avg[f] / hustle_df["G"].mean()) if hustle_df["G"].mean() > 0 else 0 for f in rf]

            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(
                r=player_vals + [player_vals[0]],
                theta=radar_labels + [radar_labels[0]],
                fill="toself", name=selected_name,
                line=dict(color="#e94560"), fillcolor="rgba(233,69,96,0.2)",
            ))
            fig.add_trace(go.Scatterpolar(
                r=league_vals + [league_vals[0]],
                theta=radar_labels + [radar_labels[0]],
                fill="toself", name="League Avg",
                line=dict(color="#0f3460", dash="dash"), fillcolor="rgba(15,52,96,0.2)",
            ))
            fig.update_layout(
                polar=dict(bgcolor="#0d0d0d",
                           radialaxis=dict(visible=True, color="#555"),
                           angularaxis=dict(color="#aaa")),
                template="plotly_dark", paper_bgcolor="#0d0d0d",
                showlegend=True, height=420,
                legend=dict(orientation="h", yanchor="bottom", y=1.05),
                margin=dict(l=60, r=60, t=40, b=40),
            )
            st.plotly_chart(fig, use_container_width=True)

    # Speed/distance for player
    if not speed_df.empty and "PLAYER_ID" in speed_df.columns:
        sp_row = speed_df[speed_df["PLAYER_ID"] == player_id]
        if not sp_row.empty:
            st.markdown('<p class="section-header">🏃 Speed & Distance (Per Game)</p>', unsafe_allow_html=True)
            sp = sp_row.iloc[0]
            sp_metrics = [
                ("DIST_MILES",     "Miles/Game"),
                ("DIST_MILES_OFF", "Miles Off/Game"),
                ("DIST_MILES_DEF", "Miles Def/Game"),
                ("AVG_SPEED",      "Avg Speed (mph)"),
                ("AVG_SPEED_OFF",  "Avg Off Speed"),
                ("AVG_SPEED_DEF",  "Avg Def Speed"),
            ]
            sp_cols = st.columns(len(sp_metrics))
            for col, (field, label) in zip(sp_cols, sp_metrics):
                val = sp.get(field, None)
                display = f"{val:.2f}" if val is not None and pd.notna(val) else "—"
                col.markdown(f'<div class="metric-box"><h2>{display}</h2><p>{label}</p></div>', unsafe_allow_html=True)

# ── View: League Leaders ──────────────────────────────────────────────────────
else:
    st.subheader("🏆 League Hustle Leaders")

    hustle_stat = st.selectbox(
        "Rank by",
        [
            ("DEFLECTIONS",     "Deflections"),
            ("CONTESTED_SHOTS", "Contested Shots"),
            ("CHARGES_DRAWN",   "Charges Drawn"),
            ("SCREEN_ASSISTS",  "Screen Assists"),
            ("SCREEN_AST_PTS",  "Screen Assist Points"),
            ("BOX_OUTS",        "Box Outs"),
            ("LOOSE_BALLS_RECOVERED", "Loose Balls Recovered"),
        ],
        format_func=lambda x: x[1],
        index=0,
    )
    stat_field, stat_label = hustle_stat

    if stat_field in hustle_df.columns and "G" in hustle_df.columns:
        hustle_df["_STAT_PG"] = hustle_df[stat_field] / hustle_df["G"].replace(0, 1)
        top = hustle_df.nlargest(top_n, "_STAT_PG")[["PLAYER_NAME","TEAM_ABBREVIATION","G","MIN",stat_field,"_STAT_PG"]]
        top = top.rename(columns={
            "PLAYER_NAME":"Player","TEAM_ABBREVIATION":"Team","G":"GP","MIN":"MPG",
            stat_field: f"Total {stat_label}", "_STAT_PG": f"{stat_label}/Game",
        })

        fig = px.bar(
            top.sort_values(f"{stat_label}/Game"),
            x=f"{stat_label}/Game", y="Player",
            orientation="h", color=f"{stat_label}/Game",
            color_continuous_scale="Reds",
            template="plotly_dark",
            title=f"Top {top_n} — {stat_label} Per Game (2025-26)",
        )
        fig.update_layout(
            paper_bgcolor="#0d0d0d", plot_bgcolor="#0d0d0d",
            showlegend=False, height=max(350, top_n * 28),
            yaxis=dict(autorange="reversed"),
            coloraxis_showscale=False,
            margin=dict(l=10, r=20, t=40, b=20),
        )
        fig.update_traces(hovertemplate="%{y}: %{x:.2f}")
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(top.reset_index(drop=True), use_container_width=True, hide_index=True)

st.caption("Data via NBA Stats API · Season 2025-26 · Cached 1 hr")
