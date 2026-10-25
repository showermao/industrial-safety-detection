import re

from flask import Blueprint, Response, current_app, jsonify, request, session

from app.controllers.camera_access import camera_access
from app.services.camera_service import CameraError
from app.repositories.inspection_repository import InspectionRepository

api_bp = Blueprint("api", __name__)


@api_bp.route("/health", methods=["GET"])
def health_check():
    return jsonify({"success": True, "status": "ok"})


@api_bp.route("/overview", methods=["GET"])
def overview():
    return jsonify(
        {
            "success": True,
            "data": {
                "brand": "台南大學實驗室監控系統",
                "areas": [
                    {"name": "實驗室 A", "status": "normal"},
                    {"name": "實驗室 B", "status": "attention"},
                    {"name": "實驗室 C", "status": "warning"},
                ],
            },
        }
    )


@api_bp.route("/video/start", methods=["POST"])
@camera_access(api=True, csrf=True)
def start_video():
    viewer_id = _viewer_id_from_body()
    if viewer_id is None:
        return _camera_error("invalid_viewer", "觀看者識別碼無效。", 400)
    try:
        status = current_app.extensions["camera_manager"].start(viewer_id=viewer_id)
    except CameraError as error:
        return _camera_error(*_camera_error_details(error.code))
    return jsonify({"success": True, "data": status})


@api_bp.route("/video/stop", methods=["POST"])
@camera_access(api=True, csrf=True)
def stop_video():
    viewer_id = _viewer_id_from_body()
    if viewer_id is None:
        return _camera_error("invalid_viewer", "觀看者識別碼無效。", 400)
    try:
        status = current_app.extensions["camera_manager"].stop(viewer_id=viewer_id)
    except CameraError as error:
        return _camera_error(*_camera_error_details(error.code))
    return jsonify({"success": True, "data": status})


@api_bp.route("/video/force-stop", methods=["POST"])
@camera_access(api=True, csrf=True)
def force_stop_video():
    status = current_app.extensions["camera_manager"].stop(force=True)
    return jsonify({"success": True, "data": status})


@api_bp.route("/video/status", methods=["GET"])
@camera_access(api=True)
def video_status():
    status = current_app.extensions["camera_manager"].status()
    return jsonify({"success": True, "data": status})


@api_bp.route("/video/capture", methods=["POST"])
@camera_access(api=True, csrf=True)
def capture_video():
    viewer_id = _viewer_id_from_body()
    manager = current_app.extensions["camera_manager"]
    if viewer_id is None:
        return _camera_error("invalid_viewer", "無效的影像檢視器識別碼", 400)
    if not manager.owns_active_viewer(viewer_id):
        return _camera_error("camera_not_streaming", "請先啟動即時影像", 409)
    frame = manager.latest_frame
    if not frame:
        return _camera_error("frame_not_ready", "目前尚未取得影像", 409)
    result = current_app.extensions["inspection_service"].inspect(frame)
    body = request.get_json(silent=True) or {}
    if body.get("save", False):
        result["record_id"] = InspectionRepository(current_app.config["DATABASE_PATH"]).create(
            result, actor_id=session.get("user_id"), source="auto"
        )
    return jsonify({"success": True, "data": result})


@api_bp.route("/video/records", methods=["POST"])
@camera_access(api=True, csrf=True)
def record_video_inspection():
    body = request.get_json(silent=True)
    viewer_id = body.get("viewer_id") if isinstance(body, dict) else None
    result = body.get("result") if isinstance(body, dict) else None
    if not _is_valid_viewer_id(viewer_id) or not isinstance(result, dict):
        return _camera_error("invalid_record", "無效的檢測紀錄", 400)
    if not current_app.extensions["camera_manager"].owns_active_viewer(viewer_id):
        return _camera_error("camera_not_streaming", "請先啟動即時影像", 409)
    required = {"status", "comparison_time", "problem_description"}
    if not required.issubset(result) or result["status"] not in {"normal", "problem", "unrecognized"}:
        return _camera_error("invalid_record", "檢測結果欄位不完整", 422)
    record_id = InspectionRepository(current_app.config["DATABASE_PATH"]).create(result, actor_id=session.get("user_id"), source="manual")
    return jsonify({"success": True, "data": {"record_id": record_id}}), 201


@api_bp.route("/video/stream", methods=["GET"])
@camera_access(api=True)
def video_stream():
    viewer_id = request.args.get("viewer_id", "")
    manager = current_app.extensions["camera_manager"]
    if not _is_valid_viewer_id(viewer_id):
        return _camera_error("invalid_viewer", "觀看者識別碼無效。", 400)
    if not manager.owns_active_viewer(viewer_id):
        return _camera_error("camera_not_streaming", "攝影機串流尚未啟動。", 409)

    response = Response(
        _mjpeg_frames(manager, viewer_id),
        content_type="multipart/x-mixed-replace; boundary=frame",
    )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


def _viewer_id_from_body():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return None
    viewer_id = body.get("viewer_id")
    if not isinstance(viewer_id, str) or not _is_valid_viewer_id(viewer_id):
        return None
    return viewer_id


def _is_valid_viewer_id(viewer_id):
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{20,128}", viewer_id))


def _mjpeg_frames(manager, viewer_id):
    sequence = 0
    try:
        while manager.owns_active_viewer(viewer_id):
            frame, sequence = manager.wait_for_frame(sequence, timeout=15)
            if frame is None:
                break
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: "
                + str(len(frame)).encode("ascii")
                + b"\r\n\r\n"
                + frame
                + b"\r\n"
            )
    finally:
        manager.disconnect(viewer_id)


def _camera_error_details(code):
    if code == "camera_in_use":
        return code, "攝影機目前由另一位觀看者使用。", 409
    if code in {"camera_unavailable", "camera_read_failed", "camera_start_timeout"}:
        return code, "無法啟動攝影機，請確認裝置已連接且未被其他程式占用。", 503
    return code, "攝影機發生錯誤，請稍後重試。", 503


def _camera_error(code, message, status):
    return jsonify({"success": False, "code": code, "message": message, "errors": []}), status
