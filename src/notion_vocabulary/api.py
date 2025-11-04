"""HTTP API for interacting with the Notion Vocabulary pipeline."""

from __future__ import annotations

import os
from datetime import datetime
from functools import lru_cache
from typing import Optional, cast

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, conint

from .config import DatabaseConfig
from .models import WordStatus
from .pipeline import PipelineResult, VocabularyPipeline


class Settings(BaseModel):
    """Configuration derived from environment variables."""

    db_host: str = Field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    db_port: int = Field(default_factory=lambda: int(os.getenv("DB_PORT", "3306")))
    db_user: str = Field(default_factory=lambda: os.getenv("DB_USER", "root"))
    db_password: str = Field(default_factory=lambda: os.getenv("DB_PASSWORD", ""))
    db_name: str = Field(default_factory=lambda: os.getenv("DB_NAME", "vocab_db"))
    language_model: str = Field(
        default_factory=lambda: os.getenv("LANGUAGE_MODEL", "en_core_web_sm")
    )

    @property
    def database_config(self) -> DatabaseConfig:
        return DatabaseConfig(
            host=self.db_host,
            port=self.db_port,
            user=self.db_user,
            password=self.db_password,
            database=self.db_name,
        )


settings = Settings()


@lru_cache(maxsize=4)
def _pipeline_for_model(model_name: str) -> VocabularyPipeline:
    return VocabularyPipeline(settings.database_config, language_model=model_name)


def get_pipeline(language_model: Optional[str] = None) -> VocabularyPipeline:
    """Return a cached pipeline keyed by ``language_model``."""

    model = language_model or settings.language_model
    return _pipeline_for_model(model)


class TokenIngestRequest(BaseModel):
    text: str = Field(..., min_length=1)


class BatchIngestRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1)
    language_model: Optional[str] = None


class TokenResponse(BaseModel):
    lemma: str
    sentence: str
    created: bool
    frequency_updated: bool
    context_inserted: bool

    @classmethod
    def from_result(cls, result: PipelineResult) -> "TokenResponse":
        return cls(
            lemma=result.lemma,
            sentence=result.sentence,
            created=result.created,
            frequency_updated=result.frequency_updated,
            context_inserted=result.context_inserted,
        )


class BatchIngestResponse(BaseModel):
    results: list[TokenResponse]
    total_results: int = Field(..., ge=0)


class WordContext(BaseModel):
    id: int
    sentence: str


class WordDetail(BaseModel):
    id: int
    word: str
    frequency: int
    status: WordStatus
    first_seen: datetime
    last_seen: datetime
    contexts: list[WordContext]


class WordSummary(BaseModel):
    id: int
    word: str
    frequency: int
    status: WordStatus
    last_seen: datetime


class StatusUpdateRequest(BaseModel):
    status: WordStatus


app = FastAPI(title="Notion Vocabulary API", version="1.0.0")


@app.get("/", response_class=HTMLResponse)
def landing_page() -> str:
    """Render a very small landing page for the service."""

    return """
    <!DOCTYPE html>
    <html lang=\"en\">
      <head>
        <meta charset=\"utf-8\" />
        <title>Notion Vocabulary Service</title>
        <style>
          body { font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; padding: 3rem 1.5rem; background: #f6f8fb; }
          main { max-width: 640px; margin: 0 auto; background: white; padding: 2.5rem 2rem; border-radius: 16px; box-shadow: 0 12px 32px rgba(15, 23, 42, 0.12); }
          h1 { margin-top: 0; color: #0f172a; font-size: 2rem; }
          p { color: #334155; line-height: 1.6; }
          code { background: #e2e8f0; border-radius: 4px; padding: 0.2rem 0.4rem; }
          a { color: #2563eb; text-decoration: none; }
          a:hover { text-decoration: underline; }
          ul { padding-left: 1.25rem; }
        </style>
      </head>
      <body>
        <main>
          <h1>Notion Vocabulary Service</h1>
          <p>
            欢迎来到词汇处理服务！该站点无需登录即可使用，
            你可以直接调用提供的 API 接口来分析文本并维护你的单词本。
          </p>
          <p>
            尝试以下端点来开始：
          </p>
          <ul>
            <li><code>POST /api/v1/texts</code>：提交一段文本并获取解析结果。</li>
            <li><code>POST /api/v1/texts/batch</code>：批量处理多条文本。</li>
            <li><code>GET /api/v1/words</code>：查看词汇列表及其状态。</li>
            <li><code>GET /api/v1/words/&lt;lemma&gt;</code>：查看单词详情及上下文。</li>
          </ul>
          <p>
            你也可以访问 <a href=\"/docs\">交互式 API 文档</a>，在浏览器中试用所有接口。
          </p>
        </main>
      </body>
    </html>
    """


