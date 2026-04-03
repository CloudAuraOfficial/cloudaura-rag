"""P3 ask endpoint with adaptive routing and corrective retrieval."""

from fastapi import APIRouter, HTTPException, Request

from rag_core.models.schemas import AskResponse, ErrorResponse
from app.models.schemas import AdaptiveAskRequest, AdaptiveAskResponse

router = APIRouter(prefix="/api", tags=["ask"])


@router.post(
    "/ask",
    response_model=AdaptiveAskResponse,
    responses={400: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def ask_question(request: Request, body: AdaptiveAskRequest) -> AdaptiveAskResponse:
    adaptive_router = request.app.state.adaptive_router
    corrective_retriever = request.app.state.corrective_retriever
    generator = request.app.state.generator
    retriever = request.app.state.retriever

    classification = None
    quality = None
    corrections = None
    route_taken = None

    if body.mode == "adaptive" or body.mode == "both":
        results, classification, route_taken = await adaptive_router.route(
            body.question, top_k=body.top_k
        )

        if body.mode == "both" and results:
            # Run corrective check on adaptive results
            quality_checker = request.app.state.quality_checker
            quality = quality_checker.check(body.question, results)
            if not quality.passed:
                results, quality, corrections = await corrective_retriever.retrieve(
                    body.question, top_k=body.top_k
                )
                route_taken += " → corrective retry"
    else:
        # Pure corrective mode
        results, quality, corrections = await corrective_retriever.retrieve(
            body.question, top_k=body.top_k
        )
        route_taken = "corrective (quality check + retry loop)"

    # Handle no_retrieval route — direct LLM answer
    if classification and classification.category == "no_retrieval":
        try:
            # Generate without retrieval context
            from rag_core.models.schemas import AskResponse, Citation
            import time
            import httpx as _httpx

            gen = generator
            start = time.perf_counter()
            resp = await gen._client.post(
                "/api/generate",
                json={
                    "model": gen._default_model,
                    "prompt": body.question,
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 1024},
                },
            )
            resp.raise_for_status()
            answer = resp.json().get("response", "")
            elapsed = (time.perf_counter() - start) * 1000

            return AdaptiveAskResponse(
                question=body.question,
                answer=answer,
                citations=[],
                model=gen._default_model,
                retrieval_method="direct LLM (no retrieval)",
                latency_ms=round(elapsed, 1),
                classification=classification,
                route_taken=route_taken,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail={"error": "generation_error", "message": str(exc), "status_code": 502},
            ) from exc

    if not results:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "no_results",
                "message": "No relevant documents found. Please ingest documents first.",
                "status_code": 400,
            },
        )

    try:
        answer_response = await generator.generate_answer(
            question=body.question,
            results=results,
            model=body.model,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "generation_error", "message": str(exc), "status_code": 502},
        ) from exc

    return AdaptiveAskResponse(
        question=body.question,
        answer=answer_response.answer,
        citations=answer_response.citations,
        model=answer_response.model,
        retrieval_method=answer_response.retrieval_method,
        latency_ms=answer_response.latency_ms,
        classification=classification,
        quality=quality,
        corrections=corrections,
        route_taken=route_taken,
    )
