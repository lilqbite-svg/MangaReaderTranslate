from app.core.pipeline import NLLB_CT2_DIR
from app.core.translator import NLLBTranslator


def test_ja_to_en_basic_sentence():
    assert NLLB_CT2_DIR.exists(), "Run scripts/convert_nllb_to_ct2.py first"
    translator = NLLBTranslator(NLLB_CT2_DIR)
    result = translator.translate(["こんにちは、元気ですか？"], "jpn_Jpan", "eng_Latn")
    assert len(result) == 1
    assert any(word in result[0].lower() for word in ("hello", "hi", "how"))
