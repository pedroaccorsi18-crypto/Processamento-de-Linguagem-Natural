from __future__ import annotations

from synapse_ai.application.dashboard import IntelligentExecutiveReportUseCase
from synapse_ai.ui.dashboard_use_cases import build_intelligent_executive_report_use_case


def test_dashboard_use_case_builders_return_expected_use_cases() -> None:
    assert isinstance(
        build_intelligent_executive_report_use_case(),
        IntelligentExecutiveReportUseCase,
    )
