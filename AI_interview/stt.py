import io
import re

from groq import Groq

from config import GROQ_API_KEY, STT_MODEL

_HALLUCINATIONS = {
    "thank you", "thanks for watching", "you", ".",
    "bye", "goodbye", "nhātologic", "nh", "um",
    "subscribe", "like and subscribe", "see you next time",
    "i", "the", "a", "and", "ok", "okay",
}


_HALLUCINATION_PATTERNS = [
    re.compile(r"[^\x00-\x7F\u00C0-\u024F\u1E00-\u1EFF]"),
    re.compile(r"\b(facultad|inkamaaaal|адиcumi|misontion|instructor and director)\b", re.IGNORECASE),
    re.compile(r"(.)\1{4,}"),
    re.compile(r"\b(transcription by|translated by|subtitles by|amara\.org)\b", re.IGNORECASE),
    re.compile(r"\binformation depending\b", re.IGNORECASE),
    re.compile(r"\bdepending on the evidence\b", re.IGNORECASE),
    re.compile(r"\bto refuse you\b", re.IGNORECASE),
]

_DOMAIN_PROMPTS: dict[str, str] = {
    "network": (
        "Technical IT interview. Terms: TCP, UDP, IP, DNS, DHCP, OSI, NAT, "
        "firewall, router, switch, hub, VLAN, subnet, gateway, latency, "
        "bandwidth, half-duplex, full-duplex, MAC address, ARP, ICMP, VPN, SSL, TLS."
    ),
    "backend": (
        "Technical interview. Terms: REST, API, HTTP, HTTPS, JSON, SQL, NoSQL, "
        "database, authentication, authorization, caching, Redis, microservices, "
        "Docker, Kubernetes, scalability, concurrency, async, ORM, index, query optimization."
    ),
    "frontend": (
        "Technical interview. Terms: HTML, CSS, JavaScript, React, Vue, DOM, API, "
        "fetch, async, JSON, responsive design, accessibility, TypeScript, Webpack, "
        "Vite, component, state, props, hooks, CSS flexbox, grid."
    ),
    "full-stack": (
        "Technical interview. Terms: REST, API, React, Node.js, database, SQL, "
        "authentication, JWT, HTTP, Docker, deployment, CI/CD, scalability, caching, microservices."
    ),
    "data science": (
        "Technical interview. Terms: Python, pandas, NumPy, machine learning, "
        "regression, classification, neural network, feature engineering, "
        "cross-validation, overfitting, precision, recall, F1 score, data pipeline."
    ),
    "machine learning": (
        "Technical interview. Terms: neural network, gradient descent, backpropagation, "
        "overfitting, regularization, CNN, RNN, transformer, PyTorch, TensorFlow, "
        "training, validation, loss function, hyperparameter, embedding."
    ),
    "devops": (
        "Technical interview. Terms: Docker, Kubernetes, CI/CD, Jenkins, GitHub Actions, "
        "infrastructure as code, Terraform, Ansible, monitoring, logging, Prometheus, "
        "Grafana, load balancer, auto-scaling, blue-green deployment."
    ),
    "mobile": (
        "Technical interview. Terms: iOS, Android, Swift, Kotlin, React Native, Flutter, "
        "lifecycle, activity, fragment, state management, API, JSON, push notifications, "
        "app store, performance, memory management."
    ),
}

_DEFAULT_PROMPT = (
    "Technical job interview. Expect precise technical terminology and industry-standard concepts."
)


class SpeechToText:
    def __init__(self, domain: str = "") -> None:
        self._client = Groq(api_key=GROQ_API_KEY)
        self._prompt = _DOMAIN_PROMPTS.get(domain.lower().strip(), _DEFAULT_PROMPT)

    def transcribe(self, wav_bytes: bytes) -> str | None:
        if len(wav_bytes) < 8_000:
            return None

        try:
            audio_file      = io.BytesIO(wav_bytes)
            audio_file.name = "utterance.wav"

            prompt = "The candidate says: " + self._prompt

            result = self._client.audio.transcriptions.create(
                file            = audio_file,
                model           = STT_MODEL,
                language        = "en",
                response_format = "text",
                temperature     = 0.0,
                prompt          = prompt,
            )

            text = (result or "").strip().lower()

            if not text:
                return None
            if text.strip(".?,! ") in _HALLUCINATIONS:
                return None
            if len(text.split()) < 2:
                return None
            if any(p.search(text) for p in _HALLUCINATION_PATTERNS):
                return None

            return text

        except Exception as exc:
            print(f"[STT Error] {exc}")
            return None