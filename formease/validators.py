import re
from formease.models import FieldType


def validate_field(field_type: FieldType, answer: str) -> tuple[bool, str | None]:
    """Validate a field answer based on its type.

    Returns (is_valid, error_message_or_None).
    """
    if not answer.strip():
        return True, None  # Empty is OK (required check is separate)

    answer = answer.strip()

    if field_type == FieldType.EMAIL:
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", answer):
            return False, "Please enter a valid email address (must contain @)."

    elif field_type == FieldType.PHONE:
        digits = re.sub(r"[\s\-\+\(\)]", "", answer)
        if not digits.isdigit() or len(digits) < 7 or len(digits) > 15:
            return False, "Please enter a valid phone number (7\u201315 digits)."

    elif field_type == FieldType.DATE:
        patterns = [
            r"^\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}$",
            r"^\d{4}[/\-]\d{1,2}[/\-]\d{1,2}$",
        ]
        if not any(re.match(p, answer) for p in patterns):
            return False, "Please enter a valid date (DD/MM/YYYY or YYYY-MM-DD)."

    elif field_type == FieldType.NRIC:
        if not re.match(r"^[STFGM]\d{7}[A-Z]$", answer.upper()):
            return False, "Please enter a valid NRIC/FIN (e.g., S1234567A)."

    elif field_type == FieldType.NUMBER:
        cleaned = answer.replace(".", "").replace("-", "").replace(",", "")
        if not cleaned.isdigit():
            return False, "Please enter a number."

    return True, None
