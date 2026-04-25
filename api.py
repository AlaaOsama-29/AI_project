from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import threading
import uuid
import os
from datetime import datetime

from question_delivery import run_interview
from shared import answers_store, answers_lock, sessions_store

app = FastAPI()

_cors_env = os.getenv("CORS_ALLOW_ORIGINS", "*")
_cors_origins = [origin.strip() for origin in _cors_env.split(",") if origin.strip()]
if not _cors_origins:
    _cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

LOG_FILE   = "interview_log.txt"

# ─── START INTERVIEW ──────────────────────────────────────
@app.post("/start")
def start_interview(student_name: str, topic: str = "Python"):
    session_id = str(uuid.uuid4())
    # Persist session immediately so an early /stop can find it.
    sessions_store[session_id] = {
        "session_id": session_id,
        "student_name": student_name,
        "status": "starting",
        "question": "",
        "level": "",
        "question_num": 0,
        "topic": topic,
        "timestamp": datetime.now().isoformat(),
    }

    def run():
        run_interview(student_name, session_id, from_api=True, topic=topic)

    threading.Thread(target=run, daemon=True).start()

    return {
        "message": "Interview started",
        "session_id": session_id,
        "topic": topic
    }

# ─── GET STATE ────────────────────────────────────────────
@app.get("/state/{session_id}")
def get_state(session_id: str):
    state = sessions_store.get(session_id)

    if not state:
        return {
            "status": "not_found",
            "data": None
        }

    return {
        "status": state.get("status"),
        "data": {
            "question": state.get("question"),
            "level": state.get("level"),
            "question_num": state.get("question_num"),
            "student_name": state.get("student_name"),
            "topic": state.get("topic")
        }
    }
def _latest_session_for_student(student_name: str):
    if not student_name:
        return None
    matches = [s for s in sessions_store.values() if s.get("student_name") == student_name]
    if not matches:
        return None
    latest = max(matches, key=lambda s: s.get("timestamp", ""))
    return latest.get("session_id")

# ─── SUBMIT ANSWER ────────────────────────────────────────
@app.post("/answer")
def submit_answer(student_name: str = None, session_id: str = None, answer: str = ""):

    if not session_id and not student_name:
        return {"error": "No identifier provided"}

    resolved_session = session_id or _latest_session_for_student(student_name)

    if not resolved_session:
        return {"error": "No active session found"}

    state = sessions_store.get(resolved_session)

    # Reject unknown sessions.
    if not state:
        return {"error": "Session not found"}

    # Accept answers only while recording.
    if state.get("status") != "recording":
        return {
            "error": "Not accepting answers right now",
            "current_status": state.get("status")
        }

    # Reject empty payloads.
    if not answer.strip():
        return {"error": "Empty answer not allowed"}

    # Store trimmed answer.
    with answers_lock:
        answers_store[resolved_session] = answer.strip()

    return {
        "message": "Answer received",
        "session_id": resolved_session
    }
# ─── RESULTS ─────────────────────────────────────────────
@app.get("/results/{student_name}")
def get_results(student_name: str):
    try:
        results = []
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(" | ", maxsplit=9)
                if len(parts) >= 10 and parts[1] == student_name:
                    results.append({
                        "timestamp": parts[0],
                        "student": parts[1],
                        "topic": parts[2],
                        "question_num": parts[3],
                        "level": parts[4],
                        "question": parts[5],
                        "answer": parts[6],
                        "elapsed": parts[7],
                        "adapted": parts[8],
                        "reason": parts[9],
                    })
        return {"student": student_name, "results": results}
    except Exception:
        return {"student": student_name, "results": []}

@app.post("/stop/{session_id}")
def stop_interview(session_id: str):
    state = sessions_store.get(session_id)

    if not state:
        return {"error": "Session not found", "stopped": False}

    # Mark interview as stopped and persist to backing store.
    state["status"] = "stopped"
    sessions_store[session_id] = state

    return {
        "message": "Interview stopped",
        "session_id": session_id,
        "stopped": True,
    }
