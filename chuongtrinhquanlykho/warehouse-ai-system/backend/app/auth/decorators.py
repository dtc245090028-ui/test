"""
auth/decorators.py — Middleware phân quyền theo role
======================================================
Module này cung cấp hai decorator để bảo vệ route:

  1. @jwt_required()           (từ Flask-JWT-Extended)
     → Kiểm tra token hợp lệ (chữ ký đúng + chưa hết hạn)

  2. @roles_required(*roles)   (tự viết trong file này)
     → Kiểm tra role của user trong token có nằm trong
       danh sách được phép không

NGUYÊN TẮC BẮT BUỘC (AGENTS.md mục 9):
  Phân quyền phải kiểm tra ở backend (route level),
  KHÔNG chỉ ẩn UI phía frontend.

CÁCH DÙNG trong router:
  from flask_jwt_extended import jwt_required
  from app.auth.decorators import roles_required

  @bp.route("/admin-only")
  @jwt_required()                              # bước 1: token hợp lệ?
  @roles_required("admin")                     # bước 2: đúng role?
  def admin_endpoint():
      ...
"""

from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt


def roles_required(*allowed_roles: str):
    """
    Decorator kiểm tra role của user đang gọi API.

    Cách hoạt động:
      1. Lấy claims (thông tin thêm) từ JWT đã được verify
      2. Đọc trường "role" trong claims
      3. Nếu role không nằm trong allowed_roles → trả 403 Forbidden
      4. Nếu hợp lệ → cho phép vào hàm xử lý

    Tham số:
      *allowed_roles: danh sách role được phép, ví dụ:
        @roles_required("admin")
        @roles_required("admin", "warehouse_manager")

    Lưu ý:
      Decorator này PHẢI đặt SAU @jwt_required() vì cần token
      đã được xác thực trước khi đọc claims.

    Ví dụ response khi không đủ quyền (HTTP 403):
      {
        "error_code": "FORBIDDEN",
        "message": "Bạn không có quyền thực hiện thao tác này"
      }
    """

    def decorator(fn):
        @wraps(fn)  # giữ nguyên tên hàm gốc để Flask routing không bị nhầm
        def wrapper(*args, **kwargs):
            # get_jwt() trả về dict chứa toàn bộ claims trong JWT payload
            # Claims này được đưa vào token lúc tạo trong auth/routes.py
            claims = get_jwt()

            # Đọc trường "role" từ claims — được set khi tạo token (additional_claims)
            user_role = claims.get("role")

            # Kiểm tra role có trong danh sách được phép không
            if user_role not in allowed_roles:
                return (
                    jsonify(
                        {
                            "error_code": "FORBIDDEN",
                            "message": (
                                f"Bạn không có quyền thực hiện thao tác này. "
                                f"Yêu cầu role: {', '.join(allowed_roles)}."
                            ),
                        }
                    ),
                    403,
                )

            # Role hợp lệ → cho phép tiếp tục vào hàm xử lý
            return fn(*args, **kwargs)

        return wrapper

    return decorator
