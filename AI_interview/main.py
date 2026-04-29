import signal
import sys
import threading

from audio_capture import AudioCapture
from evaluator import Evaluator
from interviewer import AIInterviewer
from stt import SpeechToText

from config import (
    REPORT_FILE,
    RESPONSE_TIMEOUT_S,
    MAX_SILENT_RETRIES,
    SILENCE_BEFORE_CUTOFF_S,
    END_PHRASES,
    UNKNOWN_PHRASES,
)


def _contains(text: str, phrases: frozenset[str]) -> bool:
    low = text.lower().strip()
    return any(p in low for p in phrases)


def _print_speaker(speaker: str, text: str) -> None:
    print(f"\n {speaker}: {text}\n")


class InterviewSession:
    """Orchestrates the full interview lifecycle."""

    def __init__(self) -> None:
        print("\n" + "═" * 56)
        print("  AI TECHNICAL INTERVIEWER")
        print("═" * 56)
        print("\n Initialising…")

        self._audio       = AudioCapture()
        self._stt: SpeechToText | None         = None
        self._evaluator   = Evaluator()
        self._interviewer: AIInterviewer | None = None
        self._running     = True

        self._stop_event  = threading.Event()

        signal.signal(signal.SIGINT, self._on_interrupt)
        print(" Ready.\n")


    def run(self) -> None:
        domain = self._get_domain()
        self._print_tips()

        self._interviewer = AIInterviewer(domain)
        self._stt         = SpeechToText(domain=domain)

        print(" Generating opening…")
        opening = self._interviewer.get_opening()
        _print_speaker("Alex", opening)

        silent_retries = 0

        while self._running and not self._interviewer.is_complete:
            user_text = self._listen_with_timeout()

            if not user_text:
                silent_retries += 1

                if silent_retries < MAX_SILENT_RETRIES:
                    nudge = self._interviewer.prompt_retry(attempt=silent_retries)
                    if nudge:
                        _print_speaker("Alex", nudge)
                else:
                    _print_speaker(
                        "Alex",
                        "Seems like you might be having trouble with that one — "
                        "let's try something different.",
                    )
                    reply = self._interviewer.handle_skip()
                    _print_speaker("Alex", reply)
                    silent_retries = 0
                continue

            silent_retries = 0

            if _contains(user_text, END_PHRASES):
                self._running = False
                _print_speaker(
                    "Alex",
                    "Alright, let's wrap up here — it was great speaking with you. "
                    "Give me a moment to put together your evaluation.",
                )
                break

            if _contains(user_text, UNKNOWN_PHRASES):
                reply = self._interviewer.handle_skip()
            else:
                reply = self._interviewer.respond(user_text)

            _print_speaker("Alex", reply)

        if self._interviewer and self._interviewer.question_count > 0:
            self._generate_report()

        self._cleanup()


    def _listen_with_timeout(self) -> str | None:
        result_holder: list[str | None]       = [None]
        error_holder:  list[Exception | None] = [None]

        self._stop_event.clear()

        def _record() -> None:
            try:
                wav = self._audio.record_utterance(stop_event=self._stop_event)
                if wav:
                    print(" Transcribing…")
                    text = self._stt.transcribe(wav)
                    if text:
                        print(f" You: {text}")
                    result_holder[0] = text
            except Exception as exc:
                error_holder[0] = exc

        thread = threading.Thread(target=_record, daemon=True)
        thread.start()
        thread.join(timeout=RESPONSE_TIMEOUT_S)

        if thread.is_alive():
            self._stop_event.set()
            thread.join(timeout=2.0)
            print(f"\n [No response within {RESPONSE_TIMEOUT_S}s]")
            return None

        if error_holder[0]:
            print(f" [Listen Error] {error_holder[0]}")
            return None

        return result_holder[0]


    def _generate_report(self) -> None:
        print("\n" + "═" * 56)
        print("  GENERATING EVALUATION REPORT…")
        print("═" * 56 + "\n")

 
        report = self._evaluator.generate_report(
            self._interviewer.get_transcript(),
            questions_asked=self._interviewer.question_count,
        )

        print("\n" + "═" * 56)
        print("           FINAL EVALUATION REPORT")
        print("═" * 56)
        print(report)
        print("═" * 56)
        print(f"\n  Saved → {REPORT_FILE}\n")


    def _get_domain(self) -> str:
        domains = (
            "Backend", "Frontend", "Full-Stack", "Data Science",
            "Machine Learning", "DevOps", "Network", "Mobile",
        )
        print(" Available roles: " + " | ".join(domains))
        domain = ""
        while not domain.strip():
            domain = input(" Enter the job role: ").strip().lower()
        return domain

    def _print_tips(self) -> None:
        print("\n" + "─" * 56)
        print("   Tips:")
        print("   • Speak naturally — mic stays open until you pause")
        print(f"   • After {int(SILENCE_BEFORE_CUTOFF_S)}s of complete silence → question is skipped")
        print("   • Say 'I don't know' to skip to the next question")
        print("   • Say 'end interview' to finish early")
        print("   • Press Ctrl+C to force quit")
        print("─" * 56 + "\n")


    def _cleanup(self) -> None:
        self._stop_event.set()  
        try:
            self._audio.close()
        except Exception:
            pass

    def _on_interrupt(self, _sig: int, _frame: object) -> None:
        print("\n\n [Interrupted — generating partial report…]")
        self._running = False
        self._stop_event.set()
        if self._interviewer and self._interviewer.question_count > 0:
            self._generate_report()
        self._cleanup()
        sys.exit(0)


def main() -> None:
    session = InterviewSession()
    session.run()


if __name__ == "__main__":
    main()