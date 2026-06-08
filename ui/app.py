# ui/app.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import tempfile
import os
from datetime import datetime

st.set_page_config(
    page_title="Metric Watchdog",
    page_icon="🐕",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif !important; }
#MainMenu, footer, header { visibility: hidden; }
.stApp { background: linear-gradient(135deg, #0a1628 0%, #0f1e2e 100%); }

[data-testid="stSidebar"] {
    background: rgba(15,30,46,0.95) !important;
    border-right: 1px solid rgba(255,255,255,0.08) !important;
}

.stTabs [data-baseweb="tab-list"] {
    background: rgba(255,255,255,0.03) !important;
    border-radius: 10px !important;
    padding: 4px !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    color: #94a3b8 !important;
}
.stTabs [aria-selected="true"] {
    background: #3b82f6 !important;
    color: white !important;
    font-weight: 600 !important;
}

.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #3b82f6, #1d4ed8) !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 14px rgba(59,130,246,0.3) !important;
    transition: all 0.2s ease !important;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(59,130,246,0.4) !important;
}

[data-testid="stMetric"] {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 12px !important;
    padding: 1rem !important;
}

.briefing-box {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 1.5rem;
    font-family: 'DM Sans', sans-serif;
    white-space: pre-wrap;
    font-size: 0.88rem;
    line-height: 1.7;
    color: #e2e8f0;
}

.severity-critical {
    display: inline-block;
    background: rgba(220,38,38,0.15);
    border: 1px solid rgba(220,38,38,0.4);
    color: #f87171;
    border-radius: 6px;
    padding: 0.2rem 0.6rem;
    font-family: 'DM Mono', monospace;
    font-size: 0.75rem;
    font-weight: 600;
}
.severity-warning {
    display: inline-block;
    background: rgba(217,119,6,0.15);
    border: 1px solid rgba(217,119,6,0.4);
    color: #fbbf24;
    border-radius: 6px;
    padding: 0.2rem 0.6rem;
    font-family: 'DM Mono', monospace;
    font-size: 0.75rem;
    font-weight: 600;
}
.severity-normal {
    display: inline-block;
    background: rgba(22,163,74,0.15);
    border: 1px solid rgba(22,163,74,0.4);
    color: #4ade80;
    border-radius: 6px;
    padding: 0.2rem 0.6rem;
    font-family: 'DM Mono', monospace;
    font-size: 0.75rem;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)


# ── Sidebar ──────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding: 1rem 0 0.5rem 0;">
        <div style="font-size: 1.5rem; font-weight: 700; color: #e2e8f0;">
            🐕 Metric Watchdog
        </div>
        <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 0.2rem;">
            Autonomous morning intelligence
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    # Schedule status
    from config.settings import settings
    from core.scheduler import load_schedule
    schedule = load_schedule()

    st.markdown("**⏰ Schedule**")
    enabled = schedule.get("enabled", True)
    st.markdown(
        f"{'🟢 Active' if enabled else '🔴 Disabled'} — "
        f"Daily at **{schedule.get('hour', 8):02d}:{schedule.get('minute', 0):02d}** "
        f"{schedule.get('timezone', 'UTC')}"
    )

    st.markdown("---")
    st.markdown("**🔌 Providers**")
    st.caption(f"LLM: `{settings.llm_provider}`")
    st.caption(f"Vision: `{settings.vision_provider}`")
    st.caption(f"DB: Postgres")

    st.markdown("---")
    st.caption("Email: " + ("✅ enabled" if settings.email_enabled else "⬜ disabled"))
    st.caption("Slack: " + ("✅ enabled" if settings.slack_enabled else "⬜ disabled"))


# ── Main area ────────────────────────────────────────────────────
st.markdown("""
<div style="padding: 1.5rem 0 1rem 0;">
    <div style="font-size: 2rem; font-weight: 700; color: #e2e8f0;
                letter-spacing: -0.03em;">
        Metric Watchdog
    </div>
    <div style="color: #94a3b8; font-size: 0.95rem; margin-top: 0.3rem;">
        Reads your dashboard. Reasons through it. Diagnoses via SQL.
        Delivers a sourced briefing.
    </div>
</div>
""", unsafe_allow_html=True)
st.markdown("---")

tab1, tab2, tab3 = st.tabs([
    "▶ Run",
    "📋 History",
    "📄 Logs",
])


# ════════════════════════════════════════════════════════════════
# TAB 1 — RUN
# ════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("Run Pipeline")
    st.caption("Upload a dashboard screenshot and trigger the pipeline manually.")

    col1, col2 = st.columns([2, 1])

    with col1:
        uploaded = st.file_uploader(
            "Dashboard screenshot",
            type=["png", "jpg", "jpeg"],
            help="Upload a PNG or JPG screenshot of your dashboard",
        )

    with col2:
        st.markdown("**Schema source**")
        schema_source = st.radio(
            "Schema",
            ["Auto-discover from Postgres", "Upload .sql file"],
            label_visibility="collapsed",
        )

        schema_file = None
        if schema_source == "Upload .sql file":
            schema_file = st.file_uploader(
                "Schema file",
                type=["sql"],
                key="schema_upload",
            )

    if uploaded:
        st.image(uploaded, caption="Dashboard to analyse", width="stretch")

    st.markdown("---")

    run_btn = st.button(
        "🚀 Run Morning Intelligence",
        type="primary",
        disabled=uploaded is None,
        use_container_width=False,
    )

    if run_btn and uploaded:
        # Save uploaded image to temp file
        with tempfile.NamedTemporaryFile(
            suffix=f".{uploaded.name.split('.')[-1]}",
            delete=False,
        ) as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name

        # Load schema if provided
        schema = None
        if schema_file:
            with tempfile.NamedTemporaryFile(
                suffix=".sql", delete=False, mode="w"
            ) as tmp_sql:
                tmp_sql.write(schema_file.read().decode())
                from core.schema import load_from_file
                schema = load_from_file(tmp_sql.name)

        # Run pipeline
        with st.spinner("Running pipeline... this may take 2-5 minutes"):
            from agents.orchestrator import run_pipeline
            result = run_pipeline(tmp_path, schema=schema)
            os.unlink(tmp_path)

        # Show results
        briefing = result.briefing
        if briefing:
            severity = briefing.overall_severity
            sev_class = (
                "severity-critical" if severity == "CRITICAL"
                else "severity-warning" if severity == "WARNING"
                else "severity-normal"
            )

            st.markdown(f"""
            <div style="display:flex; align-items:center; gap:1rem; margin:1rem 0;">
                <span class="{sev_class}">{severity}</span>
                <span style="color:#94a3b8; font-size:0.85rem;">
                    {result.run_id} · {result.duration_seconds:.1f}s
                </span>
            </div>
            """, unsafe_allow_html=True)

            # Metrics summary
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Metrics Read", len(result.dashboard_reading.metrics))
            col2.metric("Concerning", len(result.reasoning.concerning_metrics))
            col3.metric(
                "Proven Claims",
                sum(len(b.proven) for b in result.evidence_bundles)
            )
            col4.metric(
                "Unverified Gaps",
                sum(len(b.unresolvable) for b in result.evidence_bundles)
            )

            st.markdown("---")

            # Briefing text
            st.subheader("Morning Briefing")
            st.markdown(
                f'<div class="briefing-box">{briefing.briefing_text}</div>',
                unsafe_allow_html=True,
            )

            # Download HTML
            st.download_button(
                label="⬇ Download HTML Briefing",
                data=briefing.briefing_html,
                file_name=f"briefing_{result.run_id}.html",
                mime="text/html",
            )


# ════════════════════════════════════════════════════════════════
# TAB 2 — HISTORY
# ════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("Run History")
    st.caption("All past pipeline runs.")

    from core.history_store import get_recent_runs
    runs = get_recent_runs(limit=30)

    if not runs:
        st.info("No runs yet. Upload a dashboard and run the pipeline.")
    else:
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Runs", len(runs))
        critical = sum(1 for r in runs if r["severity"] == "CRITICAL")
        warning = sum(1 for r in runs if r["severity"] == "WARNING")
        col2.metric("Critical", critical)
        col3.metric("Warning", warning)
        avg_duration = sum(r["duration_s"] or 0 for r in runs) / len(runs)
        col4.metric("Avg Duration", f"{avg_duration:.0f}s")

        st.markdown("---")

        for run in runs:
            severity = run.get("severity", "UNKNOWN")
            sev_icon = (
                "🔴" if severity == "CRITICAL"
                else "🟡" if severity == "WARNING"
                else "🟢"
            )
            started = run.get("started_at", "")[:16].replace("T", " ")
            duration = run.get("duration_s", 0) or 0

            with st.expander(
                f"{sev_icon} {started} — {severity} — "
                f"{run.get('metrics_count', 0)} metrics — "
                f"{duration:.0f}s",
                expanded=False,
            ):
                col1, col2, col3 = st.columns(3)
                col1.metric("Proven Claims", run.get("proven_count", 0))
                col2.metric("Unresolvable", run.get("unresolvable_count", 0))
                col3.metric("Run ID", run.get("run_id", "")[-8:])

                if briefing_text := run.get("briefing_text"):
                    st.markdown("**Briefing:**")
                    st.markdown(
                        f'<div class="briefing-box">{briefing_text[:2000]}...</div>',
                        unsafe_allow_html=True,
                    )

                if html := run.get("briefing_html"):
                    st.download_button(
                        label="⬇ Download HTML",
                        data=html,
                        file_name=f"briefing_{run.get('run_id', 'unknown')}.html",
                        mime="text/html",
                        key=f"dl_{run.get('run_id')}",
                    )


# ════════════════════════════════════════════════════════════════
# TAB 3 — LOGS
# ════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("Run Logs")
    st.caption("Live log viewer — shows SQL queries, failures, and stage timing.")

    log_dir = Path("logs")
    if not log_dir.exists() or not list(log_dir.glob("*.log")):
        st.info("No log files yet. Run the pipeline to generate logs.")
    else:
        # File selector
        log_files = sorted(log_dir.glob("*.log"), reverse=True)
        selected_log = st.selectbox(
            "Log file",
            options=[f.name for f in log_files],
            index=0,
        )

        log_path = log_dir / selected_log
        log_content = log_path.read_text(encoding="utf-8")

        # Filter options
        col1, col2 = st.columns(2)
        with col1:
            filter_stage = st.selectbox(
                "Filter by stage",
                ["All", "reader", "reasoning", "diagnosis", "diagnosis:sql",
                 "narrator", "delivery", "schema"],
            )
        with col2:
            filter_level = st.selectbox(
                "Filter by level",
                ["All", "ERROR", "WARNING", "INFO"],
            )

        # Apply filters
        lines = log_content.split("\n")
        if filter_stage != "All":
            lines = [l for l in lines if f"[{filter_stage}]" in l]
        if filter_level != "All":
            lines = [l for l in lines if f"| {filter_level} |" in l]

        filtered = "\n".join(lines)

        # Highlight errors in red
        st.markdown("---")

        # Show line count
        st.caption(f"{len(lines)} lines shown")

        # Display log
        st.code(filtered or "No matching log entries.", language=None)

        # Refresh button
        if st.button("🔄 Refresh", key="refresh_logs"):
            st.rerun()

        # Download
        st.download_button(
            label="⬇ Download Log",
            data=log_content,
            file_name=selected_log,
            mime="text/plain",
        )