from __future__ import annotations

import json
from io import BytesIO
from zipfile import ZipFile

from synapse_ai.models.document import DocumentStatus
from synapse_ai.services.document_service import (
    DocumentProcessingError,
    UploadedDocument,
    build_document_payload,
    is_audio_document,
    parse_transcribed_audio_document,
    parse_uploaded_document,
    preview_text,
)


def test_parse_text_document_extracts_text_and_metadata() -> None:
    parsed = parse_uploaded_document(
        UploadedDocument(
            filename="ata.txt",
            content_type="text/plain",
            content="Decisão aprovada pela diretoria.".encode(),
        )
    )

    assert parsed.status == DocumentStatus.EXTRACTED
    assert parsed.text == "Decisão aprovada pela diretoria."
    assert parsed.metadata["file_extension"] == "txt"
    assert parsed.metadata["word_count"] == 4
    assert "checksum_sha256" in parsed.metadata


def test_parse_markdown_document_normalizes_line_endings() -> None:
    parsed = parse_uploaded_document(
        UploadedDocument(
            filename="relatorio.md",
            content_type="text/markdown",
            content=b"# Titulo\r\n\r\nConteudo",
        )
    )

    assert parsed.text == "# Titulo\n\nConteudo"


def test_parse_csv_document_extracts_plain_text() -> None:
    parsed = parse_uploaded_document(
        UploadedDocument(
            filename="indicadores.csv",
            content_type="text/csv",
            content=b"categoria;valor\nrisco;alto",
        )
    )

    assert parsed.text == "categoria;valor\nrisco;alto"
    assert parsed.metadata["file_extension"] == "csv"
    assert parsed.metadata["encoding"] == "utf-8-sig"


def test_parse_jira_csv_document_formats_tickets_for_analysis() -> None:
    parsed = parse_uploaded_document(
        UploadedDocument(
            filename="jira_export.csv",
            content_type="text/csv",
            content=(
                "Issue key;Summary;Status;Priority;Assignee;Due date;Description\n"
                "ORION-42;Corrigir autenticação;Em andamento;Alta;Equipe Tecnologia;"
                "2026-08-05;Falhas de login aumentaram no portal\n"
                "ORION-43;Aprovar orçamento;Pendente;Crítica;Fernanda Lima;"
                "2026-07-30;Sem aprovação financeira o lançamento pode atrasar"
            ).encode(),
        )
    )

    assert parsed.metadata["source_type"] == "ticket_export"
    assert parsed.metadata["ticket_count"] == 2
    assert "Exportação de tickets detectada" in parsed.text
    assert "Ticket 1: Corrigir autenticação" in parsed.text
    assert "Chave: ORION-42" in parsed.text
    assert "Responsável: Equipe Tecnologia" in parsed.text
    assert "Prazo: 2026-08-05" in parsed.text
    assert "Ticket 2: Aprovar orçamento" in parsed.text
    assert "Prioridade: Crítica" in parsed.text


def test_parse_slack_json_document_formats_messages_for_analysis() -> None:
    parsed = parse_uploaded_document(
        UploadedDocument(
            filename="slack_canal_orion.json",
            content_type="application/json",
            content=json.dumps(
                [
                    {
                        "type": "message",
                        "user": "Ana Ribeiro",
                        "text": "Aprovação final do orçamento segue pendente.",
                        "ts": "2026-07-27 09:10",
                    },
                    {
                        "type": "message",
                        "user": "Bruno Costa",
                        "text": "Tecnologia precisa revisar o fluxo de autenticação.",
                        "ts": "2026-07-27 09:12",
                    },
                ],
                ensure_ascii=False,
            ).encode(),
        )
    )

    assert parsed.metadata["source_type"] == "slack_export"
    assert parsed.metadata["platform"] == "slack"
    assert parsed.metadata["message_count"] == 2
    assert "Exportação Slack detectada" in parsed.text
    assert "Autor: Ana Ribeiro" in parsed.text
    assert "Conteúdo: Aprovação final do orçamento segue pendente." in parsed.text


