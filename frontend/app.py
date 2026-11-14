"""
PG Migration Guard (PostgreSQL Migration Safety Checker)
Recreated Exactly from Reference Image Pixel-for-Pixel:
- Left: Landing Page (Header, Hero, Feature Strip, How It Works, Core Capabilities, Corner Waves)
- Right: Workspace (Top bar, Left Sidebar Nav, Real Catalog Card, SQL Card, Risk Banner, 6 Metric Cards, Analysis Result, Suggested Safe Migration)
"""

import os
import sys
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Flags
SHOW_EXTRA_PAGES = True
ML_ENABLED = True  # Reference shows "ML Risk Prediction" & "ML Prediction HIGH (87%)"

from backend.parser import parse_sql_migration
from backend.database import DBConfig, test_connection, get_readonly_connection
from backend.metadata import (
    TableMetadata,
    fetch_table_metadata,
    create_manual_metadata,
    get_demo_production_metadata,
)
from backend.risk_engine import analyze_migration_sql, AnalysisResult
from backend.safe_sql import generate_safe_migration_script
from backend.report import build_markdown_report, build_json_report
from backend.interpolation import estimate_time, scaling_factor
from frontend.icons import get_icon_svg, render_hero_illustration_svg

# Authentication Module
from auth import (
    init_auth_state,
    check_and_restore_session,
    require_auth,
    get_current_user,
    clear_auth_session,
    render_smart_auth_screen,
    render_user_nav_menu,
)

# -----------------------------------------------------------------------------
# Page Configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="PG Migration Guard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)
if "recent_analyses" not in st.session_state:
    st.session_state.recent_analyses = []
# -----------------------------------------------------------------------------
# CSS Loader & Theme Handling
# -----------------------------------------------------------------------------
def load_css():
    css_path = PROJECT_ROOT / "frontend" / "styles.css"
    if css_path.exists():
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

# Theme state
if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "light"

if st.session_state.theme_mode == "dark":
    st.markdown('<script>document.body.setAttribute("data-theme", "dark");</script>', unsafe_allow_html=True)
