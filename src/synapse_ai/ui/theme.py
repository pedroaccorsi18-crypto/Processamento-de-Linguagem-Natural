from __future__ import annotations

from html import escape

import streamlit as st


def apply_synapse_theme() -> None:
    """Apply the Synapse AI visual language on top of Streamlit defaults."""
    st.markdown(
        """
        <style>
        :root {
            --synapse-bg: #f6f8fb;
            --synapse-surface: #ffffff;
            --synapse-ink: #0f172a;
            --synapse-muted: #667085;
            --synapse-faint: #98a2b3;
            --synapse-border: #d9e2ee;
            --synapse-nav: #0b1220;
            --synapse-nav-active: #172338;
            --synapse-brand: #2563eb;
            --synapse-brand-dark: #1d4ed8;
            --synapse-danger: #e11d48;
            --synapse-danger-soft: #fff1f2;
            --synapse-blue: #1d4ed8;
            --synapse-blue-soft: #eff6ff;
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

        #MainMenu,
        footer,
        [data-testid="stToolbar"],
        [data-testid="stDecoration"] {
            visibility: hidden !important;
            display: none !important;
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

        [data-testid="stSidebar"] [data-testid="stVerticalBlock"],
        [data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"],
        [data-testid="stSidebar"] [data-testid="stRadio"],
        [data-testid="stSidebar"] div[data-testid="stForm"] {
            background: transparent !important;
            border: 0 !important;
            box-shadow: none !important;
        }

        [data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] > div {
            background: transparent !important;
            border: 0 !important;
            box-shadow: none !important;
        }

        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] label {
            color: #dbe7f5 !important;
        }

        [data-testid="stSidebar"] h1 {
            color: #f8fafc !important;
            font-size: 1.55rem !important;
            font-weight: 850 !important;
            margin-bottom: 1.25rem !important;
        }

        [data-testid="stSidebar"] label > div:last-child {
            color: #c7d2e1 !important;
            font-weight: 650;
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

        [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) * {
            color: #ffffff !important;
        }

        [data-testid="stSidebar"] [role="radio"] {
            border-color: rgba(255, 255, 255, 0.42) !important;
        }

        [data-testid="stSidebar"] [role="radio"][aria-checked="true"] {
            background: var(--synapse-brand) !important;
            border-color: var(--synapse-brand) !important;
        }

        [data-testid="stMain"] [data-testid="block-container"] {
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

        .synapse-kpi-card {
            background: var(--synapse-surface);
            border: 1px solid var(--synapse-border);
            border-radius: var(--synapse-radius);
            padding: 1rem 1.05rem;
            min-height: 118px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }

        .synapse-kpi-card strong {
            display: block;
            color: var(--synapse-muted);
            font-size: 0.9rem;
            font-weight: 750;
            line-height: 1.25;
        }

        .synapse-kpi-card span {
            color: var(--synapse-ink);
            font-size: 2rem;
            font-weight: 850;
            line-height: 1;
            margin-top: 0.75rem;
        }

        .synapse-kpi-card small {
            color: var(--synapse-muted);
            font-size: 0.78rem;
            line-height: 1.35;
            margin-top: 0.7rem;
        }

        .synapse-kpi-card.is-blue {
            border-color: #bfdbfe;
            background: #f8fbff;
        }

        .synapse-kpi-card.is-green {
            border-color: #bbf7d0;
            background: #f7fef9;
        }

        .synapse-kpi-card.is-amber {
            border-color: #fde68a;
            background: #fffdf4;
        }

        .synapse-kpi-card.is-red {
            border-color: #fecdd3;
            background: #fff8f9;
        }

        .synapse-status-badge {
            display: inline-flex;
            align-items: center;
            width: fit-content;
            border-radius: 999px;
            padding: 0.24rem 0.62rem;
            font-size: 0.78rem;
            font-weight: 800;
            line-height: 1;
            border: 1px solid transparent;
            white-space: nowrap;
        }

        .synapse-status-badge.is-pending {
            color: #92400e;
            background: #fffbeb;
            border-color: #fde68a;
        }

        .synapse-status-badge.is-running {
            color: #1d4ed8;
            background: #eff6ff;
            border-color: #bfdbfe;
        }

        .synapse-status-badge.is-done {
            color: #047857;
            background: #ecfdf5;
            border-color: #bbf7d0;
        }

        .synapse-document-card {
            background: var(--synapse-surface);
            border: 1px solid var(--synapse-border);
            border-radius: var(--synapse-radius);
            padding: 1rem;
            margin-bottom: 0.75rem;
        }

        .synapse-document-card h3 {
            margin: 0 0 0.55rem 0;
            font-size: 1rem !important;
            line-height: 1.25 !important;
        }

        .synapse-document-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem 0.6rem;
            align-items: center;
            color: var(--synapse-muted);
            font-size: 0.86rem;
        }

        .synapse-step-list {
            margin: 0.25rem 0 0.75rem 0;
            padding-left: 1.15rem;
            color: var(--synapse-ink);
        }

        .synapse-step-list li {
            margin: 0.35rem 0;
            line-height: 1.45;
        }

        .synapse-empty-state {
            background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
            border: 1px dashed #bcd0ea;
            border-radius: var(--synapse-radius-lg);
            padding: 1.35rem;
            margin: 0.85rem 0 1.25rem 0;
        }

        .synapse-empty-state-icon {
            width: 38px;
            height: 38px;
            border-radius: 12px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: var(--synapse-blue-soft);
            color: var(--synapse-brand-dark);
            font-size: 1.25rem;
            font-weight: 850;
            margin-bottom: 0.8rem;
        }

        .synapse-empty-state strong {
            display: block;
            color: var(--synapse-ink);
            font-size: 1.05rem;
            font-weight: 850;
            margin-bottom: 0.35rem;
        }

        .synapse-empty-state p {
            color: var(--synapse-muted);
            line-height: 1.5;
            margin: 0;
            max-width: 720px;
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

        [data-testid="stMain"] [data-testid="stVerticalBlockBorderWrapper"],
        [data-testid="stMain"] [data-testid="stExpander"],
        [data-testid="stMain"] div[data-testid="stForm"] {
            background: var(--synapse-surface);
            border-color: var(--synapse-border) !important;
            border-radius: var(--synapse-radius) !important;
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
            color: var(--synapse-ink) !important;
            opacity: 1 !important;
        }

        div[data-testid="stAlert"] [data-testid="stMarkdownContainer"],
        div[data-testid="stAlert"] [data-testid="stMarkdownContainer"] *,
        div[data-testid="stAlert"] p,
        div[data-testid="stAlert"] span,
        div[data-testid="stAlert"] li,
        div[data-testid="stAlert"] div {
            color: var(--synapse-ink) !important;
            opacity: 1 !important;
        }

        div[data-testid="stAlert"] p {
            line-height: 1.45;
        }

        div[data-testid="stAlert"] a {
            color: var(--synapse-brand-dark) !important;
            font-weight: 700;
        }

        div[data-testid="stAlert"] svg {
            color: currentColor !important;
            opacity: 1 !important;
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

        @media (max-width: 768px) {
            [data-testid="stMain"] [data-testid="block-container"] {
                padding-top: 2rem;
                padding-bottom: 5rem;
            }

            div[data-testid="stAlert"] {
                padding: 0.85rem 0.95rem !important;
                color: var(--synapse-ink) !important;
            }

            div[data-testid="stAlert"] [data-testid="stMarkdownContainer"],
            div[data-testid="stAlert"] [data-testid="stMarkdownContainer"] *,
            div[data-testid="stAlert"] p,
            div[data-testid="stAlert"] span,
            div[data-testid="stAlert"] li,
            div[data-testid="stAlert"] div {
                color: var(--synapse-ink) !important;
                opacity: 1 !important;
            }

            div[data-testid="stAlert"] p {
                margin-bottom: 0 !important;
                font-size: 0.95rem;
                line-height: 1.45;
            }

            .synapse-page-header {
                margin-bottom: 1.15rem;
            }

            .synapse-page-header h1 {
                font-size: 2rem;
            }

            .synapse-callout {
                padding: 1rem;
            }

            .synapse-kpi-card {
                min-height: auto;
                padding: 0.9rem;
            }

            .synapse-kpi-card span {
                font-size: 1.7rem;
            }

            .synapse-document-card {
                padding: 0.9rem;
            }

            .synapse-empty-state {
                padding: 1rem;
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


def render_kpi_card(
    label: str,
    value: str | int,
    detail: str,
    *,
    tone: str = "blue",
) -> None:
    """Render a compact KPI card with explicit visual hierarchy."""
    tone_class = _safe_tone(tone)
    st.markdown(
        f"""
        <div class="synapse-kpi-card is-{tone_class}">
            <strong>{escape(label)}</strong>
            <span>{escape(str(value))}</span>
            <small>{escape(detail)}</small>
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_badge_html(status: str, *, label: str | None = None) -> str:
    """Return a reusable HTML badge for document and process statuses."""
    normalized = _normalize_status(status)
    display_label = label or _status_label(normalized, status)
    return (
        f'<span class="synapse-status-badge is-{normalized}">'
        f"{escape(display_label)}</span>"
    )


def render_status_badge(status: str, *, label: str | None = None) -> None:
    st.markdown(status_badge_html(status, label=label), unsafe_allow_html=True)


def render_document_card(
    title: str,
    metadata: list[str],
    *,
    status: str,
    status_label: str | None = None,
) -> None:
    metadata_html = "".join(f"<span>{escape(item)}</span>" for item in metadata if item)
    st.markdown(
        f"""
        <div class="synapse-document-card">
            <h3>{escape(title)}</h3>
            <div class="synapse-document-meta">
                {status_badge_html(status, label=status_label)}
                {metadata_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_empty_state(title: str, body: str, *, icon: str = "IA") -> None:
    """Render a persuasive empty state for corporate workflows."""
    st.markdown(
        f"""
        <div class="synapse-empty-state">
            <div class="synapse-empty-state-icon">{escape(icon)}</div>
            <strong>{escape(title)}</strong>
            <p>{escape(body)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _safe_tone(tone: str) -> str:
    return tone if tone in {"blue", "green", "amber", "red"} else "blue"


def _normalize_status(status: str) -> str:
    normalized = status.strip().lower()
    if normalized in {"concluido", "concluído", "done", "prepared", "extracted"}:
        return "done"
    if normalized in {"em analise", "em análise", "running", "processing"}:
        return "running"
    return "pending"


def _status_label(normalized: str, fallback: str) -> str:
    labels = {
        "pending": "Pendente",
        "running": "Em análise",
        "done": "Concluído",
    }
    return labels.get(normalized, fallback)