def test_parse_teams_json_document_formats_messages_for_analysis() -> None:
    parsed = parse_uploaded_document(
        UploadedDocument(
            filename="teams_chat_orion.json",
            content_type="application/json",
            content=json.dumps(
                {
                    "value": [
                        {
                            "createdDateTime": "2026-07-27T12:30:00Z",
                            "from": {"user": {"displayName": "Carla Mendes"}},
                            "body": {
                                "content": "<p>Contrato de segurança ainda não foi assinado.</p>"
                            },
                        }
                    ]
                },
                ensure_ascii=False,
            ).encode(),
        )
    )

    assert parsed.metadata["source_type"] == "teams_export"
    assert parsed.metadata["platform"] == "microsoft_teams"
    assert parsed.metadata["message_count"] == 1
    assert "Exportação Microsoft Teams detectada" in parsed.text
    assert "Autor: Carla Mendes" in parsed.text
    assert "Conteúdo: Contrato de segurança ainda não foi assinado." in parsed.text


def test_parse_vtt_document_formats_meeting_transcript_for_analysis() -> None:
    parsed = parse_uploaded_document(
        UploadedDocument(
            filename="reuniao_teams.vtt",
            content_type="text/vtt",
            content=(
                "WEBVTT\n\n"
                "1\n"
                "00:00:01.000 --> 00:00:04.000\n"
                "<v Fernanda Lima>Precisamos concluir a aprovação financeira.</v>\n\n"
                "2\n"
                "00:00:05.000 --> 00:00:08.000\n"
                "<v Diego Santos>Sem isso, o lançamento fica em risco.</v>\n"
            ).encode(),
        )
    )

    assert parsed.metadata["source_type"] == "meeting_transcript"
    assert parsed.metadata["transcript_format"] == "webvtt"
    assert parsed.metadata["line_count"] == 2
    assert "Transcrição Teams/WebVTT detectada" in parsed.text
    assert "Fernanda Lima: Precisamos concluir a aprovação financeira." in parsed.text
    assert "Diego Santos: Sem isso, o lançamento fica em risco." in parsed.text


def test_parse_email_document_extracts_headers_and_body() -> None:
    parsed = parse_uploaded_document(
        UploadedDocument(
            filename="decisao.eml",
            content_type="message/rfc822",
            content=(
                "Subject: Aprovação financeira\n"
                "From: financeiro@example.com\n"
                "To: produto@example.com\n"
                "Date: Mon, 27 Jul 2026 10:00:00 -0300\n"
                "Content-Type: text/plain; charset=utf-8\n"
                "\n"
                "A aprovação do orçamento ficou pendente para sexta-feira."
            ).encode(),
        )
    )

    assert "Assunto: Aprovação financeira" in parsed.text
    assert "De: financeiro@example.com" in parsed.text
    assert "A aprovação do orçamento ficou pendente" in parsed.text
    assert parsed.metadata["file_extension"] == "eml"
    assert parsed.metadata["subject"] == "Aprovação financeira"


def test_parse_pptx_document_extracts_slide_text() -> None:
    parsed = parse_uploaded_document(
        UploadedDocument(
            filename="apresentacao.pptx",
            content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            content=_minimal_pptx(),
        )
    )

    assert "Slide 1" in parsed.text
    assert "Lançamento Projeto Orion" in parsed.text
    assert "Risco de atraso por aprovação pendente" in parsed.text
    assert parsed.metadata["file_extension"] == "pptx"
    assert parsed.metadata["slide_count"] == 1


def test_parse_xlsx_document_extracts_sheet_cells() -> None:
    parsed = parse_uploaded_document(
        UploadedDocument(
            filename="cronograma.xlsx",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            content=_minimal_xlsx(),
        )
    )

    assert "Planilha 1" in parsed.text
    assert "Projeto | Status" in parsed.text
    assert "Orion | Aprovação pendente" in parsed.text
    assert parsed.metadata["file_extension"] == "xlsx"
    assert parsed.metadata["sheet_count"] == 1
    assert parsed.metadata["row_count"] == 2
    assert parsed.metadata["cell_count"] == 4


def test_parse_jira_xlsx_document_formats_tickets_for_analysis() -> None:
    parsed = parse_uploaded_document(
        UploadedDocument(
            filename="jira_export.xlsx",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            content=_minimal_ticket_xlsx(),
        )
    )

    assert parsed.metadata["source_type"] == "ticket_export"
    assert parsed.metadata["ticket_count"] == 1
    assert parsed.metadata["sheet_count"] == 1
    assert "Exportação de tickets detectada - Planilha 1" in parsed.text
    assert "Ticket 1: Estabilizar autenticação" in parsed.text
    assert "Chave: ORION-99" in parsed.text
    assert "Status: Aberto" in parsed.text
    assert "Prioridade: Alta" in parsed.text


