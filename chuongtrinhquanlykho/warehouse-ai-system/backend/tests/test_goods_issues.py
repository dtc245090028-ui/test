"""
tests/test_goods_issues.py — Test cases cho module Phiếu xuất kho
==================================================================
Bao gồm đầy đủ các ca theo mục 10 Prompt.md:

Ca ĐÚNG:
  TC01 - Xuất hợp lệ 1 dòng → quantity_on_hand giảm đúng
  TC02 - Xuất hợp lệ nhiều dòng → tất cả tồn kho giảm đúng
  TC03 - Xuất đúng bằng tồn kho hiện tại (biên trên — cho phép)
  TC04 - Xuất kèm issued_date và note tùy chọn
  TC05 - GET danh sách phiếu xuất (phân trang)
  TC06 - GET danh sách với filter date_from, date_to
  TC07 - GET chi tiết phiếu xuất theo ID (kèm items)

Ca LỖI / biên:
  TC08 - Xuất số lượng = 0 → INVALID_QUANTITY
  TC09 - Xuất số lượng âm → INVALID_QUANTITY
  TC10 - Xuất vượt tồn kho → INSUFFICIENT_STOCK (nghiệp vụ cốt lõi)
  TC11 - Items rỗng → MISSING_FIELDS
  TC12 - Thiếu goods_id trong item → MISSING_FIELDS
  TC13 - goods_id không tồn tại → GOODS_NOT_FOUND
  TC14 - Goods inactive → GOODS_INACTIVE
  TC15 - issued_date sai định dạng → INVALID_DATE_FORMAT
  TC16 - GET chi tiết ID không tồn tại → ISSUE_NOT_FOUND

Phân quyền:
  TC17 - warehouse_manager gọi POST → 403 FORBIDDEN
  TC18 - Không có token → 401 TOKEN_MISSING
"""

import pytest
from app.main import create_app
from app.extensions import db
from app.models.user import User
from app.models.goods import Goods
from app.models.category import Category
from app.models.supplier import Supplier


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """
    Tạo Flask app riêng cho test — dùng SQLite in-memory để cô lập.
    Seed sẵn:
      - 1 user warehouse_keeper  (username='keeper_gi')
      - 1 user warehouse_manager (username='manager_gi')
      - 1 category (Electronics)
      - 1 supplier active
      - 2 goods active (sku=GI001 tồn=100, sku=GI002 tồn=50)
      - 1 goods inactive (sku=GI003)
    """
    test_app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "JWT_EXPIRE_MINUTES": "60",
        "SECRET_KEY": "test-secret-gi-key!",
        "JWT_SECRET_KEY": "test-secret-gi-key!",
    })

    with test_app.app_context():
        db.create_all()

        # Users
        keeper = User(
            username="keeper_gi", full_name="Thủ kho Test",
            email="keeper_gi@test.local", role="warehouse_keeper", is_active=True
        )
        keeper.set_password("Password@123")

        manager = User(
            username="manager_gi", full_name="Quản lý Test",
            email="manager_gi@test.local", role="warehouse_manager", is_active=True
        )
        manager.set_password("Password@123")

        db.session.add_all([keeper, manager])

        # Category
        cat = Category(name="Thiết bị điện tử")
        db.session.add(cat)

        # Supplier
        sup = Supplier(name="NCC Test", status="active")
        db.session.add(sup)

        db.session.commit()

        # Goods
        g1 = Goods(
            sku="GI001", name="Hàng A", category_id=cat.id,
            unit="Cái", min_stock=5, quantity_on_hand=100, status="active"
        )
        g2 = Goods(
            sku="GI002", name="Hàng B", category_id=cat.id,
            unit="Hộp", min_stock=10, quantity_on_hand=50, status="active"
        )
        g3 = Goods(
            sku="GI003", name="Hàng Ngừng", category_id=cat.id,
            unit="Kg", min_stock=0, quantity_on_hand=0, status="inactive"
        )
        db.session.add_all([g1, g2, g3])
        db.session.commit()

    yield test_app

    # Teardown: xóa DB in-memory sau mỗi test
    with test_app.app_context():
        db.drop_all()


@pytest.fixture
def client(app):
    """HTTP test client của Flask."""
    return app.test_client()


@pytest.fixture
def keeper_token(client):
    """
    Đăng nhập với tài khoản warehouse_keeper, trả về JWT token.
    Dùng cho các test cần quyền Thủ kho.
    """
    res = client.post("/api/auth/login", json={
        "username": "keeper_gi",
        "password": "Password@123"
    })
    return res.get_json()["access_token"]


