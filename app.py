"""
FormEase — Accessible Form-Filling Assistant

Run:
    source venv/bin/activate
    python app.py

Then open http://localhost:5000 in a browser.
"""

import io
import base64
import time

from dotenv import load_dotenv

from flask import Flask, request, jsonify, render_template
from PIL import Image

from formease.models import FormDocument, FieldType
from formease.ocr_engine import ocr_page
from formease.field_detector import detect_fields
from formease.llm_extractor import detect_fields_llm, merge_fields
from formease.field_ordering import order_fields
from formease.tts_engine import generate_tts
from formease.translator import translate_text
from formease.pdf_handler import pdf_to_images, export_filled_pdf, generate_text_summary
from formease.validators import validate_field

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB for PDFs

# Load environment variables from .env if present
load_dotenv()

# In-memory session store  {session_id: FormDocument}
sessions: dict[str, FormDocument] = {}

SESSION_TTL = 3600  # 1 hour


def _cleanup_sessions():
    """Remove sessions older than SESSION_TTL (best-effort, runs on requests)."""
    now = time.time()
    expired = [
        sid for sid, doc in sessions.items()
        if now - doc.settings.get("_created", now) > SESSION_TTL
    ]
    for sid in expired:
        del sessions[sid]


# ── Routes ──────────────────────────────────────────────────────────────


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    """Upload a form (PDF or image) -> OCR + field detection -> return session."""
    _cleanup_sessions()

    if "document" not in request.files:
        return jsonify({"error": "No document in the request."}), 400

    file = request.files["document"]
    if not file or file.filename == "":
        return jsonify({"error": "Empty file."}), 400

    try:
        filename = file.filename.lower()
        raw_bytes = file.read()

        doc = FormDocument(original_filename=file.filename)
        doc.settings["_created"] = time.time()

        # Determine input type and convert to page images
        if filename.endswith(".pdf"):
            doc.is_pdf = True
            doc.original_pdf_bytes = raw_bytes
            try:
                pil_images = pdf_to_images(raw_bytes, dpi=300)
            except Exception as exc:
                return jsonify({"error": f"Failed to parse PDF: {exc}"}), 400
        else:
            try:
                pil_images = [Image.open(io.BytesIO(raw_bytes))]
            except Exception:
                return jsonify({"error": "Could not decode that file as an image."}), 400

        # OCR each page and detect fields
        all_fields = []
        pages_response = []

        for i, img in enumerate(pil_images):
            page_data = ocr_page(img, page_index=i, dpi=300)
            doc.pages.append(page_data)

            heuristic_fields = detect_fields(page_data)
            llm_fields = detect_fields_llm(page_data)
            page_fields = merge_fields(heuristic_fields, llm_fields)
            all_fields.extend(page_fields)

            # Generate a small thumbnail for the frontend
            thumb = img.copy()
            thumb.thumbnail((600, 800))
            thumb_buf = io.BytesIO()
            thumb.save(thumb_buf, format="JPEG", quality=70)
            thumb_b64 = base64.b64encode(thumb_buf.getvalue()).decode("ascii")

            pages_response.append({
                "page_index": i,
                "thumbnail": thumb_b64,
                "width": page_data.width,
                "height": page_data.height,
            })

        # Order fields and store
        doc.fields = order_fields(all_fields)
        sessions[doc.document_id] = doc

        fields_response = []
        for f in doc.fields:
            fields_response.append({
                "field_id": f.field_id,
                "page_index": f.page_index,
                "label_text": f.label_text,
                "field_type": f.field_type.value,
                "target_bbox": list(f.target_bbox),
                "label_bbox": list(f.label_bbox),
                "required": f.required,
                "confidence": f.confidence,
            })

        return jsonify({
            "session_id": doc.document_id,
            "page_count": len(doc.pages),
            "pages": pages_response,
            "fields": fields_response,
            "total_steps": len(doc.fields),
        })
    except Exception as exc:
        return jsonify({"error": f"Upload failed: {exc}"}), 500


@app.route("/tts/<session_id>/<field_id>")
def tts(session_id, field_id):
    """Generate TTS audio for a field's label text."""
    doc = sessions.get(session_id)
    if not doc:
        return jsonify({"error": "Session not found."}), 404

    field = next((f for f in doc.fields if f.field_id == field_id), None)
    if not field:
        return jsonify({"error": "Field not found."}), 404

    lang = request.args.get("lang", "en")
    text = field.label_text

    # If requesting a non-English language, translate first
    if lang != "en":
        text = translate_text(text, lang)

    try:
        audio_bytes = generate_tts(text, lang)
    except Exception as exc:
        return jsonify({"error": f"TTS failed: {exc}"}), 503

    return jsonify({
        "audio": base64.b64encode(audio_bytes).decode("ascii"),
        "text": text,
        "lang": lang,
    })


@app.route("/translate", methods=["POST"])
def translate():
    """Translate a field label to a target language."""
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    field_id = data.get("field_id")
    target_lang = data.get("target_lang", "en")

    doc = sessions.get(session_id)
    if not doc:
        return jsonify({"error": "Session not found."}), 404

    field = next((f for f in doc.fields if f.field_id == field_id), None)
    if not field:
        return jsonify({"error": "Field not found."}), 404

    translated = translate_text(field.label_text, target_lang)

    return jsonify({
        "original": field.label_text,
        "translated": translated,
        "target_lang": target_lang,
    })


@app.route("/validate", methods=["POST"])
def validate():
    """Validate a single field answer."""
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    field_id = data.get("field_id")
    answer = data.get("answer", "")

    doc = sessions.get(session_id)
    if not doc:
        return jsonify({"error": "Session not found."}), 404

    field = next((f for f in doc.fields if f.field_id == field_id), None)
    if not field:
        return jsonify({"error": "Field not found."}), 404

    # Check required
    if field.required and not answer.strip():
        return jsonify({
            "valid": False,
            "message": "This field is required.",
            "confirmation": None,
        })

    is_valid, error_msg = validate_field(field.field_type, answer)

    return jsonify({
        "valid": is_valid,
        "message": error_msg,
        "confirmation": f"You entered: {answer}" if is_valid and answer.strip() else None,
    })


@app.route("/save-answers", methods=["POST"])
def save_answers():
    """Save all answers for a session."""
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    answers = data.get("answers", {})

    doc = sessions.get(session_id)
    if not doc:
        return jsonify({"error": "Session not found."}), 404

    for field in doc.fields:
        if field.field_id in answers:
            field.answer = answers[field.field_id]

    return jsonify({
        "status": "saved",
        "answered": sum(1 for f in doc.fields if f.answer),
        "total": len(doc.fields),
    })


@app.route("/export", methods=["POST"])
def export():
    """Generate filled PDF + text summary."""
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    font_scale = data.get("font_scale", 1.0)
    font_color = data.get("font_color", "#1d4ed8")
    font_family = data.get("font_family", "Helvetica")
    offsets = data.get("offsets", {})

    doc = sessions.get(session_id)
    if not doc:
        return jsonify({"error": "Session not found."}), 404

    answers = {f.field_id: f.answer for f in doc.fields}

    try:
        pdf_bytes = export_filled_pdf(
            doc,
            answers,
            font_scale=font_scale,
            font_color=font_color,
            font_family=font_family,
            offsets=offsets,
        )
    except Exception as exc:
        return jsonify({"error": f"PDF export failed: {exc}"}), 500

    summary = generate_text_summary(doc, answers)

    return jsonify({
        "pdf": base64.b64encode(pdf_bytes).decode("ascii"),
        "summary": summary,
        "filename": "filled_form.pdf",
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
