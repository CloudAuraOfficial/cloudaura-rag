"""P2 ask endpoint with memory and branched retrieval modes."""

from fastapi import APIRouter, HTTPException, Request

from rag_core.models.schemas import ErrorResponse
from app.models.schemas import ConversationalAskRequest, ConversationalAskResponse, SubQuestion

router = APIRouter(prefix="/api", tags=["ask"])


@router.post(
    "/ask",
    response_model=ConversationalAskResponse,
    responses={400: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def ask_question(request: Request, body: ConversationalAskRequest) -> ConversationalAskResponse:
    memory = request.app.state.memory
    memory_retriever = request.app.state.memory_retriever
    branched_retriever = request.app.state.branched_retriever
    generator = request.app.state.generator

    session_id = memory.get_or_create(body.session_id)

    # Record user message
    memory.add_message(session_id, "user", body.question)

    sub_questions = None

    if body.mode == "branched" or body.mode == "both":
        results, sq_info = await branched_retriever.retrieve(
            body.question, top_k=body.top_k
        )
        sub_questions = [SubQuestion(**sq) for sq in sq_info]
        method = "branched (decompose + parallel retrieve + merge + rerank)"

        if body.mode == "both":
            # Also get memory-augmented results and merge
            mem_results = memory_retriever.retrieve(
                body.question, session_id, top_k=body.top_k
            )
            seen = {r.chunk_id for r in results}
            for r in mem_results:
                if r.chunk_id not in seen:
                    results.append(r)
                    seen.add(r.chunk_id)
            results = results[:body.top_k]
            method = "memory + branched (combined)"
    else:
        results = memory_retriever.retrieve(
            body.question, session_id, top_k=body.top_k
        )
        method = "memory-augmented hybrid (conversation context + BM25 + vector + rerank)"

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
            detail={
                "error": "generation_error",
                "message": str(exc),
                "status_code": 502,
            },
        ) from exc

    # Record assistant response
    memory.add_message(session_id, "assistant", answer_response.answer)

    return ConversationalAskResponse(
        question=body.question,
        answer=answer_response.answer,
        citations=answer_response.citations,
        model=answer_response.model,
        retrieval_method=method,
        latency_ms=answer_response.latency_ms,
        session_id=session_id,
        conversation_context=len(memory.get_history(session_id)),
        sub_questions=sub_questions,
    )
