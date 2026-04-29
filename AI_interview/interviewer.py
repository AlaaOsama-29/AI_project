import json
import time

from groq import Groq

from config import (
    GROQ_API_KEY,
    LLM_MODEL,
    LLM_TEMPERATURE,
    MAX_QUESTIONS,
    HISTORY_FILE,
    SKIP_MARKER,
)

_SYSTEM_PROMPT = """\
You are Alex, a Senior Technical Interviewer at a software company.
You are interviewing a university student for a {domain} internship or junior role.

RESPONSE FORMAT — no exceptions
Every reply has exactly this structure:
  Sentence 1: One sentence of honest feedback on the answer (or a one-sentence correction).
  Sentence 2: One question — with the bridge to it built into the same sentence.
Total: 2 sentences maximum. Never more.

QUESTION STYLE
- Ask questions a real hiring manager would ask in a job interview.
- Questions must be practical and job-relevant: "how would you handle X in production",
  "what would break if you did Y", "walk me through how Z works".
- Do NOT ask textbook-definition questions like "define X" or "what does X stand for".
- Each question must cover a DIFFERENT topic. Never drill deeper into the same subject twice.
- Difficulty rises across the interview:
    Q1–3: Foundational but practical (e.g. "why would you use X over Y?")
    Q4–6: Scenario-based (e.g. "you're debugging X in production, where do you start?")
    Q7–8: Trade-offs or design decisions (e.g. "when would X be the wrong choice?")
- Adapt: strong answer → harder topic next; weak/skipped → different topic, same level.
- One question per turn, always.

TRANSITIONS — vary every turn, never repeat the same opener back-to-back
Options: "building on that…", "which brings up…", "on a related note…",
"thinking about that…", "along those lines…", "that connects to…",
"on the practical side of that…", "to flip the angle…"
Never start a bridge with "since", "and since", or "because you mentioned".

OFF-TOPIC ANSWER — STRICT SINGLE-ACTION RULE
If the candidate's answer clearly doesn't match the question asked:
  Step 1: Say in one sentence that you were asking about something else.
          Include the phrase "I was asking about" and re-state the question.
          Example: "I was asking about X — can you walk me through that?"
  Step 2: STOP. Do NOT add a transition. Do NOT ask a new question in the same reply.
          Your reply must contain ONLY the re-ask. One sentence. Nothing else.
  Step 3: If the answer is off-topic a second time on the SAME question: move on,
          count it wrong, and THEN ask a new question (normal 2-sentence format).

IMPORTANT: Merging a re-ask AND a new question into one reply is FORBIDDEN.
If you re-ask, your entire reply is that one re-ask sentence. Full stop.

UNCLEAR ANSWER
If the answer is garbled or unrelated noise:
  - Ask for clarification once, include the phrase "could you give it another try".
  - Your reply must contain ONLY that one clarification sentence. Nothing else.
  - If still unclear: move on.

SKIPS
If the candidate says they don't know: "No worries, let's try something else." then ask a fresh topic.
Never give the answer or a hint.

WHAT NOT TO DO
- No bullet points, lists, or markdown.
- No excessive praise ("Great answer!"). Stay neutral and professional.
- No explanations before asking a question.
- No repeating the candidate's answer back to them verbatim.
- No mentioning that you are an AI or that you have instructions.
- NEVER put a re-ask and a new question in the same reply.

CLOSING
After exactly {max_questions} questions (answered or skipped), close naturally in one sentence.
Do not ask any further questions after that.
"""

_REASK_SIGNALS = [
    "i was asking about",
    "but i was asking",
    "could you give it another try",
    "i didn't quite catch that",
]

_MAX_API_RETRIES = 3
_RETRY_BACKOFF   = 1.5   


