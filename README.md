# FormEase — Accessible Form-Filling Assistant

Upload a form (PDF or image), let AI detect every field, then fill it step-by-step with **voice**, **translation**, and **validation** — and export a **filled PDF**.

**Live App:** [http://15.134.129.165/](http://15.134.129.165/)

---

## What It Does

1. **Upload** — Drag a form (PDF or image) onto the dropzone
2. **AI Detection** — OCR + LLM automatically detect all form fields (name, email, phone, NRIC, date, etc.)
3. **Step-by-Step Wizard** — Fill each field one at a time with:
   - **Text-to-Speech** — hear the question read aloud (English, Chinese, Malay, Tamil)
   - **Translation** — translate field labels into Chinese, Malay, or Tamil
   - **Validation** — real-time checks for email, phone, date, NRIC, and number formats
4. **Review** — check all your answers in a table, edit any field
5. **Preview** — see a filled-form preview before exporting; drag to reposition text, adjust font size, font, and color
6. **Export** — download the filled PDF or copy a text summary

---

## Accessibility

Two display modes, togglable from the top bar:

| Mode | Description |
|------|-------------|
| **Standard** | Default sizing and spacing |
| **Enlarged** | Scales up the entire UI — bigger text, buttons, inputs, and spacing for easier reading and interaction |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python, Flask |
| **OCR** | Tesseract (pytesseract) |
| **Field Detection** | Heuristic (keyword + OpenCV) + LLM-assisted extraction |
| **TTS** | gTTS (Google Text-to-Speech) |
| **Translation** | deep-translator (Google Translate) |
| **PDF Export** | reportlab + PyPDF2 |
| **Frontend** | Vanilla JS single-page app |
| **Deployment** | Docker on AWS EC2 |

---

## Deployment

The app runs in a Docker container on an AWS EC2 instance.

```
EC2 Instance → Docker → Gunicorn (2 workers) → Flask app on port 80
```

### Run It Yourself

```bash
# Clone the repo
git clone <repo-url>
cd iNTUitionProject

# Build and run with Docker
docker build -t formease .
docker run -d --restart unless-stopped \
  -p 80:5000 \
  -e OPENAI_API_KEY=your_key_here \
  --name formease \
  formease
```

### Prerequisites (if running without Docker)

```bash
sudo apt install -y tesseract-ocr poppler-utils
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open [http://localhost:5000](http://localhost:5000).

---

## Project Structure

```
app.py                    Flask server + API endpoints
templates/index.html      Multi-screen wizard SPA
formease/
  models.py               Data classes (FormDocument, FormField, etc.)
  ocr_engine.py           OCR with bounding boxes
  field_detector.py       Heuristic field detection (keywords + OpenCV)
  llm_extractor.py        LLM-assisted field extraction
  field_ordering.py       Sort fields into reading order
  tts_engine.py           Multi-language text-to-speech
  translator.py           Translation (zh/ms/ta)
  validators.py           Per-field-type validation
  pdf_handler.py          PDF input + filled PDF export
Dockerfile                Container build config
requirements.txt          Python dependencies
```
