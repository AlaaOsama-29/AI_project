import time
from config import settings


class WarningState:
    def __init__(self):
        self.is_active     = False
        self._last_trigger = 0.0

    def activate(self):
  
        self.is_active     = True
        self._last_trigger = time.time()

    def try_deactivate(self):
       
        if self.is_active:
            elapsed = time.time() - self._last_trigger
            if elapsed >= settings.WARNING_DISPLAY_DURATION:
                self.is_active = False
