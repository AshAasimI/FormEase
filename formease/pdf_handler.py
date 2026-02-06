import io
import re
from PIL import Image
from pdf2image import convert_from_bytes
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PyPDF2 import PdfReader, PdfWriter


def pdf_to_images(pdf_bytes: bytes, dpi: int = 300) -> list[Image.Image]:
    """Convert a PDF to a list of PIL Images, one per page."""
    return convert_from_bytes(pdf_bytes, dpi=dpi)


def _parse_hex_color(value: str) -> tuple[float, float, float]:
    if not isinstance(value, str):
        return (0.1137, 0.3059, 0.8471)  # #1d4ed8
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", value.strip())
    if not m:
        return (0.1137, 0.3059, 0.8471)
    hex_value = m.group(1)
    r = int(hex_value[0:2], 16) / 255.0
    g = int(hex_value[2:4], 16) / 255.0
    b = int(hex_value[4:6], 16) / 255.0
    return (r, g, b)


def export_filled_pdf(
    document,
    answers: dict,
    font_scale: float = 1.0,
    font_color: str = "#1d4ed8",
    font_family: str = "Helvetica",
    offsets: dict | None = None,
) -> bytes:
    """Generate a filled PDF by overlaying answers onto the original form.

    For PDF input: merge overlay onto original pages.
    For image input: create new PDF with image backgrounds + overlays.
    """
    if not isinstance(font_scale, (int, float)):
        font_scale = 1.0
    font_scale = max(0.6, min(1.6, float(font_scale)))
    allowed_fonts = {"Helvetica", "Times-Roman", "Courier"}
    if font_family not in allowed_fonts:
        font_family = "Helvetica"
    color_r, color_g, color_b = _parse_hex_color(font_color)
    offsets = offsets or {}

    writer = PdfWriter()

    for page_data in document.pages:
        scale = 72.0 / page_data.dpi
        page_w_pts = page_data.width * scale
        page_h_pts = page_data.height * scale

        # Create overlay with answers
        overlay_buf = io.BytesIO()
        c = canvas.Canvas(overlay_buf, pagesize=(page_w_pts, page_h_pts))

        page_fields = [
            f for f in document.fields if f.page_index == page_data.page_index
        ]
        for field in page_fields:
            answer = answers.get(field.field_id, "")
            if not answer:
                continue

            x1, y1, x2, y2 = field.target_bbox
            offset = offsets.get(field.field_id, {})
            try:
                dx = float(offset.get("dx", 0) or 0)
            except (TypeError, ValueError):
                dx = 0.0
            try:
                dy = float(offset.get("dy", 0) or 0)
            except (TypeError, ValueError):
                dy = 0.0
            pdf_x = (x1 + dx) * scale
            pdf_y = page_h_pts - ((y2 + dy) * scale)

            box_width = (x2 - x1) * scale
            font_size = min(12, box_width / max(len(answer) * 0.6, 1))
            font_size = max(8, font_size) * font_scale
            font_size = min(24, font_size)

            c.setFont(font_family, font_size)
            c.setFillColorRGB(color_r, color_g, color_b)
            c.drawString(pdf_x + 2, pdf_y + 3, answer)

        c.save()
        overlay_buf.seek(0)

        if document.is_pdf and document.original_pdf_bytes:
            # Merge overlay onto original PDF page
            original_reader = PdfReader(io.BytesIO(document.original_pdf_bytes))
            if page_data.page_index < len(original_reader.pages):
                orig_page = original_reader.pages[page_data.page_index]
                overlay_reader = PdfReader(overlay_buf)
                if overlay_reader.pages:
                    orig_page.merge_page(overlay_reader.pages[0])
                writer.add_page(orig_page)
            else:
                overlay_reader = PdfReader(overlay_buf)
                if overlay_reader.pages:
                    writer.add_page(overlay_reader.pages[0])
        else:
            # Image input: create page with image background + overlay
            bg_buf = io.BytesIO()
            c_bg = canvas.Canvas(bg_buf, pagesize=(page_w_pts, page_h_pts))

            # Draw the original image as background
            img_reader = ImageReader(io.BytesIO(page_data.image_bytes))
            c_bg.drawImage(
                img_reader, 0, 0,
                width=page_w_pts, height=page_h_pts,
                preserveAspectRatio=True,
            )
            c_bg.save()
            bg_buf.seek(0)

            bg_reader = PdfReader(bg_buf)
            overlay_reader = PdfReader(overlay_buf)

            if bg_reader.pages:
                bg_page = bg_reader.pages[0]
                if overlay_reader.pages:
                    bg_page.merge_page(overlay_reader.pages[0])
                writer.add_page(bg_page)

    output_buf = io.BytesIO()
    writer.write(output_buf)
    return output_buf.getvalue()


def generate_text_summary(document, answers: dict) -> str:
    """Generate a plain-text summary of all form answers."""
    lines = ["FORM SUMMARY", "=" * 40, ""]
    for field in document.fields:
        answer = answers.get(field.field_id, "(not answered)")
        lines.append(f"{field.label_text}: {answer}")
    lines.append("")
    lines.append("=" * 40)
    return "\n".join(lines)