def _status_from_query(value: Optional[str]) -> Optional[WordStatus]:
    if value is None:
        return None
    try:
        return WordStatus(value)
    except ValueError as exc:  # pragma: no cover - validation handled in endpoint
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown status value: {value}",
        ) from exc


def _serialize_word_detail(data: dict[str, object]) -> WordDetail:
    contexts_raw = cast(list[dict[str, object]], data.get("contexts", []))
    contexts = [
        WordContext(id=int(context["id"]), sentence=str(context["sentence"]))
        for context in contexts_raw
    ]
    return WordDetail(
        id=int(data["id"]),
        word=str(data["word"]),
        frequency=int(data["frequency"]),
        status=WordStatus(str(data["status"])),
        first_seen=cast(datetime, data["first_seen"]),
        last_seen=cast(datetime, data["last_seen"]),
        contexts=contexts,
    )


@app.post("/api/v1/texts", response_model=list[TokenResponse], status_code=status.HTTP_200_OK)
def ingest_text(payload: TokenIngestRequest, pipeline: VocabularyPipeline = Depends(get_pipeline)):
    if not payload.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text must not be empty",
        )
    results = pipeline.process_text(payload.text)
    return [TokenResponse.from_result(result) for result in results]


@app.post("/api/v1/texts/batch", response_model=BatchIngestResponse)
def ingest_texts_batch(payload: BatchIngestRequest):
    pipeline = get_pipeline(payload.language_model)
    texts = [text for text in payload.texts if text.strip()]
    if not texts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one non-empty text is required",
        )
    results = pipeline.process_many(texts)
    serialised = [TokenResponse.from_result(result) for result in results]
    return BatchIngestResponse(results=serialised, total_results=len(serialised))


@app.get("/api/v1/words", response_model=list[WordSummary])
def list_words(
    status: Optional[str] = Query(default=None),
    min_frequency: Optional[conint(ge=1)] = Query(default=None),
    limit: conint(ge=1, le=100) = Query(default=50),
    offset: conint(ge=0) = Query(default=0),
    pipeline: VocabularyPipeline = Depends(get_pipeline),
):
    parsed_status = _status_from_query(status)
    words = pipeline.repository.list_words(
        status=parsed_status,
        min_frequency=min_frequency,
        limit=limit,
        offset=offset,
    )
    return [
        WordSummary(
            id=word.id,
            word=word.word,
            frequency=word.frequency,
            status=word.status,
            last_seen=word.last_seen,
        )
        for word in words
    ]


@app.get("/api/v1/words/{lemma}", response_model=WordDetail)
def fetch_word(lemma: str, pipeline: VocabularyPipeline = Depends(get_pipeline)):
    record = pipeline.fetch_word(lemma)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Word not found")
    return _serialize_word_detail(record)


@app.patch("/api/v1/words/{lemma}", response_model=WordDetail)
def update_word_status(
    lemma: str,
    payload: StatusUpdateRequest,
    pipeline: VocabularyPipeline = Depends(get_pipeline),
):
    updated = pipeline.repository.update_word_status(lemma, payload.status)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Word not found")
    record = pipeline.fetch_word(lemma)
    if record is None:  # pragma: no cover - fetch should succeed after update
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Word not found")
    return _serialize_word_detail(record)


@app.get("/api/v1/health")
def health_check(pipeline: VocabularyPipeline = Depends(get_pipeline)):
    if pipeline.repository.ping():
        return {"status": "ok"}
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="database down")
