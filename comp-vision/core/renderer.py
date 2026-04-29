import cv2
from config import settings


class Renderer:

    def draw_timer(self, frame, time_str: str):
        h_frame, w_frame = frame.shape[:2]
        font      = cv2.FONT_HERSHEY_DUPLEX
        scale     = 1.1
        thickness = 2
        padding   = 14

        (tw, th), baseline = cv2.getTextSize(time_str, font, scale, thickness)
        box_x1 = (w_frame - tw) // 2 - padding
        box_y1 = 10
        box_x2 = (w_frame + tw) // 2 + padding
        box_y2 = 10 + th + baseline + padding * 2

        overlay = frame.copy()
        cv2.rectangle(overlay, (box_x1, box_y1), (box_x2, box_y2), (15, 15, 15), -1)
        cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)

        cv2.rectangle(frame, (box_x1, box_y1), (box_x2, box_y2), (80, 80, 80), 1)

        tx = (w_frame - tw) // 2
        ty = box_y2 - padding - baseline
        cv2.putText(frame, time_str, (tx + 2, ty + 2), font, scale, (0, 0, 0),       thickness + 1)  # shadow
        cv2.putText(frame, time_str, (tx,     ty),     font, scale, (0, 220, 180),    thickness)      # text

    def draw_faces(self, frame, faces: list, warning_active: bool):
        num = len(faces)
        for i, (x, y, w, h) in enumerate(faces):
            color = settings.COLOR_OK if num == 1 else settings.COLOR_WARNING
            label = "Interviewee" if num == 1 else f"Person {i + 1}"

            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            cv2.putText(
                frame, label, (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2,
            )

    def draw_warning_overlay(self, frame):
        overlay = frame.copy()
        h, w = frame.shape[:2]
        cv2.rectangle(overlay, (0, 0), (w, h), settings.COLOR_OVERLAY, -1)
        cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)

        text = "WARNING: Multiple Persons Detected!"
        font = cv2.FONT_HERSHEY_DUPLEX
        scale, thickness = 1.0, 2
        (tw, _), _ = cv2.getTextSize(text, font, scale, thickness)
        tx = (w - tw) // 2

        cv2.putText(frame, text, (tx + 2, 62), font, scale, (0, 0, 0),   thickness + 1)  # shadow
        cv2.putText(frame, text, (tx,     60), font, scale, (0, 0, 255), thickness)       # text

    def draw_status_bar(self, frame, num_faces: int):
        h, w = frame.shape[:2]

        if num_faces == 0:
            color, msg = settings.COLOR_ABSENT, "No face detected"
        elif num_faces == 1:
            color, msg = settings.COLOR_OK, "Status: OK - 1 person"
        else:
            color, msg = settings.COLOR_WARNING, f"ALERT: {num_faces} persons!"

        cv2.rectangle(frame, (0, h - 40), (w, h), (20, 20, 20), -1)
        cv2.putText(
            frame, msg, (15, h - 12),
            cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2,
        )

        count_text = f"Faces: {num_faces}"
        (cw, _), _ = cv2.getTextSize(count_text, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)
        cv2.putText(
            frame, count_text, (w - cw - 15, h - 12),
            cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2,
        )
