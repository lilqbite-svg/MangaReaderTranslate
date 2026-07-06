from __future__ import annotations

from app.core.types import Language

# ~40-language matrix. script_group drives both OCR backend routing
# (app/core/ocr.py) and font selection (app/core/fonts.py); nllb_code is the
# FLORES-200 code NLLBTranslator expects.
LANGUAGES: dict[str, Language] = {
    "ja": Language("ja", "Japanese", "jpn_Jpan", "cjk_ja"),
    "ko": Language("ko", "Korean", "kor_Hang", "cjk_ko"),
    "zh-Hans": Language("zh-Hans", "Chinese (Simplified)", "zho_Hans", "cjk_zh"),
    "zh-Hant": Language("zh-Hant", "Chinese (Traditional)", "zho_Hant", "cjk_zh"),
    "en": Language("en", "English", "eng_Latn", "latin"),
    "es": Language("es", "Spanish", "spa_Latn", "latin"),
    "pt": Language("pt", "Portuguese", "por_Latn", "latin"),
    "pt-BR": Language("pt-BR", "Portuguese (Brazil)", "por_Latn", "latin"),
    "fr": Language("fr", "French", "fra_Latn", "latin"),
    "de": Language("de", "German", "deu_Latn", "latin"),
    "it": Language("it", "Italian", "ita_Latn", "latin"),
    "nl": Language("nl", "Dutch", "nld_Latn", "latin"),
    "pl": Language("pl", "Polish", "pol_Latn", "latin"),
    "sv": Language("sv", "Swedish", "swe_Latn", "latin"),
    "no": Language("no", "Norwegian", "nob_Latn", "latin"),
    "da": Language("da", "Danish", "dan_Latn", "latin"),
    "fi": Language("fi", "Finnish", "fin_Latn", "latin"),
    "ro": Language("ro", "Romanian", "ron_Latn", "latin"),
    "hu": Language("hu", "Hungarian", "hun_Latn", "latin"),
    "cs": Language("cs", "Czech", "ces_Latn", "latin"),
    "tr": Language("tr", "Turkish", "tur_Latn", "latin"),
    "vi": Language("vi", "Vietnamese", "vie_Latn", "latin"),
    "id": Language("id", "Indonesian", "ind_Latn", "latin"),
    "ms": Language("ms", "Malay", "zsm_Latn", "latin"),
    "tl": Language("tl", "Filipino", "tgl_Latn", "latin"),
    "sw": Language("sw", "Swahili", "swh_Latn", "latin"),
    "ru": Language("ru", "Russian", "rus_Cyrl", "cyrillic"),
    "uk": Language("uk", "Ukrainian", "ukr_Cyrl", "cyrillic"),
    "bg": Language("bg", "Bulgarian", "bul_Cyrl", "cyrillic"),
    "sr": Language("sr", "Serbian", "srp_Cyrl", "cyrillic"),
    "el": Language("el", "Greek", "ell_Grek", "greek"),
    "ar": Language("ar", "Arabic", "arb_Arab", "arabic"),
    "he": Language("he", "Hebrew", "heb_Hebr", "hebrew"),
    "fa": Language("fa", "Persian", "pes_Arab", "arabic"),
    "ur": Language("ur", "Urdu", "urd_Arab", "arabic"),
    "hi": Language("hi", "Hindi", "hin_Deva", "devanagari"),
    "bn": Language("bn", "Bengali", "ben_Beng", "bengali"),
    "ta": Language("ta", "Tamil", "tam_Taml", "tamil"),
    "te": Language("te", "Telugu", "tel_Telu", "telugu"),
    "th": Language("th", "Thai", "tha_Thai", "thai"),
    "km": Language("km", "Khmer", "khm_Khmr", "khmer"),
}


def get(ui_code: str) -> Language:
    try:
        return LANGUAGES[ui_code]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported language code {ui_code!r}. Supported: {sorted(LANGUAGES)}"
        ) from exc
