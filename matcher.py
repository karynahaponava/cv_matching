import re

_KEYWORD_RE = re.compile(r"[a-zA-Zа-яА-Я0-9][a-zA-Zа-яА-Я0-9+#\.\-_/]*")


def calculate_match_score(requirements: str, candidate_text: str) -> float:
    """
    Returns the percentage (0..100) of keywords from requirements that appear (as a substring) in candidate_text.
    """
    req = (requirements or "").lower()
    text = (candidate_text or "").lower()

    keywords = [k for k in _KEYWORD_RE.findall(req) if len(k) >= 2]
    if not keywords:
        return 0.0

    unique_keywords = list(dict.fromkeys(keywords))
    matched = sum(1 for kw in unique_keywords if kw in text)
    return (matched / len(unique_keywords)) * 100.0
