# FormEase — Accessible Form-Filling Assistant

Upload a form (PDF or image), let AI detect every field, then fill it step-by-step with **voice**, **translation**, and **validation** — and export a **filled PDF**.

**Live App:** [http://15.134.129.165/](http://15.134.129.165/)

---

## Test It Out!

We have Sample Forms under our Sample Folder for testing.

1. Click the Live App link above.
2. Download a Sample Form, Upload it to FormEase. Users can drag and drop their intended file too
3. FormEase scans the PDF and compiles the list of information needed to fill the form
4. FormEase will question the user the prompts based on the form
5. If users find it hard to comprehend the questions, they can click the Speaker Logo, the AI will convert the text to speech and play it as an audio
6. If users find the language native to the form unfamiliar, they can translate it to Chinese, Malay and Tamil for cross-language uses
7. If users feel the fonts and buttons are too small, they can enlarge the icons with the "Enlarge" button
8. Once the user types in the answer for each question/blank in the form, FormEase will fill the form with these answers
9. A preview will be shown for the user to check their answers to each question/blank
10. Once the user confirms, a the user can save the form as a PDF

---


---

## What It Does

1. **Upload** — Upload a pdf/jpg onto the dropzone
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
