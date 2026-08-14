"""
main.py — Application Factory của Flask backend
=================================================
Đây là điểm khởi động của toàn bộ ứng dụng.

Dùng pattern "Application Factory" (create_app function) thay vì
tạo app ở global scope vì:
  1. Dễ test — mỗi test case có thể tạo app riêng với config khác nhau
  2. Tránh circular import — extensions.py tạo object, main.py bind vào app
  3. Dễ scale — có thể tạo nhiều instance app với config khác nhau

Cách chạy:
  # Từ thư mục backend/
  python -m app.main

  # Hoặc dùng Flask CLI:
  flask --app app.main run --debug
"""

import os
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

# Load biến môi trường từ file .env TRƯỚC KHI import bất cứ thứ gì dùng config
# load_dotenv() tìm file .env ở thư mục hiện tại hoặc thư mục cha
load_dotenv()

from app.extensions import db, jwt, ma
from app.models import User  # Import để SQLAlchemy nhận biết model


def create_app(test_config: dict = None) -> Flask:
    """
    Factory function — tạo và cấu hình Flask application.

    Quy trình:
      1. Tạo Flask app
      2. Load config từ biến môi trường
      3. Init các extension (db, jwt, ma)
      4. Tạo bảng CSDL nếu chưa tồn tại
      5. Đăng ký tất cả Blueprint (router)
      6. Đăng ký error handler dùng chung

    Trả về:
      Flask app đã cấu hình sẵn, sẵn sàng để run
    """

    # Tạo Flask app
    # __name__ giúp Flask xác định thư mục gốc để tìm template/static
    app = Flask(__name__)

    # ---- Cấu hình từ biến môi trường ----
    _configure_app(app)

    # ---- Override config cho môi trường test (nếu có) ----
    # test_config phải được merge TRƯỚC khi gọi db.init_app() để
    # SQLAlchemy tạo engine với đúng URI (sqlite:///:memory: khi test,
    # không phải file warehouse.db).
    if test_config:
        app.config.update(test_config)

    # ---- Bật CORS (Cross-Origin Resource Sharing) ----
    # Cho phép frontend (chạy port khác) gọi API backend
    # origins="*" chỉ dùng khi dev; production nên giới hạn domain cụ thể
    CORS(app, origins="*")

    # ---- Khởi tạo extensions với app ----
    db.init_app(app)     # SQLAlchemy biết dùng config của app này
    jwt.init_app(app)    # JWTManager biết SECRET_KEY của app này
    ma.init_app(app)     # Marshmallow biết context của app này

    # ---- Tạo bảng CSDL ----
    with app.app_context():
        # create_all() tạo các bảng chưa tồn tại (không xóa bảng đã có)
        # Các model phải đã được import trước đây (xem models/__init__.py)
        db.create_all()
        app.logger.info("✅ Bảng CSDL đã được tạo/kiểm tra xong.")

    # ---- Đăng ký Blueprints (routers) ----
    _register_blueprints(app)

    # ---- Đăng ký Error Handlers dùng chung ----
    _register_error_handlers(app)

    app.logger.info(f"🚀 Ứng dụng khởi động thành công | ENV={os.getenv('FLASK_ENV', 'development')}")
    return app


def _configure_app(app: Flask) -> None:
    """
    Load tất cả config từ biến môi trường vào app.config.
    Tách ra hàm riêng để dễ đọc và dễ test.
    """
    # CSDL — đọc từ DATABASE_URL, mặc định SQLite
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "sqlite:///./warehouse.db"
    )
    # Tắt tính năng theo dõi thay đổi (tốn RAM, không cần thiết)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Secret key — dùng để ký JWT và session cookie
    # PHẢI thay bằng chuỗi ngẫu nhiên dài khi triển khai production
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change_me_in_production")

    # JWT config
    app.config["JWT_SECRET_KEY"] = os.getenv("SECRET_KEY", "change_me_in_production")
    # Lưu JWT_EXPIRE_MINUTES vào config để auth/routes.py đọc được
    app.config["JWT_EXPIRE_MINUTES"] = os.getenv("JWT_EXPIRE_MINUTES", "60")

    # Môi trường
    app.config["DEBUG"] = os.getenv("FLASK_ENV", "development") == "development"