@pytest.fixture
def manager_token(client):
    """
    Đăng nhập với tài khoản warehouse_manager, trả về JWT token.
    Dùng để kiểm tra phân quyền (POST → 403).
    """
    res = client.post("/api/auth/login", json={
        "username": "manager_gi",
        "password": "Password@123"
    })
    return res.get_json()["access_token"]


def auth_header(token):
    """Tiện ích tạo header Authorization cho mọi request cần xác thực."""
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# TC01 — Xuất hợp lệ 1 dòng → quantity_on_hand giảm đúng
# ---------------------------------------------------------------------------
def test_create_issue_valid_single_item(client, keeper_token, app):
    """
    Ca ĐÚNG: Xuất 30 cái Hàng A (tồn ban đầu 100).
    Sau xuất: quantity_on_hand = 70. Phiếu xuất phải có items.
    """
    res = client.post("/api/goods-issues",
        json={
            "note": "Xuất cho bộ phận kinh doanh",
            "items": [{"goods_id": 1, "quantity": 30}]
        },
        headers=auth_header(keeper_token)
    )
    assert res.status_code == 201
    data = res.get_json()
    assert data["id"] is not None
    assert data["note"] == "Xuất cho bộ phận kinh doanh"
    assert len(data["items"]) == 1
    assert data["items"][0]["goods_id"] == 1
    assert data["items"][0]["quantity"] == 30

    # Kiểm tra tồn kho đã giảm đúng trong DB
    with app.app_context():
        g = Goods.query.get(1)
        assert g.quantity_on_hand == 70


# ---------------------------------------------------------------------------
# TC02 — Xuất hợp lệ nhiều dòng → tất cả tồn kho giảm đúng
# ---------------------------------------------------------------------------
def test_create_issue_valid_multiple_items(client, keeper_token, app):
    """
    Ca ĐÚNG: Xuất nhiều mặt hàng cùng lúc.
    Hàng A: xuất 10 (tồn 100 → 90)
    Hàng B: xuất 5  (tồn 50  → 45)
    """
    res = client.post("/api/goods-issues",
        json={
            "items": [
                {"goods_id": 1, "quantity": 10},
                {"goods_id": 2, "quantity": 5},
            ]
        },
        headers=auth_header(keeper_token)
    )
    assert res.status_code == 201
    data = res.get_json()
    assert len(data["items"]) == 2

    with app.app_context():
        assert Goods.query.get(1).quantity_on_hand == 90
        assert Goods.query.get(2).quantity_on_hand == 45


# ---------------------------------------------------------------------------
# TC03 — Xuất đúng bằng tồn kho (biên trên — vẫn hợp lệ)
# ---------------------------------------------------------------------------
def test_create_issue_exact_stock(client, keeper_token, app):
    """
    Ca biên ĐÚNG: Xuất đúng bằng tồn kho hiện tại.
    Hàng B tồn = 50, xuất 50 → tồn còn 0. Phải cho phép.
    """
    res = client.post("/api/goods-issues",
        json={
            "items": [{"goods_id": 2, "quantity": 50}]
        },
        headers=auth_header(keeper_token)
    )
    assert res.status_code == 201

    with app.app_context():
        assert Goods.query.get(2).quantity_on_hand == 0


# ---------------------------------------------------------------------------
# TC04 — Xuất kèm issued_date và note
# ---------------------------------------------------------------------------
def test_create_issue_with_issued_date_and_note(client, keeper_token, app):
    """
    Ca ĐÚNG: Truyền issued_date ISO 8601 và note.
    """
    res = client.post("/api/goods-issues",
        json={
            "issued_date": "2026-08-10T14:30:00Z",
            "note": "Xuất phục vụ sự kiện tháng 8",
            "items": [{"goods_id": 1, "quantity": 5}]
        },
        headers=auth_header(keeper_token)
    )
    assert res.status_code == 201
    data = res.get_json()
    # issued_date phải được lưu (dù ở định dạng khác timezone)
    assert data["issued_date"] is not None
    assert data["note"] == "Xuất phục vụ sự kiện tháng 8"


# ---------------------------------------------------------------------------
# TC05 — GET danh sách phiếu xuất (phân trang)
# ---------------------------------------------------------------------------
def test_get_goods_issues_list(client, keeper_token):
    """
    Ca ĐÚNG: Lấy danh sách phiếu xuất với phân trang chuẩn.
    Tạo 2 phiếu rồi lấy danh sách → total = 2.
    """
    # Tạo 2 phiếu xuất
    for qty in [10, 20]:
        client.post("/api/goods-issues",
            json={"items": [{"goods_id": 1, "quantity": qty}]},
            headers=auth_header(keeper_token)
        )

    res = client.get("/api/goods-issues", headers=auth_header(keeper_token))
    assert res.status_code == 200
    data = res.get_json()
    assert data["total"] == 2
    assert "page" in data
    assert "page_size" in data
    assert isinstance(data["data"], list)
    # Danh sách không có items (chỉ header)
    for item in data["data"]:
        assert "items" not in item