def test_parse_transcribed_audio_document_builds_searchable_document() -> None:
    parsed = parse_transcribed_audio_document(
        UploadedDocument(
            filename="reuniao.m4a",
            content_type="audio/mp4",
            content=b"audio-content",
        ),
        "Decidimos reprogramar o lançamento para 22 de agosto.",
        "gpt-4o-mini-transcribe",
    )

    assert parsed.status == DocumentStatus.EXTRACTED
    assert parsed.text == "Decidimos reprogramar o lançamento para 22 de agosto."
    assert parsed.metadata["file_extension"] == "m4a"
    assert parsed.metadata["source_type"] == "audio_transcription"
    assert parsed.metadata["transcription_model"] == "gpt-4o-mini-transcribe"
    assert parsed.metadata["word_count"] == 8


def test_is_audio_document_identifies_supported_audio_extensions() -> None:
    assert is_audio_document("reuniao.mp3") is True
    assert is_audio_document("reuniao.wav") is True
    assert is_audio_document("ata.pdf") is False


def test_parse_rejects_unsupported_extension() -> None:
    try:
        parse_uploaded_document(
            UploadedDocument(
                filename="arquivo.xml",
                content_type="application/xml",
                content=b"content",
            )
        )
    except DocumentProcessingError as exc:
        assert "Formato" in str(exc)
    else:
        raise AssertionError("Expected DocumentProcessingError")


def test_build_document_payload_contains_phase_2_fields() -> None:
    parsed = parse_uploaded_document(
        UploadedDocument(
            filename="ata.txt",
            content_type="text/plain",
            content=b"Texto extraido",
        )
    )

    payload = build_document_payload("user-1", parsed)

    assert payload["user_id"] == "user-1"
    assert payload["filename"] == "ata.txt"
    assert payload["status"] == "extracted"
    assert payload["extracted_text"] == "Texto extraido"
    assert payload["text_char_count"] == len("Texto extraido")
    assert isinstance(payload["metadata"], dict)


def test_preview_text_truncates_long_content() -> None:
    preview = preview_text("abcdef", limit=3)

    assert preview == "abc..."


def _minimal_pptx() -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(
            "ppt/slides/slide1.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:sp>
        <p:txBody>
          <a:p><a:r><a:t>Lançamento Projeto Orion</a:t></a:r></a:p>
          <a:p><a:r><a:t>Risco de atraso por aprovação pendente</a:t></a:r></a:p>
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:sld>
""",
        )
    return buffer.getvalue()


def _minimal_xlsx() -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(
            "xl/sharedStrings.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <si><t>Projeto</t></si>
  <si><t>Status</t></si>
  <si><t>Orion</t></si>
  <si><t>Aprovação pendente</t></si>
</sst>
""",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1" t="s"><v>0</v></c>
      <c r="B1" t="s"><v>1</v></c>
    </row>
    <row r="2">
      <c r="A2" t="s"><v>2</v></c>
      <c r="B2" t="s"><v>3</v></c>
    </row>
  </sheetData>
</worksheet>
""",
        )
    return buffer.getvalue()


def _minimal_ticket_xlsx() -> bytes:
    buffer = BytesIO()
    values = [
        "Issue key",
        "Summary",
        "Status",
        "Priority",
        "Assignee",
        "Description",
        "ORION-99",
        "Estabilizar autenticação",
        "Aberto",
        "Alta",
        "Tecnologia",
        "Chamados de login cresceram nas últimas duas semanas.",
    ]
    with ZipFile(buffer, "w") as archive:
        archive.writestr(
            "xl/sharedStrings.xml",
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            "<sst xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\">\n"
            + "\n".join(f"  <si><t>{value}</t></si>" for value in values)
            + "\n</sst>\n",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1" t="s"><v>0</v></c>
      <c r="B1" t="s"><v>1</v></c>
      <c r="C1" t="s"><v>2</v></c>
      <c r="D1" t="s"><v>3</v></c>
      <c r="E1" t="s"><v>4</v></c>
      <c r="F1" t="s"><v>5</v></c>
    </row>
    <row r="2">
      <c r="A2" t="s"><v>6</v></c>
      <c r="B2" t="s"><v>7</v></c>
      <c r="C2" t="s"><v>8</v></c>
      <c r="D2" t="s"><v>9</v></c>
      <c r="E2" t="s"><v>10</v></c>
      <c r="F2" t="s"><v>11</v></c>
    </row>
  </sheetData>
</worksheet>
""",
        )
    return buffer.getvalue()
