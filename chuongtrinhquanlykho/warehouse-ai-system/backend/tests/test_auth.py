"""
tests/test_auth.py — Test cases cho module Auth
=================================================
Kiểm thử các ca trong mục 10 (Prompt.md) liên quan đến Auth:
  - Đăng nhập đúng (ca đúng)
  - Sai password (ca lỗi)
  - Thiếu field (ca lỗi)
  - Token hết hạn (ca biên)
  - Phân quyền 403 (ca lỗi)

Chạy test:
  cd backend/
  pytest tests/test_auth.py -v
"""

import pytest
from app.main import create_app
from app.extensions import db
from app.models.user import User


# ---- Fixture: tạo test app với SQLite in-memory ----
@pytest.fixture
def app():
    """
    Tạo Flask app với CSDL SQLite in-memory riêng cho test.
    Dùng in-memory DB để mỗi test chạy độc lập, không ảnh hưởng nhau.
    """
    test_app = create_app()
    test_app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",  # in-memory, không lưu file
        "JWT_EXPIRE_MINUTES": "60",
        "SECRET_KEY": "test-secret-key",
        "JWT_SECRET_KEY": "test-secret-key",
    })

    with test_app.app_context():
        db.create_all()

        # Tạo user mẫu cho test
        test_user = User(
            username="test_admin",
            full_name="Test Admin",
            email="test@warehouse.local",
            role="admin",
            is_active=True,
        )
        test_user.set_password("Password@123")
        db.session.add(test_user)

        inactive_user = User(
            username="test_inactive",
            full_name="Inactive User",
            role="warehouse_keeper",
            is_active=False,  # tài khoản bị khóa
        )
        inactive_user.set_password("Password@123")
        db.session.add(inactive_user)

        db.session.commit()

    yield test_app

    with test_app.app_context():
        db.drop_all()


@pytest.fixture
def client(app):
    """HTTP test client của Flask"""
    return app.test_client()


# ============================================================
# CA ĐÚNG
# ============================================================

def test_login_success(client):
    """Đăng nhập hợp lệ → 200 + access_token trong response"""
    response = client.post("/api/auth/login", json={
        "username": "test_admin",
        "password": "Password@123",
    })
    data = response.get_json()

    assert response.status_code == 200
    assert "access_token" in data
    assert data["role"] == "admin"
    assert data["user"]["username"] == "test_admin"


def test_me_with_valid_token(client):
    """GET /api/auth/me với token hợp lệ → 200 + thông tin user"""
    # Đăng nhập lấy token
    login_res = client.post("/api/auth/login", json={
        "username": "test_admin",
        "password": "Password@123",
    })
    token = login_res.get_json()["access_token"]

    # Gọi /me với token
    response = client.get("/api/auth/me", headers={
        "Authorization": f"Bearer {token}"
    })
    data = response.get_json()

    assert response.status_code == 200
    assert data["username"] == "test_admin"
    assert data["role"] == "admin"
    # Đảm bảo password_hash KHÔNG có trong response
    assert "password_hash" not in data


def test_logout_success(client):
    """POST /api/auth/logout với token hợp lệ → 200"""
    login_res = client.post("/api/auth/login", json={
        "username": "test_admin",
        "password": "Password@123",
    })
    token = login_res.get_json()["access_token"]

    response = client.post("/api/auth/logout", headers={
        "Authorization": f"Bearer {token}"
    })

    assert response.status_code == 200


# ============================================================
# CA LỖI / BIÊN
# ============================================================

def test_login_wrong_password(client):
    """Sai password → 401 INVALID_CREDENTIALS"""
    response = client.post("/api/auth/login", json={
        "username": "test_admin",
        "password": "SaiPassword123",
    })
    data = response.get_json()

    assert response.status_code == 401
    assert data["error_code"] == "INVALID_CREDENTIALS"


def test_login_wrong_username(client):
    """Username không tồn tại → 401 INVALID_CREDENTIALS (không tiết lộ)"""
    response = client.post("/api/auth/login", json={
        "username": "khong_ton_tai",
        "password": "Password@123",
    })
    data = response.get_json()

    assert response.status_code == 401
    assert data["error_code"] == "INVALID_CREDENTIALS"


def test_login_missing_fields(client):
    """Thiếu password → 400 MISSING_FIELDS"""
    response = client.post("/api/auth/login", json={
        "username": "test_admin",
        # thiếu password
    })
    data = response.get_json()

    assert response.status_code == 400
    assert data["error_code"] == "MISSING_FIELDS"


def test_login_empty_body(client):
    """Body rỗng → 400 MISSING_FIELDS"""
    response = client.post("/api/auth/login", json={})
    data = response.get_json()

    assert response.status_code == 400
    assert data["error_code"] == "MISSING_FIELDS"


def test_login_inactive_account(client):
    """Tài khoản bị khóa → 403 ACCOUNT_INACTIVE"""
    response = client.post("/api/auth/login", json={
        "username": "test_inactive",
        "password": "Password@123",
    })
    data = response.get_json()

    assert response.status_code == 403
    assert data["error_code"] == "ACCOUNT_INACTIVE"


def test_me_without_token(client):
    """Gọi /me không có token → 401 TOKEN_MISSING"""
    response = client.get("/api/auth/me")
    data = response.get_json()

    assert response.status_code == 401
    assert data["error_code"] == "TOKEN_MISSING"


def test_me_with_invalid_token(client):
    """Gọi /me với token giả → 401 TOKEN_INVALID"""
    response = client.get("/api/auth/me", headers={
        "Authorization": "Bearer token.gia.mao"
    })
    data = response.get_json()

    assert response.status_code == 401
    assert data["error_code"] == "TOKEN_INVALID"


def test_logout_without_token(client):
    """Logout không có token → 401"""
    response = client.post("/api/auth/logout")

    assert response.status_code == 401
