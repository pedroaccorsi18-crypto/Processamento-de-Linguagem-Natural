from __future__ import annotations

from html import escape

import streamlit as st


def apply_synapse_theme() -> None:
    """Apply the Synapse AI visual language on top of Streamlit defaults."""
    st.markdown(
        """
        <style>
        :root {
            --synapse-bg: #f5f7fb;
            --synapse-surface: #ffffff;
            --synapse-ink: #111827;
            --synapse-muted: #667085;
            --synapse-faint: #98a2b3;
            --synapse-border: #dbe2ea;
            --synapse-nav: #0f141f;
            --synapse-nav-active: #192131;
            --synapse-brand: #f32945;
            --synapse-brand-dark: #d81e38;
            --synapse-blue: #1457c8;
            --synapse-blue-soft: #eaf3ff;
            --synapse-green: #07864f;
            --synapse-green-soft: #e8f8ee;
            --synapse-amber: #b56a08;
            --synapse-amber-soft: #fff4ce;
            --synapse-radius: 10px;
            --synapse-radius-lg: 14px;
        }

        html, body, [class*="css"] {
            font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            letter-spacing: 0;
        }

        .stApp,
        [data-testid="stAppViewContainer"] {
            background: var(--synapse-bg);
            color: var(--synapse-ink);
        }

        [data-testid="stHeader"] {
            background: rgba(245, 247, 251, 0.86);
            backdrop-filter: blur(10px);
        }

        [data-testid="stSidebar"] > div:first-child {
            background: var(--synapse-nav);
            border-right: 1px solid rgba(255, 255, 255, 0.06);
        }

        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] label {
            color: #edf2f7 !important;
        }

        [data-testid="stSidebar"] [role="radiogroup"] label {
            min-height: 42px;
            border-radius: 8px;
            padding: 8px 10px;
            margin: 3px 0;
            transition: background 0.15s ease, color 0.15s ease;
        }

        [data-testid="stSidebar"] [role="radiogroup"] label:hover {
            background: var(--synapse-nav-active);
        }

        [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
            background: var(--synapse-nav-active);
            box-shadow: inset 4px 0 0 var(--synapse-brand);
        }

        [data-testid="stSidebar"] [role="radio"] {
            border-color: rgba(255, 255, 255, 0.42) !important;
        }

        [data-testid="stSidebar"] [role="radio"][aria-checked="true"] {
            background: var(--synapse-brand) !important;
            border-color: var(--synapse-brand) !important;
        }

        [data-testid="block-container"] {
            max-width: 1180px;
            padding-top: 3.25rem;
            padding-bottom: 4rem;
        }

        h1, h2, h3 {
            color: var(--synapse-ink);
            letter-spacing: 0 !important;
        }

        h1 {
            font-size: 2.35rem !important;
            line-height: 1.08 !important;
            font-weight: 800 !important;
        }

        h2, h3 {
            font-weight: 750 !important;
        }

        .synapse-page-header {
            margin: 0 0 1.6rem 0;
        }

        .synapse-eyebrow {
            color: var(--synapse-brand);
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin-bottom: 0.55rem;
        }

        .synapse-page-header h1 {
            margin: 0;
            color: var(--synapse-ink);
            font-size: clamp(2rem, 3vw, 2.6rem);
            line-height: 1.08;
            font-weight: 850;
        }

        .synapse-page-header p {
            max-width: 820px;
            margin: 0.55rem 0 0 0;
            color: var(--synapse-muted);
            font-size: 1rem;
            line-height: 1.5;
        }

        .synapse-callout {
            background: var(--synapse-surface);
            border: 1px solid var(--synapse-border);
            border-radius: var(--synapse-radius-lg);
            padding: 1.25rem 1.35rem;
            margin: 0.85rem 0 1.25rem 0;
        }

        .synapse-callout strong {
            color: var(--synapse-ink);
        }

        .synapse-callout p {
            color: var(--synapse-muted);
            margin: 0.3rem 0 0 0;
            line-height: 1.45;
        }

        [data-testid="stMetric"] {
            background: var(--synapse-surface);
            border: 1px solid var(--synapse-border);
            border-radius: var(--synapse-radius);
            padding: 1rem 1.05rem;
            min-height: 104px;
        }

        [data-testid="stMetricLabel"] {
            color: var(--synapse-muted);
            font-weight: 650;
        }

        [data-testid="stMetricValue"] {
            color: var(--synapse-ink);
            font-weight: 800;
        }

        [data-testid="stVerticalBlockBorderWrapper"],
        [data-testid="stExpander"],
        div[data-testid="stForm"] {
            background: var(--synapse-surface);
            border-color: var(--synapse-border) !important;
            border-radius: var(--synapse-radius-lg) !important;
            box-shadow: none !important;
        }

        .stDataFrame,
        [data-testid="stDataFrame"] {
            border-radius: var(--synapse-radius) !important;
            overflow: hidden;
        }

        .stButton > button,
        .stDownloadButton > button,
        [data-testid="stLinkButton"] a {
            border-radius: 8px !important;
            min-height: 42px;
            border: 1px solid var(--synapse-brand) !important;
            background: var(--synapse-brand) !important;
            color: white !important;
            font-weight: 750 !important;
            box-shadow: none !important;
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover,
        [data-testid="stLinkButton"] a:hover {
            border-color: var(--synapse-brand-dark) !important;
            background: var(--synapse-brand-dark) !important;
            color: white !important;
        }

        .stButton > button:disabled,
        .stDownloadButton > button:disabled {
            background: #eef2f6 !important;
            border-color: #e4e7ec !important;
            color: var(--synapse-faint) !important;
        }

        input,
        textarea,
        [data-baseweb="select"] > div,
        [data-baseweb="tag"],
        [data-testid="stFileUploaderDropzone"] {
            border-radius: 10px !important;
        }

        [data-testid="stFileUploaderDropzone"] {
            background: #f7fbff;
            border-color: #adc8f0 !important;
        }

        div[data-testid="stAlert"] {
            border-radius: var(--synapse-radius) !important;
            border: 1px solid transparent;
        }

        div[data-testid="stAlert"] p {
            line-height: 1.45;
        }

        hr {
            margin: 2rem 0 !important;
            border-color: var(--synapse-border) !important;
        }

        .stProgress > div > div > div {
            background-color: var(--synapse-brand) !important;
        }

        .synapse-public-grid {
            display: grid;
            grid-template-columns: minmax(0, 1fr) minmax(280px, 420px);
            gap: 1.25rem;
            align-items: stretch;
        }

        .synapse-hero-panel {
            background: #111827;
            border-radius: 18px;
            padding: 2rem;
            color: white;
            min-height: 260px;
        }

        .synapse-hero-panel h2 {
            color: white;
            margin: 0 0 1rem 0;
            font-size: 1.6rem;
        }

        .synapse-hero-panel p {
            color: #cbd5e1;
            line-height: 1.55;
        }

        @media (max-width: 900px) {
            [data-testid="block-container"] {
                padding-left: 1rem;
                padding-right: 1rem;
            }

            .synapse-public-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(title: str, subtitle: str, eyebrow: str | None = None) -> None:
    eyebrow_html = (
        f'<div class="synapse-eyebrow">{escape(eyebrow)}</div>' if eyebrow else ""
    )
    st.markdown(
        f"""
        <section class="synapse-page-header">
            {eyebrow_html}
            <h1>{escape(title)}</h1>
            <p>{escape(subtitle)}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_callout(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="synapse-callout">
            <strong>{escape(title)}</strong>
            <p>{escape(body)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
