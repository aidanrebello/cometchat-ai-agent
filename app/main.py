from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.agent import generate_answer


app = FastAPI(
    title="CometChat AI Agent",
    description="RAG-based customer support AI agent",
    version="1.0.0"
)


# ============================================================
# CONVERSATION MEMORY
# ============================================================

conversation_store = {}

MAX_HISTORY_MESSAGES = 6


# ============================================================
# REQUEST MODEL
# ============================================================

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "message": "CometChat AI Agent is running"
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "healthy"
    }


# ============================================================
# CHAT
# ============================================================

@app.post("/chat")
def chat(request: ChatRequest):

    try:

        # ====================================================
        # VALIDATE MESSAGE
        # ====================================================

        if not request.message.strip():

            raise HTTPException(
                status_code=400,
                detail="Message cannot be empty."
            )

        # ====================================================
        # SESSION
        # ====================================================

        session_id = request.session_id

        if session_id not in conversation_store:

            conversation_store[session_id] = []

        history = conversation_store[session_id]

        # ====================================================
        # GENERATE ANSWER
        # ====================================================

        result = generate_answer(
            request.message,
            history
        )

        # ====================================================
        # SAVE USER MESSAGE
        # ====================================================

        history.append(
            {
                "role": "user",
                "content": request.message
            }
        )

        # ====================================================
        # SAVE AI RESPONSE
        # ====================================================

        history.append(
            {
                "role": "assistant",
                "content": result["answer"]
            }
        )

        # ====================================================
        # LIMIT MEMORY
        # ====================================================

        if len(history) > MAX_HISTORY_MESSAGES:

            conversation_store[session_id] = (
                history[-MAX_HISTORY_MESSAGES:]
            )

        # ====================================================
        # RETURN RESPONSE
        # ====================================================

        return {
            "session_id": session_id,
            "message": request.message,
            "answer": result["answer"],
            "sources": result["sources"]
        }

    # ========================================================
    # PRESERVE HTTP ERRORS
    # ========================================================

    except HTTPException:
        raise

    # ========================================================
    # OLLAMA ERROR
    # ========================================================

    except RuntimeError as e:

        raise HTTPException(
            status_code=503,
            detail=str(e)
        )

    # ========================================================
    # UNEXPECTED ERROR
    # ========================================================

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )