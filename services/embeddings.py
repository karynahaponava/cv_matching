import numpy as np
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")


def embed(text: str) -> list[float]:
    """Turns text into a vector of numbers."""
    if not text or not text.strip():
        return []
    return model.encode(text).tolist()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Calculates the percentage of similarity between two vectors."""
    if not a or not b:
        return 0.0
    vec_a = np.array(a)
    vec_b = np.array(b)

    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))
