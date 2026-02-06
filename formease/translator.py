from deep_translator import GoogleTranslator

LANG_MAP = {
    "zh": "zh-CN",
    "ms": "ms",
    "ta": "ta",
    "en": "en",
}

_cache: dict[tuple[str, str], str] = {}


def translate_text(text: str, target_lang: str) -> str:
    """Translate text to target language. Returns original on failure."""
    if target_lang == "en" or not text.strip():
        return text

    cache_key = (text, target_lang)
    if cache_key in _cache:
        return _cache[cache_key]

    try:
        dl_lang = LANG_MAP.get(target_lang, target_lang)
        result = GoogleTranslator(source="en", target=dl_lang).translate(text)
        _cache[cache_key] = result
        return result
    except Exception:
        return text
