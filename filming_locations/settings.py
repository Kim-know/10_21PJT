"""절약 기본값. 환경변수가 없으면 보수적인 제한을 적용한다."""
import os


def number(name, default, minimum, maximum):
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


def limits():
    size = number("CHUNK_SIZE", 700, 200, 2000)
    return {
        "chunk_size": size,
        "chunk_overlap": min(number("CHUNK_OVERLAP", 100, 0, 500), size // 2),
        "top_k": number("RETRIEVAL_TOP_K", 3, 1, 8),
        "context_chars": number("MAX_CONTEXT_CHARS", 2600, 800, 10000),
        "history_chars": number("MAX_HISTORY_CHARS", 1000, 0, 4000),
        "question_chars": number("MAX_QUESTION_CHARS", 600, 100, 2000),
        "output_tokens": number("MAX_OUTPUT_TOKENS", 600, 100, 2000),
        "daily_calls": number("DAILY_LLM_CALL_LIMIT", 30, 0, 500),
        "cache_days": number("CACHE_TTL_DAYS", 7, 1, 30),
    }
