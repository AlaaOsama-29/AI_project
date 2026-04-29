import json
import math
import re
import time

from groq import Groq

from config import GROQ_API_KEY, LLM_MODEL, REPORT_FILE, MAX_QUESTIONS, SKIP_MARKER

_MAX_API_RETRIES = 3
_RETRY_BACKOFF   = 1.5

_REASK_SIGNALS: tuple[str, ...] = (
    "i was asking about",
    "but i was asking",
    "could you give it another try",
    "i didn't quite catch that",
)

_EVALUATION_PROMPT = """\
You are a technical recruiter reviewing an interview transcript.
Produce an honest, specific evaluation. Every claim must reference something the candidate actually said.


TRANSCRIPT
{transcript}

─────────────────────────────────────────────
SCORING INSTRUCTIONS
─────────────────────────────────────────────
The interview had {total_questions} questions.
The candidate attempted {answered} genuine response(s) and skipped or failed {skipped}.

CRITICAL RULE — ANSWER-QUESTION PAIRING:
Match each Candidate turn ONLY to the Interviewer question immediately above it in the transcript.
A candidate answer must be evaluated against that specific question and no other.
Do NOT judge an answer based on a question that came before or after it.

A response counts as VALID only if it directly addresses the paired question with at least
2–3 relevant technical concepts or keywords:

  - On-topic with clear technical content = 1
  - Partially on-topic (missing key concepts) = 0.5 (round down in final score)
  - Off-topic, vague, or nonsensical = 0
  - Skipped / no response = 0

NOTE: Some candidate turns in the transcript are marked [REASK — not scored].
These are turns where the immediately following interviewer reply contained a re-ask signal,
meaning the answer was garbage or completely off-topic. Do NOT score these turns at all.
They are shown only for context.

SCORING STEPS — follow exactly:
1. List each Q&A pair: Q: <question> | A: <answer> | Score: <0 / 0.5 / 1> | Reason: <one line>
   Skip any pair where the answer is marked [REASK — not scored].
2. Sum scores → VALID_ANSWERS
3. overall_score = round(VALID_ANSWERS / {total_questions} * 10)

─────────────────────────────────────────────
SUB-SCORE ANCHORING RULE — MANDATORY
─────────────────────────────────────────────
The overall_score you computed above is the anchor for ALL sub-scores.
Sub-scores represent quality within the coverage the candidate actually provided.
They MUST obey these hard bounds:

  sub_score_floor = max(overall_score - 2, 0)
  sub_score_cap   = min(overall_score + 2, 10)

Every sub-score (Technical Knowledge, Problem-Solving & Reasoning, Communication Clarity)
MUST fall within [sub_score_floor, sub_score_cap]. No exceptions.

RATIONALE: A candidate who answered 2 out of 8 questions CANNOT score 5 or 6 on any
sub-dimension — unanswered questions are evidence of missing knowledge and must penalise
every category. The cap prevents the LLM from rewarding the quality of 2 answers while
ignoring that 6 questions went unanswered.

─────────────────────────────────────────────
OUTPUT FORMAT
─────────────────────────────────────────────
Respond ONLY with valid JSON. No markdown, no extra text, no code fences.

{{
  "overall_score": <0–10>,
  "overall_justification": "The candidate gave valid answers to X out of {total_questions} questions. <2 sentences: what they demonstrated and what they missed, based only on the transcript.>",
  "scores": {{
    "Technical Knowledge":         {{ "score": <must be within [sub_score_floor, sub_score_cap]>, "comment": "<What they knew and what they missed — cite specific answers. Explicitly mention unanswered topics.>" }},
    "Problem-Solving & Reasoning": {{ "score": <must be within [sub_score_floor, sub_score_cap]>, "comment": "<How they approached questions — note that unanswered questions count as zero problem-solving evidence.>" }},
    "Communication Clarity":       {{ "score": <must be within [sub_score_floor, sub_score_cap]>, "comment": "<Were explanations precise? Coverage is part of communication — staying silent on most questions is a communication failure.>" }}
  }},
  "strengths":    ["<observation grounded in a specific answer — must be concrete, not generic>"],
  "gaps":         ["<every skipped or failed topic + what to study>"]
}}
"""


