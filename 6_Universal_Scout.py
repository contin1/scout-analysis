"""
Module 6 — Universal Player Scout
Covers: NBA · College (NCAA Men's) · High School (via MaxPreps/ESPN ecosystem)

Data sources:
  NBA    → nba_api: PlayerCareerStats, LeagueDashPlayerStats(Advanced),
            ShotChartDetail, PlayerEstimatedMetrics, PlayerDashPtShots
  College → ESPN undocumented API: athlete gamelog + season totals
  HS      → MaxPreps via ESPN athlete search + direct page parse fallback

Stats surfaced per level:
  ✓ PPG, RPG, APG, SPG, BPG, TPG
  ✓ FG%, 3P%, FT%, eFG%/TS% (where available)
  ✓ Shot chart (NBA level — LOC_X/LOC_Y)
  ✓ Per-game game log with trend charts
  ✓ Career season-by-season timeline
"""
import time
import sys
import os
import requests
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from io import BytesIO
import streamlit as st

# ── Path setup ─────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.espn_helpers import (
    search_player, get_college_gamelog, get_college_season_totals,
    get_nba_player_gamelog_espn, get_athlete_bio, gamelog_to_numeric, parse_stat_float,
)

from nba_api.stats.static import players as nba_players_static
from nba_api.stats.endpoints import (
    playercareerstats, shotchartdetail, playerestimatedmetrics,
    leaguedashplayerstats, playerdashptshots,
)

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Universal Scout | NBA Analytics",
    page_icon="🔍",
    layout="wide",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0d0d0d,#1a1a2e);}
