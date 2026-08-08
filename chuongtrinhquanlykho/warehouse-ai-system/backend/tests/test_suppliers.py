"""
tests/test_suppliers.py — Test cases cho module Suppliers
==========================================================
Kiểm thử đầy đủ 5 endpoint theo api_contract.md mục 2:

  CA ĐÚNG (Happy path):
    TC-SUP-01: Tạo NCC mới thành công
    TC-SUP-02: Lấy danh sách NCC (có phân trang)
    TC-SUP-03: Lấy chi tiết 1 NCC
    TC-SUP-04: Cập nhật thông tin NCC
    TC-SUP-05: Ngừng hợp tác (DELETE → soft-delete, status='inactive')
    TC-SUP-06: Filter danh sách theo status
    TC-SUP-07: Tìm kiếm NCC theo từ khóa

  CA LỖI (Error path):
    TC-SUP-08: POST thiếu field 'name' → 400 MISSING_FIELDS
    TC-SUP-09: POST tên trùng → 409 SUPPLIER_NAME_DUPLICATE
    TC-SUP-10: GET /id không tồn tại → 404 SUPPLIER_NOT_FOUND
    TC-SUP-11: PUT /id không tồn tại → 404 SUPPLIER_NOT_FOUND
    TC-SUP-12: DELETE /id không tồn tại → 404 SUPPLIER_NOT_FOUND
    TC-SUP-13: DELETE NCC đã inactive → 409 SUPPLIER_ALREADY_INACTIVE
    TC-SUP-14: POST mã số thuế trùng → 409 TAX_CODE_DUPLICATE

  CA PHÂN QUYỀN (Authorization):
    TC-SUP-15: Thủ kho GET danh sách → 403 FORBIDDEN
    TC-SUP-16: Thủ kho POST tạo mới → 403 FORBIDDEN
    TC-SUP-17: warehouse_manager DELETE → 403 FORBIDDEN (chỉ admin được DELETE)
    TC-SUP-18: Không có token → 401 TOKEN_MISSING
    TC-SUP-19: Thủ kho GET chi tiết → 200 (được phép)

Chạy test:
  cd backend/
  pytest tests/test_suppliers.py -v

Chạy 1 test cụ thể:
  pytest tests/test_suppliers.py::test_create_supplier_success -v
"""

import pytest
from app.main import create_app
from app.extensions import db
from app.models.user import User
from app.models.supplier import Supplier


# ============================================================
# FIXTURE — Tạo app, CSDL, dữ liệu mẫu
# ============================================================

@pytest.fixture
def app():
    """
    Tạo Flask app với SQLite in-memory cho test.
    Mỗi test function dùng fixture này sẽ có app riêng, sạch.

    Quan trọng: test_config phải được truyền VÀO create_app() trước khi
    SQLAlchemy khởi tạo engine — tránh warehouse.db bị dùng thay vì in-memory.
    """
    test_app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "JWT_EXPIRE_MINUTES": "60",
        # Dùng key ≥ 32 ký tự để tránh InsecureKeyLengthWarning
        "SECRET_KEY": "test-secret-suppliers-key-for-pytest!",
        "JWT_SECRET_KEY": "test-secret-suppliers-key-for-pytest!",
    })

    with test_app.app_context():
        # create_all() đã được gọi trong create_app() với in-memory URI
        # Gọi lại để đảm bảo bảng tồn tại trong context này
        db.create_all()

        # ---- Tạo users với 3 role khác nhau ----

        admin_user = User(
            username="admin_sup",
            full_name="Admin Test",
            email="admin@test.local",
            role="admin",
            is_active=True,
        )
        admin_user.set_password("Password@123")
        db.session.add(admin_user)

        manager_user = User(
            username="manager_sup",
            full_name="Manager Test",
            email="manager@test.local",
            role="warehouse_manager",
            is_active=True,
        )
        manager_user.set_password("Password@123")
        db.session.add(manager_user)

        keeper_user = User(
            username="keeper_sup",
            full_name="Keeper Test",
            email="keeper@test.local",
            role="warehouse_keeper",
            is_active=True,
        )
        keeper_user.set_password("Password@123")
        db.session.add(keeper_user)

        # ---- Tạo NCC mẫu sẵn cho test cần dữ liệu có sẵn ----

        supplier_active = Supplier(
            name="Công ty TNHH ABC",
            contact_person="Nguyễn Văn A",
            phone="0901234567",
            email="abc@example.com",
            address="123 Đường Lê Lợi, TP.HCM",
            tax_code="0123456789",
            notes="Thanh toán 30 ngày",
            status="active",
        )
        db.session.add(supplier_active)

        supplier_inactive = Supplier(
            name="Công ty XYZ (đã ngừng)",
            phone="0987654321",
            status="inactive",
        )
        db.session.add(supplier_inactive)

        db.session.commit()

    yield test_app

    # ---- Teardown: xóa sạch DB sau mỗi test để đảm bảo isolation ----
    with test_app.app_context():
        db.session.remove()
        db.drop_all()