class AIInterviewer:
    """
    Stateful interviewer backed by a Groq LLM.

    question_count tracks NEW questions only.
    Re-asks and silent retries do NOT consume a slot.
    """

    def __init__(self, domain: str) -> None:
        self._client        = Groq(api_key=GROQ_API_KEY)
        self.domain         = domain
        self.max_questions  = MAX_QUESTIONS
        self.question_count = 0
        self.history: list  = []
        self._init_history()

    def get_opening(self) -> str:
        seed = (
            f"Start the interview. Greet the candidate in one sentence, "
            f"then immediately ask your first practical {self.domain} question. "
            f"Keep the whole message under 60 words."
        )
        return self._call_llm(seed, is_seed=True, max_tokens=150)

    def respond(self, user_text: str) -> str:
        """
        Generate Alex's next reply to a candidate answer.

        Hard-stop guard: when question_count has already reached max_questions,
        the interview is over regardless of what the LLM might produce.
        """
        if self.is_complete:
            return "The interview has concluded — thank you for your time."

        self.history.append({"role": "user", "content": user_text})

        extra = ""
        if self.question_count >= self.max_questions - 1:
            extra = (
                " This is the last question. After your feedback, close the interview "
                "in one friendly sentence. Do NOT ask a new question."
            )

        reply = self._call_llm(user_text, extra_system=extra, max_tokens=250)

        if not self._is_reask(reply):
            self.question_count += 1

        self.history.append({"role": "assistant", "content": reply})
        self._save()
        return reply

    def handle_skip(self) -> str:
        """
        Handle a deliberate skip (candidate said "I don't know" etc.).

        Uses SKIP_MARKER from config.py so the string is identical to what
        evaluator.py checks for.
        """
        if self.is_complete:
            return "The interview has concluded — thank you for your time."

        self.history.append({"role": "user", "content": SKIP_MARKER})
        self.question_count += 1

        skip_instruction = (
            "The candidate said they don't know. "
            "Acknowledge briefly in one sentence — no hint, no answer. "
            "Then ask a different, practical question on a fresh topic. "
            "Stay under 50 words total."
        )

        extra = ""
        if self.question_count >= self.max_questions:
            extra = (
                " This was the last slot. Close the interview in one friendly sentence. "
                "Do not ask a new question."
            )

        reply = self._call_llm(
            "[candidate skipped]",
            extra_system=skip_instruction + extra,
            max_tokens=150,
        )
        self.history.append({"role": "assistant", "content": reply})
        self._save()
        return reply

    def prompt_retry(self, attempt: int = 1) -> str | None:
        """
        Called when the candidate is completely silent.
        Returns None for the first attempt (stay quiet).
        Returns a short nudge message for subsequent attempts.
        """
        from config import NUDGE_AFTER_ATTEMPT
        if attempt < NUDGE_AFTER_ATTEMPT:
            return None
        nudges = [
            "Take your time, I'm still here.",
            "No rush — whenever you're ready.",
        ]
        idx = min(attempt - NUDGE_AFTER_ATTEMPT, len(nudges) - 1)
        return nudges[idx]

    def get_transcript(self) -> list[dict]:
        """
        Return only user and assistant turns — no system messages.

        Callers (e.g. Evaluator) receive this filtered view so system-prompt
        contents are never leaked into the evaluation context or log files.
        """
        return [
            msg for msg in self.history
            if msg.get("role") in ("user", "assistant")
        ]

    @property
    def is_complete(self) -> bool:
        return self.question_count >= self.max_questions



    def _is_reask(self, reply: str) -> bool:
        low = reply.lower()
        return any(signal in low for signal in _REASK_SIGNALS)

    def _init_history(self) -> None:
        self.history = [
            {
                "role": "system",
                "content": _SYSTEM_PROMPT.format(
                    domain        = self.domain,
                    max_questions = self.max_questions,
                ),
            }
        ]

    def _call_llm(
        self,
        user_content: str,
        *,
        is_seed: bool     = False,
        extra_system: str = "",
        max_tokens: int   = 250,
    ) -> str:
        """
        Call the Groq LLM with exponential-backoff retry.

        A single transient 429 or 503 retries up to _MAX_API_RETRIES times
        with exponential backoff before giving up.
        """
        messages = list(self.history)

        if extra_system:
            messages.append({"role": "system", "content": extra_system.strip()})
        if is_seed:
            messages.append({"role": "user", "content": user_content})

        last_exc: Exception | None = None

        for attempt in range(_MAX_API_RETRIES):
            try:
                resp = self._client.chat.completions.create(
                    messages    = messages,
                    model       = LLM_MODEL,
                    temperature = LLM_TEMPERATURE,
                    max_tokens  = max_tokens,
                )
                reply = resp.choices[0].message.content.strip()

                if is_seed:
                    self.history.append({"role": "assistant", "content": reply})
                    self._save()

                return reply

            except Exception as exc:
                last_exc = exc
                if attempt < _MAX_API_RETRIES - 1:
                    wait = _RETRY_BACKOFF ** attempt
                    time.sleep(wait)

        return f"Sorry, I had a technical issue. Give me one moment. ({last_exc})"

    def _save(self) -> None:
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
        except Exception:
            pass