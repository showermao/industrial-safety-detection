import json

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app.controllers.camera_access import camera_access, create_camera_csrf_token
from app.repositories.user_repository import UserRepository
from app.repositories.inspection_repository import InspectionRepository
from app.services.auth_service import AuthService
from app.services.monitor_service import MonitoringService

web_bp = Blueprint("web", __name__)


def get_user_repo():
    return UserRepository(current_app.config["DATABASE_PATH"])


def get_auth_service():
    return AuthService(current_app.config["DATABASE_PATH"])


def get_monitoring_service():
    return MonitoringService(current_app.config["DATABASE_PATH"])


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_user_repo().get_by_id(user_id)


def is_admin():
    user = current_user()
    return bool(user and user["role"] == "admin")


def login_required(view):
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("請先登入帳號。", "error")
            return redirect(url_for("web.login"))
        return view(*args, **kwargs)

    wrapped.__name__ = view.__name__
    return wrapped


@web_bp.route("/", methods=["GET"])
def index():
    user = current_user()
    dashboard = get_monitoring_service().dashboard_regions()
    recent_alerts = get_monitoring_service().get_recent_alerts()
    recent_audits = get_monitoring_service().get_recent_audits()
    return render_template(
        "index.html",
        user=user,
        dashboard=dashboard,
        recent_alerts=recent_alerts,
        recent_audits=recent_audits,
    )


@web_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "user")

        if not username or not email or not password:
            flash("請填寫完整資料。", "error")
            return render_template("register.html")

        try:
            get_auth_service().register_user(username, email, password, role=role)
        except ValueError:
            flash("使用者名稱已存在，請選擇其他名稱。", "error")
            return render_template("register.html")

        flash("註冊成功，帳號狀態為 pending / 待審核，待管理者審核通過後即可登入。", "success")
        return redirect(url_for("web.login"))

    return render_template("register.html")


@web_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_auth_service().authenticate(username, password)

        if user:
            session["user_id"] = user["id"]
            flash("登入成功，歡迎回到監控系統。", "success")
            return redirect(url_for("web.index"))

        flash("帳號或密碼錯誤，或帳號尚未通過審核。", "error")
        return render_template("login.html")

    return render_template("login.html")


@web_bp.route("/logout")
def logout():
    session.clear()
    flash("已登出系統。", "success")
    return redirect(url_for("web.login"))


@web_bp.route("/admin/review", methods=["GET", "POST"])
@login_required
def admin_review():
    if not is_admin():
        flash("僅管理者可進入會員審核。", "error")
        return redirect(url_for("web.index"))

    if request.method == "POST":
        user_id = int(request.form.get("user_id", 0))
        action = request.form.get("action", "approve")
        if action == "approve":
            get_auth_service().approve_user(user_id)
            flash("已核准使用者。", "success")
        else:
            get_auth_service().reject_user(user_id)
            flash("已拒絕使用者申請。", "success")

    pending_users = get_auth_service().list_pending_users()
    return render_template("admin_review.html", pending_users=pending_users)


@web_bp.route("/alerts/create", methods=["GET", "POST"])
@login_required
def create_alert():
    if request.method == "POST":
        area_name = request.form.get("area_name", "").strip()
        event_type = request.form.get("event_type", "").strip()
        severity = request.form.get("severity", "warning").strip()
        notes = request.form.get("notes", "").strip()

        if not area_name or not event_type:
            flash("請填寫區域與事件類型。", "error")
            return render_template("alert_form.html")

        alert = get_monitoring_service().create_alert(
            area_name=area_name,
            event_type=event_type,
            severity=severity,
            notes=notes,
            actor_id=current_user()["id"],
        )
        flash(f"{severity.upper()} 警示已建立，稽核紀錄已更新。", "success")
        return redirect(url_for("web.index"))

    return render_template("alert_form.html")


@web_bp.route("/audit", methods=["GET"])
@login_required
def audit_log():
    audits = get_monitoring_service().get_recent_audits()
    return render_template("audit.html", audits=audits)


@web_bp.route("/inspection-records", methods=["GET"])
@login_required
def inspection_records():
    records = InspectionRepository(current_app.config["DATABASE_PATH"]).list_recent()
    return render_template("inspection_records.html", records=records, user=current_user())


@web_bp.route("/image-inspection", methods=["GET", "POST"])
@login_required
def image_inspection():
    result = None
    error = None
    if request.method == "POST":
        upload = request.files.get("image")
        if not upload or not upload.filename:
            error = "請選擇要比對的圖片。"
        else:
            image_bytes = upload.read(current_app.config["IMAGE_UPLOAD_MAX_BYTES"] + 1)
            if len(image_bytes) > current_app.config["IMAGE_UPLOAD_MAX_BYTES"]:
                error = "圖片大小不可超過 10 MB。"
            else:
                result = current_app.extensions["inspection_service"].inspect(image_bytes)
    return render_template("image_inspection.html", user=current_user(), result=result, error=error)


@web_bp.route("/image-inspection/record", methods=["POST"])
@login_required
def record_uploaded_inspection():
    status = request.form.get("status", "")
    if status not in {"normal", "problem", "unrecognized"}:
        flash("檢測結果無效，無法紀錄。", "error")
        return redirect(url_for("web.image_inspection"))
    try:
        detections = json.loads(request.form.get("detections", "[]"))
    except (TypeError, ValueError):
        detections = []
    result = {
        "status": status,
        "status_label": request.form.get("status_label", ""),
        "comparison_time": request.form.get("comparison_time", ""),
        "problem_description": request.form.get("problem_description", ""),
        "detections": detections if isinstance(detections, list) else [],
        "image": request.form.get("image", ""),
    }
    InspectionRepository(current_app.config["DATABASE_PATH"]).create(
        result, actor_id=session.get("user_id"), source="upload"
    )
    flash("圖片比對結果已紀錄。", "success")
    return redirect(url_for("web.image_inspection"))


@web_bp.route("/camera", methods=["GET"])
@camera_access()
def camera_monitor():
    return render_template(
        "camera_monitor.html",
        user=current_user(),
        csrf_token=create_camera_csrf_token(),
    )
