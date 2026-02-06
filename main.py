"""
Image-to-Speech Pipeline
Upload a photo → OCR extracts text → text is spoken aloud → audio saved as output.mp3
"""

import sys
import os
from PIL import Image, ImageDraw, ImageFont
import pytesseract
from gtts import gTTS


# ─── Test image generator ────────────────────────────────────────────────────

def generate_test_image(output_path="test_image.png"):
    """Create a sample image with printed text so you can test without a real photo."""
    img = Image.new("RGB", (900, 500), color="white")
    draw = ImageDraw.Draw(img)

    # Try to load a nicer font; fall back to default if unavailable
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except (IOError, OSError):
        font = ImageFont.load_default()
        font_sm = font

    # Title
    draw.text((60, 30), "Image-to-Speech Test", fill="#1a1a2e", font=font)
    draw.line([(60, 80), (840, 80)], fill="#e94560", width=3)

    # Body text — this is what OCR will pick up and read aloud
    lines = [
        "The quick brown fox jumps over the lazy dog.",
        "Python is a versatile programming language.",
        "Tesseract is an open-source OCR engine.",
        "Google Text-to-Speech converts words into audio.",
        "This sentence was generated for testing purposes.",
    ]

    y = 110
    for line in lines:
        draw.text((60, y), line, fill="#222222", font=font_sm)
        y += 60

    img.save(output_path)
    return output_path


# ─── Core pipeline stages ────────────────────────────────────────────────────

def extract_text(image_path: str) -> str:
    """Run Tesseract OCR on an image and return the detected text."""
    image = Image.open(image_path).convert("RGB")
    # --psm 3  →  assume fully automatic page segmentation (default, works best
    #             for multi-line photos / screenshots / scans)
    text = pytesseract.image_to_string(image, config="--psm 3")
    return text.strip()


def text_to_speech(text: str, output_path: str = "output.mp3", lang: str = "en"):
    """Convert a text string to an MP3 audio file via Google TTS."""
    tts = gTTS(text=text, lang=lang, slow=False)
    tts.save(output_path)


# ─── CLI entry-point ─────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python main.py <image_path>       — run the full pipeline")
        print("  python main.py --generate-test    — create a sample test image")
        sys.exit(1)

    # ── helper mode: drop a test image into the current directory ──
    if sys.argv[1] == "--generate-test":
        path = generate_test_image()
        print(f"Test image created: {path}")
        print(f"Run:  python main.py {path}")
        sys.exit(0)

    # ── normal mode ──
    image_path = sys.argv[1]

    if not os.path.exists(image_path):
        print(f"Error: file '{image_path}' not found.")
        sys.exit(1)

    print(f"[1/3] Loading    {image_path}")

    print("[2/3] Extracting text (OCR) …")
    text = extract_text(image_path)

    if not text:
        print("No text detected in the image. Try a clearer photo.")
        sys.exit(1)

    print(f"\n{'─' * 50}\n{text}\n{'─' * 50}\n")

    output_path = "output.mp3"
    print(f"[3/3] Generating speech → {output_path}")
    text_to_speech(text, output_path)

    print(f"\nDone.  Audio saved to '{output_path}'")


if __name__ == "__main__":
    main()
