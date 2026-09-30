"""Day 13 Monitoring dashboard — 6 panels from data/logs.jsonl."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
DASHBOARD_CFG = REPO_ROOT / "config" / "dashboard.yaml"
SLO_CFG = REPO_ROOT / "config" / "slo.yaml"


def load_logs() -> pd.DataFrame:
    if not LOG_PATH.exists():
        return pd.DataFrame()
    rows = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "ts" in df.columns:
        df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
    return df


def percentile(series: pd.Series, q: float) -> float:
    if series.empty:
        return float("nan")
    return float(np.percentile(series.dropna().astype(float), q))


def main() -> None:
    st.set_page_config(page_title="Day 13 Monitoring & LLMOps", layout="wide")
    cfg = yaml.safe_load(DASHBOARD_CFG.read_text(encoding="utf-8"))["dashboard"]
    slo = yaml.safe_load(SLO_CFG.read_text(encoding="utf-8"))
    time_range = cfg.get("time_range_minutes", 60)

    st.title(cfg.get("title", "Day 13 Monitoring & LLMOps"))
    st.caption(
        f"Source: data/logs.jsonl | Time range: last {time_range} minutes | "
        f"Refresh: {cfg.get('refresh_seconds', 30)}s | "
        f"SLO: {slo['primary_slo']['target_percent']}% success & latency ≤ 3000ms | "
        f"Error budget: {slo['primary_slo']['error_budget_percent']}%"
    )

    df = load_logs()
    if df.empty or "ts" not in df.columns:
        st.warning("No logs found. Run the API and load_test.py first.")
        return

    cutoff = pd.Timestamp.utcnow() - pd.Timedelta(minutes=time_range)
    # pandas Timestamp.utcnow is timezone-aware in recent versions; normalize
    if df["ts"].dt.tz is None:
        df["ts"] = df["ts"].dt.tz_localize("UTC")
    window = df[df["ts"] >= cutoff].copy()
    if window.empty:
        window = df.copy()
        st.info("No events in last hour; showing all available logs.")

    responses = window[window["event"] == "response_sent"]
    received = window[window["event"] == "request_received"]
    failed = window[window["event"] == "request_failed"]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("1. Latency percentiles and TTFT")
        st.caption("Unit: ms | Threshold: P95 ≤ 3000ms (SLO)")
        if responses.empty:
            st.write("No response_sent events")
        else:
            p50 = percentile(responses["latency_ms"], 50)
            p95 = percentile(responses["latency_ms"], 95)
            p99 = percentile(responses["latency_ms"], 99)
            ttft_p95 = percentile(responses["ttft_ms"], 95)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("P50", f"{p50:.0f}")
            m2.metric("P95", f"{p95:.0f}")
            m3.metric("P99", f"{p99:.0f}")
            m4.metric("TTFT P95", f"{ttft_p95:.0f}")
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=responses["ts"],
                    y=responses["latency_ms"],
                    mode="markers+lines",
                    name="latency_ms",
                )
            )
            fig.add_hline(y=3000, line_dash="dash", annotation_text="SLO P95=3000ms")
            fig.update_layout(height=280, yaxis_title="ms", margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("2. Request traffic")
        st.caption("Unit: requests_per_minute | Threshold: rate ≥ 1")
        if received.empty:
            st.write("No request_received events")
        else:
            traffic = (
                received.set_index("ts")
                .resample("1min")
                .size()
                .rename("rpm")
                .reset_index()
            )
            st.metric("Total requests", len(received))
            st.metric("Avg RPM", f"{traffic['rpm'].mean():.1f}")
            fig = px.bar(traffic, x="ts", y="rpm", labels={"rpm": "requests/min"})
            fig.add_hline(y=1, line_dash="dash", annotation_text="threshold=1")
            fig.update_layout(height=280, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig, use_container_width=True)

    with col3:
        st.subheader("3. Error rate and retrieval success")
        st.caption("Unit: percent | Threshold: error_rate ≤ 2%")
        total_req = max(len(received), 1)
        error_rate = len(failed) / total_req * 100
        tool_rows = window[window["tool_success"].notna()] if "tool_success" in window.columns else pd.DataFrame()
        if not tool_rows.empty:
            retrieval_ok = (tool_rows["tool_success"] == True).sum() / len(tool_rows) * 100  # noqa: E712
        else:
            retrieval_ok = float("nan")
        st.metric("Error rate %", f"{error_rate:.2f}")
        st.metric("Retrieval success %", f"{retrieval_ok:.1f}" if not np.isnan(retrieval_ok) else "n/a")
        if "error_type" in failed.columns and not failed.empty:
            breakdown = failed["error_type"].value_counts().reset_index()
            breakdown.columns = ["error_type", "count"]
            fig = px.bar(breakdown, x="error_type", y="count")
            fig.update_layout(height=220, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write("No errors in window")

    col4, col5, col6 = st.columns(3)
    with col4:
        st.subheader("4. Cost over time")
        st.caption("Unit: usd | Threshold: total ≤ 2.5")
        if responses.empty or "cost_usd" not in responses.columns:
            st.write("No cost data")
        else:
            total_cost = float(responses["cost_usd"].sum())
            st.metric("Total cost USD", f"{total_cost:.6f}")
            cost = (
                responses.set_index("ts")["cost_usd"]
                .resample("1min")
                .sum()
                .reset_index()
            )
            fig = px.line(cost, x="ts", y="cost_usd", labels={"cost_usd": "USD / min"})
            fig.add_hline(y=2.5, line_dash="dash", annotation_text="daily max 2.5")
            fig.update_layout(height=280, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig, use_container_width=True)

    with col5:
        st.subheader("5. Input and output tokens")
        st.caption("Unit: tokens | Threshold: sum ≤ 50000")
        if responses.empty:
            st.write("No token data")
        else:
            tin = int(responses["tokens_in"].sum()) if "tokens_in" in responses.columns else 0
            tout = int(responses["tokens_out"].sum()) if "tokens_out" in responses.columns else 0
            st.metric("Tokens in", tin)
            st.metric("Tokens out", tout)
            st.metric("Total tokens", tin + tout)
            token_df = pd.DataFrame(
                {"field": ["tokens_in", "tokens_out"], "sum": [tin, tout]}
            )
            fig = px.bar(token_df, x="field", y="sum")
            fig.add_hline(y=50000, line_dash="dash", annotation_text="threshold=50000")
            fig.update_layout(height=280, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig, use_container_width=True)

    with col6:
        st.subheader("6. Quality proxy")
        st.caption("Unit: score_0_to_1 | Threshold: mean ≥ 0.75")
        if responses.empty or "quality_score" not in responses.columns:
            st.write("No quality data")
        else:
            mean_q = float(responses["quality_score"].mean())
            st.metric("Mean quality", f"{mean_q:.2f}")
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=responses["ts"],
                    y=responses["quality_score"],
                    mode="markers+lines",
                    name="quality_score",
                )
            )
            fig.add_hline(y=0.75, line_dash="dash", annotation_text="min 0.75")
            fig.update_layout(height=280, yaxis_title="score", margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    main()
