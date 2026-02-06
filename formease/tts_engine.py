import io
from gtts import gTTS

GTTS_LANG_MAP = {
    "en": "en",
    "zh": "zh-CN",
    "ms": "id",  # gTTS doesn't support Malay natively; Indonesian is mutually intelligible
    "ta": "ta",
}


def generate_tts(text: str, lang: str = "en") -> bytes:
    """Generate MP3 audio bytes for the given text and language."""
    gtts_lang = GTTS_LANG_MAP.get(lang, "en")
    try:
        tts = gTTS(text=text, lang=gtts_lang, slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        return buf.read()
    except Exception:
        if lang != "en":
            return generate_tts(text, "en")
        raise
