from __future__ import annotations

import os
import time
from dataclasses import dataclass

from . import metrics
from .mock_llm import FakeLLM
from .mock_rag import retrieve
from .pii import hash_user_id, summarize_text
from .prompt_management import resolve_prompt
from .tracing import get_langfuse_client, propagate_attributes, tracing_enabled


@dataclass
class AgentResult:
    answer: str
    latency_ms: int
    ttft_ms: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    quality_score: float


class LabAgent:
    def __init__(self, model: str = "claude-sonnet-4-5") -> None:
        self.model = model
        self.llm = FakeLLM(model=model)

    def run(
        self,
        user_id: str,
        feature: str,
        session_id: str,
        message: str,
        correlation_id: str,
    ) -> AgentResult:
        langfuse_client = get_langfuse_client()
        root_metadata = {
            "correlation_id": correlation_id,
            "feature": feature,
            "model": self.model,
        }
        with langfuse_client.start_as_current_observation(
            name="lab-agent-run",
            as_type="agent",
            input={"message_preview": summarize_text(message)},
            metadata=root_metadata,
        ) as root_observation:
            with propagate_attributes(
                user_id=hash_user_id(user_id),
                session_id=session_id,
                tags=["lab", feature, self.model],
                trace_name="day13-agent-request",
                environment=os.getenv("APP_ENV", "dev"),
                metadata={
                    "correlationId": correlation_id,
                    "feature": feature,
                    "model": self.model,
                },
            ):
                started = time.perf_counter()
                with langfuse_client.start_as_current_observation(
                    name="retrieval",
                    as_type="retriever",
                    input={"query_preview": summarize_text(message)},
                ):
                    docs = retrieve(message)
                    langfuse_client.update_current_span(
                        output={"doc_count": len(docs)},
                        metadata={"success": True},
                    )
                prompt = resolve_prompt(
                    langfuse_client,
                    feature=feature,
                    docs=docs,
                    message=message,
                    enabled=tracing_enabled(),
                )
                root_observation.update(
                    metadata={
                        **root_metadata,
                        "doc_count": len(docs),
                        "query_preview": summarize_text(message),
                        "prompt_name": prompt.name,
                        "prompt_label": prompt.label,
                        "prompt_version": prompt.version,
                        "prompt_source": prompt.source,
                        "prompt_fetch_error": prompt.fetch_error or "",
                    },
                    version=prompt.version,
                )
                with propagate_attributes(prompt=prompt.managed_prompt):
                    with langfuse_client.start_as_current_observation(
                        name="llm-generation",
                        as_type="generation",
                        model=self.model,
                        prompt=prompt.managed_prompt,
                        input={"prompt_preview": summarize_text(prompt.text)},
                    ):
                        response = self.llm.generate(prompt.text)
                        cost_usd = self._estimate_cost(
                            response.usage.input_tokens,
                            response.usage.output_tokens,
                        )
                        input_cost_usd = round(
                            (response.usage.input_tokens / 1_000_000) * 3, 6
                        )
                        output_cost_usd = round(
                            (response.usage.output_tokens / 1_000_000) * 15, 6
                        )
                        langfuse_client.update_current_generation(
                            output={"answer_preview": summarize_text(response.text)},
                            usage_details={
                                "input": response.usage.input_tokens,
                                "output": response.usage.output_tokens,
                                "total": (
                                    response.usage.input_tokens
                                    + response.usage.output_tokens
                                ),
                            },
                            cost_details={
                                "input": input_cost_usd,
                                "output": output_cost_usd,
                                "total": cost_usd,
                            },
                            metadata={
                                "input_tokens": response.usage.input_tokens,
                                "output_tokens": response.usage.output_tokens,
                                "cost_usd": cost_usd,
                            },
                        )
                quality_score = self._heuristic_quality(message, response.text, docs)
                latency_ms = int((time.perf_counter() - started) * 1000)
                root_observation.update(
                    output={"answer_preview": summarize_text(response.text)}
                )

        metrics.record_request(
            latency_ms=latency_ms,
            ttft_ms=response.ttft_ms,
            cost_usd=cost_usd,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            quality_score=quality_score,
        )

        return AgentResult(
            answer=response.text,
            latency_ms=latency_ms,
            ttft_ms=response.ttft_ms,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            cost_usd=cost_usd,
            quality_score=quality_score,
        )

    def _estimate_cost(self, tokens_in: int, tokens_out: int) -> float:
        input_cost = (tokens_in / 1_000_000) * 3
        output_cost = (tokens_out / 1_000_000) * 15
        return round(input_cost + output_cost, 6)

    def _heuristic_quality(self, question: str, answer: str, docs: list[str]) -> float:
        score = 0.5
        if docs:
            score += 0.2
        if len(answer) > 40:
            score += 0.1
        if question.lower().split()[0:1] and any(token in answer.lower() for token in question.lower().split()[:3]):
            score += 0.1
        if "[REDACTED" in answer:
            score -= 0.2
        return round(max(0.0, min(1.0, score)), 2)
