import time

class InterviewTimer:
    def __init__(self):
        self._start_time = time.time()

    def elapsed(self) -> float:
        return time.time() - self._start_time

    def formatted(self) -> str:
      
        total   = int(self.elapsed())
        hours   = total // 3600
        minutes = (total % 3600) // 60
        seconds = total % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def reset(self):
        self._start_time = time.time()
