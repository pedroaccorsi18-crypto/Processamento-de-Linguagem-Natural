from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from synapse_ai.services.agent_service import AgentFinding, AgentOutput, MultiAgentReport
from synapse_ai.services.alert_service import PreventiveAlert, PreventiveAlertReport
from synapse_ai.services.analysis_repository import (
    AnalysisPersistenceError,
    list_recent_analyses,
    save_action_plan_result,
    save_analysis_result,
    save_document_comparison_result,
    save_historical_pattern_report_result,
    save_intelligence_snapshot_result,
    save_multi_agent_report_result,
    save_preventive_alert_report_result,
    save_sentiment_report_result,
)
from synapse_ai.services.analysis_service import (
    ActionPlan,
    ActionPlanItem,
    RAGAnswer,
    SourceSnippet,
)
from synapse_ai.services.comparison_service import (
    DocumentComparisonIssue,
    DocumentComparisonReport,
)
from synapse_ai.services.intelligence_service import IntelligenceFinding, IntelligenceSnapshot
from synapse_ai.services.pattern_service import HistoricalPattern, HistoricalPatternReport
from synapse_ai.services.sentiment_service import SentimentReport, SentimentSignal


class FakeQuery:
    def __init__(self, response_data: Any | None = None, fail: bool = False) -> None:
        self.response_data = response_data if response_data is not None else []
        self.fail = fail
        self.inserted_payload: dict[str, Any] | None = None

    def insert(self, payload: dict[str, Any]) -> FakeQuery:
        self.inserted_payload = payload
        return self

    def select(self, _columns: str) -> FakeQuery:
        return self

    def eq(self, _column: str, _value: str) -> FakeQuery:
        return self

    def order(self, _column: str, desc: bool = False) -> FakeQuery:
        return self

    def limit(self, _limit: int) -> FakeQuery:
        return self

    def execute(self) -> SimpleNamespace:
        if self.fail:
            raise RuntimeError("failed")
        if self.inserted_payload is not None:
            return SimpleNamespace(data=[self.inserted_payload])
        return SimpleNamespace(data=self.response_data)


class FakeClient:
    def __init__(self, query: FakeQuery) -> None:
        self.query = query

    def table(self, table_name: str) -> FakeQuery:
        assert table_name == "analyses"
        return self.query


def test_save_analysis_result_persists_question_answer_and_sources() -> None:
    query = FakeQuery()
    client = FakeClient(query)
    rag_answer = RAGAnswer(
        answer="Resposta com fonte.",
        sources=[SourceSnippet("doc-1", "ata.txt", 0, "Trecho usado.", 0.9)],
    )

    record = save_analysis_result(client, "user-1", "Qual foi a decisão?", rag_answer, "gpt-5-mini")

    assert record["user_id"] == "user-1"
    assert record["document_id"] == "doc-1"
    assert record["question"] == "Qual foi a decisão?"
    assert record["answer"] == "Resposta com fonte."
    assert record["sources"][0]["filename"] == "ata.txt"
    assert record["status"] == "ready"


def test_save_action_plan_result_persists_structured_metadata() -> None:
    query = FakeQuery()
    client = FakeClient(query)
    action_plan = ActionPlan(
        items=[
            ActionPlanItem(
                task="Validar orçamento",
                responsible="Fernanda",
                deadline="30/07/2026",
                priority="Alta",
                risk="Atraso no lançamento",
                evidence="Aprovação financeira pendente.",
                source_refs=["Fonte 1"],
            )
        ],
        sources=[SourceSnippet("doc-1", "ata.txt", 0, "Trecho usado.", 0.9)],
    )

    record = save_action_plan_result(client, "user-1", action_plan, "gpt-5-mini")

    assert record["user_id"] == "user-1"
    assert record["document_id"] == "doc-1"
    assert record["metadata"]["artifact_type"] == "action_plan"
    assert record["metadata"]["item_count"] == 1
    assert record["metadata"]["items"][0]["task"] == "Validar orçamento"
    assert "Validar orçamento" in record["answer"]


