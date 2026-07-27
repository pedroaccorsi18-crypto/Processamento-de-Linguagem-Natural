from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

_REGISTERED_FONT_NAMES: tuple[str, str] | None = None


def register_pdf_fonts() -> tuple[str, str]:
    global _REGISTERED_FONT_NAMES
    if _REGISTERED_FONT_NAMES is not None:
        return _REGISTERED_FONT_NAMES

    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_candidates = [
        (Path(r"C:\Windows\Fonts\arial.ttf"), Path(r"C:\Windows\Fonts\arialbd.ttf")),
        (Path(r"C:\Windows\Fonts\calibri.ttf"), Path(r"C:\Windows\Fonts\calibrib.ttf")),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ),
    ]
    for regular_path, bold_path in font_candidates:
        if regular_path.exists() and bold_path.exists():
            pdfmetrics.registerFont(TTFont("Synapse-Regular", str(regular_path)))
            pdfmetrics.registerFont(TTFont("Synapse-Bold", str(bold_path)))
            _REGISTERED_FONT_NAMES = ("Synapse-Regular", "Synapse-Bold")
            return _REGISTERED_FONT_NAMES

    _REGISTERED_FONT_NAMES = ("Helvetica", "Helvetica-Bold")
    return _REGISTERED_FONT_NAMES


def pdf_text(value: object) -> str:
    text = str(value)
    text = (
        text.replace("\u2011", "-")
        .replace("\u2012", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2212", "-")
    )
    return escape(text)
