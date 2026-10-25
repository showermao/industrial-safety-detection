import os


_external_model = r"D:\AI_Copper_Project\best.pt"
_local_model = os.path.join(os.path.dirname(os.path.dirname(__file__)), "best.pt")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
    DATABASE_PATH = os.environ.get(
        "DATABASE_PATH",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "instance", "monitoring.db"),
    )
    CAMERA_DEVICE_INDEX = int(os.environ.get("CAMERA_DEVICE_INDEX", "0"))
    CAMERA_WIDTH = int(os.environ.get("CAMERA_WIDTH", "640"))
    CAMERA_HEIGHT = int(os.environ.get("CAMERA_HEIGHT", "480"))
    CAMERA_FPS = int(os.environ.get("CAMERA_FPS", "15"))
    YOLO_MODEL_PATH = os.environ.get(
        "YOLO_MODEL_PATH",
        _external_model if os.path.isfile(_external_model) else _local_model,
    )
    YOLO_CONFIDENCE = float(os.environ.get("YOLO_CONFIDENCE", "0.25"))
    IMAGE_UPLOAD_MAX_BYTES = int(os.environ.get("IMAGE_UPLOAD_MAX_BYTES", str(10 * 1024 * 1024)))
    TESTING = False
