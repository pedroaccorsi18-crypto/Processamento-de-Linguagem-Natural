from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from typing import Any

from synapse_ai.services.pdf_rendering import pdf_text, register_pdf_fonts


@dataclass(frozen=True)
class AuditSource:
    filename: str
    document_id: str
    chunk_index: int
    similarity: float
    content: str
    evidence_available: bool


@dataclass(frozen=True)
class AuditRecord:
    title: str
    artifact_type: str
    created_at: str
    question: str
    answer: str
    sources: list[AuditSource]
    limitations: list[str]
    has_duplicate_filenames: bool


@dataclass(frozen=True)
class AuditSummary:
    records: int
    sources: int
    documents: int
    missing_evidence: int
    duplicate_filename_records: int


def collect_source_references(analyses: list[dict[str, object]]) -> list[tuple[str, int]]:
    references: list[tuple[str, int]] = []
    for analysis in analyses:
        for source in _raw_sources(analysis):
            document_id = source.get("document_id")
            chunk_index = source.get("chunk_index")
            if isinstance(document_id, str) and isinstance(chunk_index, int):
                references.append((document_id, chunk_index))
    return sorted(set(references))


def build_audit_records(
    analyses: list[dict[str, object]],
    chunk_lookup: dict[tuple[str, int], dict[str, object]],
) -> list[AuditRecord]:
    records = []
    for analysis in analyses:
        sources = _build_audit_sources(analysis, chunk_lookup)
        filenames = [source.filename for source in sources if source.filename]
        records.append(
            AuditRecord(
                title=str(analysis.get("title") or "Registro sem título"),
                artifact_type=_artifact_type_label(analysis),
                created_at=_format_created_at(analysis.get("created_at")),
                question=str(analysis.get("question") or ""),
                answer=str(analysis.get("answer") or ""),
                sources=sources,
                limitations=_extract_limitations(analysis),
                has_duplicate_filenames=_has_duplicates(filenames),
            )
        )
    return records


def build_audit_summary(records: list[AuditRecord]) -> AuditSummary:
    document_ids = {
        source.document_id
        for record in records
        for source in record.sources
        if source.document_id
    }
    return AuditSummary(
        records=len(records),
        sources=sum(len(record.sources) for record in records),
        documents=len(document_ids),
        missing_evidence=sum(
            1
            for record in records
            for source in record.sources
            if not source.evidence_available
        ),
        duplicate_filename_records=sum(1 for record in records if record.has_duplicate_filenames),
    )


def audit_records_to_markdown(records: list[AuditRecord]) -> str:
    lines = [
        "# Pacote de evidências - Synapse AI",
        "",
        "Este pacote consolida as fontes usadas em análises e planos salvos.",
        "",
    ]
    if not records:
        lines.append("Nenhum registro auditável encontrado.")
        return "\n".join(lines)

    for index, record in enumerate(records, start=1):
        lines.extend(
            [
                f"## {index}. {record.title}",
                "",
                f"- Tipo: {record.artifact_type}",
                f"- Criado em: {record.created_at or 'A confirmar'}",
                f"- Fontes: {len(record.sources)}",
                f"- Duplicidade de nomes: {'sim' if record.has_duplicate_filenames else 'não'}",
                "",
            ]
        )
        if record.question:
            lines.extend(["### Pergunta", record.question, ""])
        if record.limitations:
            lines.extend(
                ["### Lacunas declaradas", *[f"- {item}" for item in record.limitations], ""]
            )
        lines.append("### Fontes")
        if not record.sources:
            lines.extend(["- Nenhuma fonte salva.", ""])
            continue
        for source_index, source in enumerate(record.sources, start=1):
            lines.extend(
                [
                    f"#### Fonte {source_index}: {source.filename}",
                    f"- Documento: {source.document_id or 'A confirmar'}",
                    f"- Trecho: {source.chunk_index}",
                    f"- Similaridade: {source.similarity:.3f}",
                    f"- Evidência disponível: {'sim' if source.evidence_available else 'não'}",
                    "",
                    source.content or "Trecho não encontrado na base de chunks.",
                    "",
                ]
            )
    return "\n".join(lines)


