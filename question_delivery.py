import time
import sys
import threading
import json
import os
import httpx
import re
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

STATE_FILE     = "state.json"
LOG_FILE       = "interview_log.txt"

FAST_THRESHOLD = 10
SLOW_THRESHOLD = 20
LEVELS         = ["Easy", "Medium", "Hard"]

def get_time_limit(level):
    if level == "Easy":
        return 20
    elif level == "Medium":
        return 25
    else:
        return 30

# ─── Claude via OpenRouter Setup ──────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
client = True if ANTHROPIC_API_KEY else None

if client:
    print("  [AI]  Claude ready ✅")
else:
    print("  [WARN]  No API key found — using smart random.")

# ─── Terminal UI ──────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
WHITE  = "\033[97m"
RED    = "\033[91m"

def _banner(text, color="white"):
    c = {"green": GREEN, "yellow": YELLOW, "cyan": CYAN,
         "white": WHITE, "red": RED}.get(color, WHITE)
    width = 56
    print(f"\n{c}{'─' * width}{RESET}")
    print(f"{c}  {text}{RESET}")
    print(f"{c}{'─' * width}{RESET}\n")

def _log(tag, text):
    tag_colors = {
        "SPEAK": CYAN, "INFO": DIM, "TIMER": YELLOW,
        "STATE": GREEN, "WARN": YELLOW, "ADAPT": CYAN, "AI": GREEN
    }
    c = tag_colors.get(tag, WHITE)
    print(f"  {c}[{tag}]{RESET}  {text}")

def _progress(current, total):
    filled = round(current / total * 24)
    bar    = "█" * filled + "░" * (24 - filled)
    pct    = round(current / total * 100)
    print(f"\n  {DIM}Progress{RESET}  {CYAN}{bar}{RESET}  "
          f"{WHITE}{current}/{total}{RESET}  {DIM}({pct}%){RESET}\n")

def _question_card(q_num, total, level, question, arrow=""):
    level_colors = {"Easy": GREEN, "Medium": YELLOW, "Hard": RED}
    lc    = level_colors.get(level, WHITE)
    width = 56
    print(f"  {DIM}{'─' * width}{RESET}")
    print(f"  {WHITE}{BOLD}Question {q_num}{RESET}  {DIM}of {total}{RESET}"
          f"   {lc}[{level}]{RESET}  {arrow}")
    print(f"  {DIM}{'─' * width}{RESET}")
    words, line = question.split(), ""
    for word in words:
        if len(line) + len(word) + 1 > 52:
            print(f"  {WHITE}{line}{RESET}")
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        print(f"  {WHITE}{line}{RESET}")
    print(f"  {DIM}{'─' * width}{RESET}\n")

