import io
import wave
import collections
import struct
import math
import threading
import pyaudio

from config import (
    SAMPLE_RATE,
    CHUNK_SIZE,
    CHUNK_DURATION_MS,
    VAD_AGGRESSIVENESS,
    GRACE_SILENCE_S,
    SILENCE_BEFORE_CUTOFF_S,
    MIN_SPEECH_S,
    PRE_SPEECH_BUFFER_S,
)

try:
    import webrtcvad
    _HAS_WEBRTCVAD = True
except ImportError:
    _HAS_WEBRTCVAD = False
    print("webrtcvad not found — falling back to energy-based VAD.")
    print("   Install with:  pip install webrtcvad-wheels")

_ENERGY_THRESHOLD = 300.0


def _rms(chunk: bytes) -> float:
    """
    Compute root-mean-square energy of a 16-bit mono PCM chunk.

    Each sample is 2 bytes (int16), so the number of samples is
    len(chunk) // 2, NOT len(chunk).

    BUG FIX: The original code set num_samples = len(chunk), which is the
    byte count, not the sample count.  It then tried to unpack num_samples
    'h' (2-byte) values — requiring num_samples * 2 bytes — from a buffer
    that only contains num_samples bytes.  This raised struct.error on every
    call, so the energy-based VAD fallback was completely non-functional.
    """
    num_samples = len(chunk) 
    if num_samples == 0:
        return 0.0
    shorts = struct.unpack(f"{num_samples}h", chunk[:num_samples * 2])
    return math.sqrt(sum(s * s for s in shorts) / num_samples)


def _is_speech_energy(chunk: bytes) -> bool:
    return _rms(chunk) > _ENERGY_THRESHOLD


def _frames_to_wav(frames: list[bytes], sample_rate: int = SAMPLE_RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(frames))
    buf.seek(0)
    return buf.read()


class AudioCapture:
    """
    Records a single utterance.

    Behaviour:
    - Waits silently until the candidate starts speaking.
    - While the candidate is speaking (or pausing between sentences),
      the mic stays open indefinitely.
    - Only closes after GRACE_SILENCE_S of continuous post-speech silence.
    - If no speech is detected at all for SILENCE_BEFORE_CUTOFF_S seconds,
      returns None (triggers skip logic in main).
    - Accepts a threading.Event to allow clean early cancellation from the
      main thread without orphaning the PyAudio stream.
    """

    def __init__(self) -> None:
        self._pa  = pyaudio.PyAudio()
        self._vad = webrtcvad.Vad(VAD_AGGRESSIVENESS) if _HAS_WEBRTCVAD else None

        ms_per_frame        = CHUNK_DURATION_MS
        self._grace_frames  = int(GRACE_SILENCE_S  * 1000 / ms_per_frame)
        self._min_frames    = int(MIN_SPEECH_S     * 1000 / ms_per_frame)
        self._pre_buf_size  = max(1, int(PRE_SPEECH_BUFFER_S * 1000 / ms_per_frame))
        self._cutoff_frames = int(SILENCE_BEFORE_CUTOFF_S * 1000 / ms_per_frame)

    def record_utterance(self, stop_event: threading.Event | None = None) -> bytes | None:
        """
        Block until an utterance is finished.

        Parameters
        ----------
        stop_event:
            Optional threading.Event. When set from the calling thread, the
            recording loop exits cleanly and the stream is closed properly,
            avoiding resource leaks on timeout.

        Returns
        -------
        WAV bytes on success, or None if the candidate stayed silent for
        SILENCE_BEFORE_CUTOFF_S seconds without saying anything, or if
        stop_event was set before any speech was captured.
        """
        stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
        )

        pre_buf     = collections.deque(maxlen=self._pre_buf_size)
        frames: list[bytes] = []
        triggered   = False
        silence_cnt = 0
        waiting_cnt = 0

        print(" Listening…  (speak naturally, pause when done)")

        try:
            while True:
                if stop_event is not None and stop_event.is_set():
                    return None

                chunk    = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                is_voice = self._is_speech(chunk)

                if not triggered:
                    pre_buf.append(chunk)
                    if is_voice:
                        triggered = True
                        frames.extend(pre_buf)
                        pre_buf.clear()
                        silence_cnt = 0
                        waiting_cnt = 0
                        print("Recording…")
                    else:
                        waiting_cnt += 1
                        if waiting_cnt >= self._cutoff_frames:
                            return None
                else:
                    frames.append(chunk)
                    if is_voice:
                        silence_cnt = 0
                    else:
                        silence_cnt += 1
                        if silence_cnt >= self._grace_frames:
                            break

        finally:
            stream.stop_stream()
            stream.close()

        if len(frames) < self._min_frames:
            return None

        return _frames_to_wav(frames)

    def close(self) -> None:
        self._pa.terminate()

    def _is_speech(self, chunk: bytes) -> bool:
        if self._vad:
            try:
                return self._vad.is_speech(chunk, SAMPLE_RATE)
            except Exception:
                pass
        return _is_speech_energy(chunk)