from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel, Field

from backend.settings import backend_cors_origins, load_backend_config
from synapse_ai.config import MissingConfigError
from synapse_ai.ui.copilot_page import CopilotMessage, _generate_copilot_answer


class CopilotMessagePayload(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12000)


class CopilotRequest(BaseModel):
    prompt: str | None = Field(default=None, max_length=12000)
    messages: list[CopilotMessagePayload] = Field(default_factory=list)
    current_area: str = Field(default="API REST", max_length=120)
    context: str | None = Field(default=None, max_length=20000)
    model: str | None = Field(default=None, max_length=120)


class CopilotResponse(BaseModel):
    answer: str
    model: str


class DashboardStatsResponse(BaseModel):
    """Initial dashboard contract, ready to be backed by Synapse repositories."""

    base_ready: int
    evidence_count: int
    risk_count: int
    pending_confirmation_count: int


app = FastAPI(
    title="Synapse AI API",
    version="0.1.0",
    description="REST API for the Synapse AI SaaS migration.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=backend_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/dashboard/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats() -> DashboardStatsResponse:
    """Expose the first dashboard contract while repository migration is incremental."""
    return DashboardStatsResponse(
        base_ready=0,
        evidence_count=0,
        risk_count=0,
        pending_confirmation_count=0,
    )


@app.post("/api/copilot", response_model=CopilotResponse)
async def ask_copilot(payload: CopilotRequest) -> CopilotResponse:
    messages = [
        CopilotMessage(role=message.role, content=message.content)
        for message in payload.messages
    ]
    if payload.prompt and payload.prompt.strip():
        messages.append(CopilotMessage(role="user", content=payload.prompt.strip()))
    if not messages:
        raise HTTPException(status_code=400, detail="Envie prompt ou histórico de mensagens.")

    try:
        config = load_backend_config()
    except MissingConfigError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Configuração ausente: {exc.setting_name}",
        ) from exc

    model = payload.model or config.openai.generation_model
    openai_client = OpenAI(api_key=config.openai.api_key)
    answer = await run_in_threadpool(
        _generate_copilot_answer,
        config,
        messages,
        api_key=config.openai.api_key,
        model=model,
        context_snapshot=payload.context or "Nenhum contexto documental enviado pela API.",
        current_area=payload.current_area,
        openai_client=openai_client,
    )
    return CopilotResponse(answer=answer, model=model)
