# translate.py
import logging
import os
from dotenv import load_dotenv
from deep_translator import GoogleTranslator, exceptions as dt_exceptions

load_dotenv()
logging.basicConfig(level=logging.INFO)

def is_japanese_text(text: str) -> bool:
    if not text:
        return False
    japanese_ranges = [
        (0x3040, 0x309F), (0x30A0, 0x30FF),
        (0x4E00, 0x9FFF), (0xFF66, 0xFF9F),
    ]
    for ch in text:
        code = ord(ch)
        if any(start <= code <= end for start, end in japanese_ranges):
            return True
    return False

def translate_to_english(text: str) -> str:
    """
    Translate text to English if it contains Japanese.
    Otherwise, return original text.
    """
    if not text or not is_japanese_text(text):
        return text

    try:
        translation = GoogleTranslator(source='ja', target='en').translate(text)
        logging.info(f"Translated '{text[:50]}...' to '{translation[:50]}...'")
        return translation
    except dt_exceptions.NotValidPayload as e:
        logging.error(f"Invalid input for translation: {e}")
    except dt_exceptions.NotValidLength as e:
        logging.error(f"Text too long to translate: {e}")
    except dt_exceptions.LanguageNotSupportedException as e:
        logging.error(f"Unsupported language: {e}")
    except Exception as e:
        logging.error(f"Translation error: {e}")

    return text
