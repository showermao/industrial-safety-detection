import base64
import threading
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np


class InspectionService:
    """Run YOLOv8 inference on a captured JPEG without coupling to Flask."""

    DEFECT_LABELS = {
        "scratch": "刮痕",
        "刮痕": "刮痕",
        "dent": "凹痕",
        "凹痕": "凹痕",
        "dirt": "髒污",
        "污漬": "髒污",
        "髒污": "髒污",
    }

    def __init__(self, model_path="best.pt", model_loader=None, confidence=0.25):
        self.model_path = Path(model_path) if model_path else None
        self.model_loader = model_loader or self._load_model
        self.confidence = confidence
        self._model = None
        self._load_error = None
        self._lock = threading.Lock()

    def inspect(self, jpeg_bytes):
        started = datetime.now().astimezone()
        frame = cv2.imdecode(np.frombuffer(jpeg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            return self._unable(started, "擷取影像格式無法辨識")

        try:
            model = self._get_model()
            results = model(frame, conf=self.confidence, verbose=False)
            detections = self._detections(results)
        except Exception:
            return self._unable(started, "YOLOv8 模型無法載入或推論失敗")

        annotated = self._annotate(frame, detections)
        ok, encoded = cv2.imencode(".jpg", annotated)
        if not ok:
            return self._unable(started, "結果影像無法產生")

        defects = [item for item in detections if item["label"] in self.DEFECT_LABELS.values()]
        status = "problem" if defects else "normal"
        description = "、".join(sorted({item["label"] for item in defects})) if defects else "未偵測到刮痕、凹痕或髒污"
        return {
            "status": status,
            "status_label": {"normal": "正常", "problem": "問題", "unrecognized": "無法辨識"}[status],
            "comparison_time": started.isoformat(timespec="seconds"),
            "problem_description": description,
            "detections": detections,
            "image": "data:image/jpeg;base64," + base64.b64encode(encoded.tobytes()).decode("ascii"),
        }

    def _get_model(self):
        with self._lock:
            if self._model is not None:
                return self._model
            if self._load_error:
                raise RuntimeError(self._load_error)
            self._model = self.model_loader(self.model_path)
            return self._model

    @staticmethod
    def _load_model(model_path):
        if not model_path or not model_path.is_file():
            raise FileNotFoundError(f"YOLO model not found: {model_path}")
        from ultralytics import YOLO

        return YOLO(str(model_path))

    def _detections(self, results):
        result = results[0]
        names = result.names if hasattr(result, "names") else {}
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return []
        detections = []
        for box in boxes:
            cls_id = int(box.cls[0])
            confidence = float(box.conf[0])
            name = names.get(cls_id, str(cls_id)) if isinstance(names, dict) else str(cls_id)
            coordinates = [round(float(value), 1) for value in box.xyxy[0].tolist()]
            detections.append({"label": self.DEFECT_LABELS.get(str(name).lower(), str(name)), "confidence": round(confidence, 3), "box": coordinates})
        return detections

    @staticmethod
    def _annotate(frame, detections):
        # The model result is intentionally rendered by the backend so the saved result
        # and the result shown in the browser are identical.
        for detection in detections:
            x1, y1, x2, y2 = map(int, detection["box"])
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 80, 255), 2)
            cv2.putText(frame, f"{detection['label']} {detection['confidence']:.0%}", (x1, max(24, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 80, 255), 2)
        return frame

    @staticmethod
    def _unable(started, description):
        return {
            "status": "unrecognized",
            "status_label": "無法辨識",
            "comparison_time": started.isoformat(timespec="seconds"),
            "problem_description": description,
            "detections": [],
            "image": None,
        }
