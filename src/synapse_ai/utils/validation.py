from __future__ import annotations

import re

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_PATTERN.match(email.strip()))


def validate_password(password: str) -> bool:
    return len(password) >= 8


def passwords_match(password: str, confirmation: str) -> bool:
    return password == confirmation
