"""Conversation session management endpoints."""

from fastapi import APIRouter, HTTPException, Request

from app.models.schemas import ConversationListResponse, ConversationSession, ConversationMessage

router = APIRouter(prefix="/api", tags=["conversations"])


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(request: Request) -> ConversationListResponse:
    memory = request.app.state.memory
    sessions = memory.list_sessions()
    return ConversationListResponse(
        sessions=[
            ConversationSession(
                session_id=s["session_id"],
                messages=[ConversationMessage(**m) for m in s["messages"]],
                created_at=s["created_at"],
                message_count=s["message_count"],
            )
            for s in sessions
        ],
        total=len(sessions),
    )


@router.post("/conversations", response_model=dict)
async def create_conversation(request: Request) -> dict:
    memory = request.app.state.memory
    session_id = memory.create_session()
    return {"session_id": session_id}


@router.delete("/conversations/{session_id}")
async def delete_conversation(request: Request, session_id: str) -> dict:
    memory = request.app.state.memory
    deleted = memory.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True, "session_id": session_id}
