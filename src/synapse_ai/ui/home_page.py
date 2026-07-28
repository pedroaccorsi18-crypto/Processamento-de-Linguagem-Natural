from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

LANDING_ACCESS_REQUESTED_KEY = "synapse_landing_access_requested"


def render_home_page() -> None:
    """Render the public conversion landing page.

    This page ends at `_render_case_study_section()`. The authenticated app starts in
    `app.py`, after `is_authenticated()` returns true and routes to `render_dashboard_page()`.
    """
    _render_telemetry()
    _render_hero_section()
    _render_case_study_section()


def _render_telemetry() -> None:
    """Inject optional pageview telemetry configured in Streamlit secrets.

    Example `.streamlit/secrets.toml`:

    [telemetry]
    posthog_key = "phc_xxx"
    posthog_host = "https://app.posthog.com"
    google_analytics_id = "G-XXXXXXXXXX"
    """
    telemetry = _telemetry_settings()
    posthog_key = str(telemetry.get("posthog_key") or "")
    google_analytics_id = str(telemetry.get("google_analytics_id") or "")

    if posthog_key:
        posthog_host = str(telemetry.get("posthog_host") or "https://app.posthog.com")
        components.html(_posthog_script(posthog_key, posthog_host), height=0, width=0)
    if google_analytics_id:
        components.html(_google_analytics_script(google_analytics_id), height=0, width=0)


def _render_hero_section() -> None:
    st.markdown(
        """
        <section class="synapse-landing-hero">
            <div class="synapse-eyebrow">Synapse AI</div>
            <h1>Transforme Dados Ocultos em Inteligência Corporativa Ativa.</h1>
            <p>
                O Synapse AI orquestra o conhecimento institucional da sua organização.
                Transforme contratos, PDFs e transcrições desestruturadas em respostas
                precisas e decisões estratégicas em segundos. Pare de procurar. Comece a decidir.
            </p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    _, center_col, _ = st.columns((0.32, 0.36, 0.32))
    with center_col:
        if st.button("Acessar Plataforma", type="primary", use_container_width=True):
            st.session_state[LANDING_ACCESS_REQUESTED_KEY] = True
            st.session_state["pending_public_page"] = "login"
            st.rerun()


def _render_case_study_section() -> None:
    st.markdown(
        """
        <section class="synapse-section-heading">
            <h2>Como o Synapse AI redefine a análise de dados</h2>
        </section>
        """,
        unsafe_allow_html=True,
    )
    before_col, after_col = st.columns(2)
    with before_col:
        st.markdown("### O Caos (Antes)")
        st.write(
            "O conhecimento da sua empresa está preso em silos. Analistas perdem horas "
            "vasculhando dezenas de páginas, relatórios e transcrições cruzadas. O resultado? "
            "Decisões lentas baseadas em informações fragmentadas."
        )
        st.info("Placeholder visual: screenshot_caos_dados.png")
    with after_col:
        st.markdown("### A Síntese (Depois)")
        st.write(
            "Orquestração Multiagente em ação. O Synapse AI lê, cruza e sintetiza milhares "
            "de páginas instantaneamente. Receba relatórios executivos sob demanda, com links "
            "diretos para as fontes originais."
        )
        st.success("Placeholder visual: screenshot_dashboard_inteligencia.png")


def _telemetry_settings() -> Mapping[str, Any]:
    try:
        telemetry = st.secrets.get("telemetry", {})
    except Exception:  # noqa: BLE001
        return {}
    return telemetry if isinstance(telemetry, Mapping) else {}


def _posthog_script(project_key: str, host: str) -> str:
    return f"""
    <script>
    !function(t,e){{var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){{
    function g(t,e){{var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){{
    t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}}}(p=t.createElement("script")).type="text/javascript";
    p.crossOrigin="anonymous";p.async=!0;p.src=s.api_host+"/static/array.js";
    (r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;
    for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){{
    var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e}},
    u.people.toString=function(){{return u.toString(1)+".people (stub)"}},
    o="capture identify alias people.set people.set_once".split(" "),
    n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])}},e.__SV=1)}}(document,window.posthog||[]);
    posthog.init("{project_key}", {{api_host: "{host}"}});
    posthog.capture("$pageview", {{page: "landing"}});
    </script>
    """


def _google_analytics_script(measurement_id: str) -> str:
    return f"""
    <script async src="https://www.googletagmanager.com/gtag/js?id={measurement_id}"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag("js", new Date());
      gtag("config", "{measurement_id}", {{page_title: "Synapse AI Landing"}});
    </script>
    """
