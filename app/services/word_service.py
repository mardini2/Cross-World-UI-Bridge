"""
Goal: Wrapper for Word COM to keep API simple.
"""
from typing import Optional
from app.adapters.word_com import word_count

def count_words(path: Optional[str]=None) -> int:
    return word_count(path)
