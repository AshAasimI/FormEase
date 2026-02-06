import json
import os
import re
from typing import Iterable

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore

from formease.models import FormField, FieldType, PageData
from formease.field_detector import (
    classify_label,
    clean_label,
    detect_input_regions,
    find_nearest_input_region,
    group_into_lines,
    infer_answer_region,
    is_required,
    merge_bboxes,
)


_FIELD_TYPE_VALUES = {
    FieldType.TEXT.value,
    FieldType.NUMBER.value,
    FieldType.DATE.value,
    FieldType.EMAIL.value,
    FieldType.PHONE.value,
    FieldType.CHECKBOX.value,
    FieldType.NRIC.value,
}

_ENV_STOP_LABELS = {
    s.strip().lower()
    for s in os.getenv("FORMEASE_STOP_LABELS", "").split("|")
    if s.strip()
}


def _looks_like_instruction(text: str) -> bool:
    """Heuristic filter for paragraph-like labels or instructions."""
    t = text.strip()
    lower = t.lower()
    word_count = len([w for w in re.split(r"\s+", t) if w])

    # Long sentences without typical label punctuation
    if word_count >= 9 and ":" not in t and "_" not in t:
        return True

    # Paragraph-ish: ends with a period and has several words
    if t.endswith(".") and word_count >= 6:
        return True

    # Comma-heavy sentence-like labels are usually not fields
    if "," in t and word_count >= 6 and "_" not in t:
        return True

    # Starts like a sentence (capitalized article) and is long
    if re.match(r"^(The|This|These|Those)\b", t) and word_count >= 6:
        return True

    return False


def _field_type_from_value(value: str) -> FieldType:
    try:
        return FieldType(value)
    except Exception:
        return FieldType.TEXT


def _as_int_bbox(values: Iterable[int | float]) -> tuple:
    vals = [int(round(v)) for v in values]
    if len(vals) != 4:
        return (0, 0, 0, 0)
    return tuple(vals)


def _build_line_items(page: PageData, max_lines: int = 200) -> list[dict]:
    lines = group_into_lines(page.ocr_blocks)
    items = []
    for line_words in lines:
        line_text = " ".join(w.text for w in line_words).strip()
        if not line_text:
            continue
        line_bbox = merge_bboxes([w.bbox for w in line_words])
        avg_conf = sum(w.confidence for w in line_words) / max(len(line_words), 1)
        items.append({
            "text": line_text,
            "bbox": list(line_bbox),
            "confidence": round(avg_conf, 3),
        })

    # Keep in reading order; cap to avoid huge prompts
    return items[:max_lines]


def detect_fields_llm(page: PageData, model: str | None = None) -> list[FormField]:
    """Use an OpenAI model to extract form fields from OCR lines."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or OpenAI is None:
        print("[LLM] Skipping: missing OPENAI_API_KEY or openai package.")
        return []

    model = model or os.getenv("FORMEASE_LLM_MODEL", "gpt-4o-mini")

    line_items = _build_line_items(page)
    if not line_items:
        return []

    client = OpenAI()

    system_msg = (
        "You extract form fields from OCR lines. "
        "Return JSON only, matching the schema. "
        "Identify labels that correspond to user input fields. "
        "Use only these field_type values: text, number, date, email, phone, checkbox, nric."
    )

    user_payload = {
        "page": {
            "width": page.width,
            "height": page.height,
        },
        "ocr_lines": line_items,
    }

    schema = {
        "name": "form_fields",
        "description": "Extracted form field labels from OCR lines",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "fields": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "label_text": {"type": "string"},
                            "field_type": {
                                "type": "string",
                                "enum": sorted(_FIELD_TYPE_VALUES),
                            },
                            "label_bbox": {
                                "type": "array",
                                "items": {"type": "integer"},
                                "minItems": 4,
                                "maxItems": 4,
                            },
                            "required": {"type": "boolean"},
                            "confidence": {"type": "number"},
                        },
                        "required": [
                            "label_text",
                            "field_type",
                            "label_bbox",
                            "required",
                            "confidence",
                        ],
                    },
                },
            },
            "required": ["fields"],
        },
        "strict": True,
    }

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_msg},
                {
                    "role": "user",
                    "content": "Extract fields from OCR lines as JSON: " + json.dumps(user_payload),
                },
            ],
            response_format={"type": "json_schema", "json_schema": schema},
            temperature=0,
        )
    except Exception as exc:
        print(f"[LLM] Request failed: {exc}")
        return []

    try:
        content = response.choices[0].message.content
        data = json.loads(content) if content else {}
        raw_fields = data.get("fields", [])
    except Exception as exc:
        print(f"[LLM] Response parse failed: {exc}")
        return []

    input_regions = detect_input_regions(page.image_bytes)
    fields: list[FormField] = []

    for idx, item in enumerate(raw_fields):
        label_text = clean_label(str(item.get("label_text", "")).strip())
        if not label_text:
            continue
        if label_text.strip().lower() in _ENV_STOP_LABELS:
            continue
        if _looks_like_instruction(label_text):
            continue

        field_type = _field_type_from_value(str(item.get("field_type", "text")))
        label_bbox = _as_int_bbox(item.get("label_bbox", []))
        if label_bbox == (0, 0, 0, 0):
            continue

        target = find_nearest_input_region(label_bbox, input_regions)
        inferred = False
        if target is None:
            target = infer_answer_region(label_bbox, page.width)
            inferred = True

        # If we had to infer and the label doesn't look like a real field, drop it.
        if inferred and classify_label(label_text) is None:
            continue

        required = bool(item.get("required", False))
        if not required:
            required = is_required(label_text)

        confidence = float(item.get("confidence", 0.7))

        fields.append(FormField(
            field_id=f"llm{idx:03d}",
            page_index=page.page_index,
            label_text=label_text,
            field_type=field_type,
            target_bbox=target,
            label_bbox=label_bbox,
            required=required,
            confidence=round(confidence, 2),
        ))

    print(f"[LLM] Extracted fields: {len(fields)}")
    return fields


def merge_fields(heuristic: list[FormField], llm: list[FormField]) -> list[FormField]:
    """Merge LLM fields with heuristic fields, de-duping by label text."""
    if not llm:
        return heuristic

    merged = list(heuristic)
    seen = {f.label_text.strip().lower(): f for f in heuristic}

    for f in llm:
        key = f.label_text.strip().lower()
        if not key:
            continue
        if key not in seen:
            merged.append(f)
            seen[key] = f
            continue

        # Prefer the higher-confidence field
        if f.confidence > seen[key].confidence:
            existing = seen[key]
            merged.remove(existing)
            merged.append(f)
            seen[key] = f

    return merged