# ─── AI Question Generation ───────────────────────────────
def ai_generate_question(level, history, results, topic="Python"):
    history_str = ", ".join(history) if history else "None yet"
    performance = ", ".join([
        f"{r['level']}:{round(r['elapsed'], 1)}s" for r in results
    ]) if results else "No data yet"

    fallback_by_topic = {
        "Python": {
            "Easy":   ["What is a variable?", "What is a function?", "What is a loop?",
                       "What is a list?", "What is an if statement?"],
            "Medium": ["What is OOP?", "What is a decorator?", "What is recursion?",
                       "What is a dictionary?", "What is exception handling?"],
            "Hard":   ["What is a generator?", "What is multithreading?", "What is a closure?",
                       "What is a metaclass?", "What are design patterns?"]
        },
        "SQL": {
            "Easy":   ["What is a PRIMARY KEY?", "What is SQL?", "What is SELECT?",
                       "What is WHERE clause?", "What is NULL in SQL?"],
            "Medium": ["What is a JOIN?", "What is GROUP BY?", "What is a subquery?",
                       "What is an index?", "What is HAVING clause?"],
            "Hard":   ["What is a CTE?", "What is RANK()?", "What is a trigger?",
                       "What is a deadlock?", "What are isolation levels?"]
        },
        "Frontend (HTML, CSS, JavaScript)": {
            "Easy":   ["What is HTML?", "What is CSS?", "What is a div?",
                       "What is a class in CSS?", "What is JavaScript?"],
            "Medium": ["What is the DOM?", "What is a Promise?", "What is flexbox?",
                       "What is an event listener?", "What is responsive design?"],
            "Hard":   ["What is a closure in JS?", "What is the event loop?", "What is hoisting?",
                       "What is async/await?", "What is a service worker?"]
        },
        "Backend (REST APIs, HTTP, Django/Node)": {
            "Easy":   ["What is an API?", "What is HTTP?", "What is a GET request?",
                       "What is JSON?", "What is a server?"],
            "Medium": ["What is REST?", "What is authentication?", "What is middleware?",
                       "What is a POST request?", "What is a status code?"],
            "Hard":   ["What is microservices?", "What is load balancing?", "What is Docker?",
                       "What is CI/CD?", "What is a message queue?"]
        },
        "Data Structures and Algorithms": {
            "Easy":   ["What is an array?", "What is a stack?", "What is a queue?",
                       "What is a linked list?", "What is Big O notation?"],
            "Medium": ["What is a binary tree?", "What is hashing?", "What is recursion?",
                       "What is a graph?", "What is dynamic programming?"],
            "Hard":   ["What is a red-black tree?", "What is Dijkstra algorithm?", "What is a heap?",
                       "What is memoization?", "What is a trie?"]
        }
    }
    fallback_questions = fallback_by_topic.get(topic, fallback_by_topic["Python"])

    if not client:
        import random
        asked = set(history)
        pool = [q for q in fallback_questions.get(level, fallback_questions["Medium"]) if q not in asked]
        if not pool:
            pool = fallback_questions.get(level, fallback_questions["Medium"])
        return random.choice(pool), "random fallback"

    prompt = f"""You are an AI technical interviewer assistant.

Generate ONE interview question about {topic} for a {level} level student.
Student performance so far: {performance}
Questions already asked (do NOT repeat): {history_str}

Rules:
- The question must be about {topic} concepts
- Must match the {level} difficulty level
- Must be different from questions already asked
- Keep it SHORT and conceptual (one sentence)
- Ask about definitions, differences, or explanations — NOT "write code"

Reply ONLY in this exact format:
QUESTION: <question text>
REASON: <why this question suits the student>
"""

    try:
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {ANTHROPIC_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "anthropic/claude-haiku-4-5",
                "max_tokens": 200,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=15
        )
        text = resp.json()["choices"][0]["message"]["content"].strip()
        question_line = ""
        reason_line   = ""

        for line in text.splitlines():
            if line.strip().lower().startswith("question:"):
                question_line = line.split(":", 1)[1].strip()
            elif line.strip().lower().startswith("reason:"):
                reason_line = line.split(":", 1)[1].strip()

        if question_line:
            if reason_line:
                _log("AI", reason_line)
            return question_line, reason_line

    except Exception as e:
        _log("WARN", f"Claude error — using fallback: {e}")

    import random
    asked = set(history)
    pool = [q for q in fallback_questions.get(level, fallback_questions["Medium"]) if q not in asked]
    if not pool:
        pool = fallback_questions.get(level, fallback_questions["Medium"])
    return random.choice(pool), "fallback question"

# ─── TTS ──────────────────────────────────────────────────
def setup_speaker():
    try:
        import subprocess
        ps_cmd = '''
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voices = $synth.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Gender -eq "Male" }
if ($voices) { $synth.SelectVoice($voices[0].VoiceInfo.Name) }
$synth.Volume = 100
$synth.Speak("ready")
'''
        subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, timeout=10)
        _log("INFO", "TTS ready ✅  (PowerShell)")
        return "powershell"
    except Exception as e:
        _banner(f"TTS unavailable: {e}", "yellow")
        return None

def speak(spk, text):
    _log("SPEAK", text)
    try:
        import subprocess
        safe = text.replace("'", " ")
        safe = re.sub(r'[`*_#@<>{}[\]|\\]', '', safe)
        safe = re.sub(r'\s+', ' ', safe).strip()
        ps_cmd = f"Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.SelectVoiceByHints('Male'); $s.Speak('{safe}')"
        subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, timeout=20)
    except Exception as e:
        _log("WARN", f"TTS error: {e}")
# ─── State File ───────────────────────────────────────────
def write_state(status, q_num=0, question="", level="", name="", session_id="", topic=""):
    from shared import sessions_store
    state = {
        "session_id":   session_id,
        "status":       status,
        "question_num": q_num,
        "question":     question,
        "level":        level,
        "student_name": name,
        "topic":        topic,
        "timestamp":    datetime.now().isoformat(),
    }
    # الاتنين مع بعض
    sessions_store[session_id] = state
    Path(STATE_FILE).write_text(
        json.dumps(state, indent=2, ensure_ascii=False)
    )
