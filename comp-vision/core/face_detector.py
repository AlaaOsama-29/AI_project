import cv2
from config import settings


class FaceDetector:
    def __init__(self):
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.cascade = cv2.CascadeClassifier(cascade_path)

        if self.cascade.empty():
            raise RuntimeError("Failed to load face detection model")

        print("Face detection model loaded")

    def detect(self, frame) -> list:
    
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)

        faces = self.cascade.detectMultiScale(
            gray,
            scaleFactor=settings.FACE_SCALE_FACTOR,
            minNeighbors=settings.FACE_MIN_NEIGHBORS,
            minSize=settings.FACE_MIN_SIZE,
        )

        return list(faces) if len(faces) > 0 else []
