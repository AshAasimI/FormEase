import re
import cv2
import numpy as np
from formease.models import OcrBlock, PageData, FormField, FieldType


# --- Label classification patterns ---

LABEL_PATTERNS = {
    FieldType.TEXT: [
        r"(?i)\bname\b", r"(?i)\baddress\b", r"(?i)\boccupation\b",
        r"(?i)\bnationality\b", r"(?i)\bcompany\b", r"(?i)\borganis?ation\b",
        r"(?i)\bgender\b", r"(?i)\bsex\b", r"(?i)\brace\b", r"(?i)\breligion\b",
        r"(?i)\bsignature\b", r"(?i)\bremarks?\b", r"(?i)\bpurpose\b",
    ],
    FieldType.EMAIL: [r"(?i)\be[-\s]?mail\b"],
    FieldType.PHONE: [
        r"(?i)\bphone\b", r"(?i)\btel(?:ephone)?\b", r"(?i)\bmobile\b",
        r"(?i)\bcontact\s*(?:no|number)\b", r"(?i)\bfax\b",
    ],
    FieldType.DATE: [
        r"(?i)\bdate\b", r"(?i)\bdob\b", r"(?i)\bdate\s*of\s*birth\b",
        r"(?i)\bexpiry\b", r"(?i)\bissue\s*date\b",
    ],
    FieldType.NRIC: [r"(?i)\bnric\b", r"(?i)\bfin\b", r"(?i)\bic\s*no\b"],
    FieldType.NUMBER: [
        r"(?i)\bage\b", r"(?i)\bpostal\s*code\b", r"(?i)\bzip\b",
        r"(?i)\bunit\s*no\b", r"(?i)\bblock\b",
    ],
}


def classify_label(text: str) -> FieldType | None:
    """Return the field type if text looks like a form label, else None."""
    for ftype, patterns in LABEL_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text):
                return ftype

    return None


def is_required(label_text: str) -> bool:
    """Heuristic: field is required if label contains * or (required)."""
    return bool(re.search(r"(?i)\*|\brequired\b|\bmandatory\b", label_text))


def clean_label(text: str) -> str:
    """Remove trailing colons, asterisks, and extra whitespace from a label."""
    text = re.sub(r"[:\*]+$", "", text.strip())
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# --- Group OCR words into lines ---

def group_into_lines(blocks: list[OcrBlock]) -> list[list[OcrBlock]]:
    """Group word-level OcrBlocks into lines using block_num and line_num."""
    lines_dict = {}
    for b in blocks:
        if b.level == 5:  # word level
            key = (b.block_num, b.line_num)
            lines_dict.setdefault(key, []).append(b)

    # Sort words within each line by x coordinate
    lines = []
    for key in sorted(lines_dict.keys()):
        words = sorted(lines_dict[key], key=lambda w: w.bbox[0])
        lines.append(words)

    return lines


def _int_bbox(bbox: tuple) -> tuple:
    """Ensure all bbox values are plain Python ints (not numpy int32)."""
    return tuple(int(v) for v in bbox)


def merge_bboxes(bboxes: list[tuple]) -> tuple:
    """Merge multiple bounding boxes into one encompassing box."""
    x1 = min(b[0] for b in bboxes)
    y1 = min(b[1] for b in bboxes)
    x2 = max(b[2] for b in bboxes)
    y2 = max(b[3] for b in bboxes)
    return _int_bbox((x1, y1, x2, y2))


# --- OpenCV-based visual input region detection ---

def detect_input_regions(image_bytes: bytes) -> list[tuple]:
    """Detect horizontal lines and rectangular boxes that indicate input fields."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return []

    regions = []

    # Detect horizontal lines (underscores for handwriting)
    edges = cv2.Canny(img, 50, 150)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=80, minLineLength=100, maxLineGap=10
    )
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            if abs(y2 - y1) < 5:  # roughly horizontal
                regions.append(_int_bbox((min(x1, x2), y1 - 25, max(x1, x2), y1)))

    # Detect rectangular boxes
    _, binary = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        aspect = w / max(h, 1)
        if aspect > 2.0 and w > 80 and 15 < h < 80:
            regions.append(_int_bbox((x, y, x + w, y + h)))

    return regions


# --- Spatial association ---

def find_nearest_input_region(
    label_bbox: tuple, input_regions: list[tuple], max_distance: int = 200
) -> tuple | None:
    """Find the closest input region to the right of or below a label."""
    lx1, ly1, lx2, ly2 = label_bbox
    label_center_y = (ly1 + ly2) / 2

    best = None
    best_dist = max_distance

    for region in input_regions:
        rx1, ry1, rx2, ry2 = region
        region_center_y = (ry1 + ry2) / 2

        # Region is to the right of label (same line)
        if abs(region_center_y - label_center_y) < 30 and rx1 > lx2:
            dist = rx1 - lx2
            if dist < best_dist:
                best_dist = dist
                best = region

        # Region is below the label
        elif ry1 > ly2 and abs(rx1 - lx1) < 100:
            dist = ry1 - ly2
            if dist < best_dist:
                best_dist = dist
                best = region

    return best


def infer_answer_region(label_bbox: tuple, page_width: int) -> tuple:
    """Fallback: create an answer region to the right of the label."""
    lx1, ly1, lx2, ly2 = label_bbox
    h = ly2 - ly1
    # Place answer region from end of label to 80% of page width
    target_x2 = min(lx2 + 400, int(page_width * 0.8))
    return _int_bbox((lx2 + 10, ly1, target_x2, ly2))


# --- Main detection pipeline ---

def detect_fields(page: PageData) -> list[FormField]:
    """Detect form fields from OCR data and visual analysis."""
    lines = group_into_lines(page.ocr_blocks)
    input_regions = detect_input_regions(page.image_bytes)

    fields = []
    for line_words in lines:
        line_text = " ".join(w.text for w in line_words)
        field_type = classify_label(line_text)
        if field_type is None:
            continue

        line_bbox = merge_bboxes([w.bbox for w in line_words])
        target = find_nearest_input_region(line_bbox, input_regions)
        if target is None:
            target = infer_answer_region(line_bbox, page.width)

        avg_conf = sum(w.confidence for w in line_words) / len(line_words)

        fields.append(FormField(
            field_id=f"f{len(fields):03d}",
            page_index=page.page_index,
            label_text=clean_label(line_text),
            field_type=field_type,
            target_bbox=target,
            label_bbox=line_bbox,
            required=is_required(line_text),
            confidence=round(avg_conf, 2),
        ))

    return fields
