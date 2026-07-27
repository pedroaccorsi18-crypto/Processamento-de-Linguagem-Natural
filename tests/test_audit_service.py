from __future__ import annotations

from synapse_ai.services.audit_service import (
    audit_records_to_markdown,
    audit_records_to_pdf,
    build_audit_records,
    build_audit_summary,
    collect_source_references,
)


def _analysis() -> dict[str, object]:
    return {
        "title": "Quais riscos?",
        "question": "Quais riscos aparecem?",
        "answer": "Há risco financeiro.",
        "created_at": "2026-07-27T10:00:00+00:00",
        "sources": [
            {
                "document_id": "doc-1",
                "filename": "ata.pdf",
                "chunk_index": 0,
                "similarity": 0.91,
            },
            {
                "document_id": "doc-2",
                "filename": "ata.pdf",
                "chunk_index": 1,
                "similarity": 0.82,
            },
        ],
        "metadata": {
            "artifact_type": "action_plan",
            "items": [
                {
                    "task": "Validar orçamento",
                    "responsible": "A confirmar",
                    "deadline": "30/07/2026",
                    "risk": "Atraso",
                }
            ],
        },
    }


def test_collect_source_references_from_saved_analyses() -> None:
    assert collect_source_references([_analysis()]) == [("doc-1", 0), ("doc-2", 1)]


def test_build_audit_records_enriches_sources_with_chunk_content() -> None:
    records = build_audit_records(
        [_analysis()],
        {
            ("doc-1", 0): {"content": "Orçamento pendente."},
        },
    )

    record = records[0]
    assert record.artifact_type == "Plano de ação"
    assert record.has_duplicate_filenames is True
    assert record.sources[0].content == "Orçamento pendente."
    assert record.sources[0].evidence_available is True
    assert record.sources[1].evidence_available is False
    assert "Validar orçamento" in record.limitations[0]


def test_build_audit_summary_counts_risks() -> None:
    records = build_audit_records([_analysis()], {})

    summary = build_audit_summary(records)

    assert summary.records == 1
    assert summary.sources == 2
    assert summary.documents == 2
    assert summary.missing_evidence == 2
    assert summary.duplicate_filename_records == 1


def test_build_audit_records_labels_intelligence_snapshot() -> None:
    analysis = _analysis()
    analysis["metadata"] = {
        "artifact_type": "intelligence_snapshot",
        "findings": [
            {
                "title": "Prazo crítico",
                "responsible": "A confirmar",
                "deadline": "22/08/2026",
                "recommendation": "Validar cronograma.",
            }
        ],
    }

    record = build_audit_records([analysis], {})[0]

    assert record.artifact_type == "Inteligência organizacional"
    assert "Prazo crítico" in record.limitations[0]


def test_build_audit_records_labels_document_comparison() -> None:
    analysis = _analysis()
    analysis["metadata"] = {
        "artifact_type": "document_comparison",
        "issues": [
            {
                "title": "Data divergente",
                "impact": "A confirmar",
                "evidence": "15/08 versus 22/08.",
                "recommendation": "Confirmar cronograma.",
            }
        ],
    }

    record = build_audit_records([analysis], {})[0]

    assert record.artifact_type == "Comparação documental"
    assert "Data divergente" in record.limitations[0]


def test_build_audit_records_labels_sentiment_report() -> None:
    analysis = _analysis()
    analysis["metadata"] = {
        "artifact_type": "sentiment_report",
        "signals": [
            {
                "dimension": "Urgência",
                "evidence": "A confirmar",
                "interpretation": "Há pressão de prazo.",
                "recommendation": "Alinhar comunicação.",
            }
        ],
    }

    record = build_audit_records([analysis], {})[0]

    assert record.artifact_type == "Sentimentos organizacionais"
    assert "Urgência" in record.limitations[0]


def test_build_audit_records_labels_preventive_alert_report() -> None:
    analysis = _analysis()
    analysis["metadata"] = {
        "artifact_type": "preventive_alert_report",
        "alerts": [
            {
                "title": "Prazo crítico",
                "owner": "A confirmar",
                "deadline": "30/07/2026",
                "evidence": "Aprovação pendente.",
                "recommendation": "Escalar validação.",
            }
        ],
    }

    record = build_audit_records([analysis], {})[0]

    assert record.artifact_type == "Alertas preventivos"
    assert "Prazo crítico" in record.limitations[0]


def test_build_audit_records_labels_historical_pattern_report() -> None:
    analysis = _analysis()
    analysis["metadata"] = {
        "artifact_type": "historical_pattern_report",
        "patterns": [
            {
                "title": "Risco recorrente",
                "recurrence": "A confirmar",
                "historical_evidence": "Alerta anterior citou atraso.",
                "recommendation": "Monitorar semanalmente.",
            }
        ],
    }

    record = build_audit_records([analysis], {})[0]

    assert record.artifact_type == "Padrões históricos"
    assert "Risco recorrente" in record.limitations[0]


def test_audit_records_to_markdown_includes_evidence_package() -> None:
    records = build_audit_records(
        [_analysis()],
        {("doc-1", 0): {"content": "Orçamento pendente."}},
    )

    markdown = audit_records_to_markdown(records)

    assert "# Pacote de evidências - Synapse AI" in markdown
    assert "Quais riscos?" in markdown
    assert "Orçamento pendente." in markdown
    assert "Trecho não encontrado" in markdown


def test_audit_records_to_pdf_generates_evidence_package() -> None:
    records = build_audit_records(
        [_analysis()],
        {("doc-1", 0): {"content": "Orçamento pendente."}},
    )

    pdf_bytes = audit_records_to_pdf(records)

    assert pdf_bytes.startswith(b"%PDF")
