import atexit
import os

from flask import Flask

from app.controllers.api import api_bp
from app.controllers.web import web_bp
from app.services.camera_service import CameraManager
from app.services.inspection_service import InspectionService
from app.extensions import init_db


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object("app.config.Config")

    if test_config:
        app.config.from_mapping(test_config)

    app.extensions["camera_manager"] = CameraManager(
        device_index=app.config["CAMERA_DEVICE_INDEX"],
        width=app.config["CAMERA_WIDTH"],
        height=app.config["CAMERA_HEIGHT"],
        fps=app.config["CAMERA_FPS"],
        capture_factory=app.config.get("CAMERA_CAPTURE_FACTORY"),
        frame_encoder=app.config.get("CAMERA_FRAME_ENCODER"),
    )
    app.extensions["inspection_service"] = InspectionService(
        model_path=app.config["YOLO_MODEL_PATH"],
        confidence=app.config["YOLO_CONFIDENCE"],
    )
    atexit.register(app.extensions["camera_manager"].stop, force=True)

    os.makedirs(os.path.dirname(app.config["DATABASE_PATH"]), exist_ok=True)
    init_db(app)

    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp, url_prefix="/api/v1")

    return app
