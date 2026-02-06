import io
import pytesseract
from PIL import Image
from formease.models import OcrBlock, PageData


def ocr_page(image: Image.Image, page_index: int, dpi: int = 300) -> PageData:
    """Run OCR on a PIL Image and return structured data with bounding boxes."""
    image_rgb = image.convert("RGB")

    data = pytesseract.image_to_data(
        image_rgb, config="--psm 3", output_type=pytesseract.Output.DICT
    )

    blocks = []
    n = len(data["text"])
    for i in range(n):
        text = data["text"][i].strip()
        conf = int(data["conf"][i])
        if conf < 0 or not text:
            continue

        x = data["left"][i]
        y = data["top"][i]
        w = data["width"][i]
        h = data["height"][i]

        blocks.append(OcrBlock(
            text=text,
            bbox=(x, y, x + w, y + h),
            confidence=conf / 100.0,
            level=data["level"][i],
            block_num=data["block_num"][i],
            line_num=data["line_num"][i],
            word_num=data["word_num"][i],
        ))

    buf = io.BytesIO()
    image_rgb.save(buf, format="PNG")

    return PageData(
        page_index=page_index,
        image_bytes=buf.getvalue(),
        width=image_rgb.width,
        height=image_rgb.height,
        ocr_blocks=blocks,
        dpi=dpi,
    )
