import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    raise EnvironmentError(
        "GROQ_API_KEY is not set. "
        "Add it to your .env file or export it as an environment variable."
    )

SAMPLE_RATE         = 16_000
CHANNELS            = 1
CHUNK_DURATION_MS   = 20
CHUNK_SIZE          = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)

VAD_AGGRESSIVENESS  = 1     
PRE_SPEECH_BUFFER_S = 0.4  
MIN_SPEECH_S        = 0.3   

SILENCE_BEFORE_CUTOFF_S = 60.0   
GRACE_SILENCE_S         = 3.5   

MAX_QUESTIONS       = 8
RESPONSE_TIMEOUT_S  = 120
MAX_SILENT_RETRIES  = 4
NUDGE_AFTER_ATTEMPT = 2

STT_MODEL           = "whisper-large-v3-turbo"
LLM_MODEL           = "llama-3.3-70b-versatile"
LLM_TEMPERATURE     = 0.70

HISTORY_FILE        = "session_history.json"
REPORT_FILE         = "interview_report.txt"


SKIP_MARKER = "I'm not sure about that one."

UNKNOWN_PHRASES: frozenset[str] = frozenset({
    "i don't know", "i dont know", "i do not know",
    "no idea", "not sure", "i have no idea",
    "i can't answer", "i cannot answer", "i'm not sure",
    "skip", "pass", "next question", "i'm unsure",
})

END_PHRASES: frozenset[str] = frozenset({
    "end interview", "stop interview", "end the interview",
    "quit", "exit", "goodbye", "that's all", "i'm done",
    "finish the interview", "stop it", "please stop",
    "leave this interview", "leave the interview",
    "end this interview", "stop this interview",
    "finish this interview", "close the interview",
    "wrap up the interview", "wrap this up",
})