# ─── Log ──────────────────────────────────────────────────
def save_log(name, q_num, question, level, topic, answer, elapsed, adapted, reason):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
            f"{name} | {topic} | Q{q_num} | [{level}] | {question} | "
            f"{answer} | {elapsed:.2f}s | adapt:{adapted} | "
            f"reason:{reason}\n"
        )

# ─── Countdown Timer ──────────────────────────────────────
def countdown_timer(seconds, stop_event):
    for remaining in range(int(seconds), 0, -1):
        if stop_event.is_set():
            break
        filled  = round((seconds - remaining) / seconds * 10)
        bar     = "█" * filled + "░" * (10 - filled)
        urgency = RED if remaining <= 10 else YELLOW if remaining <= 20 else GREEN
        print(f"  {urgency}⏱  [{bar}]  {remaining:2d}s{RESET}", flush=True)
        time.sleep(1)
    print(f"  {DIM}⏱  [{'█' * 10}]  Done{RESET}", flush=True)

# ─── Answer Input ─────────────────────────────────────────
def get_answer(spk, question, q_num, level, time_limit, student_name="", session_id="", from_api=False):
    from shared import answers_store, answers_lock

    if from_api:
        with answers_lock:
            answers_store.pop(session_id, None)

        start = time.perf_counter()
        repeat_count = 0

        while time.perf_counter() - start < time_limit:
            with answers_lock:
                answer = answers_store.pop(session_id, None)

            if answer is not None:
                cleaned = answer.strip().lower()

                if cleaned == "r":
                    if repeat_count >= 1:
                        speak(spk, "No more repeats allowed.")
                        continue

                    repeat_count += 1
                    speak(spk, f"Question again. {question}")
                    continue


                elapsed = time.perf_counter() - start
                return answer, elapsed

            time.sleep(0.3)

        speak(spk, "Time is up.")
        return "", time_limit
# ─── Adaptive Difficulty ──────────────────────────────────
def get_next_level(current_level, elapsed):
    idx = LEVELS.index(current_level)
    if elapsed < FAST_THRESHOLD:
        new_idx = min(idx + 1, len(LEVELS) - 1)
        arrow   = f"{GREEN}⬆ Upgrading to {LEVELS[new_idx]}{RESET}"
        adapted = "up"
    elif elapsed > SLOW_THRESHOLD:
        new_idx = max(idx - 1, 0)
        arrow   = f"{YELLOW}⬇ Downgrading to {LEVELS[new_idx]}{RESET}"
        adapted = "down"
    else:
        new_idx = idx
        arrow   = ""
        adapted = "same"
    return LEVELS[new_idx], arrow, adapted

# ─── Summary ──────────────────────────────────────────────
def print_summary(name, total_time, results):
    _banner("INTERVIEW SUMMARY", "cyan")
    print(f"  {DIM}Student    {RESET}{WHITE}{name}{RESET}")
    print(f"  {DIM}Total time {RESET}{WHITE}{total_time:.0f}s{RESET}")
    print(f"  {DIM}Questions  {RESET}{WHITE}{len(results)}{RESET}\n")
    print(f"  {DIM}{'─' * 56}{RESET}")
    for r in results:
        level_colors = {"Easy": GREEN, "Medium": YELLOW, "Hard": RED}
        lc     = level_colors.get(r["level"], WHITE)
        timing = f"{GREEN}fast{RESET}"   if r["elapsed"] < FAST_THRESHOLD else \
                 f"{RED}slow{RESET}"     if r["elapsed"] > SLOW_THRESHOLD else \
                 f"{DIM}normal{RESET}"
        print(
            f"  Q{r['q_num']}  {lc}[{r['level']:6}]{RESET}  "
            f"{timing}  {DIM}{r['elapsed']:.1f}s{RESET}"
        )
    print(f"  {DIM}{'─' * 56}{RESET}\n")

