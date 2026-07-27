from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from typing import Any

from synapse_ai.services.analysis_service import SourceSnippet
from synapse_ai.services.pdf_rendering import pdf_text, register_pdf_fonts


@dataclass(frozen=True)
class ReportDocument:
    filename: str
    ai_status: str
    text_char_count: int
    created_at: str


@dataclass(frozen=True)
class ReportActionItem:
    task: str
    responsible: str
    deadline: str
    priority: str
    risk: str
    evidence: str
    sources: str


@dataclass(frozen=True)
class ExecutiveReport:
    generated_at: datetime
    total_documents: int
    prepared_documents: int
    pending_documents: int
    saved_analyses: int
    action_plans: int
    action_items: list[ReportActionItem]
    documents: list[ReportDocument]
    source_filenames: list[str]


@dataclass(frozen=True)
class IntelligentExecutiveReport:
    generated_at: datetime
    title: str
    executive_summary: str
    key_findings: list[str]
    risks: list[str]
    recommendations: list[str]
    action_items: list[ReportActionItem]
    limitations: list[str]
    source_filenames: list[str]


class ReportGenerationError(RuntimeError):
    """Raised when an intelligent executive report cannot be generated."""


def build_executive_report(
    documents: list[dict[str, object]],
    chunk_counts: dict[str, int],
    analyses: list[dict[str, object]],
) -> ExecutiveReport:
    report_documents = [_build_report_document(document, chunk_counts) for document in documents]
    action_plans = [analysis for analysis in analyses if _is_action_plan(analysis)]
    action_items = _extract_action_items(action_plans)
    source_filenames = sorted(
        {
            filename
            for analysis in analyses
            for filename in _extract_source_filenames(analysis)
            if filename
        }
    )
    return ExecutiveReport(
        generated_at=datetime.now(UTC),
        total_documents=len(documents),
        prepared_documents=sum(
            1 for document in report_documents if document.ai_status.startswith("Preparado")
        ),
        pending_documents=sum(
            1 for document in report_documents if document.ai_status.startswith("Pendente")
        ),
        saved_analyses=len(analyses),
        action_plans=len(action_plans),
        action_items=action_items,
        documents=report_documents,
        source_filenames=source_filenames,
    )


def generate_intelligent_executive_report(
    client: Any,
    sources: list[SourceSnippet],
    documents: list[dict[str, object]],
    analyses: list[dict[str, object]],
    model: str,
) -> IntelligentExecutiveReport:
    if not sources:
        raise ReportGenerationError("Nenhuma fonte semântica foi recuperada para o relatório.")

    try:
        response = client.responses.create(
            model=model,
            instructions=_intelligent_report_instructions(),
            input=_build_intelligent_report_input(sources, documents, analyses),
        )
    except Exception as exc:  # noqa: BLE001
        raise ReportGenerationError("Não foi possível gerar o relatório executivo com IA.") from exc

    response_text = _extract_response_text(response)
    payload = _load_json_object(response_text)
    action_items = _parse_report_action_items(payload.get("action_items"))
    return IntelligentExecutiveReport(
        generated_at=datetime.now(UTC),
        title=_text(payload.get("title"), "Relatório executivo Synapse AI"),
        executive_summary=_text(payload.get("executive_summary"), "Síntese não disponível."),
        key_findings=_text_items(payload.get("key_findings")),
        risks=_text_items(payload.get("risks")),
        recommendations=_text_items(payload.get("recommendations")),
        action_items=action_items,
        limitations=_text_items(payload.get("limitations")),
        source_filenames=sorted({source.filename for source in sources if source.filename}),
    )


