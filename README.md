# AI Technical Interviewer 🎤🤖

Alaa — Question Delivery Module

---

## 📋 Responsibilities

- Generate 5 questions using Claude AI based on the selected topic
- Read questions aloud using Text-to-Speech
- Display questions sequentially and wait for student answers
- Adaptive difficulty — increases or decreases based on student performance
- Supports multiple topics (Python, SQL, Frontend, Backend, DSA)

---

## 📂 Files

| File | Purpose |
|---|---|
| `question_delivery.py` | Main code |
| `api.py` | FastAPI endpoints for the team |
| `shared.py` | Shared data between modules |
| `state.json` | Real-time interview state (for team) |
| `interview_log.txt` | Full log after interview ends (for team) |

---

## ⚙️ Setup

1. Install dependencies:
```
pip install -r requirements.txt
```

2. Copy `.env.example` and rename it `.env`, then add your API Key:
```
ANTHROPIC_API_KEY=your_api_key_here
```

3. Run the interview directly:
```
python question_delivery.py
```

4. Or run the API for the team:
```
uvicorn api:app --reload
```

---

## 🎯 Available Topics

| Number | Topic |
|---|---|
| 1 | Python |
| 2 | SQL |
| 3 | Frontend (HTML, CSS, JavaScript) |
| 4 | Backend (REST APIs, HTTP, Django/Node) |
| 5 | Data Structures and Algorithms |

---

## 🔗 Integration with Team

### API Endpoints — at `http://localhost:8000`

| Endpoint | Method | Used By | Description |
|---|---|---|---|
| `/start?student_name=alaa&topic=Python` | POST | Frontend | Starts the interview and returns session_id |
| `/state/{session_id}` | GET | Frontend + Camera | Returns current interview state |
| `/answer?student_name=alaa&answer=...` | POST | Frontend | Submits student answer |
| `/results/{student_name}` | GET | Backend | Returns student results |

### Example `/start` Response
```json
{
  "message": "Interview started",
  "session_id": "abc-123-xyz",
  "topic": "Python"
}
```

### Example `/state/{session_id}` Response
```json
{
  "status": "recording",
  "question_num": 3,
  "question": "What is a decorator?",
  "level": "Hard",
  "student_name": "alaa",
  "session_id": "abc-123-xyz",
  "topic": "Python",
  "timestamp": "2026-04-20T01:00:00"
}
```
Status values: `idle` / `waiting` / `recording` / `done`

### Example `/results/{student_name}` Response
```json
{
  "student": "alaa",
  "results": [
    {
      "question_num": "Q1",
      "level": "[Medium]",
      "question": "What is OOP?",
      "answer": "...",
      "elapsed": "4.04s"
    }
  ]
}
```

---

## ⏱️ Time Limits

| Level | Time |
|---|---|
| Easy | 20s |
| Medium | 25s |
| Hard | 30s |

---

## 👩‍💻 Author
Alaa