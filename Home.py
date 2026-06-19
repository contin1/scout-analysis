"""
NBA Analytics Portfolio — 2025-26 Season
Main entry point / landing page
"""
import streamlit as st

st.set_page_config(
    page_title="NBA Analytics Portfolio | 2025-26",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ──────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d0d0d 0%, #1a1a2e 100%);
    }
    [data-testid="stSidebar"] * { color: #e0e0e0 !important; }

    /* Cards */
    .stat-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid #0f3460;
        border-radius: 12px;
        padding: 1.2rem 1.4rem;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .stat-card h1 { font-size: 2rem; font-weight: 700; color: #e94560; margin: 0; }
    .stat-card p  { font-size: 0.75rem; color: #8a8a9a; margin: 0.2rem 0 0; text-transform: uppercase; letter-spacing: 0.08em; }

    /* Feature tiles */
    .feature-tile {
        background: #16213e;
        border-left: 4px solid #e94560;
        border-radius: 8px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.8rem;
    }
    .feature-tile h4 { color: #ffffff; margin: 0 0 0.3rem; font-size: 1rem; }
    .feature-tile p  { color: #8a8a9a; margin: 0; font-size: 0.82rem; }

    /* Hero banner */
    .hero {
        background: linear-gradient(135deg, #0d0d0d 0%, #1a1a2e 50%, #0f3460 100%);
        border-radius: 16px;
        padding: 2.5rem 3rem;
        margin-bottom: 2rem;
        border: 1px solid #0f3460;
    }
    .hero h1 { font-size: 2.4rem; font-weight: 700; color: #ffffff; margin-bottom: 0.4rem; }
    .hero p  { color: #8a8a9a; font-size: 1rem; margin: 0; }
    .hero .badge {
        display: inline-block;
        background: #e94560;
        color: white;
        font-size: 0.7rem;
        font-weight: 700;
        padding: 0.2rem 0.7rem;
        border-radius: 20px;
        margin-bottom: 0.8rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Hero ─────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="hero">
        <div class="badge">2025–26 NBA Season</div>
        <h1>🏀 NBA Analytics Portfolio</h1>
        <p>Cutting-edge player & team intelligence — built on NBA Stats API v1.11.4</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── KPI row ──────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
kpis = [
    ("168", "API Endpoints"),
    ("5", "Dashboard Modules"),
    ("30", "Teams Covered"),
    ("500+", "Active Players"),
    ("Real-Time", "Live Data"),
]
for col, (val, label) in zip([c1, c2, c3, c4, c5], kpis):
    col.markdown(
        f'<div class="stat-card"><h1>{val}</h1><p>{label}</p></div>',
        unsafe_allow_html=True,
    )

st.markdown("---")

# ── Module feature tiles ──────────────────────────────────────────────────────
st.subheader("Portfolio Modules")

left, right = st.columns(2)

modules = [
    (
        "🎯 Player Profile",
        "Deep per-player breakdown: traditional stats, advanced metrics (TS%, eFG%, USG%), "
        "estimated ratings, shot-clock splits, and clutch performance for every player in the league.",
    ),
    (
        "🗺️ Shot Chart Lab",
        "Interactive hex-bin shot charts using (LOC_X, LOC_Y) coordinates from the ShotChartDetail "
        "endpoint. Compare makes vs. misses, filter by game date range, shot type, and zone.",
    ),
    (
        "💪 Hustle & Tracking",
        "The stats the box score ignores: deflections, contested shots, charges drawn, screen assists, "
        "box-outs, and full tracking data (speed/distance). Built from the LeagueHustleStatsPlayer and "
        "LeagueDashPtStats endpoints.",
    ),
    (
        "📊 League Leaderboard",
        "Full league-wide leaderboard sortable by any stat. Toggle between Base, Advanced, Hustle, "
        "Shooting, and Clutch stat modes. Instantly see who leads the league in any metric.",
    ),
    (
        "⚡ Play-Type Breakdown",
        "Synergy play-type efficiency per player: PPP and percentile ranks for isolation, pick-and-roll, "
        "post-up, hand-off, cut, and transition. Identify offensive role and skill profile.",
    ),
]

for i, (title, desc) in enumerate(modules):
    col = left if i % 2 == 0 else right
    col.markdown(
        f'<div class="feature-tile"><h4>{title}</h4><p>{desc}</p></div>',
        unsafe_allow_html=True,
    )

st.markdown("---")

# ── Quick start guide ────────────────────────────────────────────────────────
st.subheader("Quick Start")
st.markdown(
    """
    Use the **sidebar** to navigate between modules.

    | Module | Best For |
    |--------|----------|
    | Player Profile | Scouting a single player |
    | Shot Chart Lab | Visualizing shooting tendencies |
    | Hustle & Tracking | Evaluating effort/off-ball impact |
    | League Leaderboard | Finding league leaders in any stat |
    | Play-Type Breakdown | Understanding offensive role |

    > **Tip:** All data is cached for 1 hour. If you see a spinner, the API is being queried live.
    """,
    unsafe_allow_html=True,
)

st.caption("Built with nba_api 1.11.4 · Data © NBA Stats · Portfolio by Nicholas Conti")
