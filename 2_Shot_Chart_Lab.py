"""
Module 2 — Shot Chart Lab
Endpoints used:
  - ShotChartDetail  → LOC_X, LOC_Y, SHOT_MADE_FLAG, SHOT_ZONE_BASIC, ACTION_TYPE
  - PlayerDashPtShots → dribble shooting, touch time, closest defender distance
"""
import time
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from matplotlib.patches import Circle, Rectangle, Arc
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from io import BytesIO

from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import shotchartdetail, playerdashptshots

st.set_page_config(page_title="Shot Chart Lab | NBA Analytics", page_icon="🗺️", layout="wide")

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0d0d0d,#1a1a2e);}
[data-testid="stSidebar"] *{color:#e0e0e0!important;}
.metric-box{background:#16213e;border:1px solid #0f3460;border-radius:10px;padding:1rem;text-align:center;}
.metric-box h2{color:#e94560;font-size:1.6rem;margin:0;}
.metric-box p{color:#8a8a9a;font-size:0.7rem;text-transform:uppercase;letter-spacing:.07em;margin:.2rem 0 0;}
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

@st.cache_data(ttl=86400, show_spinner=False)
def load_active_players():
    return sorted([p for p in players.get_players() if p["is_active"]], key=lambda x: x["full_name"])

@st.cache_data(ttl=86400, show_spinner=False)
def load_teams():
    return sorted(teams.get_teams(), key=lambda x: x["full_name"])

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
st.sidebar.title("🗺️ Shot Chart Lab")
active = load_active_players()
names = [p["full_name"] for p in active]
default_idx = names.index("Stephen Curry") if "Stephen Curry" in names else 0
selected_name = st.sidebar.selectbox("Player", names, index=default_idx)
player_id = next(p["id"] for p in active if p["full_name"] == selected_name)

season_type = st.sidebar.selectbox("Season Type", ["Regular Season", "Playoffs"], index=0)
chart_type  = st.sidebar.selectbox("Chart Style", ["Scatter (Hex)", "Hexbin", "Zone Efficiency"], index=0)

st.title(f"🗺️ Shot Chart — {selected_name}")
st.caption(f"2025–26 Season · {season_type}")

# ── Load shot data ─────────────────────────────────────────────────────────────
with st.spinner("Fetching shot locations…"):
    all_teams = load_teams()
    resp = fetch(
        shotchartdetail.ShotChartDetail,
        team_id=0,
        player_id=player_id,
        season_nullable=SEASON,
        season_type_all_star=season_type,
        context_measure_simple="FGA",
    )

if resp is None:
    st.error("Could not load shot data. Try again in a moment.")
    st.stop()

try:
    df = resp.get_data_frames()[0]
except Exception as e:
    st.error(f"Parse error: {e}")
    st.stop()

if df.empty:
    st.warning("No shot data found for this player/season combo.")
    st.stop()

# ── KPIs ─────────────────────────────────────────────────────────────────────
made   = df["SHOT_MADE_FLAG"].sum()
total  = len(df)
fg_pct = made / total if total > 0 else 0

three_df  = df[df["SHOT_TYPE"] == "3PT Field Goal"]
three_pct = three_df["SHOT_MADE_FLAG"].mean() if not three_df.empty else 0

paint_df  = df[df["SHOT_ZONE_BASIC"] == "In The Paint (Non-RA)"]
ra_df     = df[df["SHOT_ZONE_BASIC"] == "Restricted Area"]

c1,c2,c3,c4,c5 = st.columns(5)
for col, (val,label) in zip(
    [c1,c2,c3,c4,c5],
    [(total,"Total FGA"),(made,"FGM"),(f"{fg_pct:.1%}","FG%"),
     (len(three_df),"3PA"),(f"{three_pct:.1%}","3P%")]
):
    col.markdown(f'<div class="metric-box"><h2>{val}</h2><p>{label}</p></div>', unsafe_allow_html=True)

st.markdown("---")

# ── Draw court + scatter ───────────────────────────────────────────────────────
def draw_court(ax, color="#ffffff", lw=1.5, outer_lines=False):
    """Draw half-court lines (NBA scale: 1 unit ≈ 1 foot × 10)."""
    hoop = Circle((0, 0), radius=7.5, linewidth=lw, color=color, fill=False)
    backboard = Rectangle((-30, -7.5), 60, -1, linewidth=lw, color=color)
    outer_box = Rectangle((-80, -47.5), 160, 190, linewidth=lw, color=color, fill=False)
    inner_box = Rectangle((-60, -47.5), 120, 190, linewidth=lw, color=color, fill=False)
    top_free_throw = Arc((0, 142.5), 120, 120, theta1=0, theta2=180, linewidth=lw, color=color)
    bottom_free_throw = Arc((0, 142.5), 120, 120, theta1=180, theta2=0, linewidth=lw, color=color, linestyle="dashed")
    restricted = Arc((0, 0), 80, 80, theta1=0, theta2=180, linewidth=lw, color=color)
    corner_three_a = Rectangle((-220, -47.5), 0, 140, linewidth=lw, color=color)
    corner_three_b = Rectangle((220, -47.5), 0, 140, linewidth=lw, color=color)
    three_arc = Arc((0, 0), 475, 475, theta1=22, theta2=158, linewidth=lw, color=color)
    center_outer = Arc((0, 422.5), 120, 120, theta1=180, theta2=0, linewidth=lw, color=color)
    for element in [hoop, backboard, outer_box, inner_box, top_free_throw, bottom_free_throw,
                    restricted, corner_three_a, corner_three_b, three_arc, center_outer]:
        ax.add_patch(element)
    if outer_lines:
        outer = Rectangle((-250, -47.5), 500, 470, linewidth=lw, color=color, fill=False)
        ax.add_patch(outer)
    return ax

fig, ax = plt.subplots(figsize=(10, 9.4))
ax.set_facecolor("#0d0d0d")
fig.patch.set_facecolor("#0d0d0d")

made_mask   = df["SHOT_MADE_FLAG"] == 1
missed_mask = df["SHOT_MADE_FLAG"] == 0

if chart_type == "Hexbin":
    hb = ax.hexbin(df["LOC_X"], df["LOC_Y"], gridsize=25, cmap="YlOrRd",
                   extent=(-250, 250, -47.5, 422.5), mincnt=1, alpha=0.85)
    plt.colorbar(hb, ax=ax, label="Shots", pad=0.01)
    ax.scatter([], [], label="Shots (density)", alpha=0)
elif chart_type == "Zone Efficiency":
    # Color by zone FG%
    zone_eff = df.groupby("SHOT_ZONE_BASIC")["SHOT_MADE_FLAG"].agg(["sum","count"])
    zone_eff["pct"] = zone_eff["sum"] / zone_eff["count"]
    zone_color_map = {z: pct for z, pct in zip(zone_eff.index, zone_eff["pct"])}
    df["zone_pct"] = df["SHOT_ZONE_BASIC"].map(zone_color_map).fillna(0)
    sc = ax.scatter(df.loc[made_mask,"LOC_X"], df.loc[made_mask,"LOC_Y"],
                    c=df.loc[made_mask,"zone_pct"], cmap="RdYlGn",
                    vmin=0.3, vmax=0.7, s=14, alpha=0.85, marker="o", zorder=3)
    ax.scatter(df.loc[missed_mask,"LOC_X"], df.loc[missed_mask,"LOC_Y"],
               c="#555555", s=10, alpha=0.4, marker="x", zorder=2)
    plt.colorbar(sc, ax=ax, label="Zone FG%", pad=0.01)
else:  # Scatter hex default
    ax.scatter(df.loc[made_mask,"LOC_X"],   df.loc[made_mask,"LOC_Y"],
               c="#e94560", s=12, alpha=0.7, marker="o", label="Made", zorder=3)
    ax.scatter(df.loc[missed_mask,"LOC_X"], df.loc[missed_mask,"LOC_Y"],
               c="#555555", s=10, alpha=0.5, marker="x", label="Missed", zorder=2)
    ax.legend(loc="upper right", facecolor="#0d0d0d", labelcolor="white", fontsize=8)

draw_court(ax, color="#444444", lw=1.5, outer_lines=True)
ax.set_xlim(-260, 260)
ax.set_ylim(-60, 440)
ax.set_title(f"{selected_name} — Shot Chart 2025-26", color="white", fontsize=13, fontweight="bold", pad=10)
ax.axis("off")

buf = BytesIO()
fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
buf.seek(0)
st.image(buf, use_column_width=True)
plt.close(fig)

# ── Zone breakdown table ──────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Shot Zone Breakdown")

zone_df = (
    df.groupby("SHOT_ZONE_BASIC")["SHOT_MADE_FLAG"]
    .agg(FGM="sum", FGA="count")
    .assign(FG_PCT=lambda d: (d["FGM"] / d["FGA"]).map("{:.1%}".format))
    .sort_values("FGA", ascending=False)
    .reset_index()
    .rename(columns={"SHOT_ZONE_BASIC": "Zone"})
)
st.dataframe(zone_df, use_container_width=True, hide_index=True)

# ── Shot quality: dribbles / defender distance ────────────────────────────────
st.markdown("---")
st.subheader("Shooting Profile — Touch Type & Defender Distance")

with st.spinner("Loading shot quality data…"):
    pt_resp = fetch(playerdashptshots.PlayerDashPtShots, player_id=player_id, season=SEASON)

if pt_resp:
    try:
        dfs = pt_resp.get_data_frames()
        # index 0 = ClosestDefender10ft+, 1 = ClosestDefender, 2 = DribbleShooting, 3 = GeneralShooting, 4 = ShotClockShooting, 5 = TouchTimeShooting
        tab1, tab2, tab3 = st.tabs(["Dribble Shooting", "Touch Time", "Shot Clock"])
        dribble_df = dfs[2] if len(dfs) > 2 else pd.DataFrame()
        touch_df   = dfs[5] if len(dfs) > 5 else pd.DataFrame()
        clock_df   = dfs[4] if len(dfs) > 4 else pd.DataFrame()

        def clean_pt(d, label_col):
            cols = [label_col,"FGA","FGM","FG_PCT","FG3A","FG3M","FG3_PCT","EFG_PCT","FGA_FREQUENCY"]
            present = [c for c in cols if c in d.columns]
            return d[present]

        with tab1:
            if not dribble_df.empty:
                st.dataframe(clean_pt(dribble_df, "DRIBBLE_RANGE"), use_container_width=True, hide_index=True)
        with tab2:
            if not touch_df.empty:
                st.dataframe(clean_pt(touch_df, "TOUCH_TIME_RANGE"), use_container_width=True, hide_index=True)
        with tab3:
            if not clock_df.empty:
                st.dataframe(clean_pt(clock_df, "SHOT_CLOCK_RANGE"), use_container_width=True, hide_index=True)
    except Exception as e:
        st.info(f"Shot quality data unavailable: {e}")

st.caption("Data via NBA Stats API · Season 2025-26")
