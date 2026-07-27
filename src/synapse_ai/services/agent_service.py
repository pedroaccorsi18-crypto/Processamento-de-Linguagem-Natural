from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass
from io import StringIO
from typing import Any

from synapse_ai.services.analysis_service import SourceSnippet
from synapse_ai.services.pattern_service import build_history_digest
from synapse_ai.services.spreadsheet_export import XlsxSheet, workbook_to_xlsx

logger = logging.getLogger(__name__)


class AgentOrchestrationError(RuntimeError):
    """Raised when the specialized agent workflow cannot be completed."""


@dataclass(frozen=True)
class AgentSpec:
    agent_id: str
    name: str
    mission: str
    focus: str


@dataclass(frozen=True)
class AgentFinding:
    category: str
    title: str
    severity: str
    evidence: str
    recommendation: str
    source_refs: list[str]


@dataclass(frozen=True)
class AgentOutput:
    agent_id: str
    agent_name: str
    mission: str
    summary: str
    confidence: str
    findings: list[AgentFinding]


@dataclass(frozen=True)
class MultiAgentReport:
    executive_summary: str
    consensus: list[str]
    conflicts: list[str]
    recommendations: list[str]
    agent_outputs: list[AgentOutput]
    sources: list[SourceSnippet]
    historical_record_count: int


SPECIALIZED_AGENTS = [
    AgentSpec(
        agent_id="decision_agent",
        name="Agente de Decisões",
        mission="Consolidar decisões, responsáveis, prazos e dependências explícitas.",
        focus="decisões, responsáveis, prazos, dependências, critérios de aceite",
    ),
    AgentSpec(
        agent_id="risk_agent",
        name="Agente de Riscos",
        mission="Identificar riscos operacionais, financeiros, técnicos e de cronograma.",
        focus="riscos, impacto, severidade, mitigação, pendências críticas",
    ),
    AgentSpec(
        agent_id="consistency_agent",
        name="Agente de Consistência",
        mission="Detectar contradições, lacunas e divergências entre documentos e histórico.",
        focus="inconsistências, divergências, lacunas de evidência, conflitos de data",
    ),
    AgentSpec(
        agent_id="sentiment_agent",
        name="Agente de Sentimentos",
        mission="Analisar tom organizacional, tensão, urgência e risco comunicacional.",
        focus="sentimento, urgência, tensão, confiança, conflito, comunicação",
    ),
    AgentSpec(
        agent_id="governance_agent",
        name="Agente de Governança",
        mission="Avaliar rastreabilidade, confiabilidade das fontes e cuidados de validação.",
        focus="fontes, evidência, governança, auditoria, limitações, validação humana",
    ),
]


def generate_multi_agent_report(
    client: Any,
    sources: list[SourceSnippet],
    historical_analyses: list[dict[str, object]],
    model: str,
) -> MultiAgentReport:
    if not sources:
        raise AgentOrchestrationError("Nenhum trecho relevante foi encontrado.")

    history_digest = build_history_digest(historical_analyses)
    agent_outputs = [
        _run_specialized_agent(client, agent, sources, history_digest, model)
        for agent in SPECIALIZED_AGENTS
    ]
    if not any(output.findings for output in agent_outputs):
        raise AgentOrchestrationError("Os agentes não encontraram achados claros neste escopo.")

    orchestration = _run_orchestrator(client, agent_outputs, model)
    return MultiAgentReport(
        executive_summary=_text(orchestration.get("executive_summary"), "Síntese não disponível."),
        consensus=_text_list(orchestration.get("consensus")),
        conflicts=_text_list(orchestration.get("conflicts")),
        recommendations=_text_list(orchestration.get("recommendations")),
        agent_outputs=agent_outputs,
        sources=sources,
        historical_record_count=len(history_digest),
    )


def serialize_agent_outputs(outputs: list[AgentOutput]) -> list[dict[str, object]]:
    return [
        {
            "agent_id": output.agent_id,
            "agent_name": output.agent_name,
            "mission": output.mission,
            "summary": output.summary,
            "confidence": output.confidence,
            "findings": serialize_agent_findings(output.findings),
        }
        for output in outputs
    ]


def serialize_agent_findings(findings: list[AgentFinding]) -> list[dict[str, object]]:
    return [
        {
            "category": finding.category,
            "title": finding.title,
            "severity": finding.severity,
            "evidence": finding.evidence,
            "recommendation": finding.recommendation,
            "source_refs": finding.source_refs,
        }
        for finding in findings
    ]