def audit_records_to_pdf(records: list[AuditRecord]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    font_regular, font_bold = register_pdf_fonts()
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.45 * cm,
        rightMargin=1.45 * cm,
        topMargin=1.35 * cm,
        bottomMargin=1.35 * cm,
        title="Pacote de evidências - Synapse AI",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "AuditTitle",
        parent=styles["Title"],
        fontName=font_bold,
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#111827"),
        spaceAfter=7,
    )
    subtitle_style = ParagraphStyle(
        "AuditSubtitle",
        parent=styles["BodyText"],
        fontName=font_regular,
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=8,
    )
    heading_style = ParagraphStyle(
        "AuditHeading",
        parent=styles["Heading2"],
        fontName=font_bold,
        fontSize=12.2,
        leading=14.5,
        textColor=colors.HexColor("#172033"),
        spaceBefore=9,
        spaceAfter=5,
    )
    body_style = ParagraphStyle(
        "AuditBody",
        parent=styles["BodyText"],
        fontName=font_regular,
        fontSize=8.6,
        leading=11.2,
        textColor=colors.HexColor("#263043"),
        spaceAfter=4,
    )
    evidence_style = ParagraphStyle(
        "AuditEvidence",
        parent=body_style,
        fontSize=7.9,
        leading=10.3,
        leftIndent=6,
        borderColor=colors.HexColor("#cbd5e1"),
        borderWidth=0.3,
        borderPadding=5,
        backColor=colors.HexColor("#f8fafc"),
        spaceBefore=3,
        spaceAfter=7,
    )

    summary = build_audit_summary(records)
    story: list[Any] = [
        Paragraph("Pacote de evidências - Synapse AI", title_style),
        Paragraph(
            "Trilha auditável das análises salvas, com documentos, fontes e trechos usados.",
            subtitle_style,
        ),
        _audit_metric_table(summary, body_style),
        Spacer(1, 8),
    ]
    if not records:
        story.append(Paragraph("Nenhum registro auditável encontrado.", body_style))
    for index, record in enumerate(records, start=1):
        story.extend(_audit_record_story(index, record, heading_style, body_style, evidence_style))
    document.build(story)
    return buffer.getvalue()


def _audit_metric_table(summary: AuditSummary, body_style: Any) -> Any:
    from reportlab.lib.units import cm

    rows = [
        ["Indicador", "Valor"],
        ["Registros auditados", str(summary.records)],
        ["Fontes registradas", str(summary.sources)],
        ["Documentos distintos", str(summary.documents)],
        ["Fontes sem evidência recuperada", str(summary.missing_evidence)],
        ["Registros com nomes duplicados", str(summary.duplicate_filename_records)],
    ]
    return _styled_audit_table(rows, [9.4 * cm, 5.8 * cm], body_style)


def _audit_record_story(
    index: int,
    record: AuditRecord,
    heading_style: Any,
    body_style: Any,
    evidence_style: Any,
) -> list[Any]:
    from reportlab.platypus import Paragraph

    story: list[Any] = [
        Paragraph(pdf_text(f"{index}. {record.title}"), heading_style),
        Paragraph(pdf_text(f"Tipo: {record.artifact_type}"), body_style),
        Paragraph(pdf_text(f"Criado em: {record.created_at or 'A confirmar'}"), body_style),
        Paragraph(pdf_text(f"Fontes vinculadas: {len(record.sources)}"), body_style),
    ]
    if record.has_duplicate_filenames:
        story.append(
            Paragraph(
                pdf_text("Atenção: este registro usa fontes com nomes de documento repetidos."),
                body_style,
            )
        )
    if record.question:
        story.extend(
            [
                Paragraph("Pergunta ou solicitação", heading_style),
                Paragraph(pdf_text(record.question), body_style),
            ]
        )
    if record.limitations:
        story.append(Paragraph("Lacunas e validações", heading_style))
        story.extend(
            Paragraph(pdf_text(f"- {limitation}"), body_style)
            for limitation in record.limitations
        )
    story.append(Paragraph("Fontes e trechos", heading_style))
    if not record.sources:
        story.append(Paragraph("Nenhuma fonte salva para este registro.", body_style))
        return story
    for source_index, source in enumerate(record.sources, start=1):
        story.extend(_audit_source_story(source_index, source, body_style, evidence_style))
    return story


def _audit_source_story(
    index: int,
    source: AuditSource,
    body_style: Any,
    evidence_style: Any,
) -> list[Any]:
    from reportlab.platypus import Paragraph

    status = "disponível" if source.evidence_available else "não encontrada"
    content = source.content or "Trecho não encontrado na base de chunks."
    return [
        Paragraph(pdf_text(f"Fonte {index}: {source.filename}"), body_style),
        Paragraph(pdf_text(f"Documento: {source.document_id or 'A confirmar'}"), body_style),
        Paragraph(
            pdf_text(
                f"Trecho: {source.chunk_index} | Similaridade: {source.similarity:.3f} | "
                f"Evidência: {status}"
            ),
            body_style,
        ),
        Paragraph(pdf_text(content), evidence_style),
    ]