[data-testid="stSidebar"] *{color:#e0e0e0!important;}
.level-badge{display:inline-block;padding:.25rem .7rem;border-radius:20px;font-size:.7rem;
             font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:1rem;}
.nba-badge  {background:#e94560;color:#fff;}
.ncaa-badge {background:#0f3460;color:#fff;}
.hs-badge   {background:#533483;color:#fff;}
.metric-box{background:#16213e;border:1px solid #0f3460;border-radius:10px;padding:1rem;text-align:center;}
.metric-box h2{color:#e94560;font-size:1.5rem;margin:0;}
.metric-box p{color:#8a8a9a;font-size:.68rem;text-transform:uppercase;letter-spacing:.07em;margin:.2rem 0 0;}
.section-header{color:#e94560;font-size:.68rem;font-weight:700;text-transform:uppercase;
                letter-spacing:.12em;margin:1.4rem 0 .4rem;}
.player-card{background:linear-gradient(135deg,#1a1a2e,#16213e);
             border:1px solid #0f3460;border-radius:12px;padding:1.5rem;margin-bottom:1rem;}
.info-row{display:flex;gap:2rem;flex-wrap:wrap;margin:.5rem 0;}
.info-item{color:#8a8a9a;font-size:.82rem;}
.info-item span{color:#fff;font-weight:600;}
</style>
""", unsafe_allow_html=True)

NBA_HEADERS = {
    "Host": "stats.nba.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
    "Referer": "https://stats.nba.com/",
}
SEASON = "2025-26"

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
st.sidebar.title("🔍 Universal Scout")
st.sidebar.markdown("Search any NBA, college, or high school player.")

search_query  = st.sidebar.text_input("Player Name", placeholder="e.g. LeBron James, Cooper Flagg, AJ Dybantsa")
level_hint    = st.sidebar.selectbox("Level", ["Auto-detect", "NBA", "College (NCAA)", "High School"], index=0)
college_season = st.sidebar.selectbox("College Season (if applicable)", [2026, 2025, 2024, 2023, 2022], index=0,
                                      help="ESPN year-end convention: 2026 = 2025-26 season")
nba_season    = st.sidebar.selectbox("NBA Season (if applicable)", ["2025-26","2024-25","2023-24","2022-23"], index=0)

# ─────────────────────────────────────────────────────────────────────────────
# NBA helpers
# ─────────────────────────────────────────────────────────────────────────────
def nba_fetch(func, **kwargs):
    for attempt in range(3):
        try:
            time.sleep(0.7)
            return func(headers=NBA_HEADERS, timeout=60, **kwargs)
        except Exception:
            if attempt == 2:
                return None
            time.sleep(2 ** attempt)

@st.cache_data(ttl=86400, show_spinner=False)
def get_nba_active():
    return {p["full_name"].lower(): p for p in nba_players_static.get_players() if p["is_active"]}

# ─────────────────────────────────────────────────────────────────────────────
# Court drawing
# ─────────────────────────────────────────────────────────────────────────────
def draw_court(ax, color="#444444"):
    from matplotlib.patches import Circle, Rectangle, Arc
    for patch in [
        Circle((0,0), 7.5, lw=1.5, color=color, fill=False),
        Rectangle((-30,-7.5), 60, -1, lw=1.5, color=color),
        Rectangle((-80,-47.5), 160, 190, lw=1.5, color=color, fill=False),
        Rectangle((-60,-47.5), 120, 190, lw=1.5, color=color, fill=False),
        Arc((0,142.5), 120, 120, theta1=0, theta2=180, lw=1.5, color=color),
        Arc((0,142.5), 120, 120, theta1=180, theta2=0, lw=1.5, color=color, ls="dashed"),
        Arc((0,0), 80, 80, theta1=0, theta2=180, lw=1.5, color=color),
        Rectangle((-220,-47.5), 0, 140, lw=1.5, color=color),
        Rectangle((220,-47.5), 0, 140, lw=1.5, color=color),
        Arc((0,0), 475, 475, theta1=22, theta2=158, lw=1.5, color=color),
        Arc((0,422.5), 120, 120, theta1=180, theta2=0, lw=1.5, color=color),
        Rectangle((-250,-47.5), 500, 470, lw=1.5, color=color, fill=False),
    ]:
        ax.add_patch(patch)
    return ax

# ─────────────────────────────────────────────────────────────────────────────
# NBA DISPLAY
# ─────────────────────────────────────────────────────────────────────────────
def show_nba_player(nba_id: int, full_name: str, season: str):
    badge_html = '<span class="level-badge nba-badge">NBA</span>'
    st.markdown(f"# 🏀 {full_name}  {badge_html}", unsafe_allow_html=True)

    with st.spinner("Loading NBA data…"):
        career_r = nba_fetch(playercareerstats.PlayerCareerStats, player_id=nba_id, per_mode36="PerGame")
        adv_r    = nba_fetch(leaguedashplayerstats.LeagueDashPlayerStats, season=season,
                             measure_type_detailed_defense="Advanced", per_mode_detailed="PerGame")
        est_r    = nba_fetch(playerestimatedmetrics.PlayerEstimatedMetrics, season=season)
        shot_r   = nba_fetch(shotchartdetail.ShotChartDetail, team_id=0, player_id=nba_id,
                             season_nullable=season, context_measure_simple="FGA")
        pt_r     = nba_fetch(playerdashptshots.PlayerDashPtShots, player_id=nba_id, season=season)

    career_df = career_r.get_data_frames()[0] if career_r else pd.DataFrame()
    adv_df    = adv_r.get_data_frames()[0]    if adv_r    else pd.DataFrame()
    est_df    = est_r.get_data_frames()[0]    if est_r    else pd.DataFrame()
    shot_df   = shot_r.get_data_frames()[0]   if shot_r   else pd.DataFrame()

    adv_row = adv_df[adv_df["PLAYER_ID"] == nba_id] if not adv_df.empty and "PLAYER_ID" in adv_df.columns else pd.DataFrame()
    est_row = est_df[est_df["PLAYER_ID"] == nba_id] if not est_df.empty and "PLAYER_ID" in est_df.columns else pd.DataFrame()

    # ── Current season KPIs from career_df
    tabs = st.tabs(["📊 Season Stats", "🗺️ Shot Chart", "📈 Career Trend", "⚡ Advanced", "🎯 Shot Quality"])

    with tabs[0]:
        st.markdown('<p class="section-header">Current Season (Per Game)</p>', unsafe_allow_html=True)
        if not career_df.empty:
            reg = career_df[career_df.get("TEAM_ABBREVIATION", pd.Series(["X"] * len(career_df))) != "TOT"]
            curr = reg[reg["SEASON_ID"] == season] if "SEASON_ID" in reg.columns else pd.DataFrame()
            if curr.empty and not reg.empty:
                curr = reg.iloc[[-1]]

            if not curr.empty:
                row = curr.iloc[0]
                kpi_pairs = [
                    ("PTS","PPG"),("REB","RPG"),("AST","APG"),("STL","SPG"),
                    ("BLK","BPG"),("TOV","TO/G"),("FG_PCT","FG%"),
                    ("FG3_PCT","3P%"),("FT_PCT","FT%"),
                ]
                cols = st.columns(len(kpi_pairs))
                for col, (field, label) in zip(cols, kpi_pairs):
                    val = row.get(field)
                    if val is not None and pd.notna(val):
                        disp = f"{val:.1%}" if "PCT" in field else f"{val:.1f}"
                    else:
                        disp = "—"
                    col.markdown(f'<div class="metric-box"><h2>{disp}</h2><p>{label}</p></div>', unsafe_allow_html=True)
            else:
                st.info("No current season data.")
        else:
            st.info("Career data unavailable.")

        # Full career table
        st.markdown('<p class="section-header">Career Season-by-Season</p>', unsafe_allow_html=True)
        show_cols = ["SEASON_ID","TEAM_ABBREVIATION","GP","MIN","PTS","REB","AST","STL","BLK","TOV","FG_PCT","FG3_PCT","FT_PCT","PLUS_MINUS"]
        if not career_df.empty:
            present = [c for c in show_cols if c in career_df.columns]
            st.dataframe(career_df[present].sort_values("SEASON_ID", ascending=False), use_container_width=True, hide_index=True)

    with tabs[1]:
        st.markdown('<p class="section-header">Shot Chart — {}</p>'.format(season), unsafe_allow_html=True)
        if not shot_df.empty:
            made_m   = shot_df["SHOT_MADE_FLAG"] == 1
            missed_m = shot_df["SHOT_MADE_FLAG"] == 0
            made     = made_m.sum()
            total    = len(shot_df)
            fg_pct   = made / total if total else 0

            c1,c2,c3,c4 = st.columns(4)
            for col,(v,l) in zip([c1,c2,c3,c4],[(total,"FGA"),(made,"FGM"),(f"{fg_pct:.1%}","FG%"),(len(shot_df[shot_df["SHOT_TYPE"]=="3PT Field Goal"]),"3PA")]):
                col.markdown(f'<div class="metric-box"><h2>{v}</h2><p>{l}</p></div>', unsafe_allow_html=True)

            chart_mode = st.radio("Style", ["Scatter","Hexbin","Zone Efficiency"], horizontal=True)
            fig, ax = plt.subplots(figsize=(9,8.5))
            ax.set_facecolor("#0d0d0d"); fig.patch.set_facecolor("#0d0d0d")

            if chart_mode == "Hexbin":
                ax.hexbin(shot_df["LOC_X"], shot_df["LOC_Y"], gridsize=25, cmap="YlOrRd",
                          extent=(-250,250,-47.5,422.5), mincnt=1, alpha=0.85)
            elif chart_mode == "Zone Efficiency":
                ze = shot_df.groupby("SHOT_ZONE_BASIC")["SHOT_MADE_FLAG"].agg(["sum","count"])
                ze["pct"] = ze["sum"] / ze["count"]
                shot_df["zpct"] = shot_df["SHOT_ZONE_BASIC"].map(ze["pct"]).fillna(0)
                sc = ax.scatter(shot_df.loc[made_m,"LOC_X"], shot_df.loc[made_m,"LOC_Y"],
                                c=shot_df.loc[made_m,"zpct"], cmap="RdYlGn", vmin=0.3, vmax=0.7, s=14, alpha=0.85, zorder=3)
                ax.scatter(shot_df.loc[missed_m,"LOC_X"], shot_df.loc[missed_m,"LOC_Y"],
                           c="#555", s=10, alpha=0.4, marker="x", zorder=2)
                plt.colorbar(sc, ax=ax, label="Zone FG%", pad=0.01)
            else:
                ax.scatter(shot_df.loc[made_m,"LOC_X"],   shot_df.loc[made_m,"LOC_Y"],   c="#e94560", s=12, alpha=0.7, label="Made")
                ax.scatter(shot_df.loc[missed_m,"LOC_X"], shot_df.loc[missed_m,"LOC_Y"], c="#555",   s=10, alpha=0.5, marker="x", label="Missed")
                ax.legend(loc="upper right", facecolor="#0d0d0d", labelcolor="white", fontsize=8)

            draw_court(ax); ax.set_xlim(-260,260); ax.set_ylim(-60,440); ax.axis("off")
            ax.set_title(f"{full_name} — Shot Chart {season}", color="white", fontsize=12, fontweight="bold")
            buf = BytesIO(); fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="#0d0d0d"); buf.seek(0)
            st.image(buf, use_column_width=True); plt.close(fig)

            # Zone table
            zone_df = shot_df.groupby("SHOT_ZONE_BASIC")["SHOT_MADE_FLAG"].agg(FGM="sum",FGA="count").assign(
                FG_PCT=lambda d: (d.FGM/d.FGA).map("{:.1%}".format)).sort_values("FGA",ascending=False).reset_index()
            st.dataframe(zone_df.rename(columns={"SHOT_ZONE_BASIC":"Zone"}), use_container_width=True, hide_index=True)
        else:
            st.info("No shot data for this season.")

    with tabs[2]:
        st.markdown('<p class="section-header">Points / Assists / Rebounds Per Game — Career</p>', unsafe_allow_html=True)
        if not career_df.empty and "SEASON_ID" in career_df.columns:
            reg = career_df[career_df.get("TEAM_ABBREVIATION", pd.Series(["X"]*len(career_df))) != "TOT"]
            reg = reg.sort_values("SEASON_ID")
            fig = go.Figure()
            for stat,color,name in [("PTS","#e94560","Points"),("AST","#0f3460","Assists"),("REB","#16213e","Rebounds")]:
                if stat in reg.columns:
                    fig.add_trace(go.Scatter(x=reg["SEASON_ID"], y=reg[stat], mode="lines+markers",
                                             name=name, line=dict(color=color, width=2.5), marker=dict(size=6)))
            fig.update_layout(template="plotly_dark", paper_bgcolor="#0d0d0d", plot_bgcolor="#0d0d0d",
                              height=380, xaxis=dict(tickangle=-45), margin=dict(l=40,r=20,t=30,b=60),
                              legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1))
            st.plotly_chart(fig, use_container_width=True)

    with tabs[3]:
        st.markdown('<p class="section-header">Advanced Metrics — {} Season</p>'.format(season), unsafe_allow_html=True)
        if not adv_row.empty:
            adv_metrics = [
                ("TS_PCT","True Shooting %"), ("EFG_PCT","Effective FG %"),
                ("USG_PCT","Usage %"), ("NET_RATING","Net Rating"),
                ("OFF_RATING","Off Rating"), ("DEF_RATING","Def Rating"),
                ("AST_PCT","Ast %"), ("REB_PCT","Reb %"), ("PIE","PIE"),
            ]
            cols = st.columns(len(adv_metrics))
            for col,(f,l) in zip(cols, adv_metrics):
                val = adv_row[f].iloc[0] if f in adv_row.columns else None
                if val is not None and pd.notna(val):
                    disp = f"{val:.1%}" if "PCT" in f else f"{val:.2f}"
                else:
                    disp = "—"
                col.markdown(f'<div class="metric-box"><h2>{disp}</h2><p>{l}</p></div>', unsafe_allow_html=True)

        if not est_row.empty:
            st.markdown('<p class="section-header">Estimated Impact (RAPTOR-adjacent)</p>', unsafe_allow_html=True)
            est_fields = [("E_OFF_RATING","Est Off Rtg"),("E_DEF_RATING","Est Def Rtg"),
                          ("E_NET_RATING","Est Net Rtg"),("E_USG_PCT","Est USG%"),("E_PACE","Est Pace")]
            cols = st.columns(len(est_fields))
            for col,(f,l) in zip(cols, est_fields):
                val = est_row[f].iloc[0] if f in est_row.columns else None
                disp = f"{val:.2f}" if val is not None and pd.notna(val) else "—"
                col.markdown(f'<div class="metric-box"><h2>{disp}</h2><p>{l}</p></div>', unsafe_allow_html=True)

    with tabs[4]:
        st.markdown('<p class="section-header">Dribble Shooting / Touch Time / Shot Clock / Defender Distance</p>', unsafe_allow_html=True)
        if pt_r:
            try:
                dfs_pt = pt_r.get_data_frames()
                tab_labels = ["Dribble Shooting","Touch Time","Shot Clock","Closest Defender","Closest Def 10ft+"]
                idx_map = {0:1, 1:5, 2:4, 3:1, 4:0}  # (tab_label_idx → df index)
                inner_tabs = st.tabs(tab_labels)
                for ti, (tab_label, df_idx) in enumerate([(tab_labels[0],2),(tab_labels[1],5),(tab_labels[2],4),(tab_labels[3],1),(tab_labels[4],0)]):
                    with inner_tabs[ti]:
                        if df_idx < len(dfs_pt):
                            d = dfs_pt[df_idx]
                            show = ["DRIBBLE_RANGE","TOUCH_TIME_RANGE","SHOT_CLOCK_RANGE","CLOSE_DEF_DIST_RANGE"]
                            label_col = next((c for c in show if c in d.columns), d.columns[0] if not d.empty else None)
                            if label_col:
                                cols_show = [label_col,"FGA","FGM","FG_PCT","FG3A","FG3M","FG3_PCT","EFG_PCT","FGA_FREQUENCY"]
                                present = [c for c in cols_show if c in d.columns]
                                st.dataframe(d[present], use_container_width=True, hide_index=True)
            except Exception as e:
                st.info(f"Shot quality data not available: {e}")
        else:
            st.info("Shot quality data not available.")


# ─────────────────────────────────────────────────────────────────────────────
# COLLEGE DISPLAY
# ─────────────────────────────────────────────────────────────────────────────
def show_college_player(espn_id: str, full_name: str, subtitle: str, season: int):
    badge = '<span class="level-badge ncaa-badge">NCAA Men\'s Basketball</span>'
    st.markdown(f"# 🎓 {full_name}  {badge}", unsafe_allow_html=True)
    st.caption(f"{subtitle} · Season {season-1}–{str(season)[2:]}")

    with st.spinner("Loading college data from ESPN…"):
        gamelog_df = get_college_gamelog(espn_id, season)
        totals     = get_college_season_totals(espn_id, season)

    if gamelog_df.empty and not totals:
        st.warning("No data found. Try a different season or check the player name.")
        return

    # ── Season Totals KPIs ─────────────────────────────────────────────────────
    st.markdown('<p class="section-header">Season Totals / Averages</p>', unsafe_allow_html=True)
    kpi_map = {"PTS":"Season PTS","REB":"Season REB","AST":"Season AST",
               "STL":"Season STL","BLK":"Season BLK","FG%":"FG%","3P%":"3P%","FT%":"FT%"}
    kpi_cols = st.columns(len(kpi_map))
    for col,(field,label) in zip(kpi_cols, kpi_map.items()):
        val = totals.get(field, "—")
        kpi_cols[list(kpi_map.keys()).index(field)].markdown(
            f'<div class="metric-box"><h2>{val}</h2><p>{label}</p></div>', unsafe_allow_html=True)

    if gamelog_df.empty:
        st.info("Game-by-game log not available for this season.")
        return

    # Compute per-game averages
    numeric_df = gamelog_to_numeric(gamelog_df.copy())
    num_games  = len(numeric_df)

    pct_fields = {"FG%","3P%","FT%"}
    avg_labels = [("PTS","PPG"),("REB","RPG"),("AST","APG"),("STL","SPG"),
                  ("BLK","BPG"),("TO","TO/G"),("FG%","FG%"),("3P%","3P%"),("FT%","FT%")]
    st.markdown(f'<p class="section-header">Per-Game Averages ({num_games} games)</p>', unsafe_allow_html=True)
    avg_cols = st.columns(len(avg_labels))
    for col,(field,label) in zip(avg_cols, avg_labels):
        if field in numeric_df.columns:
            series = pd.to_numeric(numeric_df[field], errors="coerce")
            mean_val = series.mean()
            if pd.notna(mean_val):
                disp = f"{mean_val:.1f}%" if field in pct_fields else f"{mean_val:.1f}"
            else:
                disp = "—"
        else:
            disp = "—"
        col.markdown(f'<div class="metric-box"><h2>{disp}</h2><p>{label}</p></div>', unsafe_allow_html=True)

    tabs = st.tabs(["📋 Game Log", "📈 Trend Charts"])

    with tabs[0]:
        st.markdown('<p class="section-header">Game-by-Game Log</p>', unsafe_allow_html=True)
        display_cols = ["game_date","opponent","location","result","MIN","FG","FG%","3PT","3P%","FT","FT%","REB","AST","BLK","STL","TO","PTS"]
        present = [c for c in display_cols if c in gamelog_df.columns]
        styled = gamelog_df[present].sort_values("game_date", ascending=False).reset_index(drop=True)
        styled.index += 1
        st.dataframe(styled, use_container_width=True)

    with tabs[1]:
        stat_to_plot = st.multiselect("Stats to chart", ["PTS","REB","AST","STL","BLK","FG%","3P%"],
                                       default=["PTS","AST","REB"])
        color_map = {"PTS":"#e94560","REB":"#0f3460","AST":"#16213e",
                     "STL":"#f5a623","BLK":"#7b2fff","FG%":"#00d4aa","3P%":"#00bcd4"}
        if stat_to_plot and numeric_df is not None:
            fig = go.Figure()
            x = list(range(1, len(numeric_df)+1))
            for s in stat_to_plot:
                if s in numeric_df.columns:
                    y = pd.to_numeric(numeric_df[s], errors="coerce")
                    fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers", name=s,
                                            line=dict(color=color_map.get(s,"#fff"), width=2),
                                            marker=dict(size=5)))
            fig.update_layout(template="plotly_dark", paper_bgcolor="#0d0d0d", plot_bgcolor="#0d0d0d",
                              height=380, xaxis_title="Game #", yaxis_title="Value",
                              legend=dict(orientation="h",yanchor="bottom",y=1.02),
                              margin=dict(l=40,r=20,t=30,b=40))
            st.plotly_chart(fig, use_container_width=True)

        # Shooting % radar
        st.markdown('<p class="section-header">Shooting Profile Radar</p>', unsafe_allow_html=True)
        radar_stats = ["FG%","3P%","FT%"]
        radar_vals = []
        for rs in radar_stats:
            if rs in numeric_df.columns:
                v = pd.to_numeric(numeric_df[rs], errors="coerce").mean()
                radar_vals.append(round(v, 1) if pd.notna(v) else 0)
            else:
                radar_vals.append(0)

        # League averages for college (approximate 2025)
        league_avgs = [45.0, 34.0, 71.0]

        fig2 = go.Figure()
        fig2.add_trace(go.Scatterpolar(r=radar_vals+[radar_vals[0]], theta=radar_stats+[radar_stats[0]],
                                       fill="toself", name=full_name,
                                       line=dict(color="#e94560"), fillcolor="rgba(233,69,96,0.2)"))
        fig2.add_trace(go.Scatterpolar(r=league_avgs+[league_avgs[0]], theta=radar_stats+[radar_stats[0]],
                                       fill="toself", name="D1 Avg",
                                       line=dict(color="#0f3460",dash="dash"), fillcolor="rgba(15,52,96,0.2)"))
        fig2.update_layout(polar=dict(bgcolor="#0d0d0d", radialaxis=dict(visible=True,range=[0,100],color="#555"),
                                      angularaxis=dict(color="#aaa")),
                           template="plotly_dark", paper_bgcolor="#0d0d0d",
                           height=380, legend=dict(orientation="h",yanchor="bottom",y=1.08),
                           margin=dict(l=60,r=60,t=40,b=40))
        st.plotly_chart(fig2, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# HIGH SCHOOL DISPLAY (via ESPN search + MaxPreps fallback)
# ─────────────────────────────────────────────────────────────────────────────
def show_hs_player(full_name: str, espn_id: str | None, subtitle: str):
    badge = '<span class="level-badge hs-badge">High School</span>'
    st.markdown(f"# 🏫 {full_name}  {badge}", unsafe_allow_html=True)
    st.caption(subtitle)

    # HS players tracked by ESPN/MaxPreps often have college gamelog available if recruited
    # Try ESPN college endpoint first (some HS players have ESPN IDs from their college commits coverage)
    # Otherwise show MaxPreps search link + manual entry
    if espn_id:
        with st.spinner("Attempting to load HS/recruiting stats via ESPN…"):
            # Try to get any gamelog
            for season in [2025, 2024, 2023]:
                gl = get_college_gamelog(espn_id, season)
                if not gl.empty:
                    show_college_player(espn_id, full_name, subtitle, season)
                    return

    # ── Fallback: MaxPreps + manual search guidance ────────────────────────────
    st.info(
        "High school player data is hosted on MaxPreps.com. "
        "Live stat ingestion requires a MaxPreps account. "
        "Use the link below to find the player's stats page, then paste their game log here."
    )
    maxpreps_url = f"https://www.maxpreps.com/search/default.aspx?q={full_name.replace(' ', '+')}"
    st.markdown(f"[🔗 Search MaxPreps for {full_name}]({maxpreps_url})")

    st.markdown("---")
    st.subheader("Manual Stat Entry")
    st.caption("Paste a player's season stats manually to generate charts and comparisons.")

    col1, col2, col3 = st.columns(3)
    with col1:
        ppg  = st.number_input("PPG", 0.0, 60.0, 0.0, 0.1)
        rpg  = st.number_input("RPG", 0.0, 30.0, 0.0, 0.1)
        apg  = st.number_input("APG", 0.0, 20.0, 0.0, 0.1)
    with col2:
        spg  = st.number_input("SPG", 0.0, 10.0, 0.0, 0.1)
        bpg  = st.number_input("BPG", 0.0, 10.0, 0.0, 0.1)
        tpg  = st.number_input("TO/G", 0.0, 15.0, 0.0, 0.1)
    with col3:
        fgp  = st.number_input("FG%", 0.0, 100.0, 0.0, 0.1)
        p3   = st.number_input("3P%", 0.0, 100.0, 0.0, 0.1)
        ftp  = st.number_input("FT%", 0.0, 100.0, 0.0, 0.1)

    gp   = st.number_input("Games Played", 1, 50, 1, 1)
    name = st.text_input("School / Team Name", value="")

    if st.button("Generate Profile", type="primary"):
        stats = {"PPG":ppg,"RPG":rpg,"APG":apg,"SPG":spg,"BPG":bpg,"TO/G":tpg,"FG%":fgp,"3P%":p3,"FT%":ftp}
        st.markdown(f"### {full_name} · {name}")
        st.caption(f"{gp} games played")

        stat_cols = st.columns(len(stats))
        for col,(label,val) in zip(stat_cols, stats.items()):
            col.markdown(f'<div class="metric-box"><h2>{val:.1f}</h2><p>{label}</p></div>', unsafe_allow_html=True)

        # Radar vs HS national averages (NHFS rough estimates)
        hs_avg = {"PPG":11.0,"RPG":4.5,"APG":2.1,"SPG":0.9,"BPG":0.4,"FG%":42.0,"3P%":31.0,"FT%":66.0}
        radar_keys = ["PPG","RPG","APG","SPG","FG%","3P%","FT%"]

        def normalize(val, field):
            mx = {"PPG":40,"RPG":20,"APG":12,"SPG":5,"BPG":5,"FG%":100,"3P%":100,"FT%":100}
            return min(val / mx.get(field,1) * 100, 100)

        player_r = [normalize(stats[k], k) for k in radar_keys]
        avg_r    = [normalize(hs_avg.get(k,0), k) for k in radar_keys]

        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(r=player_r+[player_r[0]], theta=radar_keys+[radar_keys[0]],
                                      fill="toself", name=full_name,
                                      line=dict(color="#e94560"), fillcolor="rgba(233,69,96,0.2)"))
        fig.add_trace(go.Scatterpolar(r=avg_r+[avg_r[0]], theta=radar_keys+[radar_keys[0]],
                                      fill="toself", name="HS National Avg",
                                      line=dict(color="#533483",dash="dash"), fillcolor="rgba(83,52,131,0.2)"))
        fig.update_layout(polar=dict(bgcolor="#0d0d0d",radialaxis=dict(visible=True,range=[0,100],color="#555"),
                                     angularaxis=dict(color="#aaa")),
                          template="plotly_dark", paper_bgcolor="#0d0d0d",
                          height=400, legend=dict(orientation="h",yanchor="bottom",y=1.08),
                          margin=dict(l=60,r=60,t=40,b=40),
                          title=f"{full_name} vs HS National Average")
        st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN LOGIC
# ─────────────────────────────────────────────────────────────────────────────
st.title("🔍 Universal Player Scout")
st.caption("NBA · College (NCAAM) · High School · Any player, one tool.")

if not search_query.strip():
    st.markdown("""
    <div style="background:#16213e;border:1px solid #0f3460;border-radius:12px;padding:2rem;text-align:center;">
        <h3 style="color:#fff;">Enter a player name in the sidebar to begin</h3>
        <p style="color:#8a8a9a;">Works for any NBA, NCAA Men's Basketball, or high school player</p>
        <p style="color:#8a8a9a;">Examples: <strong>Stephen Curry</strong> · <strong>Cooper Flagg</strong> · <strong>AJ Dybantsa</strong></p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── Step 1: Search ─────────────────────────────────────────────────────────────
with st.spinner(f"Searching for '{search_query}'…"):
    espn_results = search_player(search_query, limit=10)
    # Also check NBA static list for direct match
    nba_active = get_nba_active()
    nba_direct = nba_active.get(search_query.strip().lower())

# ── Step 2: Handle direct NBA match ───────────────────────────────────────────
if nba_direct and (level_hint in ["Auto-detect", "NBA"]):
    show_nba_player(nba_direct["id"], nba_direct["full_name"], nba_season)
    st.stop()

# ── Step 3: Resolve from ESPN search results ───────────────────────────────────
if not espn_results:
    st.warning(f"No results found for '{search_query}'. Check spelling or try a different name.")
    st.stop()

# Filter by level if user specified
level_filter_map = {
    "NBA":             "nba",
    "College (NCAA)":  "college",
    "High School":     "other",
}
if level_hint != "Auto-detect":
    preferred_slug = level_filter_map.get(level_hint)
    filtered = [r for r in espn_results if r["league_slug"] == preferred_slug]
    if not filtered:
        filtered = espn_results  # fall back to all results
    espn_results = filtered

# If multiple results, let user pick
if len(espn_results) > 1:
    st.markdown("**Multiple players found — select one:**")
    options = {
        f"{r['displayName']} · {r['description']} · {r['subtitle']} [{r['league_slug'].upper()}]": r
        for r in espn_results
    }
    chosen_label = st.selectbox("Match", list(options.keys()))
    chosen = options[chosen_label]
else:
    chosen = espn_results[0]

league_slug = chosen["league_slug"]
espn_id     = chosen["id"]
full_name   = chosen["displayName"]
subtitle    = f"{chosen['description']} · {chosen['subtitle']}"

# ── Step 4: Dispatch to correct display function ───────────────────────────────
if league_slug == "nba":
    # Cross-reference with nba_api for full stats
    nba_match = nba_active.get(full_name.lower())
    if nba_match:
        show_nba_player(nba_match["id"], full_name, nba_season)
    else:
        # Try partial match
        matches = [(k,v) for k,v in nba_active.items() if full_name.lower() in k]
        if matches:
            show_nba_player(matches[0][1]["id"], matches[0][1]["full_name"], nba_season)
        else:
            st.warning(f"Found '{full_name}' on ESPN but couldn't match in nba_api roster. Showing ESPN gamelog.")
            gl = get_nba_player_gamelog_espn(espn_id, int(nba_season[:4])+1)
            if not gl.empty:
                st.dataframe(gl, use_container_width=True)

elif league_slug == "college":
    show_college_player(espn_id, full_name, subtitle, college_season)

else:
    # High school or unknown
    show_hs_player(full_name, espn_id if espn_id else None, subtitle)

st.markdown("---")
st.caption("NBA data via nba_api · College data via ESPN API · HS data via MaxPreps · Season 2025-26")
