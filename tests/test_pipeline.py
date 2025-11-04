from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from unittest import TestCase
from unittest.mock import MagicMock

from notion_vocabulary.config import DatabaseConfig
from notion_vocabulary.pipeline import PipelineResult, VocabularyPipeline
from notion_vocabulary.text_processing import ProcessedToken, TokenProcessor


class DummyProcessor(TokenProcessor):
    def __init__(self, tokens: list[ProcessedToken]):
        self._tokens = tokens
        self._model_name = "dummy"

    def iter_processed_tokens(self, text: str):  # type: ignore[override]
        yield from self._tokens


class PipelineTests(TestCase):
    def setUp(self) -> None:
        self.config = DatabaseConfig(
            host="localhost", port=3306, user="root", password="", database="test"
        )

    def test_process_text_delegates_to_repository(self) -> None:
        tokens = [ProcessedToken(lemma="example", sentence="An example sentence.")]
        processor = DummyProcessor(tokens)
        pipeline = VocabularyPipeline(self.config, processor=processor)  # type: ignore[arg-type]
        pipeline._repository = MagicMock()  # type: ignore[attr-defined]
        pipeline._repository.upsert_word_with_context.return_value = MagicMock(
            created=True, frequency_updated=False, context_inserted=True
        )

        results = pipeline.process_text("irrelevant")

        pipeline._repository.upsert_word_with_context.assert_called_once_with(
            "example", "An example sentence."
        )
        self.assertEqual(
            results,
            [
                PipelineResult(
                    lemma="example",
                    sentence="An example sentence.",
                    created=True,
                    frequency_updated=False,
                    context_inserted=True,
                )
            ],
        )