def _styled_audit_table(rows: list[list[str]], widths: list[float], body_style: Any) -> Any:
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Table, TableStyle

    _, font_bold = register_pdf_fonts()
    paragraph_rows = [[Paragraph(pdf_text(cell), body_style) for cell in row] for row in rows]
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


def _build_audit_sources(
    analysis: dict[str, object],
    chunk_lookup: dict[tuple[str, int], dict[str, object]],
) -> list[AuditSource]:
    sources: list[AuditSource] = []
    for source in _raw_sources(analysis):
        document_id = str(source.get("document_id") or "")
        chunk_index = source.get("chunk_index")
        chunk_index = chunk_index if isinstance(chunk_index, int) else 0
        chunk = chunk_lookup.get((document_id, chunk_index), {})
        content = chunk.get("content")
        content_text = content if isinstance(content, str) else ""
        sources.append(
            AuditSource(
                filename=str(source.get("filename") or "Documento sem nome"),
                document_id=document_id,
                chunk_index=chunk_index,
                similarity=_as_float(source.get("similarity")),
                content=content_text,
                evidence_available=bool(content_text),
            )
        )
    return sources


def _raw_sources(analysis: dict[str, object]) -> list[dict[str, object]]:
    sources = analysis.get("sources")
    if not isinstance(sources, list):
        return []
    return [source for source in sources if isinstance(source, dict)]


def _artifact_type_label(analysis: dict[str, object]) -> str:
    metadata = analysis.get("metadata")
    if isinstance(metadata, dict) and metadata.get("artifact_type") == "action_plan":
        return "Plano de ação"
    if isinstance(metadata, dict) and metadata.get("artifact_type") == "document_comparison":
        return "Comparação documental"
    if isinstance(metadata, dict) and metadata.get("artifact_type") == "preventive_alert_report":
        return "Alertas preventivos"
    if isinstance(metadata, dict) and metadata.get("artifact_type") == "historical_pattern_report":
        return "Padrões históricos"
    if isinstance(metadata, dict) and metadata.get("artifact_type") == "multi_agent_report":
        return "Orquestração multiagente"
    if isinstance(metadata, dict) and metadata.get("artifact_type") == "intelligence_snapshot":
        return "Inteligência organizacional"
    if isinstance(metadata, dict) and metadata.get("artifact_type") == "sentiment_report":
        return "Sentimentos organizacionais"
    if isinstance(metadata, dict) and metadata.get("artifact_type") == "intelligent_report":
        return "Relatório executivo"
    return "Pergunta e resposta"


def _extract_limitations(analysis: dict[str, object]) -> list[str]:
    metadata = analysis.get("metadata")
    limitations: list[str] = []
    if isinstance(metadata, dict):
        raw_limitations = metadata.get("limitations")
        if isinstance(raw_limitations, list):
            limitations.extend(item for item in raw_limitations if isinstance(item, str))
        raw_items = metadata.get("items")
        if isinstance(raw_items, list):
            for item in raw_items:
                if isinstance(item, dict) and _item_requires_confirmation(item):
                    task = item.get("task") if isinstance(item.get("task"), str) else "Item"
                    limitations.append(f"{task}: responsável, prazo ou risco a confirmar.")
        raw_findings = metadata.get("findings")
        if isinstance(raw_findings, list):
            for finding in raw_findings:
                if isinstance(finding, dict) and _finding_requires_confirmation(finding):
                    title = (
                        finding.get("title")
                        if isinstance(finding.get("title"), str)
                        else "Achado"
                    )
                    limitations.append(
                        f"{title}: responsável, prazo ou recomendação a confirmar."
                    )
        raw_issues = metadata.get("issues")
        if isinstance(raw_issues, list):
            for issue in raw_issues:
                if isinstance(issue, dict) and _issue_requires_confirmation(issue):
                    title = (
                        issue.get("title")
                        if isinstance(issue.get("title"), str)
                        else "Divergência"
                    )
                    limitations.append(
                        f"{title}: impacto, evidência ou recomendação a confirmar."
                    )
        raw_signals = metadata.get("signals")
        if isinstance(raw_signals, list):
            for signal in raw_signals:
                if isinstance(signal, dict) and _signal_requires_confirmation(signal):
                    dimension = (
                        signal.get("dimension")
                        if isinstance(signal.get("dimension"), str)
                        else "Sinal"
                    )
                    limitations.append(
                        f"{dimension}: evidência, interpretação ou recomendação a confirmar."
                    )
        raw_alerts = metadata.get("alerts")
        if isinstance(raw_alerts, list):
            for alert in raw_alerts:
                if isinstance(alert, dict) and _alert_requires_confirmation(alert):
                    title = (
                        alert.get("title")
                        if isinstance(alert.get("title"), str)
                        else "Alerta"
                    )
                    limitations.append(
                        f"{title}: responsável, prazo, evidência ou recomendação a confirmar."
                    )
        raw_patterns = metadata.get("patterns")
        if isinstance(raw_patterns, list):
            for pattern in raw_patterns:
                if isinstance(pattern, dict) and _pattern_requires_confirmation(pattern):
                    title = (
                        pattern.get("title")
                        if isinstance(pattern.get("title"), str)
                        else "Padrão"
                    )
                    limitations.append(
                        f"{title}: recorrência, evidência histórica ou recomendação a confirmar."
                    )
        raw_outputs = metadata.get("agent_outputs")
        if isinstance(raw_outputs, list):
            for output in raw_outputs:
                if isinstance(output, dict):
                    limitations.extend(_agent_output_limitations(output))
    return sorted(set(limitations))