def multi_agent_report_to_markdown(report: MultiAgentReport) -> str:
    lines = [
        "# Orquestração multiagente - Synapse AI",
        "",
        "## Síntese executiva",
        "",
        report.executive_summary,
        "",
        f"Registros históricos considerados: {report.historical_record_count}",
        "",
        "## Consensos",
        "",
        *[f"- {item}" for item in report.consensus or ["A confirmar"]],
        "",
        "## Conflitos e lacunas",
        "",
        *[f"- {item}" for item in report.conflicts or ["A confirmar"]],
        "",
        "## Recomendações consolidadas",
        "",
        *[f"- {item}" for item in report.recommendations or ["A confirmar"]],
        "",
        "## Parecer dos agentes",
        "",
    ]
    for output in report.agent_outputs:
        lines.extend(
            [
                f"### {output.agent_name}",
                f"- Missão: {output.mission}",
                f"- Confiança: {output.confidence}",
                f"- Síntese: {output.summary}",
                "",
            ]
        )
        for index, finding in enumerate(output.findings, start=1):
            refs = ", ".join(finding.source_refs) if finding.source_refs else "Fonte não indicada"
            lines.extend(
                [
                    f"{index}. {finding.title}",
                    f"   - Categoria: {finding.category}",
                    f"   - Severidade: {finding.severity}",
                    f"   - Evidência: {finding.evidence}",
                    f"   - Recomendação: {finding.recommendation}",
                    f"   - Fontes: {refs}",
                    "",
                ]
            )
    lines.extend(["## Nota de governança", ""])
    lines.append(
        "Cada agente executa uma análise especializada própria. A consolidação final organiza "
        "consensos e lacunas, mas não executa ações automaticamente."
    )
    return "\n".join(lines).strip() + "\n"


def multi_agent_report_to_csv(report: MultiAgentReport) -> str:
    output = StringIO()
    output.write("\ufeff")
    writer = csv.DictWriter(
        output,
        delimiter=";",
        fieldnames=[
            "agente",
            "missão",
            "confiança",
            "categoria",
            "título",
            "severidade",
            "evidência",
            "recomendação",
            "fontes",
        ],
    )
    writer.writeheader()
    for agent_output in report.agent_outputs:
        for finding in agent_output.findings:
            writer.writerow(
                {
                    "agente": agent_output.agent_name,
                    "missão": agent_output.mission,
                    "confiança": agent_output.confidence,
                    "categoria": finding.category,
                    "título": finding.title,
                    "severidade": finding.severity,
                    "evidência": finding.evidence,
                    "recomendação": finding.recommendation,
                    "fontes": ", ".join(finding.source_refs),
                }
            )
    return output.getvalue()


def multi_agent_report_to_xlsx(report: MultiAgentReport) -> bytes:
    finding_rows = [
        [
            output.agent_name,
            output.confidence,
            finding.category,
            finding.title,
            finding.severity,
            finding.evidence,
            finding.recommendation,
            ", ".join(finding.source_refs),
        ]
        for output in report.agent_outputs
        for finding in output.findings
    ]
    return workbook_to_xlsx(
        [
            XlsxSheet(
                name="Resumo",
                headers=["Indicador", "Resultado"],
                rows=[
                    ["Síntese executiva", report.executive_summary],
                    ["Agentes executados", len(report.agent_outputs)],
                    ["Registros históricos considerados", report.historical_record_count],
                    ["Consensos", "\n".join(report.consensus) or "A confirmar"],
                    ["Conflitos e lacunas", "\n".join(report.conflicts) or "A confirmar"],
                    ["Recomendações", "\n".join(report.recommendations) or "A confirmar"],
                ],
                column_widths=[36, 86],
            ),
            XlsxSheet(
                name="Agentes",
                headers=["Agente", "Missão", "Confiança", "Síntese"],
                rows=[
                    [output.agent_name, output.mission, output.confidence, output.summary]
                    for output in report.agent_outputs
                ],
                column_widths=[28, 58, 16, 72],
            ),
            XlsxSheet(
                name="Achados",
                headers=[
                    "Agente",
                    "Confiança",
                    "Categoria",
                    "Título",
                    "Severidade",
                    "Evidência",
                    "Recomendação",
                    "Fontes",
                ],
                rows=finding_rows,
                column_widths=[28, 16, 22, 42, 14, 58, 58, 20],
            ),
        ]
    )