def test_save_intelligence_snapshot_result_persists_structured_metadata() -> None:
    query = FakeQuery()
    client = FakeClient(query)
    snapshot = IntelligenceSnapshot(
        executive_summary="Há risco financeiro relevante.",
        findings=[
            IntelligenceFinding(
                category="Risco",
                title="Atraso por orçamento",
                description="O cronograma depende de aprovação financeira.",
                severity="Alta",
                responsible="Financeiro",
                deadline="30/07/2026",
                evidence="Orçamento pendente.",
                recommendation="Antecipar validação financeira.",
                source_refs=["Fonte 1"],
            )
        ],
        sources=[SourceSnippet("doc-1", "ata.txt", 0, "Trecho usado.", 0.9)],
    )

    record = save_intelligence_snapshot_result(client, "user-1", snapshot, "gpt-5-mini")

    assert record["user_id"] == "user-1"
    assert record["document_id"] == "doc-1"
    assert record["metadata"]["artifact_type"] == "intelligence_snapshot"
    assert record["metadata"]["finding_count"] == 1
    assert record["metadata"]["findings"][0]["title"] == "Atraso por orçamento"
    assert "Inteligência organizacional" in record["answer"]


def test_save_document_comparison_result_persists_structured_metadata() -> None:
    query = FakeQuery()
    client = FakeClient(query)
    report = DocumentComparisonReport(
        executive_summary="Há divergência de cronograma.",
        issues=[
            DocumentComparisonIssue(
                issue_type="Cronograma",
                title="Datas divergentes",
                description="Um documento cita 15/08 e outro 22/08.",
                severity="Alta",
                documents=["ata.pdf", "email.pdf"],
                impact="Comunicação inconsistente.",
                evidence="15/08 versus 22/08.",
                recommendation="Confirmar data oficial.",
                source_refs=["Fonte 1", "Fonte 2"],
            )
        ],
        sources=[SourceSnippet("doc-1", "ata.txt", 0, "Trecho usado.", 0.9)],
    )

    record = save_document_comparison_result(client, "user-1", report, "gpt-5-mini")

    assert record["user_id"] == "user-1"
    assert record["document_id"] == "doc-1"
    assert record["metadata"]["artifact_type"] == "document_comparison"
    assert record["metadata"]["issue_count"] == 1
    assert record["metadata"]["issues"][0]["title"] == "Datas divergentes"
    assert "Comparação documental" in record["answer"]


def test_save_sentiment_report_result_persists_structured_metadata() -> None:
    query = FakeQuery()
    client = FakeClient(query)
    report = SentimentReport(
        overall_sentiment="Misto",
        executive_summary="Há tensão e urgência no escopo analisado.",
        risk_level="Médio",
        dominant_signals=["Urgência"],
        signals=[
            SentimentSignal(
                dimension="Urgência",
                label="Negativo",
                intensity="Alta",
                polarity=-0.65,
                evidence="Validação urgente solicitada.",
                interpretation="O texto indica pressão por prazo.",
                recommendation="Alinhar responsáveis e prazo.",
                source_refs=["Fonte 1"],
            )
        ],
        sources=[SourceSnippet("doc-1", "ata.txt", 0, "Trecho usado.", 0.9)],
    )

    record = save_sentiment_report_result(client, "user-1", report, "gpt-5-mini")

    assert record["user_id"] == "user-1"
    assert record["document_id"] == "doc-1"
    assert record["metadata"]["artifact_type"] == "sentiment_report"
    assert record["metadata"]["overall_sentiment"] == "Misto"
    assert record["metadata"]["signal_count"] == 1
    assert record["metadata"]["signals"][0]["dimension"] == "Urgência"
    assert "sentimentos organizacionais" in record["answer"]


def test_save_preventive_alert_report_result_persists_structured_metadata() -> None:
    query = FakeQuery()
    client = FakeClient(query)
    report = PreventiveAlertReport(
        executive_summary="Há risco preventivo por prazo crítico.",
        alerts=[
            PreventiveAlert(
                alert_type="Prazo",
                title="Prazo crítico para aprovação",
                severity="Crítica",
                status="Aberto",
                trigger="Aprovação pendente próxima do limite.",
                evidence="Aprovação exigida até 30/07/2026.",
                impact="Risco de atraso no lançamento.",
                recommendation="Escalar validação com Financeiro.",
                owner="Financeiro",
                deadline="30/07/2026",
                source_refs=["Fonte 1"],
            )
        ],
        sources=[SourceSnippet("doc-1", "ata.txt", 0, "Trecho usado.", 0.9)],
    )

    record = save_preventive_alert_report_result(client, "user-1", report, "gpt-5-mini")

    assert record["user_id"] == "user-1"
    assert record["document_id"] == "doc-1"
    assert record["metadata"]["artifact_type"] == "preventive_alert_report"
    assert record["metadata"]["alert_count"] == 1
    assert record["metadata"]["critical_alert_count"] == 1
    assert record["metadata"]["alerts"][0]["title"] == "Prazo crítico para aprovação"
    assert "Alertas preventivos" in record["answer"]


