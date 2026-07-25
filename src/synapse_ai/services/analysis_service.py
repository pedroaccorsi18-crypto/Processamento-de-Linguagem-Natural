from __future__ import annotations


def describe_planned_analysis_capabilities() -> list[str]:
    return [
        "Busca semântica em documentos organizacionais",
        "Perguntas em linguagem natural com rastreabilidade",
        "Sínteses executivas",
        "Identificação de decisões, responsáveis, riscos e inconsistências",
    ]


def analysis_pipeline_available() -> bool:
    return False