def intelligent_report_to_markdown(report: IntelligentExecutiveReport) -> str:
    lines = [
        f"# {report.title}",
        "",
        f"Gerado em: {_format_report_datetime(report.generated_at)}",
        "",
        "## Síntese executiva",
        "",
        report.executive_summary,
        "",
        "## Principais achados",
        "",
        *_markdown_items(report.key_findings, "Nenhum achado principal foi identificado."),
        "",
        "## Riscos e inconsistências",
        "",
        *_markdown_items(report.risks, "Nenhum risco principal foi identificado."),
        "",
        "## Recomendações",
        "",
        *_markdown_items(report.recommendations, "Nenhuma recomendação foi identificada."),
        "",
        "## Plano de ação sugerido",
        "",
    ]
    if report.action_items:
        for index, item in enumerate(report.action_items, start=1):
            lines.extend(
                [
                    f"### {index}. {item.task}",
                    f"- Responsável: {item.responsible}",
                    f"- Prazo: {item.deadline}",
                    f"- Prioridade: {item.priority}",
                    f"- Risco: {item.risk}",
                    f"- Evidência: {item.evidence}",
                    f"- Fontes: {item.sources or 'A confirmar'}",
                    "",
                ]
            )
    else:
        lines.append("- Nenhuma ação sugerida foi identificada.")

    lines.extend(
        [
            "",
            "## Lacunas e validações necessárias",
            "",
            *_markdown_items(report.limitations, "Nenhuma lacuna explícita foi identificada."),
            "",
            "## Fontes documentais",
            "",
            *_markdown_items(report.source_filenames, "Nenhuma fonte documental recuperada."),
            "",
            "## Nota de governança",
            "",
            (
                "Este relatório foi gerado como apoio à decisão. As conclusões devem ser "
                "validadas por pessoas responsáveis antes de qualquer ação operacional, "
                "jurídica ou financeira."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def intelligent_report_to_pdf(report: IntelligentExecutiveReport) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate

    font_regular, font_bold = register_pdf_fonts()
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.45 * cm,
        rightMargin=1.45 * cm,
        topMargin=1.35 * cm,
        bottomMargin=1.35 * cm,
        title=_pdf_text(report.title),
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "IntelligentReportTitle",
        parent=styles["Title"],
        fontName=font_bold,
        fontSize=21,
        leading=25,
        textColor=colors.HexColor("#111827"),
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "IntelligentReportSubtitle",
        parent=styles["BodyText"],
        fontName=font_regular,
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=8,
    )
    heading_style = ParagraphStyle(
        "IntelligentReportHeading",
        parent=styles["Heading2"],
        fontName=font_bold,
        fontSize=12.5,
        leading=15,
        textColor=colors.HexColor("#172033"),
        spaceBefore=10,
        spaceAfter=5,
    )
    body_style = ParagraphStyle(
        "IntelligentReportBody",
        parent=styles["BodyText"],
        fontName=font_regular,
        fontSize=8.7,
        leading=11.2,
        textColor=colors.HexColor("#263043"),
        spaceAfter=4,
    )

    story: list[Any] = [
        Paragraph(_pdf_text(report.title), title_style),
        Paragraph(f"Gerado em: {_format_report_datetime(report.generated_at)}", subtitle_style),
        _section("Síntese executiva", report.executive_summary, heading_style, body_style),
        _bullet_section("Principais achados", report.key_findings, heading_style, body_style),
        _bullet_section("Riscos e inconsistências", report.risks, heading_style, body_style),
        _bullet_section("Recomendações", report.recommendations, heading_style, body_style),
        Paragraph("Plano de ação sugerido", heading_style),
        _build_intelligent_action_items_table(report.action_items, body_style),
        _bullet_section(
            "Lacunas e validações necessárias",
            report.limitations,
            heading_style,
            body_style,
        ),
        _bullet_section("Fontes documentais", report.source_filenames, heading_style, body_style),
        _section(
            "Nota de governança",
            (
                "Este relatório foi gerado como apoio à decisão. As conclusões devem ser "
                "validadas por pessoas responsáveis antes de qualquer ação operacional, "
                "jurídica ou financeira."
            ),
            heading_style,
            body_style,
        ),
    ]
    story = _flatten_story(story)
    document.build(story)
    return buffer.getvalue()


def executive_report_to_markdown(report: ExecutiveReport) -> str:
    lines = [
        "# Relatório executivo - Synapse AI",
        "",
        f"Gerado em: {_format_report_datetime(report.generated_at)}",
        "",
        "## Resumo executivo",
        "",
        f"- Documentos enviados: {report.total_documents}",
        f"- Documentos preparados para IA: {report.prepared_documents}",
        f"- Documentos pendentes de preparação: {report.pending_documents}",
        f"- Análises salvas: {report.saved_analyses}",
        f"- Planos de ação salvos: {report.action_plans}",
        f"- Itens de ação identificados: {len(report.action_items)}",
        "",
        "## Saúde da base documental",
        "",
    ]
    if report.documents:
        for document in report.documents:
            lines.append(
                "- "
                f"{document.filename} | {document.ai_status} | "
                f"{document.text_char_count} caracteres | {document.created_at}"
            )
    else:
        lines.append("- Nenhum documento enviado.")

    lines.extend(["", "## Plano de ação consolidado", ""])
    if report.action_items:
        for index, item in enumerate(report.action_items, start=1):
            lines.extend(
                [
                    f"### {index}. {item.task}",
                    f"- Responsável: {item.responsible}",
                    f"- Prazo: {item.deadline}",
                    f"- Prioridade: {item.priority}",
                    f"- Risco: {item.risk}",
                    f"- Evidência: {item.evidence}",
                    f"- Fontes: {item.sources or 'A confirmar'}",
                    "",
                ]
            )
    else:
        lines.append("- Nenhum plano de ação salvo ainda.")

    lines.extend(["", "## Fontes documentais", ""])
    if report.source_filenames:
        lines.extend(f"- {filename}" for filename in report.source_filenames)
    else:
        lines.append("- Nenhuma fonte salva no histórico.")

    lines.extend(
        [
            "",
            "## Nota de governança",
            "",
            (
                "Este relatório foi gerado como apoio à decisão. "
                "As conclusões devem ser validadas por pessoas responsáveis antes de "
                "qualquer ação operacional, jurídica ou financeira."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def executive_report_to_pdf(report: ExecutiveReport) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
    )

    font_regular, font_bold = register_pdf_fonts()
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.4 * cm,
        title="Relatório executivo - Synapse AI",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "SynapseTitle",
        parent=styles["Title"],
        fontName=font_bold,
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#172033"),
        spaceAfter=10,
    )
    heading_style = ParagraphStyle(
        "SynapseHeading",
        parent=styles["Heading2"],
        fontName=font_bold,
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#172033"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "SynapseBody",
        parent=styles["BodyText"],
        fontName=font_regular,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#263043"),
    )
    small_style = ParagraphStyle(
        "SynapseSmall",
        parent=body_style,
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#4b5563"),
    )

    story: list[Any] = [
        Paragraph("Relatório executivo - Synapse AI", title_style),
        Paragraph(f"Gerado em: {_format_report_datetime(report.generated_at)}", small_style),
        Spacer(1, 8),
        Paragraph("Resumo executivo", heading_style),
        _build_metric_table(report, body_style),
        Paragraph("Saúde da base documental", heading_style),
        _build_documents_table(report.documents, body_style),
        Paragraph("Plano de ação consolidado", heading_style),
        _build_action_items_table(report.action_items, body_style),
        Paragraph("Fontes documentais", heading_style),
        Paragraph(_format_pdf_sources(report.source_filenames), body_style),
        Paragraph("Nota de governança", heading_style),
        Paragraph(
            "Este relatório foi gerado como apoio à decisão. As conclusões devem ser "
            "validadas por pessoas responsáveis antes de qualquer ação operacional, "
            "jurídica ou financeira.",
            body_style,
        ),
    ]
    document.build(story)
    return buffer.getvalue()


def _build_metric_table(report: ExecutiveReport, body_style: Any) -> Any:
    from reportlab.lib.units import cm

    rows = [
        ["Indicador", "Valor"],
        ["Documentos enviados", str(report.total_documents)],
        ["Documentos preparados para IA", str(report.prepared_documents)],
        ["Documentos pendentes de preparação", str(report.pending_documents)],
        ["Análises salvas", str(report.saved_analyses)],
        ["Planos de ação salvos", str(report.action_plans)],
        ["Itens de ação identificados", str(len(report.action_items))],
    ]
    return _styled_table(rows, [11 * cm, 4 * cm], body_style)


def _build_documents_table(documents: list[ReportDocument], body_style: Any) -> Any:
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph

    if not documents:
        return Paragraph("Nenhum documento enviado.", body_style)
    rows = [["Documento", "IA", "Caracteres", "Enviado em"]]
    rows.extend(
        [
            [
                document.filename,
                document.ai_status,
                str(document.text_char_count),
                document.created_at,
            ]
            for document in documents[:12]
        ]
    )
    return _styled_table(rows, [6.3 * cm, 4.4 * cm, 2.2 * cm, 3.1 * cm], body_style)


def _build_action_items_table(items: list[ReportActionItem], body_style: Any) -> Any:
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph

    if not items:
        return Paragraph("Nenhum plano de ação salvo ainda.", body_style)
    rows = [["Tarefa", "Responsavel", "Prazo", "Prioridade", "Risco"]]
    rows.extend(
        [
            [
                item.task,
                item.responsible,
                item.deadline,
                item.priority,
                item.risk,
            ]
            for item in items[:12]
        ]
    )
    return _styled_table(rows, [5.2 * cm, 3 * cm, 2.5 * cm, 2 * cm, 3.3 * cm], body_style)


def _build_intelligent_action_items_table(items: list[ReportActionItem], body_style: Any) -> Any:
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph

    if not items:
        return Paragraph("Nenhuma ação sugerida foi identificada.", body_style)
    rows = [["Acao", "Responsavel", "Prazo", "Prioridade", "Risco"]]
    rows.extend(
        [
            [item.task, item.responsible, item.deadline, item.priority, item.risk]
            for item in items[:12]
        ]
    )
    return _styled_table(rows, [5.3 * cm, 3 * cm, 2.5 * cm, 2.1 * cm, 3.1 * cm], body_style)


def _styled_table(rows: list[list[str]], widths: list[float], body_style: Any) -> Any:
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Table, TableStyle

    _, font_bold = register_pdf_fonts()
    paragraph_rows = [
        [Paragraph(_pdf_text(cell), body_style) for cell in row]
        for row in rows
    ]
    table = Table(paragraph_rows, colWidths=widths, hAlign="LEFT", repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf7")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#172033")),
                ("FONTNAME", (0, 0), (-1, 0), font_bold),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _section(title: str, content: str, heading_style: Any, body_style: Any) -> list[Any]:
    from reportlab.platypus import Paragraph

    return [
        Paragraph(_pdf_text(title), heading_style),
        Paragraph(_pdf_text(content), body_style),
    ]


def _bullet_section(
    title: str,
    items: list[str],
    heading_style: Any,
    body_style: Any,
) -> list[Any]:
    from reportlab.platypus import Paragraph

    rendered_items = items or ["Nenhum item identificado."]
    return [
        Paragraph(_pdf_text(title), heading_style),
        *[Paragraph(_pdf_text(f"- {item}"), body_style) for item in rendered_items],
    ]


def _flatten_story(items: list[Any]) -> list[Any]:
    from reportlab.platypus import Spacer

    story: list[Any] = []
    for item in items:
        if isinstance(item, list):
            story.extend(item)
        else:
            story.append(item)
        story.append(Spacer(1, 3))
    return story


def _build_report_document(
    document: dict[str, object],
    chunk_counts: dict[str, int],
) -> ReportDocument:
    document_id = document.get("id")
    chunk_count = chunk_counts.get(document_id, 0) if isinstance(document_id, str) else 0
    ai_status = f"Preparado ({chunk_count} trechos)" if chunk_count else "Pendente"
    return ReportDocument(
        filename=str(document.get("filename") or "Documento sem nome"),
        ai_status=ai_status,
        text_char_count=_as_int(document.get("text_char_count")),
        created_at=_format_created_at(document.get("created_at")),
    )


def _extract_action_items(analyses: list[dict[str, object]]) -> list[ReportActionItem]:
    items: list[ReportActionItem] = []
    for analysis in analyses:
        metadata = analysis.get("metadata")
        if not isinstance(metadata, dict):
            continue
        raw_items = metadata.get("items")
        if not isinstance(raw_items, list):
            continue
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            items.append(
                ReportActionItem(
                    task=_text(raw_item.get("task"), "A confirmar"),
                    responsible=_text(raw_item.get("responsible"), "A confirmar"),
                    deadline=_text(raw_item.get("deadline"), "A confirmar"),
                    priority=_text(raw_item.get("priority"), "Média"),
                    risk=_text(raw_item.get("risk"), "A confirmar"),
                    evidence=_text(raw_item.get("evidence"), "A confirmar"),
                    sources=", ".join(_text_list(raw_item.get("source_refs"))),
                )
            )
    return items


def _parse_report_action_items(value: object) -> list[ReportActionItem]:
    if not isinstance(value, list):
        return []
    items: list[ReportActionItem] = []
    for raw_item in value:
        if not isinstance(raw_item, dict):
            continue
        task = _text(raw_item.get("task"), "")
        if not task:
            continue
        items.append(
            ReportActionItem(
                task=task,
                responsible=_text(raw_item.get("responsible"), "A confirmar"),
                deadline=_text(raw_item.get("deadline"), "A confirmar"),
                priority=_normalize_priority(raw_item.get("priority")),
                risk=_text(raw_item.get("risk"), "A confirmar"),
                evidence=_text(raw_item.get("evidence"), "A confirmar"),
                sources=", ".join(_text_list(raw_item.get("source_refs"))),
            )
        )
    return items


def _extract_source_filenames(analysis: dict[str, object]) -> list[str]:
    metadata = analysis.get("metadata")
    if isinstance(metadata, dict):
        source_filenames = metadata.get("source_filenames")
        if isinstance(source_filenames, list):
            return [filename for filename in source_filenames if isinstance(filename, str)]
    sources = analysis.get("sources")
    if not isinstance(sources, list):
        return []
    filenames = []
    for source in sources:
        if isinstance(source, dict) and isinstance(source.get("filename"), str):
            filenames.append(str(source["filename"]))
    return filenames


def _is_action_plan(analysis: dict[str, object]) -> bool:
    metadata = analysis.get("metadata")
    return isinstance(metadata, dict) and metadata.get("artifact_type") == "action_plan"


def _intelligent_report_instructions() -> str:
    return (
        "Você é o Synapse AI gerando um relatório executivo para inteligência "
        "organizacional. Use apenas o contexto fornecido. Não invente fatos, datas, "
        "responsáveis ou decisões. Quando faltar evidência, registre em limitations. "
        "A resposta deve ser somente JSON válido com este formato: "
        '{"title":"...","executive_summary":"...","key_findings":["..."],'
        '"risks":["..."],"recommendations":["..."],'
        '"action_items":[{"task":"...","responsible":"...","deadline":"...",'
        '"priority":"Alta|Média|Baixa","risk":"...","evidence":"...",'
        '"source_refs":["Fonte 1"]}],"limitations":["..."]}.'
    )


def _build_intelligent_report_input(
    sources: list[SourceSnippet],
    documents: list[dict[str, object]],
    analyses: list[dict[str, object]],
) -> str:
    document_context = "\n".join(
        (
            f"- {document.get('filename', 'Documento sem nome')} | "
            f"caracteres: {document.get('text_char_count', 0)} | "
            f"criado em: {document.get('created_at', '')}"
        )
        for document in documents[:20]
    )
    source_context = "\n\n".join(
        (
            f"[Fonte {index}] Documento: {source.filename}\n"
            f"Trecho {source.chunk_index} | similaridade {source.similarity:.3f}\n"
            f"{source.content}"
        )
        for index, source in enumerate(sources, start=1)
    )
    analysis_context = "\n\n".join(_render_analysis_context(analysis) for analysis in analyses[:8])
    return (
        "Objetivo: produzir um relatório executivo acionável, conciso e rastreável.\n\n"
        f"Inventário documental:\n{document_context or 'Nenhum documento informado.'}\n\n"
        f"Histórico salvo:\n{analysis_context or 'Nenhum histórico salvo.'}\n\n"
        f"Fontes recuperadas semanticamente:\n{source_context}"
    )


def _render_analysis_context(analysis: dict[str, object]) -> str:
    metadata = analysis.get("metadata")
    if isinstance(metadata, dict) and metadata.get("artifact_type") == "action_plan":
        items = metadata.get("items")
        if isinstance(items, list):
            rendered_items = []
            for item in items[:5]:
                if isinstance(item, dict):
                    rendered_items.append(
                        "- "
                        f"{item.get('task', '')} | responsável: {item.get('responsible', '')} | "
                        f"prazo: {item.get('deadline', '')} | risco: {item.get('risk', '')}"
                    )
            return "Plano de ação salvo:\n" + "\n".join(rendered_items)
    question = _text(analysis.get("question"), "")
    answer = _text(analysis.get("answer"), "")
    return f"Pergunta salva: {question}\nResposta salva: {_truncate(answer, 700)}"


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
        raise ReportGenerationError("A IA retornou o relatório em formato inesperado.") from exc
    if not isinstance(value, dict):
        raise ReportGenerationError("A IA retornou o relatório em formato inesperado.")
    return value


def _get_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _format_sources(source_filenames: list[str]) -> str:
    if not source_filenames:
        return "Nenhuma fonte salva no histórico."
    return "<br/>".join(source_filenames)


def _markdown_items(items: list[str], fallback: str) -> list[str]:
    rendered_items = items or [fallback]
    return [f"- {item}" for item in rendered_items]


def _format_pdf_sources(source_filenames: list[str]) -> str:
    if not source_filenames:
        return "Nenhuma fonte salva no histórico."
    return "<br/>".join(_pdf_text(filename) for filename in source_filenames)


def _pdf_text(value: object) -> str:
    return pdf_text(value)


def _format_report_datetime(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%d/%m/%Y %H:%M UTC")


def _format_created_at(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    normalized_value = value.replace("Z", "+00:00")
    try:
        created_at = datetime.fromisoformat(normalized_value)
    except ValueError:
        return value
    return created_at.strftime("%d/%m/%Y %H:%M")


def _text(value: object, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _text_items(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _normalize_priority(value: object) -> str:
    priority = _text(value, "Média").strip().title()
    return priority if priority in {"Alta", "Média", "Baixa"} else "Média"


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 3].rstrip()}..."


def _text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _as_int(value: object) -> int:
    return value if isinstance(value, int) else 0