def test_save_historical_pattern_report_result_persists_structured_metadata() -> None:
    query = FakeQuery()
    client = FakeClient(query)
    report = HistoricalPatternReport(
        executive_summary="Há recorrência de risco financeiro.",
        historical_record_count=2,
        patterns=[
            HistoricalPattern(
                pattern_type="Orçamento",
                title="Aprovação financeira recorrente",
                recurrence="Aparece no escopo atual e em análise anterior.",
                severity="Alta",
                current_signal="Orçamento pendente.",
                historical_evidence="Alerta anterior citou aprovação financeira pendente.",
                interpretation="O gargalo financeiro voltou a aparecer.",
                recommendation="Criar validação financeira antecipada.",
                source_refs=["Fonte 1"],
                related_records=["Alertas preventivos gerados"],
            )
        ],
        sources=[SourceSnippet("doc-1", "ata.txt", 0, "Trecho usado.", 0.9)],
    )

    record = save_historical_pattern_report_result(client, "user-1", report, "gpt-5-mini")

    assert record["user_id"] == "user-1"
    assert record["document_id"] == "doc-1"
    assert record["metadata"]["artifact_type"] == "historical_pattern_report"
    assert record["metadata"]["pattern_count"] == 1
    assert record["metadata"]["historical_record_count"] == 2
    assert record["metadata"]["patterns"][0]["title"] == "Aprovação financeira recorrente"
    assert "Padrões históricos" in record["answer"]


def test_save_multi_agent_report_result_persists_structured_metadata() -> None:
    query = FakeQuery()
    client = FakeClient(query)
    report = MultiAgentReport(
        executive_summary="Há consenso multiagente sobre risco financeiro.",
        consensus=["Risco financeiro recorrente."],
        conflicts=["Evidência de aprovação ainda insuficiente."],
        recommendations=["Priorizar validação financeira."],
        historical_record_count=2,
        agent_outputs=[
            AgentOutput(
                agent_id="risk_agent",
                agent_name="Agente de Riscos",
                mission="Identificar riscos.",
                summary="Há risco de atraso.",
                confidence="Alta",
                findings=[
                    AgentFinding(
                        category="Risco",
                        title="Aprovação pendente",
                        severity="Alta",
                        evidence="Orçamento depende de aprovação.",
                        recommendation="Escalar validação.",
                        source_refs=["Fonte 1"],
                    )
                ],
            )
        ],
        sources=[SourceSnippet("doc-1", "ata.txt", 0, "Trecho usado.", 0.9)],
    )

    record = save_multi_agent_report_result(client, "user-1", report, "gpt-5-mini")

    assert record["user_id"] == "user-1"
    assert record["document_id"] == "doc-1"
    assert record["metadata"]["artifact_type"] == "multi_agent_report"
    assert record["metadata"]["agent_count"] == 1
    assert record["metadata"]["finding_count"] == 1
    assert record["metadata"]["agent_outputs"][0]["agent_name"] == "Agente de Riscos"
    assert "Orquestração multiagente" in record["answer"]


def test_save_analysis_result_wraps_errors() -> None:
    client = FakeClient(FakeQuery(fail=True))
    rag_answer = RAGAnswer(
        answer="Resposta.",
        sources=[SourceSnippet("doc-1", "ata.txt", 0, "Trecho.", 0.9)],
    )

    with pytest.raises(AnalysisPersistenceError):
        save_analysis_result(client, "user-1", "Pergunta?", rag_answer, "gpt-5-mini")


def test_list_recent_analyses_returns_response_data() -> None:
    analyses = [{"id": "analysis-1", "question": "Pergunta?"}]
    client = FakeClient(FakeQuery(response_data=analyses))

    assert list_recent_analyses(client, "user-1") == analyses
