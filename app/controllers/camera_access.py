import hmac
import ipaddress
import secrets
from functools import wraps

from flask import abort, current_app, flash, jsonify, redirect, request, session, url_for

from app.repositories.user_repository import UserRepository

CAMERA_CSRF_SESSION_KEY = "camera_csrf_token"
CAMERA_CSRF_HEADER = "X-CSRF-Token"


def create_camera_csrf_token():
    token = session.get(CAMERA_CSRF_SESSION_KEY)
    if token is None:
        token = secrets.token_urlsafe(32)
        session[CAMERA_CSRF_SESSION_KEY] = token
    return token


def camera_access(*, api=False, csrf=False):
    def decorate(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not _is_loopback_client(request.remote_addr):
                if api:
                    return _json_error("local_only", "此功能僅允許在攝影機主機本機使用。", 403)
                abort(403)

            user_id = session.get("user_id")
            try:
                user = UserRepository(current_app.config["DATABASE_PATH"]).get_by_id(user_id)
            except (TypeError, ValueError):
                user = None

            if not user or user.get("status") != "approved":
                if api:
                    return _json_error("unauthorized", "請先登入已核准的帳號。", 401)
                flash("請先登入已核准的帳號。", "error")
                return redirect(url_for("web.login"))

            if csrf:
                expected = session.get(CAMERA_CSRF_SESSION_KEY, "")
                supplied = request.headers.get(CAMERA_CSRF_HEADER, "")
                if not expected or not hmac.compare_digest(expected, supplied):
                    return _json_error("csrf_invalid", "請求驗證失敗，請重新載入頁面後再試。", 403)

            return view(*args, **kwargs)

        return wrapped

    return decorate


def _is_loopback_client(remote_addr):
    if not remote_addr:
        return False
    try:
        address = ipaddress.ip_address(remote_addr)
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return address.is_loopback


def _json_error(code, message, status):
    return jsonify({"success": False, "code": code, "message": message, "errors": []}), status