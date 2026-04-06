"""P4 ask endpoint with Self-RAG and Agentic RAG modes."""

import time

from fastapi import APIRouter, HTTPException, Request

from app.models.schemas import AutonomousAskRequest, AutonomousAskResponse
from rag_core.models.schemas import Citation, ErrorResponse

router = APIRouter(prefix="/api", tags=["ask"])


@router.post(
    "/ask",
    response_model=AutonomousAskResponse,
    responses={400: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def ask_question(request: Request, body: AutonomousAskRequest) -> AutonomousAskResponse:
    self_rag = request.app.state.self_rag
    agent_executor = request.app.state.agent_executor
    tool_registry = request.app.state.tool_registry
    generator = request.app.state.generator

    start = time.perf_counter()

    if body.mode == "self_rag":
        answer, grades, filtered_count, critique = await self_rag.run(
            body.question, top_k=body.top_k, model=body.model,
        )

        if not answer:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "no_results",
                    "message": "No relevant documents found after relevance filtering.",
                    "status_code": 400,
                },
            )

        elapsed = (time.perf_counter() - start) * 1000
        return AutonomousAskResponse(
            question=body.question,
            answer=answer.answer,
            citations=answer.citations,
            model=answer.model,
            retrieval_method="self-rag (grade + filter + critique)",
            latency_ms=round(elapsed, 1),
            mode="self_rag",
            relevance_grades=grades,
            filtered_count=filtered_count,
            critique=critique,
        )

    elif body.mode == "agentic":
        try:
            final_answer, steps = await agent_executor.run(body.question)
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail={"error": "agent_error", "message": str(exc), "status_code": 502},
            ) from exc

        # Build citations from retrieved results
        citations = [
            Citation(
                document=r.document,
                chunk_id=r.chunk_id,
                content=r.content[:200],
                score=r.rerank_score or 0.0,
            )
            for r in tool_registry.retrieved_results
        ]

        elapsed = (time.perf_counter() - start) * 1000
        return AutonomousAskResponse(
            question=body.question,
            answer=final_answer,
            citations=citations,
            model=generator._default_model,
            retrieval_method="agentic (plan + tools + synthesize)",
            latency_ms=round(elapsed, 1),
            mode="agentic",
            agent_steps=steps,
        )

    else:
        # "both" mode: Self-RAG first, then use agent if critique fails
        answer, grades, filtered_count, critique = await self_rag.run(
            body.question, top_k=body.top_k, model=body.model,
        )

        agent_steps = None
        if not answer or (critique and critique.overall_score < request.app.state.settings.hallucination_threshold):
            # Fallback to agentic approach
            try:
                final_answer, agent_steps = await agent_executor.run(body.question)
            except Exception as exc:
                raise HTTPException(
                    status_code=502,
                    detail={"error": "agent_error", "message": str(exc), "status_code": 502},
                ) from exc

            citations = [
                Citation(
                    document=r.document,
                    chunk_id=r.chunk_id,
                    content=r.content[:200],
                    score=r.rerank_score or 0.0,
                )
                for r in tool_registry.retrieved_results
            ]

            elapsed = (time.perf_counter() - start) * 1000
            return AutonomousAskResponse(
                question=body.question,
                answer=final_answer,
                citations=citations,
                model=generator._default_model,
                retrieval_method="self-rag → agentic fallback",
                latency_ms=round(elapsed, 1),
                mode="both",
                relevance_grades=grades,
                filtered_count=filtered_count,
                critique=critique,
                agent_steps=agent_steps,
            )

        elapsed = (time.perf_counter() - start) * 1000
        return AutonomousAskResponse(
            question=body.question,
            answer=answer.answer,
            citations=answer.citations,
            model=answer.model,
            retrieval_method="self-rag (passed critique)",
            latency_ms=round(elapsed, 1),
            mode="both",
            relevance_grades=grades,
            filtered_count=filtered_count,
            critique=critique,
        )
