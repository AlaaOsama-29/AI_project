import sys
import cv2

from config import settings
from core.face_detector import FaceDetector
from core.renderer import Renderer
from utils.sound import SoundManager
from utils.warning_state import WarningState
from utils.timer import InterviewTimer


class InterviewMonitor:
    def __init__(self):
        self.detector = FaceDetector()
        self.renderer = Renderer()
        self.sound    = SoundManager()
        self.warning  = WarningState()
        self.timer    = InterviewTimer()
        self.cap      = self._open_camera()

    def _open_camera(self):
        cap = cv2.VideoCapture(settings.CAMERA_INDEX)
        if not cap.isOpened():
            print("Could not open camera!")
            sys.exit(1)

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings.CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.CAMERA_HEIGHT)
        print("Camera ready")
        return cap

    def run(self):
        print("Monitoring started - press 'q' to quit\n")

        while True:
            ret, frame = self.cap.read()
            if not ret:
                print("Error reading from camera")
                break

            frame     = cv2.flip(frame, 1)       
            faces     = self.detector.detect(frame)
            num_faces = len(faces)

            if num_faces > 1:
                self.warning.activate()
                if self.sound.can_beep():
                    self.sound.beep()
            else:
                self.warning.try_deactivate()

            self.renderer.draw_faces(frame, faces, self.warning.is_active)

            if self.warning.is_active:
                self.renderer.draw_warning_overlay(frame)

            self.renderer.draw_timer(frame, self.timer.formatted())
            self.renderer.draw_status_bar(frame, num_faces)

            cv2.imshow("Interview Monitor", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        self._cleanup()

    def _cleanup(self):
        self.cap.release()
        cv2.destroyAllWindows()
        self.sound.quit()
        print("\n Closed successfully")