# ─── Main ─────────────────────────────────────────────────
def run_interview(student_name: str = None, session_id: str = "", from_api: bool = False, topic: str = ""):

    spk           = setup_speaker()
    total         = 5
    results       = []
    history       = []
    current_level = "Medium"
    arrow         = ""

    _banner("AI TECHNICAL INTERVIEWER", "cyan")
    speak(spk, "Welcome to your technical interview.")
    write_state("idle", session_id=session_id)

    if student_name:
        name = student_name
    else:
        while not (name := input(f"  {DIM}Your name:{RESET}  ").strip()):
            print(f"  {RED}Name cannot be empty.{RESET}")

    # ─── Topic Selection ──────────────────────────────────
    topics = {
        "1": "Python",
        "2": "SQL",
        "3": "Frontend (HTML, CSS, JavaScript)",
        "4": "Backend (REST APIs, HTTP, Django/Node)",
        "5": "Data Structures and Algorithms"
    }

    if not topic:
        print(f"\n  {DIM}Choose your topic:{RESET}")
        print(f"  {CYAN}1{RESET}  Python")
        print(f"  {CYAN}2{RESET}  SQL")
        print(f"  {CYAN}3{RESET}  Frontend  (HTML / CSS / JavaScript)")
        print(f"  {CYAN}4{RESET}  Backend   (REST APIs / Node / Django)")
        print(f"  {CYAN}5{RESET}  Data Structures & Algorithms")

        while True:
            choice = input(f"\n  {CYAN}>{RESET}  Enter number (1-5): ").strip()
            if choice in topics:
                topic = topics[choice]
                break
            print(f"  {RED}Please enter a number from 1 to 5.{RESET}")

    print(f"\n  {GREEN}✓ Topic: {topic}{RESET}\n")
    speak(spk, f"Topic selected: {topic}.")
    speak(spk, f"Hello {name}. The interview will begin now.")
    _log("INFO", f"Student: {WHITE}{name}{RESET}  |  Topic: {WHITE}{topic}{RESET}  |  Questions: {total}")
    time.sleep(1)

    interview_start = time.perf_counter()

    for idx in range(total):
        q_num = idx + 1

        _log("AI", f"Generating best {WHITE}{current_level}{RESET} question...")

        question, reason = "", ""

        for _ in range(2):  # يحاول مرتين
            question, reason = ai_generate_question(current_level, history, results, topic)
            if question:
                break

        # منع التكرار
        while question in history:
            question, reason = ai_generate_question(current_level, history, results, topic)

        level = current_level
        history.append(question)

        _progress(q_num, total)
        if arrow:
            _log("ADAPT", arrow)

        _question_card(q_num, total, level, question)
        if "fallback" in reason.lower() or "random" in reason.lower():
            print(f"  {YELLOW}[FALLBACK]{RESET}")
        else:
            print(f"  {GREEN}[AI GENERATED]{RESET}")

        write_state("waiting", q_num, question, level, name, session_id, topic)
        speak(spk, f"Question {q_num}. {question}")

        time_limit = get_time_limit(level)
        speak(spk, f"You have {time_limit} seconds to answer.")
        write_state("recording", q_num, question, level, name, session_id, topic)

        answer, elapsed = get_answer(spk, question, q_num, level, time_limit,
                                     student_name=name, session_id=session_id, from_api=from_api)

        write_state("waiting", q_num, question, level, name, session_id, topic)

        current_level, arrow, adapted = get_next_level(current_level, elapsed)

        save_log(name, q_num, question, level, topic, answer, elapsed, adapted, reason)
        results.append({
            "q_num":   q_num,
            "level":   level,
            "elapsed": elapsed,
        })

        if elapsed > time_limit:
            speak(spk, f"Time is over. You took {round(elapsed)} seconds.")
            _log("TIMER", f"{RED}Over limit{RESET}  {elapsed:.1f}s")
        else:
            speak(spk, f"Answer recorded in {round(elapsed)} seconds.")
            _log("TIMER", f"{GREEN}In time{RESET}  {elapsed:.1f}s")

        if idx < total - 1:
            speak(spk, "Next question.")
            print(f"\n  {DIM}Please get ready...{RESET}")
            time.sleep(2)

    total_time = time.perf_counter() - interview_start
    write_state("done", q_num, "", "", name, session_id, topic)
    _banner("INTERVIEW FINISHED", "green")
    speak(spk, f"The interview is finished. Thank you {name} for your time.")
    print_summary(name, total_time, results)
    _log("INFO", f"Log saved to {WHITE}{LOG_FILE}{RESET}")

# ─── Entry Point ──────────────────────────────────────────
if __name__ == "__main__":
    run_interview()