@pytest.fixture
def client(app):
    """Flask test client — gửi HTTP request không cần server thật"""
    return app.test_client()


# ---- Helper functions ----

def _login(client, username: str, password: str = "Password@123") -> str:
    """
    Đăng nhập và trả về access_token.
    Dùng trong các test cần token trước khi gọi API.
    """
    resp = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, f"Login failed: {resp.get_json()}"
    return resp.get_json()["access_token"]


def _auth_header(token: str) -> dict:
    """Tạo dict Authorization header từ token"""
    return {"Authorization": f"Bearer {token}"}


# ============================================================
# TC-SUP-01: Tạo NCC mới thành công
# ============================================================

def test_create_supplier_success(client):
    """
    CA ĐÚNG: Admin tạo NCC với đủ thông tin.
    Kỳ vọng: 201, trả về NCC vừa tạo với đúng field.
    """
    token = _login(client, "admin_sup")

    resp = client.post(
        "/api/suppliers",
        json={
            "name": "Nhà cung cấp Mới",
            "contact_person": "Trần Thị B",
            "phone": "0911111111",
            "email": "moi@supplier.vn",
            "address": "456 Đường Nguyễn Huệ",
            "tax_code": "9876543210",
            "notes": "Ghi chú test",
            "status": "active",
        },
        headers=_auth_header(token),
    )

    assert resp.status_code == 201
    data = resp.get_json()
    assert data["name"] == "Nhà cung cấp Mới"
    assert data["contact_person"] == "Trần Thị B"
    assert data["tax_code"] == "9876543210"
    assert data["status"] == "active"
    # Phải có id và timestamps
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


# ============================================================
# TC-SUP-02: Danh sách NCC với phân trang
# ============================================================

