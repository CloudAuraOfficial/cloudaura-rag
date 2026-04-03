from fastapi import APIRouter, HTTPException, Request

from rag_core.models.schemas import AskRequest, AskResponse, ErrorResponse

router = APIRouter(prefix="/api", tags=["ask"])


@router.post(
    "/ask",
    response_model=AskResponse,
    responses={400: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def ask_question(request: Request, body: AskRequest) -> AskResponse:
    retriever = request.app.state.retriever
    generator = request.app.state.generator

    results = retriever.retrieve(body.question, top_k=body.top_k)

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
        return await generator.generate_answer(
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
