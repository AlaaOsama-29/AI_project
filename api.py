from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json
import threading
from pathlib import Path
import uuid

from question_delivery import run_interview
from shared import answers_store, answers_lock

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATE_FILE = "state.json"
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
    from shared import sessions_store
    state = sessions_store.get(session_id)
    if state:
        return state
    return {"status": "not_found"}

# ─── SUBMIT ANSWER ────────────────────────────────────────
@app.post("/answer")
def submit_answer(student_name: str = None, session_id: str = None, answer: str = ""):

    if not session_id and not student_name:
        return {"error": "No identifier provided"}

    key = session_id or student_name

    with answers_lock:
        answers_store[key] = answer.strip()

    return {"message": "Answer received"}
# ─── RESULTS ─────────────────────────────────────────────
@app.get("/results/{student_name}")
def get_results(student_name: str):
    try:
        results = []
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(" | ")
                if len(parts) >= 7 and parts[1] == student_name:
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