# ---------------------------------------------------------------------------
# TC06 — GET danh sách với filter date_from, date_to
# ---------------------------------------------------------------------------
def test_get_goods_issues_filter_date(client, keeper_token):
    """
    Ca ĐÚNG: Filter theo khoảng ngày.
    Filter ngoài phạm vi → total = 0.
    """
    # Tạo 1 phiếu
    client.post("/api/goods-issues",
        json={"items": [{"goods_id": 1, "quantity": 5}]},
        headers=auth_header(keeper_token)
    )

    # Filter ngày xa trong tương lai → không có kết quả
    res = client.get(
        "/api/goods-issues?date_from=2030-01-01",
        headers=auth_header(keeper_token)
    )
    assert res.status_code == 200
    assert res.get_json()["total"] == 0


# ---------------------------------------------------------------------------
# TC07 — GET chi tiết phiếu xuất theo ID (kèm items)
# ---------------------------------------------------------------------------
def test_get_goods_issue_detail(client, keeper_token):
    """
    Ca ĐÚNG: Tạo phiếu rồi lấy chi tiết theo ID.
    Chi tiết phải bao gồm mảng items đầy đủ.
    """
    create_res = client.post("/api/goods-issues",
        json={
            "note": "Test chi tiết",
            "items": [{"goods_id": 1, "quantity": 15}]
        },
        headers=auth_header(keeper_token)
    )
    issue_id = create_res.get_json()["id"]

    res = client.get(f"/api/goods-issues/{issue_id}", headers=auth_header(keeper_token))
    assert res.status_code == 200
    data = res.get_json()
    assert data["id"] == issue_id
    assert data["note"] == "Test chi tiết"
    assert "items" in data
    assert len(data["items"]) == 1
    assert data["items"][0]["quantity"] == 15


# ---------------------------------------------------------------------------
# TC08 — Xuất số lượng = 0 → INVALID_QUANTITY
# ---------------------------------------------------------------------------
def test_create_issue_quantity_zero(client, keeper_token):
    """
    Ca LỖI: quantity = 0 → phải bị chặn với INVALID_QUANTITY.
    (Prompt.md mục 10 — ca lỗi/biên)
    """
    res = client.post("/api/goods-issues",
        json={"items": [{"goods_id": 1, "quantity": 0}]},
        headers=auth_header(keeper_token)
    )
    assert res.status_code == 400
    assert res.get_json()["error_code"] == "INVALID_QUANTITY"


# ---------------------------------------------------------------------------
# TC09 — Xuất số lượng âm → INVALID_QUANTITY
# ---------------------------------------------------------------------------
def test_create_issue_quantity_negative(client, keeper_token):
    """
    Ca LỖI: quantity < 0 → phải bị chặn với INVALID_QUANTITY.
    """
    res = client.post("/api/goods-issues",
        json={"items": [{"goods_id": 1, "quantity": -5}]},
        headers=auth_header(keeper_token)
    )
    assert res.status_code == 400
    assert res.get_json()["error_code"] == "INVALID_QUANTITY"


# ---------------------------------------------------------------------------
# TC10 — Xuất vượt tồn kho → INSUFFICIENT_STOCK (nghiệp vụ cốt lõi)
# ---------------------------------------------------------------------------
def test_create_issue_exceeds_stock(client, keeper_token, app):
    """
    Ca LỖI NGHIỆP VỤ CỐT LÕI:
    Hàng A tồn = 100, xuất 101 → phải bị chặn với INSUFFICIENT_STOCK.
    quantity_on_hand KHÔNG được thay đổi sau khi bị chặn.
    (Prompt.md mục 3.3: "không cho xuất vượt tồn (tồn kho âm)")
    """
    res = client.post("/api/goods-issues",
        json={"items": [{"goods_id": 1, "quantity": 101}]},
        headers=auth_header(keeper_token)
    )
    assert res.status_code == 400
    data = res.get_json()
    assert data["error_code"] == "INSUFFICIENT_STOCK"
    # Thông báo lỗi phải có tên hàng, số lượng yêu cầu và tồn hiện tại
    assert "Hàng A" in data["message"]

    # Quan trọng: tồn kho KHÔNG được thay đổi (rollback thành công)
    with app.app_context():
        g = Goods.query.get(1)
        assert g.quantity_on_hand == 100


