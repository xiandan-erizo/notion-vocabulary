"""Top-level package for the Notion Vocabulary project."""

from .config import DatabaseConfig
from .pipeline import VocabularyPipeline

__all__ = ["DatabaseConfig", "VocabularyPipeline"]
