from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import uuid


class FieldType(Enum):
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    EMAIL = "email"
    PHONE = "phone"
    CHECKBOX = "checkbox"
    NRIC = "nric"


class AccessibilityMode(Enum):
    STANDARD = "standard"
    VISION = "vision"
    MOTOR = "motor"
    COGNITIVE = "cognitive"


@dataclass
class OcrBlock:
    text: str
    bbox: tuple  # (x1, y1, x2, y2)
    confidence: float
    level: int  # tesseract hierarchy: 1=page, 2=block, 3=para, 4=line, 5=word
    block_num: int
    line_num: int
    word_num: int


@dataclass
class FormField:
    field_id: str
    page_index: int
    label_text: str
    field_type: FieldType
    target_bbox: tuple  # (x1, y1, x2, y2) -- where to place answer
    label_bbox: tuple  # (x1, y1, x2, y2) -- where the label is
    required: bool
    confidence: float
    answer: str = ""
    validation_hint: str = ""


@dataclass
class PageData:
    page_index: int
    image_bytes: bytes  # original page image as PNG bytes
    width: int
    height: int
    ocr_blocks: list  # list[OcrBlock]
    dpi: int = 300


@dataclass
class FormDocument:
    document_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    original_filename: str = ""
    is_pdf: bool = False
    pages: list = field(default_factory=list)  # list[PageData]
    fields: list = field(default_factory=list)  # list[FormField]
    original_pdf_bytes: Optional[bytes] = None
    settings: dict = field(default_factory=lambda: {
        "mode": "standard",
        "tts_enabled": True,
        "language": "en",
    })
