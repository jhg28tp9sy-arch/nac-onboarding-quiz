import re
import unicodedata
from difflib import SequenceMatcher


def normalize(value):
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"[.'’]", "", value)
    return " ".join(re.sub(r"[^\w\s]|_", " ", value).split())


def grade(answer, expected, alternatives=()):
    answer, expected = normalize(answer), normalize(expected)
    if not answer:
        return "Incorrect"
    if answer == expected:
        return "Correct"
    candidates = {normalize(value) for value in alternatives} - {expected}
    if answer in candidates:
        return "Incorrect"
    if len(answer) >= 4 and SequenceMatcher(None, answer, expected, autojunk=False).ratio() >= 0.82:
        return "Review"
    return "Incorrect"


def spreadsheet_value(value):
    if isinstance(value, str) and (
        value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(("=", "+", "-", "@"))
    ):
        return "'" + value
    return value