def _register_blueprints(app: Flask) -> None:
    """
    Đăng ký tất cả Blueprint vào app.
    Mỗi Blueprint tương ứng 1 module nghiệp vụ (auth, suppliers, goods...).
    """
    # Module Auth — /api/auth/login, /api/auth/logout, /api/auth/me
    from app.auth import auth_bp
    app.register_blueprint(auth_bp)

    # Module Suppliers — /api/suppliers (GET, POST, GET/id, PUT/id, DELETE/id)
    from app.routers.suppliers import suppliers_bp
    app.register_blueprint(suppliers_bp)

    # Module Goods — /api/goods
    from app.routers.goods import goods_bp
    app.register_blueprint(goods_bp)

    # Module Purchase Orders — /api/purchase-orders
    from app.routers.purchase_orders import bp as purchase_orders_bp
    app.register_blueprint(purchase_orders_bp)

    # Module Goods Receipts (Phiếu nhập) — /api/goods-receipts
    from app.routers.goods_receipts import goods_receipts_bp
    app.register_blueprint(goods_receipts_bp)

    # Module Goods Issues (Phiếu xuất) — /api/goods-issues
    from app.routers.goods_issues import goods_issues_bp
    app.register_blueprint(goods_issues_bp)

    app.logger.info("✅ Đã đăng ký tất cả Blueprint.")


def _register_error_handlers(app: Flask) -> None:
    """
    Đăng ký error handler dùng chung cho toàn app.
    Đảm bảo mọi lỗi đều trả về JSON đúng format (AGENTS.md mục 8),
    không bao giờ trả HTML error page của Flask.
    """
    from flask import jsonify
    from flask_jwt_extended.exceptions import NoAuthorizationError, InvalidHeaderError
    from jwt.exceptions import ExpiredSignatureError

    @app.errorhandler(400)
    def bad_request(e):
        """400 Bad Request — request sai định dạng"""
        return jsonify({
            "error_code": "BAD_REQUEST",
            "message": "Yêu cầu không hợp lệ",
        }), 400

    @app.errorhandler(401)
    def unauthorized(e):
        """401 Unauthorized — chưa đăng nhập hoặc token hết hạn"""
        return jsonify({
            "error_code": "UNAUTHORIZED",
            "message": "Bạn cần đăng nhập để thực hiện thao tác này",
        }), 401

    @app.errorhandler(403)
    def forbidden(e):
        """403 Forbidden — đã đăng nhập nhưng không đủ quyền"""
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": "Bạn không có quyền thực hiện thao tác này",
        }), 403

    @app.errorhandler(404)
    def not_found(e):
        """404 Not Found — route hoặc resource không tồn tại"""
        return jsonify({
            "error_code": "NOT_FOUND",
            "message": "Không tìm thấy tài nguyên yêu cầu",
        }), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        """405 Method Not Allowed — gọi sai HTTP method"""
        return jsonify({
            "error_code": "METHOD_NOT_ALLOWED",
            "message": "Phương thức HTTP không được phép cho endpoint này",
        }), 405

    @app.errorhandler(500)
    def internal_error(e):
        """500 Internal Server Error — lỗi hệ thống không mong muốn"""
        app.logger.error(f"Lỗi server: {e}")
        return jsonify({
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "Đã xảy ra lỗi hệ thống. Vui lòng thử lại sau.",
        }), 500

    # Xử lý lỗi JWT từ Flask-JWT-Extended
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        """Token đã hết hạn (quá JWT_EXPIRE_MINUTES)"""
        return jsonify({
            "error_code": "TOKEN_EXPIRED",
            "message": "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.",
        }), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        """Token không hợp lệ (bị sửa, sai chữ ký)"""
        return jsonify({
            "error_code": "TOKEN_INVALID",
            "message": "Token không hợp lệ. Vui lòng đăng nhập lại.",
        }), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        """Không có Authorization header"""
        return jsonify({
            "error_code": "TOKEN_MISSING",
            "message": "Thiếu token xác thực. Vui lòng đăng nhập.",
        }), 401

    app.logger.info("✅ Đã đăng ký Error Handlers.")


# ---- Chạy trực tiếp (python -m app.main) ----
if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("FLASK_PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=app.config["DEBUG"])