def test_list_suppliers_success(client):
    """
    CA ĐÚNG: Manager lấy danh sách NCC.
    Kỳ vọng: 200, có data và pagination.
    """
    token = _login(client, "manager_sup")

    resp = client.get(
        "/api/suppliers?page=1&page_size=10",
        headers=_auth_header(token),
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert "data" in body
    assert "pagination" in body
    # Có ít nhất 2 NCC mẫu đã tạo trong fixture
    assert body["pagination"]["total"] >= 2
    assert body["pagination"]["page"] == 1
    assert body["pagination"]["page_size"] == 10


# ============================================================
# TC-SUP-03: Lấy chi tiết 1 NCC
# ============================================================

def test_get_supplier_by_id_success(client, app):
    """
    CA ĐÚNG: Lấy chi tiết NCC tồn tại theo ID.
    Kỳ vọng: 200, đúng thông tin NCC.
    """
    token = _login(client, "manager_sup")

    # Lấy id của NCC mẫu 'Công ty TNHH ABC' từ CSDL
    with app.app_context():
        supplier = Supplier.query.filter_by(name="Công ty TNHH ABC").first()
        supplier_id = supplier.id

    resp = client.get(
        f"/api/suppliers/{supplier_id}",
        headers=_auth_header(token),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == supplier_id
    assert data["name"] == "Công ty TNHH ABC"
    assert data["tax_code"] == "0123456789"
    assert data["status"] == "active"


# ============================================================
# TC-SUP-04: Cập nhật thông tin NCC
# ============================================================

def test_update_supplier_success(client, app):
    """
    CA ĐÚNG: Manager cập nhật email và ghi chú của NCC.
    Kỳ vọng: 200, field được cập nhật, field khác giữ nguyên.
    """
    token = _login(client, "manager_sup")

    with app.app_context():
        supplier = Supplier.query.filter_by(name="Công ty TNHH ABC").first()
        supplier_id = supplier.id

    resp = client.put(
        f"/api/suppliers/{supplier_id}",
        json={
            "email": "abc_updated@example.com",
            "notes": "Cập nhật ghi chú mới",
        },
        headers=_auth_header(token),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["email"] == "abc_updated@example.com"
    assert data["notes"] == "Cập nhật ghi chú mới"
    # Field không gửi lên → giữ nguyên
    assert data["name"] == "Công ty TNHH ABC"
    assert data["phone"] == "0901234567"


# ============================================================
# TC-SUP-05: Ngừng hợp tác (soft-delete)
# ============================================================

def test_deactivate_supplier_success(client, app):
    """
    CA ĐÚNG: Admin DELETE NCC → chỉ đổi status='inactive', không xóa.
    Kỳ vọng: 200, NCC vẫn tồn tại trong DB với status='inactive'.
    """
    token = _login(client, "admin_sup")

    with app.app_context():
        supplier = Supplier.query.filter_by(name="Công ty TNHH ABC").first()
        supplier_id = supplier.id

    resp = client.delete(
        f"/api/suppliers/{supplier_id}",
        headers=_auth_header(token),
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert "message" in body
    assert body["supplier"]["status"] == "inactive"

    # Xác nhận bản ghi vẫn còn trong CSDL (không bị xóa cứng)
    with app.app_context():
        still_exists = db.session.get(Supplier, supplier_id)
        assert still_exists is not None
        assert still_exists.status == "inactive"


# ============================================================
# TC-SUP-06: Filter danh sách theo status
# ============================================================

def test_list_suppliers_filter_by_status(client):
    """
    CA ĐÚNG: Filter danh sách chỉ lấy NCC đang active.
    Kỳ vọng: Tất cả kết quả trả về đều có status='active'.
    """
    token = _login(client, "admin_sup")

    resp = client.get(
        "/api/suppliers?status=active",
        headers=_auth_header(token),
    )

    assert resp.status_code == 200
    body = resp.get_json()
    for supplier in body["data"]:
        assert supplier["status"] == "active"


# ============================================================
# TC-SUP-07: Tìm kiếm NCC theo từ khóa
# ============================================================

def test_list_suppliers_search(client):
    """
    CA ĐÚNG: Tìm kiếm NCC theo tên (case-insensitive).
    Kỳ vọng: Trả về đúng NCC có chứa từ khóa.
    """
    token = _login(client, "manager_sup")

    resp = client.get(
        "/api/suppliers?search=abc",  # 'abc' khớp 'Công ty TNHH ABC'
        headers=_auth_header(token),
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["pagination"]["total"] >= 1
    names = [s["name"] for s in body["data"]]
    # Ít nhất 1 kết quả có chứa 'abc' (case-insensitive)
    assert any("abc" in name.lower() for name in names)


# ============================================================
# TC-SUP-08: POST thiếu field name
# ============================================================

def test_create_supplier_missing_name(client):
    """
    CA LỖI: POST không có field 'name'.
    Kỳ vọng: 400, error_code='MISSING_FIELDS'.
    """
    token = _login(client, "admin_sup")

    resp = client.post(
        "/api/suppliers",
        json={"phone": "0900000000"},  # Thiếu 'name'
        headers=_auth_header(token),
    )

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["error_code"] == "MISSING_FIELDS"
    assert "message" in body


# ============================================================
# TC-SUP-09: POST tên trùng
# ============================================================

def test_create_supplier_duplicate_name(client):
    """
    CA LỖI: POST NCC với tên đã tồn tại.
    Kỳ vọng: 409, error_code='SUPPLIER_NAME_DUPLICATE'.
    """
    token = _login(client, "admin_sup")

    resp = client.post(
        "/api/suppliers",
        json={"name": "Công ty TNHH ABC"},  # Tên đã có từ fixture
        headers=_auth_header(token),
    )

    assert resp.status_code == 409
    body = resp.get_json()
    assert body["error_code"] == "SUPPLIER_NAME_DUPLICATE"


# ============================================================
# TC-SUP-10: GET chi tiết NCC không tồn tại
# ============================================================

def test_get_supplier_not_found(client):
    """
    CA LỖI: GET NCC với ID không tồn tại.
    Kỳ vọng: 404, error_code='SUPPLIER_NOT_FOUND'.
    """
    token = _login(client, "manager_sup")

    resp = client.get(
        "/api/suppliers/99999",  # ID chắc chắn không tồn tại
        headers=_auth_header(token),
    )

    assert resp.status_code == 404
    body = resp.get_json()
    assert body["error_code"] == "SUPPLIER_NOT_FOUND"


# ============================================================
# TC-SUP-11: PUT NCC không tồn tại
# ============================================================

def test_update_supplier_not_found(client):
    """
    CA LỖI: PUT cập nhật NCC với ID không tồn tại.
    Kỳ vọng: 404, error_code='SUPPLIER_NOT_FOUND'.
    """
    token = _login(client, "manager_sup")

    resp = client.put(
        "/api/suppliers/99999",
        json={"name": "Tên mới"},
        headers=_auth_header(token),
    )

    assert resp.status_code == 404
    body = resp.get_json()
    assert body["error_code"] == "SUPPLIER_NOT_FOUND"


# ============================================================
# TC-SUP-12: DELETE NCC không tồn tại
# ============================================================

def test_deactivate_supplier_not_found(client):
    """
    CA LỖI: DELETE NCC với ID không tồn tại.
    Kỳ vọng: 404, error_code='SUPPLIER_NOT_FOUND'.
    """
    token = _login(client, "admin_sup")

    resp = client.delete(
        "/api/suppliers/99999",
        headers=_auth_header(token),
    )

    assert resp.status_code == 404
    body = resp.get_json()
    assert body["error_code"] == "SUPPLIER_NOT_FOUND"


# ============================================================
# TC-SUP-13: DELETE NCC đã inactive
# ============================================================

def test_deactivate_supplier_already_inactive(client, app):
    """
    CA LỖI: DELETE NCC đã ở trạng thái 'inactive'.
    Kỳ vọng: 409, error_code='SUPPLIER_ALREADY_INACTIVE'.
    """
    token = _login(client, "admin_sup")

    with app.app_context():
        inactive = Supplier.query.filter_by(status="inactive").first()
        supplier_id = inactive.id

    resp = client.delete(
        f"/api/suppliers/{supplier_id}",
        headers=_auth_header(token),
    )

    assert resp.status_code == 409
    body = resp.get_json()
    assert body["error_code"] == "SUPPLIER_ALREADY_INACTIVE"


# ============================================================
# TC-SUP-14: POST mã số thuế trùng
# ============================================================

def test_create_supplier_duplicate_tax_code(client):
    """
    CA LỖI: POST NCC với mã số thuế đã tồn tại.
    Kỳ vọng: 409, error_code='TAX_CODE_DUPLICATE'.
    """
    token = _login(client, "admin_sup")

    resp = client.post(
        "/api/suppliers",
        json={
            "name": "NCC Khác Tên",
            "tax_code": "0123456789",  # MST đã có từ fixture
        },
        headers=_auth_header(token),
    )

    assert resp.status_code == 409
    body = resp.get_json()
    assert body["error_code"] == "TAX_CODE_DUPLICATE"


# ============================================================
# TC-SUP-15: Thủ kho GET danh sách → 403
# ============================================================

def test_keeper_cannot_list_suppliers(client):
    """
    CA PHÂN QUYỀN: warehouse_keeper cố GET danh sách NCC.
    Kỳ vọng: 403, error_code='FORBIDDEN'.
    (Thủ kho chỉ được GET chi tiết, không được GET danh sách)
    """
    token = _login(client, "keeper_sup")

    resp = client.get(
        "/api/suppliers",
        headers=_auth_header(token),
    )

    assert resp.status_code == 403
    body = resp.get_json()
    assert body["error_code"] == "FORBIDDEN"


# ============================================================
# TC-SUP-16: Thủ kho POST tạo mới → 403
# ============================================================

def test_keeper_cannot_create_supplier(client):
    """
    CA PHÂN QUYỀN: warehouse_keeper cố tạo NCC mới.
    Kỳ vọng: 403, error_code='FORBIDDEN'.
    """
    token = _login(client, "keeper_sup")

    resp = client.post(
        "/api/suppliers",
        json={"name": "NCC từ thủ kho"},
        headers=_auth_header(token),
    )

    assert resp.status_code == 403
    body = resp.get_json()
    assert body["error_code"] == "FORBIDDEN"


# ============================================================
# TC-SUP-17: warehouse_manager DELETE → 403
# ============================================================

def test_manager_cannot_delete_supplier(client, app):
    """
    CA PHÂN QUYỀN: warehouse_manager cố DELETE NCC.
    Kỳ vọng: 403, error_code='FORBIDDEN'.
    (Chỉ admin mới được DELETE theo api_contract.md mục 2)
    """
    token = _login(client, "manager_sup")

    with app.app_context():
        supplier = Supplier.query.filter_by(name="Công ty TNHH ABC").first()
        supplier_id = supplier.id

    resp = client.delete(
        f"/api/suppliers/{supplier_id}",
        headers=_auth_header(token),
    )

    assert resp.status_code == 403
    body = resp.get_json()
    assert body["error_code"] == "FORBIDDEN"


# ============================================================
# TC-SUP-18: Không có token → 401
# ============================================================

def test_no_token_returns_401(client):
    """
    CA PHÂN QUYỀN: Gọi API không có Authorization header.
    Kỳ vọng: 401, error_code='TOKEN_MISSING'.
    """
    resp = client.get("/api/suppliers")  # Không có header

    assert resp.status_code == 401
    body = resp.get_json()
    assert body["error_code"] == "TOKEN_MISSING"


# ============================================================
# TC-SUP-19: Thủ kho GET chi tiết → 200
# ============================================================

def test_keeper_can_get_supplier_detail(client, app):
    """
    CA ĐÚNG (phân quyền): warehouse_keeper được phép GET chi tiết 1 NCC.
    Kỳ vọng: 200, trả về thông tin NCC.
    """
    token = _login(client, "keeper_sup")

    with app.app_context():
        supplier = Supplier.query.filter_by(name="Công ty TNHH ABC").first()
        supplier_id = supplier.id

    resp = client.get(
        f"/api/suppliers/{supplier_id}",
        headers=_auth_header(token),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == supplier_id
    assert data["name"] == "Công ty TNHH ABC"
