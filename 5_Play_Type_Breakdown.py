"""
Module 5 — Play-Type Breakdown
Endpoints used:
  - SynergyPlayTypes (PlayerOrTeam=P) → PPP, PERCENTILE, POSS_PCT per play type
  - LeagueDashPlayerStats (MeasureType=Advanced) → USG%, NET_RATING for context
Play types available: Isolation, PRBallHandler, PRRollman, Postup, Spotup,
                      Handoff, Cut, OffScreen, OffRebound, Misc, Transition
"""
import time
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from nba_api.stats.static import players
from nba_api.stats.endpoints import synergyplaytypes

st.set_page_config(page_title="Play-Type Breakdown | NBA Analytics", page_icon="⚡", layout="wide")

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
.ptype-card{background:#16213e;border-left:3px solid;border-radius:8px;padding:.8rem 1rem;margin-bottom:.5rem;}
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

PLAY_TYPES = [
    "Isolation","PRBallHandler","PRRollman","Postup","Spotup",
    "Handoff","Cut","OffScreen","OffRebound","Misc","Transition",
]

PLAY_TYPE_LABELS = {
    "Isolation":      "Isolation",
    "PRBallHandler":  "PnR Ball Handler",
    "PRRollman":      "PnR Roll Man",
    "Postup":         "Post Up",
    "Spotup":         "Spot Up",
    "Handoff":        "Hand Off",
    "Cut":            "Cut",
    "OffScreen":      "Off Screen",
    "OffRebound":     "Off Rebound",
    "Misc":           "Miscellaneous",
    "Transition":     "Transition",
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
st.sidebar.title("⚡ Play-Type Breakdown")
view = st.sidebar.radio("View", ["Player Profile", "League Leaders by Play Type"])
active = load_active_players()
names = [p["full_name"] for p in active]
default_idx = names.index("Shai Gilgeous-Alexander") if "Shai Gilgeous-Alexander" in names else 0
selected_name = st.sidebar.selectbox("Player", names, index=default_idx)
player_id = next(p["id"] for p in active if p["full_name"] == selected_name)
season_type = st.sidebar.selectbox("Season Type", ["Regular Season", "Playoffs"], index=0)
min_poss = st.sidebar.slider("Min Possessions (league view)", 10, 200, 30)

st.title("⚡ Play-Type Breakdown — 2025-26")

# ── Load all play type data ────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def load_all_play_types(season_type_label):
    dfs = {}
    st_param = "Regular+Season" if season_type_label == "Regular Season" else "Playoffs"
    for pt in PLAY_TYPES:
        r = fetch(synergyplaytypes.SynergyPlayTypes,
                  season=SEASON,
                  player_or_team_abbreviation="P",
                  season_type_all_star=season_type_label,
                  play_type_nullable=pt,
                  type_grouping_nullable="offensive",
                  per_mode_simple="PerGame")
        if r:
            try:
                df = r.get_data_frames()[0]
                if not df.empty:
                    df["PLAY_TYPE"] = pt
                    dfs[pt] = df
            except Exception:
                pass
    if dfs:
        return pd.concat(dfs.values(), ignore_index=True)
    return pd.DataFrame()

with st.spinner("Loading Synergy play-type data (this may take ~30s first load)…"):
    all_pt_df = load_all_play_types(season_type)

if all_pt_df.empty:
    st.warning("Synergy play-type data unavailable. NBA may restrict this endpoint — try again shortly.")
    st.stop()

# Normalize column names
if "TEAM_ID" in all_pt_df.columns:
    id_col  = "TEAM_ID"
    name_col = "TEAM_NAME"
else:
    id_col  = "PLAYER_ID" if "PLAYER_ID" in all_pt_df.columns else None
    name_col = "PLAYER_NAME" if "PLAYER_NAME" in all_pt_df.columns else None

# ── View: Player Profile ───────────────────────────────────────────────────────
if view == "Player Profile":
    st.subheader(f"⚡ {selected_name} — Offensive Play-Type Profile")

    if id_col and id_col in all_pt_df.columns:
        player_pt = all_pt_df[all_pt_df[id_col] == player_id].copy()
    else:
        player_pt = pd.DataFrame()

    if player_pt.empty:
        st.info("No play-type data for this player (may lack enough possessions in any category).")
    else:
        player_pt["PLAY_TYPE_LABEL"] = player_pt["PLAY_TYPE"].map(PLAY_TYPE_LABELS)

        # ── PPP bar chart ─────────────────────────────────────────────────────
        if "PPP" in player_pt.columns and "POSS" in player_pt.columns:
            pt_sorted = player_pt.sort_values("POSS", ascending=False)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=pt_sorted["PLAY_TYPE_LABEL"],
                y=pt_sorted["PPP"],
                name="PPP",
                marker=dict(
                    color=pt_sorted["PPP"],
                    colorscale="RdYlGn",
                    cmin=0.8, cmax=1.2,
                    showscale=True,
                    colorbar=dict(title="PPP", thickness=12),
                ),
                text=pt_sorted["PPP"].map("{:.3f}".format),
                textposition="outside",
            ))
            fig.update_layout(
                template="plotly_dark", paper_bgcolor="#0d0d0d", plot_bgcolor="#0d0d0d",
                title="Points Per Possession by Play Type",
                xaxis_title="Play Type", yaxis_title="PPP",
                height=380, margin=dict(l=40, r=20, t=50, b=80),
                yaxis=dict(range=[0, pt_sorted["PPP"].max() * 1.2]),
            )
            fig.add_hline(y=1.0, line_dash="dash", line_color="#aaa", annotation_text="League avg ≈ 1.0")
            st.plotly_chart(fig, use_container_width=True)

        # ── Possession share pie ───────────────────────────────────────────────
        if "POSS" in player_pt.columns and "POSS_PCT" in player_pt.columns:
            col1, col2 = st.columns([1, 1])

            with col1:
                st.markdown('<p class="section-header">Possession Share</p>', unsafe_allow_html=True)
                fig2 = px.pie(
                    player_pt,
                    values="POSS",
                    names="PLAY_TYPE_LABEL",
                    color_discrete_sequence=px.colors.qualitative.Set3,
                    hole=0.4,
                    template="plotly_dark",
                )
                fig2.update_traces(textinfo="label+percent")
                fig2.update_layout(
                    paper_bgcolor="#0d0d0d",
                    showlegend=False,
                    margin=dict(l=10, r=10, t=20, b=10),
                    height=320,
                )
                st.plotly_chart(fig2, use_container_width=True)

            with col2:
                st.markdown('<p class="section-header">Percentile Rankings</p>', unsafe_allow_html=True)
                if "PERCENTILE" in player_pt.columns:
                    pct_df = player_pt[["PLAY_TYPE_LABEL","PERCENTILE","PPP","POSS"]].sort_values("POSS", ascending=False)
                    for _, row in pct_df.iterrows():
                        pct = row["PERCENTILE"]
                        ppp = row["PPP"]
                        poss = row["POSS"]
                        if pd.isna(pct): continue
                        color = "#e94560" if pct >= 0.7 else ("#f5a623" if pct >= 0.4 else "#0f3460")
                        st.markdown(
                            f'<div class="ptype-card" style="border-color:{color};">'
                            f'<strong style="color:#fff;">{row["PLAY_TYPE_LABEL"]}</strong> '
                            f'<span style="color:#8a8a9a;font-size:.75rem;">({int(poss)} poss)</span><br>'
                            f'<span style="color:{color};font-size:1.1rem;font-weight:700;">{pct:.0%} percentile</span> '
                            f'<span style="color:#aaa;font-size:.8rem;">· {ppp:.3f} PPP</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

        # ── Detail table ──────────────────────────────────────────────────────
        st.markdown("---")
        detail_cols = ["PLAY_TYPE_LABEL","POSS","PPP","FG_PCT","EFG_PCT","FT_POSS_PCT","TOV_POSS_PCT","SCORE_POSS_PCT","PERCENTILE"]
        present = [c for c in detail_cols if c in player_pt.columns]
        st.dataframe(
            player_pt[present].rename(columns={"PLAY_TYPE_LABEL":"Play Type","POSS":"Poss","PPP":"PPP",
                "FG_PCT":"FG%","EFG_PCT":"eFG%","FT_POSS_PCT":"FT/Poss","TOV_POSS_PCT":"TOV/Poss",
                "SCORE_POSS_PCT":"Score/Poss","PERCENTILE":"Percentile"}).sort_values("Poss",ascending=False),
            use_container_width=True, hide_index=True,
        )

# ── View: League Leaders ─────────────────────────────────────────────────────
else:
    st.subheader("🏆 League Leaders by Play Type")
    selected_pt = st.selectbox(
        "Play Type",
        PLAY_TYPES,
        format_func=lambda x: PLAY_TYPE_LABELS.get(x, x),
        index=0,
    )
    sort_by = st.selectbox("Sort By", ["PPP","POSS","POSS_PCT","FG_PCT","EFG_PCT","SCORE_POSS_PCT","TOV_POSS_PCT"], index=0)

    pt_df = all_pt_df[all_pt_df["PLAY_TYPE"] == selected_pt].copy()
    if "POSS" in pt_df.columns:
        pt_df = pt_df[pt_df["POSS"] >= min_poss]

    if pt_df.empty:
        st.info("No players meet the minimum possession threshold for this play type.")
    else:
        if sort_by in pt_df.columns:
            pt_df = pt_df.sort_values(sort_by, ascending=(sort_by == "TOV_POSS_PCT"))

        # Determine player/team name column
        disp_name_col = name_col if name_col and name_col in pt_df.columns else pt_df.columns[0]
        show_cols = [disp_name_col, "POSS","PPP","FG_PCT","EFG_PCT","FT_POSS_PCT","TOV_POSS_PCT","SCORE_POSS_PCT","PERCENTILE"]
        show_cols = [c for c in show_cols if c in pt_df.columns]

        top25 = pt_df[show_cols].head(25)

        if "PPP" in top25.columns:
            fig = px.bar(
                top25.head(15).sort_values(sort_by),
                x=sort_by, y=disp_name_col,
                orientation="h",
                color="PPP",
                color_continuous_scale="RdYlGn",
                template="plotly_dark",
                title=f"Top 15 — {PLAY_TYPE_LABELS[selected_pt]} · Sorted by {sort_by}",
            )
            fig.update_layout(
                paper_bgcolor="#0d0d0d", plot_bgcolor="#0d0d0d",
                showlegend=False, height=420,
                yaxis=dict(autorange="reversed"),
                coloraxis_showscale=True,
                margin=dict(l=10, r=60, t=40, b=20),
            )
            st.plotly_chart(fig, use_container_width=True)

        st.dataframe(top25.reset_index(drop=True), use_container_width=True, hide_index=True)

st.caption("Data via Synergy / NBA Stats API · Season 2025-26 · Cached 1 hr")
