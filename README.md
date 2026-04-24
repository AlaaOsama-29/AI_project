# AI Technical Interviewer 🎤🤖

Alaa — Question Delivery Module

---

## 📋 Responsibilities

- Generate 5 questions using Claude AI (via Anthropic API or OpenRouter) based on the selected topic
- Read questions aloud using Text-to-Speech (Windows PowerShell)
- Display questions sequentially and wait for student answers
- Adaptive difficulty — increases or decreases based on student performance
- Supports 16 built-in topics + custom topic input
- Supports both CLI mode and API mode (for team integration)

---

## 📂 Files

| File | Purpose |
| --- | --- |
| `question_delivery.py` | Main interview logic |
| `api.py` | FastAPI endpoints for the team |
| `shared.py` | Shared data between modules (`sessions_store`, `answers_store`, `answers_lock`) |
| `state_{session_id}.json` | Real-time interview state per session (for team) |
| `interview_log.txt` | Full log after interview ends (for team) |
| `.env` | API keys and model configuration |

---

## ⚙️ Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Copy `.env.example` and rename it `.env`, then add your API key.

**Option A — Anthropic API (direct):**

```
ANTHROPIC_API_KEY=sk-ant-api...
```

**Option B — OpenRouter:**

```
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=anthropic/claude-3.5-haiku
```

> If both keys are set, OpenRouter takes priority.

3. Run the interview directly (CLI mode):

```bash
python question_delivery.py
```

4. Or run the API for the team:

```bash
uvicorn api:app --reload
```

---

## 🎯 Available Topics

| Number | Topic |
| --- | --- |
| 1 | Python |
| 2 | Java |
| 3 | C++ |
| 4 | SQL |
| 5 | Frontend (HTML, CSS, JavaScript) |
| 6 | Backend (REST APIs, HTTP, Django/Node) |
| 7 | DevOps and Cloud |
| 8 | Machine Learning |
| 9 | Data Science and Statistics |
| 10 | Cybersecurity |
| 11 | Operating Systems |
| 12 | Computer Networks |
| 13 | Mobile Development (Android/iOS) |
| 14 | Software Testing and QA |
| 15 | System Design |
| 16 | Data Structures and Algorithms |
| C | Custom topic (type your own) |

---

## 🔗 Integration with Team

### API Endpoints — at `http://localhost:8000`

| Endpoint | Method | Used By | Description |
| --- | --- | --- | --- |
| `/start?student_name=alaa&topic=Python` | POST | Frontend | Starts the interview, returns `session_id` |
| `/state/{session_id}` | GET | Frontend + Camera | Returns current interview state |
| `/answer?session_id=...&answer=...` | POST | Frontend | Submits student answer |
| `/results/{student_name}` | GET | Backend | Returns all results for a student |

> ⚠️ **Important:** Always use `session_id` (returned from `/start`) when calling `/answer`.
> The `/answer` endpoint rejects requests if the session status is not `recording`.

---

### Example `/start` Response

```json
{
  "message": "Interview started",
  "session_id": "abc-123-xyz",
  "topic": "Python"
}
```

---

### Example `/state/{session_id}` Response

```json
{
  "status": "recording",
  "data": {
    "question": "What is a decorator?",
    "level": "Hard",
    "question_num": 3,
    "student_name": "alaa",
    "topic": "Python"
  }
}
```

**Status values:**

| Status | Meaning |
| --- | --- |
| `idle` | Interview just started, not yet asking |
| `waiting` | Question displayed, waiting for timer |
| `recording` | Actively waiting for student answer |
| `done` | Interview finished |
| `stopped` | Interview stopped manually |
| `not_found` | Session ID does not exist |

---

### Example `/answer` Request

```
POST /answer?session_id=abc-123-xyz&answer=A decorator is a function that wraps another function
```

> ⚠️ Empty answers are rejected with an error response.

---

### Example `/answer` Error Responses

```json
{ "error": "Not accepting answers right now", "current_status": "waiting" }
```

```json
{ "error": "Empty answer not allowed" }
```

```json
{ "error": "Session not found" }
```

---

### Example `/results/{student_name}` Response

```json
{
  "student": "alaa",
  "results": [
    {
      "timestamp": "2026-04-20 01:00:00",
      "student": "alaa",
      "topic": "Python",
      "question_num": "Q1",
      "level": "[Medium]",
      "question": "What is OOP?",
      "answer": "Object-oriented programming ...",
      "elapsed": "4.04s",
      "adapted": "adapt:up"
    }
  ]
}
```

---

## ⏱️ Time Limits & Adaptive Difficulty

| Level | Time Limit |
| --- | --- |
| Easy | 20s |
| Medium | 25s |
| Hard | 30s |

**Difficulty adapts automatically based on answer speed:**

| Answer Time | Action |
| --- | --- |
| Under 10s | Level goes **UP** |
| 10s – 20s | Level stays the **SAME** |
| Over 20s | Level goes **DOWN** |

---

## 🔁 Repeat Feature

Students can type `r` (or `repeat` / `again`) and press Enter to hear the question again.
Each student gets **one repeat per question** only.

---

## 🚨 Notes for the Team

- The interview runs in a **background thread** — do not block `/start`
- State is stored in both memory (`sessions_store`) and a file (`state_{session_id}.json`)
- If no API key is set, the system falls back to **pre-written questions automatically**
- TTS only works on **Windows** (uses PowerShell System.Speech)

---

## 👩‍💻 Author

Alaa