# ---------------------------------------------------------------------------
# TC11 — Items rỗng → MISSING_FIELDS
# ---------------------------------------------------------------------------
def test_create_issue_empty_items(client, keeper_token):
    """
    Ca LỖI: items = [] → phải bị chặn với MISSING_FIELDS.
    """
    res = client.post("/api/goods-issues",
        json={"items": []},
        headers=auth_header(keeper_token)
    )
    assert res.status_code == 400
    assert res.get_json()["error_code"] == "MISSING_FIELDS"


# ---------------------------------------------------------------------------
# TC12 — Thiếu goods_id trong item → MISSING_FIELDS
# ---------------------------------------------------------------------------
def test_create_issue_missing_goods_id(client, keeper_token):
    """
    Ca LỖI: một dòng item không có goods_id → MISSING_FIELDS.
    """
    res = client.post("/api/goods-issues",
        json={"items": [{"quantity": 10}]},
        headers=auth_header(keeper_token)
    )
    assert res.status_code == 400
    assert res.get_json()["error_code"] == "MISSING_FIELDS"


# ---------------------------------------------------------------------------
# TC13 — goods_id không tồn tại → GOODS_NOT_FOUND
# ---------------------------------------------------------------------------
def test_create_issue_goods_not_found(client, keeper_token):
    """
    Ca LỖI: goods_id=999 không tồn tại trong DB → GOODS_NOT_FOUND.
    """
    res = client.post("/api/goods-issues",
        json={"items": [{"goods_id": 999, "quantity": 5}]},
        headers=auth_header(keeper_token)
    )
    assert res.status_code == 404
    assert res.get_json()["error_code"] == "GOODS_NOT_FOUND"


# ---------------------------------------------------------------------------
# TC14 — Goods inactive → GOODS_INACTIVE
# ---------------------------------------------------------------------------
def test_create_issue_goods_inactive(client, keeper_token):
    """
    Ca LỖI: Hàng GI003 có status='inactive' → GOODS_INACTIVE.
    """
    res = client.post("/api/goods-issues",
        json={"items": [{"goods_id": 3, "quantity": 1}]},
        headers=auth_header(keeper_token)
    )
    assert res.status_code == 400
    assert res.get_json()["error_code"] == "GOODS_INACTIVE"


# ---------------------------------------------------------------------------
# TC15 — issued_date sai định dạng → INVALID_DATE_FORMAT
# ---------------------------------------------------------------------------
def test_create_issue_invalid_date_format(client, keeper_token):
    """
    Ca LỖI: issued_date không phải ISO 8601 → INVALID_DATE_FORMAT.
    """
    res = client.post("/api/goods-issues",
        json={
            "issued_date": "14/08/2026 08:00",  # sai định dạng
            "items": [{"goods_id": 1, "quantity": 5}]
        },
        headers=auth_header(keeper_token)
    )
    assert res.status_code == 400
    assert res.get_json()["error_code"] == "INVALID_DATE_FORMAT"


# ---------------------------------------------------------------------------
# TC16 — GET chi tiết ID không tồn tại → ISSUE_NOT_FOUND
# ---------------------------------------------------------------------------
def test_get_goods_issue_detail_not_found(client, keeper_token):
    """
    Ca LỖI: GET /api/goods-issues/9999 → ISSUE_NOT_FOUND.
    """
    res = client.get("/api/goods-issues/9999", headers=auth_header(keeper_token))
    assert res.status_code == 404
    assert res.get_json()["error_code"] == "ISSUE_NOT_FOUND"


# ---------------------------------------------------------------------------
# TC17 — warehouse_manager gọi POST → 403 FORBIDDEN
# ---------------------------------------------------------------------------
def test_create_issue_forbidden_for_manager(client, manager_token):
    """
    Ca PHÂN QUYỀN: warehouse_manager không được lập phiếu xuất.
    POST → 403 FORBIDDEN.
    (Prompt.md mục 3.1: Thủ kho mới có quyền xuất kho)
    """
    res = client.post("/api/goods-issues",
        json={"items": [{"goods_id": 1, "quantity": 5}]},
        headers=auth_header(manager_token)
    )
    assert res.status_code == 403
    assert res.get_json()["error_code"] == "FORBIDDEN"


# ---------------------------------------------------------------------------
# TC18 — Không có token → 401 TOKEN_MISSING
# ---------------------------------------------------------------------------
def test_create_issue_no_token(client):
    """
    Ca PHÂN QUYỀN: Không có Authorization header → 401 TOKEN_MISSING.
    """
    res = client.post("/api/goods-issues",
        json={"items": [{"goods_id": 1, "quantity": 5}]}
    )
    assert res.status_code == 401
    assert res.get_json()["error_code"] == "TOKEN_MISSING"