def _run_specialized_agent(
    client: Any,
    agent: AgentSpec,
    sources: list[SourceSnippet],
    history_digest: list[dict[str, object]],
    model: str,
) -> AgentOutput:
    try:
        response = client.responses.create(
            model=model,
            instructions=_agent_instructions(agent),
            input=_build_agent_input(agent, sources, history_digest),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s failed: %s", agent.agent_id, exc.__class__.__name__)
        raise AgentOrchestrationError(f"{agent.name} não conseguiu concluir a análise.") from exc

    payload = _load_json_object(_extract_response_text(response))
    findings = _parse_findings(payload.get("findings"))
    return AgentOutput(
        agent_id=agent.agent_id,
        agent_name=agent.name,
        mission=agent.mission,
        summary=_text(payload.get("summary"), "Síntese não disponível."),
        confidence=_normalize_confidence(payload.get("confidence")),
        findings=findings,
    )


def _run_orchestrator(
    client: Any,
    agent_outputs: list[AgentOutput],
    model: str,
) -> dict[str, Any]:
    try:
        response = client.responses.create(
            model=model,
            instructions=_orchestrator_instructions(),
            input=json.dumps(serialize_agent_outputs(agent_outputs), ensure_ascii=False, indent=2),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Agent orchestrator failed: %s", exc.__class__.__name__)
        raise AgentOrchestrationError(
            "O orquestrador multiagente não conseguiu consolidar."
        ) from exc
    return _load_json_object(_extract_response_text(response))


def _agent_instructions(agent: AgentSpec) -> str:
    return (
        f"Você é o {agent.name} do Synapse AI. Missão: {agent.mission} "
        f"Foco analítico: {agent.focus}. Execute sua análise de forma independente, use apenas "
        "as fontes e o histórico fornecidos, não invente fatos e declare lacunas quando a "
        "evidência for insuficiente. Responda somente com JSON válido no formato: "
        '{"summary":"...","confidence":"Alta|Média|Baixa","findings":[{"category":"...",'
        '"title":"...","severity":"Alta|Média|Baixa","evidence":"...",'
        '"recommendation":"...","source_refs":["Fonte 1"]}]}'
    )


def _orchestrator_instructions() -> str:
    return (
        "Você é o Orquestrador Multiagente do Synapse AI. Consolide somente os achados "
        "produzidos pelos agentes especializados. Identifique consensos, conflitos, lacunas e "
        "recomendações executivas. Não invente novos fatos. Responda somente com JSON válido no "
        "formato: "
        '{"executive_summary":"...","consensus":["..."],"conflicts":["..."],'
        '"recommendations":["..."]}'
    )


def _build_agent_input(
    agent: AgentSpec,
    sources: list[SourceSnippet],
    history_digest: list[dict[str, object]],
) -> str:
    rendered_sources = "\n\n".join(
        (
            f"[Fonte {index}] Documento: {source.filename}\n"
            f"Trecho {source.chunk_index} | similaridade {source.similarity:.3f}\n"
            f"{source.content}"
        )
        for index, source in enumerate(sources, start=1)
    )
    rendered_history = json.dumps(history_digest[:12], ensure_ascii=False, indent=2)
    return (
        f"Missão específica: {agent.mission}\n\n"
        f"Fontes atuais:\n{rendered_sources}\n\n"
        f"Histórico salvo resumido:\n{rendered_history}"
    )


def _parse_findings(value: object) -> list[AgentFinding]:
    if not isinstance(value, list):
        return []
    findings: list[AgentFinding] = []
    for raw_finding in value:
        if not isinstance(raw_finding, dict):
            continue
        title = _text(raw_finding.get("title"), "")
        if not title:
            continue
        findings.append(
            AgentFinding(
                category=_text(raw_finding.get("category"), "A confirmar"),
                title=title,
                severity=_normalize_severity(raw_finding.get("severity")),
                evidence=_text(raw_finding.get("evidence"), "A confirmar"),
                recommendation=_text(raw_finding.get("recommendation"), "A confirmar"),
                source_refs=_text_list(raw_finding.get("source_refs")),
            )
        )
    return findings


def _extract_response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str):
        return output_text.strip()

    output = getattr(response, "output", None)
    if not isinstance(output, list):
        return ""

    parts: list[str] = []
    for item in output:
        content_items = _get_value(item, "content")
        if not isinstance(content_items, list):
            continue
        for content_item in content_items:
            text = _get_value(content_item, "text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()


def _load_json_object(response_text: str) -> dict[str, Any]:
    clean_text = response_text.strip()
    if clean_text.startswith("```"):
        clean_text = clean_text.strip("`")
        if clean_text.lower().startswith("json"):
            clean_text = clean_text[4:].strip()
    try:
        value = json.loads(clean_text)
    except json.JSONDecodeError as exc:
        raise AgentOrchestrationError("A IA retornou resposta multiagente inesperada.") from exc
    if not isinstance(value, dict):
        raise AgentOrchestrationError("A IA retornou resposta multiagente inesperada.")
    return value


def _normalize_severity(value: object) -> str:
    severity = _text(value, "Média").strip().title()
    return severity if severity in {"Alta", "Média", "Baixa"} else "Média"


def _normalize_confidence(value: object) -> str:
    confidence = _text(value, "Média").strip().title()
    return confidence if confidence in {"Alta", "Média", "Baixa"} else "Média"


def _text(value: object, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _get_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)
