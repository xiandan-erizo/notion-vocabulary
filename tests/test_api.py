from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient

from notion_vocabulary.api import app, get_pipeline
from notion_vocabulary.models import Word, WordStatus
from notion_vocabulary.pipeline import PipelineResult


class APITests(TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.pipeline = MagicMock()
        self.pipeline.repository = MagicMock()

        token_result = PipelineResult(
            lemma="lemma",
            sentence="Sentence",
            created=True,
            frequency_updated=False,
            context_inserted=True,
        )
        self.pipeline.process_text.return_value = [token_result]
        self.pipeline.process_many.return_value = [token_result, token_result]

        now = datetime.now(UTC)
        self.word = Word(
            id=1,
            word="lemma",
            frequency=2,
            status=WordStatus.LEARNING,
            first_seen=now - timedelta(days=1),
            last_seen=now,
        )
        self.pipeline.repository.list_words.return_value = [self.word]
        self.pipeline.repository.update_word_status.return_value = self.word
        self.pipeline.repository.ping.return_value = True

        self.word_payload = {
            "id": self.word.id,
            "word": self.word.word,
            "frequency": self.word.frequency,
            "status": self.word.status.value,
            "first_seen": self.word.first_seen,
            "last_seen": self.word.last_seen,
            "contexts": [
                {"id": 10, "word_id": self.word.id, "sentence": "Sentence"}
            ],
        }
        self.pipeline.fetch_word.return_value = self.word_payload

        app.dependency_overrides[get_pipeline] = lambda: self.pipeline

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_ingest_text(self) -> None:
        response = self.client.post("/api/v1/texts", json={"text": "hello"})
        self.assertEqual(200, response.status_code)
        self.pipeline.process_text.assert_called_once_with("hello")
        payload = response.json()
        self.assertEqual(1, len(payload))
        self.assertEqual("lemma", payload[0]["lemma"])

    def test_ingest_text_rejects_blank_input(self) -> None:
        response = self.client.post("/api/v1/texts", json={"text": "   "})
        self.assertEqual(400, response.status_code)

    def test_batch_ingest_filters_empty_strings(self) -> None:
        with patch("notion_vocabulary.api.get_pipeline", return_value=self.pipeline):
            response = self.client.post(
                "/api/v1/texts/batch",
                json={"texts": ["hello", "", " world "]},
            )
        self.assertEqual(200, response.status_code)
        self.pipeline.process_many.assert_called_once_with(["hello", " world "])
        payload = response.json()
        self.assertEqual(2, payload["total_results"])

    def test_list_words_returns_summaries(self) -> None:
        response = self.client.get("/api/v1/words")
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data))
        self.assertEqual("lemma", data[0]["word"])
        self.assertEqual("learning", data[0]["status"])

    def test_fetch_word(self) -> None:
        response = self.client.get("/api/v1/words/lemma")
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, data["id"])
        self.assertEqual(1, len(data["contexts"]))

    def test_fetch_word_not_found(self) -> None:
        self.pipeline.fetch_word.return_value = None
        response = self.client.get("/api/v1/words/missing")
        self.assertEqual(404, response.status_code)

    def test_update_word_status(self) -> None:
        response = self.client.patch(
            "/api/v1/words/lemma",
            json={"status": "mastered"},
        )
        self.assertEqual(200, response.status_code)
        self.pipeline.repository.update_word_status.assert_called_once()

    def test_update_word_status_missing(self) -> None:
        self.pipeline.repository.update_word_status.return_value = None
        response = self.client.patch(
            "/api/v1/words/missing",
            json={"status": "mastered"},
        )
        self.assertEqual(404, response.status_code)

    def test_health_check(self) -> None:
        response = self.client.get("/api/v1/health")
        self.assertEqual(200, response.status_code)
        self.assertEqual({"status": "ok"}, response.json())

    def test_landing_page_returns_html(self) -> None:
        response = self.client.get("/")
        self.assertEqual(200, response.status_code)
        self.assertEqual("text/html; charset=utf-8", response.headers["content-type"])
        self.assertIn("Notion Vocabulary Service", response.text)
        self.assertIn("无需登录", response.text)
