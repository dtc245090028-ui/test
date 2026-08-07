"""
auth/routes.py — Các endpoint xác thực (Auth API)
===================================================
Triển khai đúng theo docs/api_contract.md mục 1:
  POST /api/auth/login   → Đăng nhập, trả JWT
  POST /api/auth/logout  → Đăng xuất (invalidate token phía client)
  GET  /api/auth/me      → Lấy thông tin user hiện tại

Quy trình đăng nhập (POST /api/auth/login):
  1. Nhận username + password từ request body (JSON)
  2. Validate dữ liệu đầu vào (không rỗng)
  3. Tìm user trong DB theo username
  4. Kiểm tra user tồn tại + is_active = True
  5. Dùng bcrypt verify password (check_password)
  6. Tạo JWT access token với claims: user_id, role
  7. Trả token + role về client

JWT Claims (thông tin nhúng vào token):
  - sub  (subject)  : user_id — định danh duy nhất
  - role            : role của user — dùng để phân quyền ở decorator
  - Thời hạn (exp)  : tính từ JWT_EXPIRE_MINUTES trong .env
"""

from datetime import timedelta
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token,  # tạo JWT token
    jwt_required,          # decorator: yêu cầu token hợp lệ
    get_jwt_identity,      # lấy "subject" (user_id) từ token
    get_jwt,               # lấy toàn bộ claims từ token
)
from app.extensions import db
from app.models.user import User

# Blueprint — nhóm tất cả route auth dưới prefix /api/auth
# Được đăng ký vào app trong main.py: app.register_blueprint(auth_bp)
auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


# ============================================================
# POST /api/auth/login
# ============================================================
@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Đăng nhập và nhận JWT access token.

    Request body (JSON):
      { "username": "admin01", "password": "Password@123" }

    Response thành công (200):
      { "access_token": "<jwt>", "role": "admin" }

    Response lỗi:
      400 MISSING_FIELDS     — thiếu username hoặc password
      401 INVALID_CREDENTIALS — sai username hoặc password
      403 ACCOUNT_INACTIVE   — tài khoản bị vô hiệu hóa
    """
    # --- Bước 1: Đọc dữ liệu từ request body ---
    data = request.get_json()

    # Kiểm tra request có phải JSON không
    if not data:
        return jsonify({
            "error_code": "MISSING_FIELDS",
            "message": "Request body phải là JSON hợp lệ",
        }), 400

    username = data.get("username", "").strip()
    password = data.get("password", "")

    # --- Bước 2: Validate dữ liệu đầu vào ---
    if not username or not password:
        return jsonify({
            "error_code": "MISSING_FIELDS",
            "message": "Vui lòng nhập đầy đủ username và password",
        }), 400

    # --- Bước 3: Tìm user trong CSDL ---
    # filter_by tìm theo username, first() trả None nếu không tìm thấy
    user = User.query.filter_by(username=username).first()

    # --- Bước 4: Kiểm tra user tồn tại và trạng thái ---
    # Gộp 2 trường hợp (không tìm thấy + sai password) vào cùng 1 thông báo
    # → tránh tiết lộ "username này có tồn tại không" (security best practice)
    if user is None or not user.check_password(password):
        return jsonify({
            "error_code": "INVALID_CREDENTIALS",
            "message": "Tên đăng nhập hoặc mật khẩu không chính xác",
        }), 401

    # Kiểm tra riêng tài khoản bị khóa (sau khi confirm user tồn tại)
    if not user.is_active:
        return jsonify({
            "error_code": "ACCOUNT_INACTIVE",
            "message": "Tài khoản đã bị vô hiệu hóa. Liên hệ Ban điều hành để được hỗ trợ.",
        }), 403

    # --- Bước 5: Tạo JWT access token ---
    # `identity` = user_id (str) — đây là trường "sub" trong JWT
    # `additional_claims` = thêm role vào payload để decorator đọc
    # `expires_delta` = thời hạn token lấy từ .env (JWT_EXPIRE_MINUTES)

    expire_minutes = int(current_app.config.get("JWT_EXPIRE_MINUTES", 60))
    expire_delta = timedelta(minutes=expire_minutes)

    access_token = create_access_token(
        identity=str(user.id),                  # subject: dùng để lấy lại user_id
        additional_claims={"role": user.role},   # thêm role vào payload JWT
        expires_delta=expire_delta,
    )

    # --- Bước 6: Trả response ---
    return jsonify({
        "access_token": access_token,
        "role": user.role,
        # Trả thêm thông tin user cơ bản để frontend không cần gọi thêm /me
        "user": {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
        },
    }), 200


# ============================================================
# POST /api/auth/logout
# ============================================================
@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    """
    Đăng xuất.

    Với JWT stateless, server không lưu danh sách token → không thể
    "xóa" token phía server. Có 2 cách xử lý:

    Cách 1 (đơn giản — dùng trong demo này):
      Server trả 200, client tự xóa token khỏi localStorage/cookie.
      Token vẫn còn hiệu lực cho đến khi hết hạn, nhưng client không
      còn giữ nó → đủ cho phạm vi đồ án.

    Cách 2 (production — nếu cần):
      Lưu danh sách token đã logout vào Redis (blocklist).
      Mỗi request vào check token có trong blocklist không.
      → Phức tạp hơn nhưng an toàn hơn cho hệ thống thực.

    Response thành công (200):
      { "message": "Đăng xuất thành công" }
    """
    # Lấy user_id từ token để log (tùy chọn, phục vụ audit log sau này)
    current_user_id = get_jwt_identity()
    current_app.logger.info(f"User {current_user_id} đã đăng xuất.")

    return jsonify({"message": "Đăng xuất thành công"}), 200


# ============================================================
# GET /api/auth/me
# ============================================================
@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    """
    Lấy thông tin user đang đăng nhập.

    Dùng trong frontend để:
      - Hiển thị tên + role sau khi đăng nhập
      - Kiểm tra token còn hiệu lực không (nếu /me trả 401 → hết hạn)

    Header yêu cầu:
      Authorization: Bearer <access_token>

    Response thành công (200):
      {
        "id": 1,
        "username": "admin01",
        "full_name": "Nguyễn Văn Admin",
        "email": "admin@warehouse.local",
        "role": "admin",
        "is_active": true,
        "created_at": "2026-01-01T08:00:00"
      }

    Response lỗi:
      401 — token không hợp lệ hoặc đã hết hạn
      404 — user trong token không còn trong CSDL (đã bị xóa)
    """
    # get_jwt_identity() trả về "sub" của token = user_id (str)
    current_user_id = get_jwt_identity()

    # Truy vấn lại DB để lấy thông tin mới nhất
    # (quan trọng: is_active có thể đã thay đổi kể từ khi cấp token)
    user = db.session.get(User, int(current_user_id))

    if user is None:
        return jsonify({
            "error_code": "USER_NOT_FOUND",
            "message": "Tài khoản không còn tồn tại trong hệ thống",
        }), 404

    # Kiểm tra lại is_active (có thể bị khóa sau khi token được cấp)
    if not user.is_active:
        return jsonify({
            "error_code": "ACCOUNT_INACTIVE",
            "message": "Tài khoản đã bị vô hiệu hóa",
        }), 403

    return jsonify(user.to_dict()), 200
