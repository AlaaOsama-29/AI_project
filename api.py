from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import threading
import uuid

from question_delivery import run_interview
from shared import answers_store, answers_lock, sessions_store

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

LOG_FILE   = "interview_log.txt"

# ─── START INTERVIEW ──────────────────────────────────────
@app.post("/start")
def start_interview(student_name: str, topic: str = "Python"):
    session_id = str(uuid.uuid4())

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
    if state:
        return state
    return {"status": "not_found"}


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
        return {"error": "No active session found for this student"}

    with answers_lock:
        answers_store[resolved_session] = answer.strip()

    return {"message": "Answer received", "session_id": resolved_session}
# ─── RESULTS ─────────────────────────────────────────────
@app.get("/results/{student_name}")
def get_results(student_name: str):
    try:
        results = []
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(" | ")
                if len(parts) >= 9 and parts[1] == student_name:
                    results.append({
                        "timestamp": parts[0],
                        "student": parts[1],
                        "topic": parts[2],
                        "question_num": parts[3],
                        "level": parts[4],
                        "question": parts[5],
                        "answer": parts[6],
                        "elapsed": parts[7],
                        "adapted": parts[8] if len(parts) > 8 else "",
                    })
        return {"student": student_name, "results": results}
    except Exception:
        return {"student": student_name, "results": []}