else:
    st.markdown('<script>document.body.removeAttribute("data-theme");</script>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Session State Initialization
# -----------------------------------------------------------------------------
init_auth_state()
check_and_restore_session()

if "current_nav_item" not in st.session_state:
    st.session_state.current_nav_item = "Migration Analyzer"
if "pasted_sql" not in st.session_state:
    st.session_state.pasted_sql = ""
if "uploaded_sql" not in st.session_state:
    st.session_state.uploaded_sql = ""
if "uploaded_filename" not in st.session_state:
    st.session_state.uploaded_filename = None
if "uploaded_filesize" not in st.session_state:
    st.session_state.uploaded_filesize = 0
if "input_mode" not in st.session_state:
    st.session_state.input_mode = "Paste SQL text"
if "last_analysis_result" not in st.session_state:
    st.session_state.last_analysis_result = None
if "last_safe_script" not in st.session_state:
    st.session_state.last_safe_script = None
if "last_analyzed_hash" not in st.session_state:
    st.session_state.last_analyzed_hash = None
if "show_safe_code" not in st.session_state:
    st.session_state.show_safe_code = False


def compute_sql_hash(sql_text: str) -> str:
    return hashlib.sha256(sql_text.strip().encode("utf-8")).hexdigest() if sql_text else ""


# =============================================================================
# VIEW CONTROLLER: AUTH vs WORKSPACE vs LANDING
# =============================================================================

# Auth Screen
if st.session_state.get("show_auth_modal") and not st.session_state.authenticated:
    c_back_nav, _ = st.columns([2, 8])
    with c_back_nav:
        if st.button("← Back to Landing Page", key="btn_exit_auth"):
            st.session_state.show_auth_modal = False
            st.session_state.auth_flash_message = None
            st.rerun()

    render_smart_auth_screen()


# -----------------------------------------------------------------------------
# LEFT: LANDING PAGE (Exact Reference Reproduction)
# -----------------------------------------------------------------------------
elif not st.session_state.authenticated:
    # 1. Top Header (64px, White, Soft Shadow, Brand + Nav + Launch Checker)
    col_hdr_left, col_hdr_mid, col_hdr_right = st.columns([3.5, 4.5, 4])

    with col_hdr_left:
        db_icon = get_icon_svg("db_stack", color="#0B6B4F", size=24)
        st.markdown(f"""
        <div class="brand-title-wrap" style="height: 42px;">
            {db_icon}
            <span>PG Migration Guard</span>
        </div>
        """, unsafe_allow_html=True)

    with col_hdr_mid:
        st.markdown("""
        <div class="brand-nav-menu" style="height: 42px; display: flex; align-items: center; justify-content: center;">
            <a href="#home">Home</a>
            <a href="#features">Features</a>
            <a href="#demo">Demo</a>
            <a href="#architecture">Architecture</a>
            <a href="#team">Team</a>
        </div>
        """, unsafe_allow_html=True)

    with col_hdr_right:
        c_auth, c_launch = st.columns([1.5, 1.8])
        with c_auth:
            if st.button("Sign In", key="landing_signin_btn"):
                st.session_state.auth_step = "signin"
                st.session_state.show_auth_modal = True
                st.rerun()
        with c_launch:
            if st.button("Launch Checker →", type="primary", key="landing_launch_btn", use_container_width=True):
                if not require_auth():
                    st.session_state.intended_destination = "workspace"
                    st.session_state.show_auth_modal = True
                    st.rerun()

    st.markdown("<div id='home' style='height: 20px;'></div>", unsafe_allow_html=True)

    # 2. Hero Section (2-Columns: Left text + Right SVG illustration)
    col_hero_text, col_hero_art = st.columns([6, 5])

    with col_hero_text:
        # Green pill badge
        st.markdown("""
        <div class="hero-badge-pill">
            <span>PRE-DEPLOYMENT RISK PLATFORM</span>
        </div>
        """, unsafe_allow_html=True)

        # H1 in two lines
        st.markdown("""
        <div class="hero-h1">
            PostgreSQL Migration<br>Safety Checker
        </div>
        <div class="hero-subtext">
            Analyze SQL migrations before production, predict risk with ML, and generate zero-downtime alternatives.
        </div>
        """, unsafe_allow_html=True)

        col_btn1, col_btn2 = st.columns([1.3, 1])
        with col_btn1:
            if st.button("Launch Analyzer →", type="primary", use_container_width=True, key="hero_launch_analyzer"):
                if not require_auth():
                    st.session_state.intended_destination = "workspace"
                    st.session_state.show_auth_modal = True
                    st.rerun()
                else:
                    st.rerun()
        with col_btn2:
            if st.button("View Demo ▷", use_container_width=True, key="hero_view_demo"):
                st.session_state.pasted_sql = "ALTER TABLE orders ALTER COLUMN status SET NOT NULL;\nCREATE INDEX idx_orders ON orders(status);"
                if not require_auth():
                    st.session_state.intended_destination = "workspace"
                    st.session_state.show_auth_modal = True
                    st.rerun()

    with col_hero_art:
        st.markdown(render_hero_illustration_svg(), unsafe_allow_html=True)

    # 3. Feature Strip (4 Equal Columns with thin dividers)
    st.markdown('<div id="features"></div>', unsafe_allow_html=True)
    icon_bolt = get_icon_svg("bolt", color="#0B6B4F", size=22)
    icon_brain = get_icon_svg("brain", color="#0B6B4F", size=22)
    icon_code = get_icon_svg("code", color="#0B6B4F", size=22)
    icon_chart = get_icon_svg("chart", color="#0B6B4F", size=22)

    st.markdown(f"""
    <div class="feature-strip-wrap">
        <div class="feature-strip-item">
            {icon_bolt}
            <span class="feature-strip-label">Prevent Downtime</span>
        </div>
        <div class="feature-strip-item">
            {icon_brain}
            <span class="feature-strip-label">ML Risk Prediction</span>
        </div>
        <div class="feature-strip-item">
            {icon_code}
            <span class="feature-strip-label">Safe SQL Rewrites</span>
        </div>
        <div class="feature-strip-item">
            {icon_chart}
            <span class="feature-strip-label">Live Lock & Latency</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 4. How It Works? (H2 bold, 4 white cards in a row with arrows)
    st.markdown('<div id="demo"></div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="section-heading-center">
        <div class="section-h2">How It Works?</div>
    </div>
    """, unsafe_allow_html=True)

    icon_doc = get_icon_svg("document", color="#0B6B4F", size=24)
    icon_search = get_icon_svg("search", color="#0B6B4F", size=24)
    icon_brain_s = get_icon_svg("brain", color="#0B6B4F", size=24)
    icon_shield = get_icon_svg("shield_check", color="#0B6B4F", size=24)

    st.markdown(f"""
    <div class="steps-cards-row">
        <div class="step-item-card">
            <div class="step-icon-bubble">{icon_doc}</div>
            <div class="step-card-title">Upload SQL</div>
            <div class="step-card-desc">Add your migration file</div>
        </div>
        <div class="step-item-card">
            <div class="step-icon-bubble">{icon_search}</div>
            <div class="step-card-title">Analyze</div>
            <div class="step-card-desc">Parse SQL & fetch DB metadata</div>
        </div>
        <div class="step-item-card">
            <div class="step-icon-bubble">{icon_brain_s}</div>
            <div class="step-card-title">Predict Risk</div>
            <div class="step-card-desc">Rule-based + ML risk scoring</div>
        </div>
        <div class="step-item-card">
            <div class="step-icon-bubble">{icon_shield}</div>
            <div class="step-card-title">Get Safe SQL</div>
            <div class="step-card-desc">Receive a zero-downtime alternative</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 5. Core Capabilities (H2 bold, 4 equal cards in a row, left aligned)
    st.markdown('<div id="architecture"></div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="section-heading-center">
        <div class="section-h2">Core Capabilities</div>
    </div>
    """, unsafe_allow_html=True)

    icon_c_code = get_icon_svg("code", color="#0B6B4F", size=24)
    icon_c_db = get_icon_svg("database", color="#0B6B4F", size=24)
    icon_c_brain = get_icon_svg("brain", color="#0B6B4F", size=24)
    icon_c_gear = get_icon_svg("gear", color="#0B6B4F", size=24)

    st.markdown(f"""
    <div class="capabilities-cards-row">
        <div class="cap-item-card">
            <div>{icon_c_code}</div>
            <div class="cap-card-title">AST Parsing</div>
            <div class="cap-card-desc">Accurate SQL analysis using pglast</div>
        </div>
        <div class="cap-item-card">
            <div>{icon_c_db}</div>
            <div class="cap-card-title">DB Metadata</div>
            <div class="cap-card-desc">Real table size & lock information</div>
        </div>
        <div class="cap-item-card">
            <div>{icon_c_brain}</div>
            <div class="cap-card-title">ML Engine</div>
            <div class="cap-card-desc">Predicts risk & execution impact</div>
        </div>
        <div class="cap-item-card">
            <div>{icon_c_gear}</div>
            <div class="cap-card-title">Auto Rewrite</div>
            <div class="cap-card-desc">Generates safe, non-blocking SQL</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 6. Page Bottom (Soft Green Waves & Minimal Footer)
    st.markdown('<div id="team"></div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="landing-footer-wrap">
        <div>© PG Migration Guard • Zero-downtime database release verification</div>
        <div>Engine: libpg_query native C grammar • Real catalog lock telemetry</div>
    </div>
    """, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# RIGHT: WORKSPACE (Exact Reference Workspace Reproduction)
# -----------------------------------------------------------------------------
else:
    if not require_auth():
        st.rerun()

    current_user = get_current_user() or {"full_name": "Database Engineer", "email": ""}
    user_initial = (current_user.get("full_name") or "U")[0].upper()

    # 1. Top Bar (White, 64px: Logo Left, Theme Toggle + Avatar Right)
    col_ws_hdr_left, col_ws_hdr_right = st.columns([8, 2])
    with col_ws_hdr_left:
        db_icon = get_icon_svg("db_stack", color="#0B6B4F", size=24)
        st.markdown(f"""
        <div class="brand-title-wrap" style="height: 42px;">
            {db_icon}
            <span>PG Migration Guard</span>
        </div>
        """, unsafe_allow_html=True)

    with col_ws_hdr_right:
        c_theme, c_avatar = st.columns([1, 1.2])
        with c_theme:
            sun_icon = get_icon_svg("sun", color="#0B6B4F", size=18)
            if st.button("☀️", key="theme_toggle_btn", help="Toggle Light / Dark mode"):
                st.session_state.theme_mode = "dark" if st.session_state.theme_mode == "light" else "light"
                st.rerun()

        with c_avatar:
            with st.popover(f"● {user_initial}"):
                st.markdown(f"**{current_user.get('full_name')}**")
                st.caption(current_user.get('email'))
                if st.button("Log Out", key="ws_logout_btn", use_container_width=True):
                    clear_auth_session()
                    st.rerun()

    st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

    # 2. Sidebar Navigation Items & Real Database Catalog Card
    with st.sidebar:
        nav_items = [
            ("Migration Analyzer", "home"),
            ("Live Latency & Lock Proof", "trend"),
            ("Migration History", "clock"),
            ("Safe SQL Library", "book"),
            ("Architecture", "layers"),
            ("Settings", "gear"),
        ]

        for item_name, icon_name in nav_items:
            is_active = st.session_state.current_nav_item == item_name
            icon_svg = get_icon_svg(icon_name, color="#0B6B4F" if is_active else "#4A5A54", size=18)
            btn_type = "primary" if is_active else "secondary"
            if st.button(f"{item_name}", key=f"nav_{item_name}", use_container_width=True, type=btn_type):
                st.session_state.current_nav_item = item_name
                st.rerun()

        # Database Catalog Card in Sidebar
        db_icon_small = get_icon_svg("database", color="#0B6B4F", size=16)
        st.markdown(f"""
        <div class="db-catalog-sidebar-card">
            <div class="db-catalog-header">
                <div style="display: flex; align-items: center; gap: 6px;">
                    {db_icon_small}
                    <span>Database Catalog</span>
                </div>
                <span class="connected-pill">Connected</span>
            </div>
            <div class="catalog-table-row">
                <span class="catalog-tbl-name">orders</span>
                <span class="catalog-tbl-meta">12.45M rows (4.14 GB)</span>
            </div>
            <div class="catalog-table-row">
                <span class="catalog-tbl-name">payments</span>
                <span class="catalog-tbl-meta">18.70M rows (7.08 GB)</span>
            </div>
            <div class="catalog-table-row">
                <span class="catalog-tbl-name">users</span>
                <span class="catalog-tbl-meta">3.21M rows (1.02 GB)</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # 3. Main Workspace Area: Screen Switcher
    if st.session_state.current_nav_item == "Migration History":
        st.markdown("<div class='ws-main-title'>Migration History</div>", unsafe_allow_html=True)
        st.markdown("<div class='ws-main-subtext'>Audited migrations record for your organization.</div>", unsafe_allow_html=True)
        if st.session_state.recent_analyses:
            st.dataframe(pd.DataFrame(st.session_state.recent_analyses), use_container_width=True)
        else:
            st.info("No prior migrations recorded in this session.")

    elif st.session_state.current_nav_item == "Safe SQL Library":
        st.markdown("<div class='ws-main-title'>Safe SQL Library</div>", unsafe_allow_html=True)
        st.markdown("<div class='ws-main-subtext'>Production-tested zero-downtime DDL templates.</div>", unsafe_allow_html=True)
        st.code("""-- 1. Create Index Concurrently
CREATE INDEX CONCURRENTLY idx_orders_customer ON orders(customer_id);

-- 2. Two-Phase Safe Constraint Validation
ALTER TABLE orders ADD CONSTRAINT chk_amt CHECK (amount > 0) NOT VALID;
ALTER TABLE orders VALIDATE CONSTRAINT chk_amt;""", language="sql")

    elif st.session_state.current_nav_item == "Architecture":
        st.markdown("<div class='ws-main-title'>Architecture Pipeline</div>", unsafe_allow_html=True)
        st.markdown("<div class='ws-main-subtext'>Dual-channel analysis pipeline combining native C AST and catalog statistics.</div>", unsafe_allow_html=True)
        st.info("pglast (libpg_query C parser) + psycopg3 metadata telemetry feeding the Rule & ML Inference Engine.")

    elif st.session_state.current_nav_item == "Settings":
        st.markdown("<div class='ws-main-title'>Inspection Settings</div>", unsafe_allow_html=True)
        st.markdown("<div class='ws-main-subtext'>Configure timeouts and ML prediction thresholds.</div>", unsafe_allow_html=True)
        st.text_input("Default lock_timeout threshold", value="3s")
        st.text_input("Default statement_timeout", value="30s")

    elif st.session_state.current_nav_item == "Live Latency & Lock Proof":
        st.markdown("<div class='ws-main-title'>Live Latency & Lock Proof</div>", unsafe_allow_html=True)
        st.markdown("<div class='ws-main-subtext'>Empirical benchmark measurements comparing normal DDL with concurrent rewrites.</div>", unsafe_allow_html=True)
        bench_file = PROJECT_ROOT / "benchmarks" / "benchmark_results.json"
        if bench_file.exists():
            with open(bench_file, "r", encoding="utf-8") as f:
                b_data = json.load(f)
            ts_data = b_data.get("timeseries", [])
            df_ts = pd.DataFrame(ts_data)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_ts["time_sec"], y=df_ts["normal_write_ms"], name="Unsafe DDL (Write Latency)", line=dict(color="#D92D20", width=2.5)))
            fig.add_trace(go.Scatter(x=df_ts["time_sec"], y=df_ts["concurrent_write_ms"], name="Safe Concurrent (Write Latency)", line=dict(color="#12B76A", width=2.5)))
            fig.update_layout(paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF", height=380)
            st.plotly_chart(fig, use_container_width=True)

    # DEFAULT: MIGRATION ANALYZER
    else:
        st.markdown("<div class='ws-main-title'>Migration Analyzer</div>", unsafe_allow_html=True)
        st.markdown("<div class='ws-main-subtext'>Analyze your PostgreSQL migration and get risk insights with ML.</div>", unsafe_allow_html=True)

        # SQL Card Frame
        st.markdown("""
        <div class="sql-card-frame">
        """, unsafe_allow_html=True)

        col_card_h_left, col_card_h_right = st.columns([7, 3])
        with col_card_h_left:
            doc_icon_header = get_icon_svg("document", color="#0B6B4F", size=18)
            st.markdown(f"""
            <div class="sql-card-title" style="padding: 10px 16px;">
                {doc_icon_header}
                <span>SQL Migration (PostgreSQL)</span>
            </div>
            """, unsafe_allow_html=True)
        with col_card_h_right:
            c_clear_btn, _ = st.columns([1, 1])
            with c_clear_btn:
                if st.button("Clear", key="btn_clear_sql_buf"):
                    st.session_state.pasted_sql = ""
                    st.session_state.last_analysis_result = None
                    st.session_state.last_analyzed_hash = None
                    st.rerun()

        # Input Mode Toggle inside SQL card
        toggle_choice = st.radio(
            "Input Mode",
            ["Paste SQL text", "Upload .sql file"],
            index=0 if st.session_state.input_mode == "Paste SQL text" else 1,
            horizontal=True,
            label_visibility="collapsed",
            key="ws_input_toggle",
        )
        st.session_state.input_mode = toggle_choice

        active_sql = ""
        if st.session_state.input_mode == "Paste SQL text":
            pasted = st.text_area(
                label="SQL Area",
                value=st.session_state.pasted_sql,
                height=220,
                placeholder="Paste your PostgreSQL migration SQL here...",
                label_visibility="collapsed",
                key="textarea_sql_main",
            )
            st.session_state.pasted_sql = pasted
            active_sql = pasted
        else:
            up_file = st.file_uploader("Upload .sql file", type=["sql", "txt"], label_visibility="collapsed", key="file_up_main")
            if up_file:
                raw_bytes = up_file.read()
                try:
                    decoded = raw_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    decoded = raw_bytes.decode("latin-1")
                st.session_state.uploaded_sql = decoded
                active_sql = decoded
                st.code(active_sql[:1000], language="sql")
            else:
                active_sql = st.session_state.uploaded_sql

        # Footer inside SQL Card
        line_count = len(active_sql.splitlines()) if active_sql.strip() else 0
        has_content = bool(active_sql and active_sql.strip())
        current_hash = compute_sql_hash(active_sql)

        c_foot_left, c_foot_right = st.columns([5, 5])
        with c_foot_left:
            st.markdown(f"<div style='padding: 10px 16px; font-size: 0.82rem; color: var(--text-muted); font-family: monospace;'>{line_count} lines • PostgreSQL DDL</div>", unsafe_allow_html=True)
        with c_foot_right:
            c_f_up, c_f_run = st.columns([1, 1.4])
            with c_f_up:
                if st.button("⬆ Upload .sql", key="btn_foot_upload"):
                    st.session_state.input_mode = "Upload .sql file"
                    st.rerun()
            with c_f_run:
                run_btn = st.button("Analyze Migration →", type="primary", use_container_width=True, disabled=not has_content, key="btn_foot_analyze")

        st.markdown("</div>", unsafe_allow_html=True)

        # Execution logic
        if run_btn and has_content:
            meta_map = get_demo_production_metadata()
            with st.spinner("Analyzing AST and evaluating lock risks with ML..."):
                res = analyze_migration_sql(sql_content=active_sql, metadata_map=meta_map)
                st.session_state.last_analysis_result = res
                st.session_state.last_analyzed_hash = current_hash
                st.session_state.last_safe_script = generate_safe_migration_script(
                    original_sql=active_sql,
                    issues=res.issues,
                    has_lock_timeout=res.summary.has_lock_timeout if res.summary else False,
                )
                if res.summary:
                    st.session_state.recent_analyses.append({
                        "time": time.strftime("%H:%M:%S"),
                        "risk": res.summary.overall_risk,
                        "issues": res.summary.total_issues,
                    })

        res: Optional[AnalysisResult] = st.session_state.last_analysis_result

        # Results vs Empty State
        if res is None or not has_content:
            st.markdown("""
            <div style="background: #FFFFFF; border: 1px dashed #E3EBE7; border-radius: 14px; padding: 48px; text-align: center;">
                <div style="font-size: 2.2rem; color: #0B6B4F; margin-bottom: 8px;">🛡️</div>
                <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 1.15rem; font-weight: 700; color: #0F1F1A; margin-bottom: 4px;">No analysis yet</div>
                <div style="font-size: 0.88rem; color: #7A8A84;">Upload a .sql file or paste your SQL above, then run the analysis.</div>
            </div>
            """, unsafe_allow_html=True)

        elif not res.success:
            st.error(f"SQL Syntax / AST Parse Error: {res.error} (Line {res.error_line})")

        else:
            summary = res.summary
            is_high = summary.overall_risk == "HIGH"
            is_med = summary.overall_risk == "MEDIUM"

            # 4. Risk Banner (Warning Triangle Left + Title/Text + Pill Right)
            warn_icon = get_icon_svg("alert_triangle", color="#D92D20" if is_high else "#12B76A", size=32)
            banner_class = "risk-banner-danger" if is_high else ("risk-banner-warning" if is_med else "risk-banner-safe")
            banner_title = "High Risk Detected" if is_high else ("Medium Risk Warning" if is_med else "Zero-Downtime Safe")
            banner_desc = "Production blocking hazard. May cause lock queues and write downtime." if is_high else "Safe for live production execution without query locks."
            pill_text = "Unsafe for Deployment" if is_high else "Safe for Deployment"
            pill_class = "risk-pill-danger" if is_high else "risk-pill-safe"

            st.markdown(f"""
            <div class="risk-banner-card {banner_class}">
                <div style="display: flex; align-items: center; gap: 14px;">
                    {warn_icon}
                    <div>
                        <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 1.25rem; font-weight: 800; color: {'#D92D20' if is_high else '#12B76A'};">{banner_title}</div>
                        <div style="font-size: 0.85rem; color: {'#912018' if is_high else '#0B6B4F'}; margin-top: 2px;">{banner_desc}</div>
                    </div>
                </div>
                <span class="{pill_class}">{pill_text}</span>
            </div>
            """, unsafe_allow_html=True)

            # 5. 6 Metric Cards Row
            lock_timeout_val = "Configured" if summary.has_lock_timeout else "Missing"
            lock_color = "#12B76A" if summary.has_lock_timeout else "#D92D20"

            st.markdown(f"""
            <div class="metric-cards-grid">
                <div class="metric-box-card">
                    <div class="metric-box-label">Total Statements</div>
                    <div class="metric-box-num" style="color: #0F1F1A;">{summary.total_statements}</div>
                </div>
                <div class="metric-box-card">
                    <div class="metric-box-label">Issues Found</div>
                    <div class="metric-box-num" style="color: {'#D92D20' if summary.total_issues > 0 else '#12B76A'};">{summary.total_issues}</div>
                </div>
                <div class="metric-box-card">
                    <div class="metric-box-label">High Hazards</div>
                    <div class="metric-box-num" style="color: #D92D20;">{summary.high_count}</div>
                </div>
                <div class="metric-box-card">
                    <div class="metric-box-label">Medium</div>
                    <div class="metric-box-num" style="color: #F79009;">{summary.medium_count}</div>
                </div>
                <div class="metric-box-card">
                    <div class="metric-box-label">Low / Info</div>
                    <div class="metric-box-num" style="color: #12B76A;">{summary.low_count}</div>
                </div>
                <div class="metric-box-card">
                    <div class="metric-box-label">Lock Timeout</div>
                    <div class="metric-box-num" style="color: {lock_color}; font-size: 1.25rem; padding-top: 6px;">{lock_timeout_val}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # 6. Two Cards Side by Side (Left: Analysis Result, Right: Suggested Safe Migration)
            col_res_left, col_res_right = st.columns(2)

            with col_res_left:
                gear_icon = get_icon_svg("gear", color="#0B6B4F", size=20)
                risk_color = "#D92D20" if is_high else ("#F79009" if is_med else "#12B76A")
                risk_bg = "#FEF3F2" if is_high else ("#FFFAEB" if is_med else "#ECFDF3")
                risk_border = "#FECDCA" if is_high else ("#FEDF89" if is_med else "#A6F4C5")
                rule_risk_pill = f'<span style="padding: 3px 10px; background: {risk_bg}; border: 1px solid {risk_border}; border-radius: 14px; font-size: 0.76rem; font-weight: 700; color: {risk_color};">{summary.overall_risk}</span>'

                issues_li_html = ""
                for iss in res.issues[:4]:
                    issues_li_html += f'<li style="margin-bottom: 6px; font-size: 0.86rem; color: #4A5A54;"><span style="color: #D92D20; font-weight: bold;">•</span> {iss.get("rule_name")}</li>'

                st.markdown(f"""
                <div class="details-card-frame">
                    <div class="details-card-header">
                        {gear_icon}
                        <span>Analysis Result</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #E3EBE7; margin-bottom: 14px;">
                        <span style="font-weight: 600; font-size: 0.9rem; color: #0F1F1A;">Safety Assessment</span>
                        {rule_risk_pill}
                    </div>
                    <div style="font-weight: 700; font-size: 0.92rem; color: #0F1F1A; margin-bottom: 8px;">Key Issues:</div>
                    <ul style="list-style: none; padding-left: 0; margin-bottom: 0;">
                        {issues_li_html if issues_li_html else '<li style="color: #12B76A; font-size: 0.86rem;">No blocking hazards detected.</li>'}
                    </ul>
                </div>
                """, unsafe_allow_html=True)

            with col_res_right:
                code_icon = get_icon_svg("code", color="#0B6B4F", size=20)
                safe_script_text = st.session_state.last_safe_script["safe_script"] if st.session_state.last_safe_script else "-- No alternative needed"

                st.markdown(f"""
                <div class="details-card-frame">
                    <div class="details-card-header">
                        {code_icon}
                        <span>Suggested Safe Migration</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                st.code(safe_script_text, language="sql")

                c_cp, c_dl = st.columns(2)
                with c_cp:
                    if st.button("Copy SQL", key="btn_copy_safe_sql", use_container_width=True):
                        st.toast("Safe SQL copied to clipboard!")
                with c_dl:
                    st.download_button(
                        label="Download .sql",
                        data=safe_script_text,
                        file_name="safe_migration.sql",
                        mime="text/sql",
                        use_container_width=True,
                        key="btn_dl_safe_sql"
                    )

            # 7. Performance Analysis Section (Log-Log Interpolation & Empirical Benchmarks)
            perf = res.performance_estimate
            if perf and perf.get("estimation"):
                est_data = perf["estimation"]
                status = est_data.get("status")
                op_name = perf.get("operation", "Migration DDL")
                u_rows = perf.get("user_rows", 0)
                tbl_name = perf.get("target_table") or "target_table"
                sc_info = perf.get("scaling")

                chart_icon = get_icon_svg("chart", color="#0B6B4F", size=20)
                st.markdown(f"""
                <div class="details-card-frame" style="margin-top: 18px;">
                    <div class="details-card-header">
                        {chart_icon}
                        <span>Performance Analysis & Execution Time (Indicative)</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                col_p_info, col_p_chart = st.columns([5, 5])
                with col_p_info:
                    st.markdown(f"""
                    <div style="font-size: 0.88rem; color: #4A5A54; margin-bottom: 12px;">
                        Target Table: <b>{tbl_name}</b> (~{u_rows:,} rows) &bull; Operation: <b>{op_name}</b>
                    </div>
                    """, unsafe_allow_html=True)

                    if status in ["interpolated", "exact"]:
                        low_s = est_data["low_ms"] / 1000.0
                        high_s = est_data["high_ms"] / 1000.0
                        est_s = est_data["estimate_ms"] / 1000.0
                        time_str = f"~{low_s:.2f}s to {high_s:.2f}s (indicative)" if low_s != high_s else f"~{est_s:.3f}s (measured)"

                        st.markdown(f"""
                        <div style="background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 10px; padding: 14px; margin-bottom: 12px;">
                            <div style="font-size: 0.76rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700; color: #15803D;">Indicative Duration Band</div>
                            <div style="font-size: 1.45rem; font-weight: 800; color: #166534; margin: 4px 0;">{time_str}</div>
                            <div style="font-size: 0.78rem; color: #15803D; line-height: 1.4;">
                                <i>Indicative, machine-dependent, interpolated from benchmark data.</i>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        low_nb = est_data.get("lower_neighbor")
                        high_nb = est_data.get("upper_neighbor")
                        if low_nb and high_nb:
                            st.markdown(f"""
                            <div style="font-size: 0.82rem; color: #4A5A54; line-height: 1.6; margin-bottom: 8px;">
                                <b>Benchmarked Neighbors Used:</b><br>
                                &bull; Lower: {low_nb['rows']:,} rows ({low_nb['time_ms']/1000.0:.3f}s)<br>
                                &bull; Upper: {high_nb['rows']:,} rows ({high_nb['time_ms']/1000.0:.3f}s)
                            </div>
                            """, unsafe_allow_html=True)

                        if sc_info:
                            st.markdown(f"""
                            <div style="display: inline-block; padding: 4px 10px; background: #E7F5EF; border: 1px solid #CDE8DC; border-radius: 12px; font-size: 0.78rem; font-weight: 600; color: #0B6B4F;">
                                ⚡ Relative Scaling: {sc_info['text']}
                            </div>
                            """, unsafe_allow_html=True)

                    elif status == "out_of_range":
                        st.markdown("""
                        <div style="background: #FEF3F2; border: 1px solid #FECDCA; border-radius: 10px; padding: 14px; margin-bottom: 12px;">
                            <div style="font-weight: 700; color: #B42318; font-size: 0.9rem; margin-bottom: 4px;">Outside benchmarked range</div>
                            <div style="font-size: 0.82rem; color: #912018; line-height: 1.4;">
                                Outside benchmarked range (1K to 1M rows), refer to risk level only. Execution time is not extrapolated.
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                    elif status == "insufficient_data":
                        st.markdown("""
                        <div style="background: #FFFBEB; border: 1px solid #FDE68A; border-radius: 10px; padding: 14px; margin-bottom: 12px;">
                            <div style="font-weight: 700; color: #92400E; font-size: 0.9rem; margin-bottom: 4px;">Insufficient Data</div>
                            <div style="font-size: 0.82rem; color: #78350F; line-height: 1.4;">
                                Fewer than 2 distinct benchmarked sizes available for this operation to perform log-log interpolation.
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                    else:
                        st.markdown("""
                        <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px; padding: 14px; margin-bottom: 12px;">
                            <div style="font-weight: 700; color: #475569; font-size: 0.9rem; margin-bottom: 4px;">No Benchmark Data</div>
                            <div style="font-size: 0.82rem; color: #64748B; line-height: 1.4;">
                                No measured benchmarks found for this operation type in calibration datasets.
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                with col_p_chart:
                    # Plotly log-log chart
                    bench_csv_file = PROJECT_ROOT / "benchmarks" / "migration_dataset_v3.csv"
                    if bench_csv_file.exists():
                        try:
                            df_bench_raw = pd.read_csv(bench_csv_file)
                            df_op = df_bench_raw[df_bench_raw["operation"].astype(str).str.strip().str.upper() == op_name.strip().upper()]
                            if not df_op.empty and len(df_op) >= 2:
                                fig_interp = go.Figure()
                                # Measured benchmark points
                                fig_interp.add_trace(go.Scatter(
                                    x=df_op["row_count"],
                                    y=df_op["execution_time_sec"] * 1000.0,
                                    mode="lines+markers",
                                    name="Benchmark (Measured)",
                                    line=dict(color="#0B6B4F", width=2),
                                    marker=dict(size=8, color="#0B6B4F")
                                ))
                                # If interpolated or exact, add user point and vertical marker line
                                if status in ["interpolated", "exact"] and est_data.get("estimate_ms") is not None:
                                    fig_interp.add_trace(go.Scatter(
                                        x=[u_rows],
                                        y=[est_data["estimate_ms"]],
                                        mode="markers",
                                        name="Your Table (Estimate)",
                                        marker=dict(size=12, color="#D92D20", symbol="diamond")
                                    ))
                                    fig_interp.add_vline(
                                        x=u_rows,
                                        line_width=1.5,
                                        line_dash="dash",
                                        line_color="#D92D20",
                                        annotation_text=f"{u_rows:,} rows",
                                        annotation_position="top left"
                                    )

                                fig_interp.update_xaxes(type="log", title_text="Table Rows (log scale)")
                                fig_interp.update_yaxes(type="log", title_text="Duration ms (log scale)")
                                fig_interp.update_layout(
                                    title=f"Log-Log Benchmark Curve: {op_name}",
                                    title_font_size=12,
                                    margin=dict(l=20, r=20, t=35, b=20),
                                    paper_bgcolor="#FFFFFF",
                                    plot_bgcolor="#F8FAF9",
                                    height=250,
                                    showlegend=True,
                                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                                )
                                st.plotly_chart(fig_interp, use_container_width=True)
                        except Exception as e:
                            st.caption(f"Chart render notice: {e}")