def _item_requires_confirmation(item: dict[str, object]) -> bool:
    return (
        _is_confirmation_value(item.get("responsible"))
        or _is_confirmation_value(item.get("deadline"))
        or _is_confirmation_value(item.get("risk"))
    )


def _finding_requires_confirmation(finding: dict[str, object]) -> bool:
    return (
        _is_confirmation_value(finding.get("responsible"))
        or _is_confirmation_value(finding.get("deadline"))
        or _is_confirmation_value(finding.get("recommendation"))
    )


def _issue_requires_confirmation(issue: dict[str, object]) -> bool:
    return (
        _is_confirmation_value(issue.get("impact"))
        or _is_confirmation_value(issue.get("evidence"))
        or _is_confirmation_value(issue.get("recommendation"))
    )


def _signal_requires_confirmation(signal: dict[str, object]) -> bool:
    return (
        _is_confirmation_value(signal.get("evidence"))
        or _is_confirmation_value(signal.get("interpretation"))
        or _is_confirmation_value(signal.get("recommendation"))
    )


def _alert_requires_confirmation(alert: dict[str, object]) -> bool:
    return (
        _is_confirmation_value(alert.get("owner"))
        or _is_confirmation_value(alert.get("deadline"))
        or _is_confirmation_value(alert.get("evidence"))
        or _is_confirmation_value(alert.get("recommendation"))
    )


def _pattern_requires_confirmation(pattern: dict[str, object]) -> bool:
    return (
        _is_confirmation_value(pattern.get("recurrence"))
        or _is_confirmation_value(pattern.get("historical_evidence"))
        or _is_confirmation_value(pattern.get("recommendation"))
    )


def _agent_output_limitations(output: dict[str, object]) -> list[str]:
    limitations = []
    raw_findings = output.get("findings")
    if not isinstance(raw_findings, list):
        return limitations
    agent_name = str(output.get("agent_name") or "Agente")
    for finding in raw_findings:
        if not isinstance(finding, dict):
            continue
        if (
            _is_confirmation_value(finding.get("evidence"))
            or _is_confirmation_value(finding.get("recommendation"))
        ):
            title = (
                finding.get("title")
                if isinstance(finding.get("title"), str)
                else "Achado"
            )
            limitations.append(f"{agent_name} - {title}: evidência ou recomendação a confirmar.")
    return limitations


def _is_confirmation_value(value: object) -> bool:
    if not isinstance(value, str):
        return True
    clean_value = value.strip()
    return not clean_value or clean_value.casefold() == "a confirmar"


def _has_duplicates(values: list[str]) -> bool:
    counts = Counter(values)
    return any(count > 1 for count in counts.values())


def _format_created_at(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    normalized_value = value.replace("Z", "+00:00")
    try:
        created_at = datetime.fromisoformat(normalized_value)
    except ValueError:
        return value
    return created_at.strftime("%d/%m/%Y %H:%M")


def _as_float(value: object) -> float:
    return float(value) if isinstance(value, int | float) else 0.0
