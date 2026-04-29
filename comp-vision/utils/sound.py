import time
import numpy as np
import pygame

from config import settings


class SoundManager:
    def __init__(self):
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)  # غيّرنا 1 لـ 2
        self._beep_sound = self._generate_beep()
        self._last_beep  = 0.0
        print("Sound initialized")

    def _generate_beep(self):
        sample_rate = 44100
        frames = int(settings.BEEP_DURATION * sample_rate)
        t      = np.linspace(0, settings.BEEP_DURATION, frames, False)
        wave   = (
                np.sin(2 * np.pi * settings.BEEP_FREQUENCY * t)
                * settings.BEEP_VOLUME
                * 32767
        ).astype(np.int16)
        wave_stereo = np.column_stack([wave, wave])  # السطر الجديد
        return pygame.sndarray.make_sound(wave_stereo)

    def can_beep(self) -> bool:
        return (time.time() - self._last_beep) >= settings.BEEP_COOLDOWN

    def beep(self):
        self._beep_sound.play()
        self._last_beep = time.time()

    def quit(self):
        pygame.mixer.quit()