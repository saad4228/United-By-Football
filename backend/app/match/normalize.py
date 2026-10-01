"""Team-name normalization.

Sources describe the same club in many ways ("Man City", "Manchester City FC",
"MCI"). Everything is reduced to a canonical token string before comparison.
"""

import re
from difflib import SequenceMatcher

from app.utils.text import strip_accents

# Organisational prefixes/suffixes that carry no identity ("FC Barcelona" == "Barcelona").
_STOPWORDS = {
    "fc", "cf", "afc", "sc", "ac", "as", "ss", "ssc", "cd", "ud", "rc", "rcd", "sd", "club", "de", "del", "the",
    "calcio", "fk", "sk", "bk", "sv", "tsg", "ogc", "osc", "bc", "acf", "cp", "football", "futbol", "fútbol",
}
# Common abbreviations expanded so both sides of a comparison use the same words.
_EXPANSIONS = {
    "utd": "united",
    "man": "manchester",
    "st": "saint",
    "nottm": "nottingham",
    "spurs": "tottenham",
}
_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")
_APOSTROPHES = re.compile(r"['’`´]")
_INITIAL_DOT = re.compile(r"(?<![a-z])([a-z])\.")  # "f.c." -> "fc", "a.c. milan" -> "ac milan"


def normalize_name(value: str) -> str:
    text = strip_accents(value).lower().replace("&", " and ")
    text = _APOSTROPHES.sub("", text)
    text = _INITIAL_DOT.sub(r"\1", text)
    text = _NON_ALNUM.sub(" ", text)
    tokens = []
    for token in text.split():
        if token in _STOPWORDS or token.isdigit():
            continue
        tokens.append(_EXPANSIONS.get(token, token))
    if not tokens:  # e.g. the whole name was "FC" — keep something comparable
        return text.strip()
    return " ".join(tokens)


def name_similarity(candidate: str, known_forms: set[str]) -> float:
    """Score 0..1 for how well a normalized candidate matches any known normalized form."""
    if not candidate:
        return 0.0
    if candidate in known_forms:
        return 1.0
    cand_tokens = candidate.split()
    best = 0.0
    for form in known_forms:
        form_tokens = form.split()
        # Every candidate token is a word (or a 3+ char prefix of a word) in the known form:
        # "bayern" -> "bayern munchen", "dortmund" -> "borussia dortmund".
        if cand_tokens and all(
            any(ft == ct or (len(ct) >= 3 and ft.startswith(ct)) for ft in form_tokens) for ct in cand_tokens
        ):
            coverage = len(cand_tokens) / max(len(form_tokens), 1)
            best = max(best, 0.86 + 0.08 * coverage)
            continue
        best = max(best, SequenceMatcher(None, candidate, form).ratio() * 0.92)
    return best
