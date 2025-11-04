"""High level pipeline that orchestrates text processing and persistence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from .config import DatabaseConfig
from .repository import VocabularyRepository
from .text_processing import ProcessedToken, TokenProcessor


@dataclass
class PipelineResult:
    """Capture the outcome for each processed token."""

    lemma: str
    sentence: str
    created: bool
    frequency_updated: bool
    context_inserted: bool


class VocabularyPipeline:
    """Main entry point for turning raw text into persistent vocabulary."""

    def __init__(
        self,
        db_config: DatabaseConfig,
        language_model: str = "en_core_web_sm",
        processor: Optional[TokenProcessor] = None,
    ) -> None:
        self._repository = VocabularyRepository(db_config)
        self._processor = processor or TokenProcessor(language_model)

    def process_text(self, text: str) -> list[PipelineResult]:
        """Process a single piece of text and persist all relevant tokens."""

        results: list[PipelineResult] = []
        for token in self._processor.iter_processed_tokens(text):
            upsert_result = self._repository.upsert_word_with_context(
                token.lemma, token.sentence
            )
            results.append(
                PipelineResult(
                    lemma=token.lemma,
                    sentence=token.sentence,
                    created=upsert_result.created,
                    frequency_updated=upsert_result.frequency_updated,
                    context_inserted=upsert_result.context_inserted,
                )
            )
        return results

    def process_many(self, texts: Iterable[str]) -> list[PipelineResult]:
        """Process multiple pieces of text."""

        aggregated: list[PipelineResult] = []
        for text in texts:
            aggregated.extend(self.process_text(text))
        return aggregated

    def fetch_word(self, lemma: str) -> Optional[dict[str, object]]:
        """Return a serialisable representation of a stored word."""

        return self._repository.fetch_word_with_contexts(lemma)

    @property
    def processor(self) -> TokenProcessor:
        return self._processor