class Evaluator:
    """Generate an evaluation report from the interview transcript."""

    def __init__(self) -> None:
        self._client = Groq(api_key=GROQ_API_KEY)

    def generate_report(self, transcript_turns: list[dict], questions_asked: int = 0) -> str:
        """
        Generate and save the evaluation report.

        Parameters
        ----------
        transcript_turns:
            Filtered list of user/assistant turns from AIInterviewer.get_transcript().
            System prompt turns are excluded by the caller.
        questions_asked:
            Number of questions asked (informational, used for coverage%).
        """
        transcript = self._build_transcript(transcript_turns)
        answered   = self._count_answered(transcript_turns)
        total      = MAX_QUESTIONS
        skipped    = total - answered

        prompt = _EVALUATION_PROMPT.format(
            transcript      = transcript,
            total_questions = total,
            answered        = answered,
            skipped         = skipped,
        )

        try:
            data = self._call_with_retry(prompt)

            # ── Post-processing: clamp sub-scores to the anchoring window ──────
            # Even if the LLM ignores the prompt instruction, we enforce the cap
            # in Python so it is mathematically impossible to get a sub-score of
            # 5/10 when the overall is 2/10.
            #
            # FIX: The LLM was producing sub-scores (5, 5, 6) that bore no
            # relation to an overall_score of 2. Root cause: the prompt evaluated
            # "quality of what was said" without penalising the 75% of questions
            # that went unanswered. The prompt now explains the required bounds,
            # and this code enforces them as a hard backstop.
            overall = data.get("overall_score", 0)
            if isinstance(overall, (int, float)):
                sub_floor = max(int(overall) - 2, 0)
                sub_cap   = min(int(math.ceil(overall)) + 2, 10)
                for key, info in data.get("scores", {}).items():
                    if isinstance(info, dict) and isinstance(info.get("score"), (int, float)):
                        clamped = max(sub_floor, min(sub_cap, int(info["score"])))
                        if clamped != info["score"]:
                            info["comment"] = (
                                f"[Score adjusted from {info['score']} to {clamped} "
                                f"to reflect coverage: {answered}/{total} questions answered.] "
                                + info.get("comment", "")
                            )
                            info["score"] = clamped

            valid_recs = {"Strong Hire", "Hire", "Consider", "No Hire"}
            if data.get("recommendation") not in valid_recs:
                score = data.get("overall_score", 0)
                if score >= 8:
                    data["recommendation"] = "Strong Hire"
                elif score >= 6:
                    data["recommendation"] = "Hire"
                elif score >= 4:
                    data["recommendation"] = "Consider"
                else:
                    data["recommendation"] = "No Hire"

            if not isinstance(data.get("overall_score"), (int, float)):
                data["overall_score"] = 0

        except Exception as exc:
            fallback = f"[Evaluation Error] Could not generate report: {exc}"
            self._save(fallback)
            return fallback

        report = self._format_report(data, answered=answered, total=total, skipped=skipped)
        self._save(report)
        return report

    def _call_with_retry(self, prompt: str) -> dict:
        """Call the Groq LLM with exponential-backoff retry and return parsed JSON."""
        last_exc: Exception | None = None

        for attempt in range(_MAX_API_RETRIES):
            try:
                resp = self._client.chat.completions.create(
                    messages    = [{"role": "user", "content": prompt}],
                    model       = LLM_MODEL,
                    temperature = 0.1,
                    max_tokens  = 1_200,
                )
                raw = resp.choices[0].message.content.strip()

                raw = re.sub(r"^```[a-z]*\n?", "", raw)
                raw = re.sub(r"\n?```$", "", raw).strip()

                match = re.search(r"\{.*\}", raw, re.DOTALL)
                if not match:
                    raise ValueError("No JSON object found in LLM response")

                return json.loads(match.group())

            except Exception as exc:
                last_exc = exc
                if attempt < _MAX_API_RETRIES - 1:
                    time.sleep(_RETRY_BACKOFF ** attempt)

        raise RuntimeError(f"LLM call failed after {_MAX_API_RETRIES} attempts: {last_exc}")

    def _format_report(self, d: dict, *, answered: int, total: int, skipped: int) -> str:
        coverage = round((answered / total) * 100)
        sep      = "─" * 56

        lines = [
            sep,
            "  TECHNICAL INTERVIEW — EVALUATION REPORT",
            sep,
            "",
            f"  Questions attempted : {answered} / {total}  ({skipped} skipped, {coverage}% coverage)",
            f"  Recommendation      : {d.get('recommendation')}",
            f"  Overall Score       : {d.get('overall_score')} / 10",
            "",
            f"  {d.get('overall_justification', '')}",
            "",
            sep,
            "",
        ]

        for label, info in d.get("scores", {}).items():
            lines.append(f"  {label}  —  {info.get('score')} / 10")
            lines.append(f"  {info.get('comment', '')}")
            lines.append("")

        lines += [sep, "", "  STRENGTHS"]
        for s in d.get("strengths", []):
            lines.append(f"  • {s}")

        lines += ["", "  GAPS TO ADDRESS"]
        for s in d.get("gaps", []):
            lines.append(f"  • {s}")

        lines += ["", sep]
        return "\n".join(lines)

    def _save(self, text: str) -> None:
        try:
            with open(REPORT_FILE, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception:
            pass

    @staticmethod
    def _build_transcript(turns: list[dict]) -> str:
        """
        Build a readable transcript string from user/assistant turns.

        Garbage/off-topic user turns (those immediately followed by an assistant
        re-ask) are labelled [REASK — not scored] so the evaluation LLM knows
        to exclude them from scoring.
        """
        lines = []
        turns_list = [t for t in turns if t.get("role") != "system"]

        for i, msg in enumerate(turns_list):
            role    = msg.get("role", "")
            content = msg.get("content", "").strip()

            if role == "assistant":
                lines.append(f"Interviewer: {content}")
            elif role == "user":
                next_assistant = next(
                    (t for t in turns_list[i + 1:] if t.get("role") == "assistant"),
                    None,
                )
                is_reask_trigger = (
                    next_assistant is not None
                    and any(
                        sig in next_assistant.get("content", "").lower()
                        for sig in _REASK_SIGNALS
                    )
                )
                if is_reask_trigger:
                    lines.append(f"Candidate: [REASK — not scored] {content}")
                else:
                    lines.append(f"Candidate: {content}")

        return "\n\n".join(lines)

    @staticmethod
    def _count_answered(turns: list[dict]) -> int:
        """
        Count how many candidate turns were genuine answers.

        A turn is NOT counted if:
          (a) its content equals SKIP_MARKER (explicit skip), OR
          (b) the immediately following assistant turn contains a re-ask signal,
              meaning the answer was garbage or off-topic.
        """
        turns_list = [t for t in turns if t.get("role") != "system"]

        count = 0
        for i, msg in enumerate(turns_list):
            if msg.get("role") != "user":
                continue

            content = msg.get("content", "").strip()

            if content == SKIP_MARKER:
                continue

            next_assistant = next(
                (t for t in turns_list[i + 1:] if t.get("role") == "assistant"),
                None,
            )
            if next_assistant is not None and any(
                sig in next_assistant.get("content", "").lower()
                for sig in _REASK_SIGNALS
            ):
                continue

            count += 1

        return count