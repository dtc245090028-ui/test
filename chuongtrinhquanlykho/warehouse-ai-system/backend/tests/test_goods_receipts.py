"""
tests/test_goods_receipts.py — Test cases cho module Phiếu nhập kho
====================================================================
Bao gồm đầy đủ các ca theo mục 10 Prompt.md:

Ca ĐÚNG:
  - Nhập hợp lệ → cập nhật đúng tồn kho (quantity_on_hand tăng)
  - Nhập kèm po_id hợp lệ → phiếu nhập liên kết PO
  - Lấy danh sách phiếu nhập (phân trang)
  - Lấy chi tiết phiếu nhập theo ID

Ca LỖI / biên:
  - Nhập số lượng <= 0 → phải bị chặn (INVALID_QUANTITY)
  - Nhập đơn giá âm → phải bị chặn (INVALID_UNIT_PRICE)
  - Mã hàng không tồn tại → phải bị chặn (GOODS_NOT_FOUND)
  - NCC không tồn tại → phải bị chặn (SUPPLIER_NOT_FOUND)
  - NCC inactive → phải bị chặn (SUPPLIER_INACTIVE)
  - Items rỗng → phải bị chặn (MISSING_FIELDS)
  - Thiếu supplier_id → phải bị chặn (MISSING_FIELDS)
  - PO không tồn tại → phải bị chặn (PO_NOT_FOUND)
  - PO không khớp NCC → phải bị chặn (PO_SUPPLIER_MISMATCH)

Phân quyền:
  - warehouse_manager gọi POST → 403 FORBIDDEN
  - Không có token → 401 TOKEN_MISSING
"""

import pytest
from app.main import create_app
from app.extensions import db
from app.models.user import User
from app.models.goods import Goods
from app.models.category import Category
from app.models.supplier import Supplier
from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """
    Tạo Flask app riêng cho test — dùng SQLite in-memory để cô lập.
    Seed sẵn:
      - 1 user warehouse_keeper  (username='keeper_gr')
      - 1 user warehouse_manager (username='manager_gr')
      - 1 category (Electronics)
      - 1 supplier active (id=1)
      - 1 supplier inactive (id=2)
      - 2 goods active (sku=GR001, GR002), quantity_on_hand=50 mỗi cái
      - 1 PO (po_id=1) liên kết supplier_id=1
    """
    test_app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "JWT_EXPIRE_MINUTES": "60",
        "SECRET_KEY": "test-secret-gr-key!",
        "JWT_SECRET_KEY": "test-secret-gr-key!",
    })

    with test_app.app_context():
        db.create_all()

        # Users
        keeper = User(
            username="keeper_gr", full_name="Thủ kho Test",
            email="keeper_gr@test.local", role="warehouse_keeper", is_active=True
        )
        keeper.set_password("Password@123")

        manager = User(
            username="manager_gr", full_name="Quản lý Test",
            email="manager_gr@test.local", role="warehouse_manager", is_active=True
        )
        manager.set_password("Password@123")

        db.session.add_all([keeper, manager])

        # Category
        cat = Category(name="Electronics")
        db.session.add(cat)

        # Suppliers
        sup_active = Supplier(name="NCC Hoạt động", status="active")
        sup_inactive = Supplier(name="NCC Ngừng hợp tác", status="inactive")
        db.session.add_all([sup_active, sup_inactive])

        db.session.commit()

        # Goods
        g1 = Goods(
            sku="GR001", name="Hàng A", category_id=cat.id,
            unit="Cái", min_stock=5, quantity_on_hand=50, status="active"
        )
        g2 = Goods(
            sku="GR002", name="Hàng B", category_id=cat.id,
            unit="Hộp", min_stock=10, quantity_on_hand=50, status="active"
        )
        g_inactive = Goods(
            sku="GR999", name="Hàng ngừng KD", category_id=cat.id,
            unit="Cái", min_stock=0, quantity_on_hand=0, status="inactive"
        )
        db.session.add_all([g1, g2, g_inactive])

        db.session.commit()

        # PO — supplier_id=1 (sup_active)
        po = PurchaseOrder(
            supplier_id=sup_active.id,
            created_by=keeper.id,
            status="đã xác nhận"
        )
        db.session.add(po)
        db.session.commit()

        # PO item
        po_item = PurchaseOrderItem(
            po_id=po.id, goods_id=g1.id, quantity_ordered=100, unit_price=5000.0
        )
        db.session.add(po_item)
        db.session.commit()

    yield test_app

    with test_app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def keeper_token(client):
    res = client.post("/api/auth/login", json={"username": "keeper_gr", "password": "Password@123"})
    return res.json["access_token"]


@pytest.fixture
def keeper_headers(keeper_token):
    return {"Authorization": f"Bearer {keeper_token}"}


@pytest.fixture
def manager_token(client):
    res = client.post("/api/auth/login", json={"username": "manager_gr", "password": "Password@123"})
    return res.json["access_token"]


@pytest.fixture
def manager_headers(manager_token):
    return {"Authorization": f"Bearer {manager_token}"}


# ---------------------------------------------------------------------------
# Helper — payload nhập hợp lệ mặc định
# ---------------------------------------------------------------------------
def valid_receipt_payload(supplier_id=1, goods_id=1, quantity=20, unit_price=5000.0, **kwargs):
    payload = {
        "supplier_id": supplier_id,
        "items": [
            {"goods_id": goods_id, "quantity": quantity, "unit_price": unit_price}
        ],
    }
    payload.update(kwargs)
    return payload


# ===========================================================================
# CA ĐÚNG
# ===========================================================================

def test_create_receipt_success_updates_quantity(client, keeper_headers, app):
    """
    TC-GR-01: Nhập hợp lệ → HTTP 201, tồn kho tăng đúng lượng đã nhập.
    (Ca đúng chính — Prompt.md mục 10)
    """
    payload = valid_receipt_payload(quantity=20)
    res = client.post("/api/goods-receipts", json=payload, headers=keeper_headers)

    assert res.status_code == 201, res.json
    body = res.json
    assert body["supplier_id"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["quantity"] == 20
    assert body["items"][0]["unit_price"] == 5000.0  # snapshot đúng

    # Kiểm tra tồn kho đã được cập nhật (50 + 20 = 70)
    with app.app_context():
        from app.models.goods import Goods
        g = Goods.query.filter_by(sku="GR001").first()
        assert g.quantity_on_hand == 70.0


def test_create_receipt_multiple_items(client, keeper_headers, app):
    """
    TC-GR-02: Nhập nhiều dòng hàng trong 1 phiếu → tồn kho từng mặt hàng đều tăng đúng.
    """
    payload = {
        "supplier_id": 1,
        "items": [
            {"goods_id": 1, "quantity": 10, "unit_price": 5000.0},
            {"goods_id": 2, "quantity": 30, "unit_price": 8000.0},
        ],
    }
    res = client.post("/api/goods-receipts", json=payload, headers=keeper_headers)
    assert res.status_code == 201

    with app.app_context():
        from app.models.goods import Goods
        g1 = Goods.query.filter_by(sku="GR001").first()
        g2 = Goods.query.filter_by(sku="GR002").first()
        assert g1.quantity_on_hand == 60.0  # 50 + 10
        assert g2.quantity_on_hand == 80.0  # 50 + 30


def test_create_receipt_with_po_id(client, keeper_headers, app):
    """
    TC-GR-03: Nhập có kèm po_id hợp lệ → phiếu nhập liên kết PO, HTTP 201.
    """
    payload = valid_receipt_payload(po_id=1)
    res = client.post("/api/goods-receipts", json=payload, headers=keeper_headers)
    assert res.status_code == 201
    assert res.json["po_id"] == 1


def test_create_receipt_unit_price_is_snapshot(client, keeper_headers, app):
    """
    TC-GR-04: unit_price lưu cố định đúng với giá lúc nhập.
    Xác nhận ràng buộc api_contract.md mục 5 — 'unit_price lưu cố định theo lần nhập'.
    """
    payload = valid_receipt_payload(unit_price=12345.67)
    res = client.post("/api/goods-receipts", json=payload, headers=keeper_headers)
    assert res.status_code == 201
    assert res.json["items"][0]["unit_price"] == 12345.67


def test_get_receipts_list(client, keeper_headers):
    """
    TC-GR-05: GET danh sách → HTTP 200, cấu trúc phân trang chuẩn.
    """
    # Tạo trước 1 phiếu
    client.post("/api/goods-receipts", json=valid_receipt_payload(), headers=keeper_headers)

    res = client.get("/api/goods-receipts", headers=keeper_headers)
    assert res.status_code == 200
    body = res.json
    assert "total" in body
    assert "page" in body
    assert "page_size" in body
    assert "data" in body
    assert body["total"] >= 1


def test_get_receipt_detail(client, keeper_headers):
    """
    TC-GR-06: GET chi tiết theo ID → HTTP 200, có mảng items.
    """
    res_create = client.post(
        "/api/goods-receipts", json=valid_receipt_payload(), headers=keeper_headers
    )
    receipt_id = res_create.json["id"]

    res = client.get(f"/api/goods-receipts/{receipt_id}", headers=keeper_headers)
    assert res.status_code == 200
    assert res.json["id"] == receipt_id
    assert "items" in res.json


def test_manager_can_read_receipts(client, manager_headers):
    """
    TC-GR-07: Quản lý kho (warehouse_manager) được phép đọc danh sách và chi tiết.
    """
    res = client.get("/api/goods-receipts", headers=manager_headers)
    assert res.status_code == 200


def test_filter_by_supplier(client, keeper_headers):
    """
    TC-GR-08: Filter danh sách theo supplier_id → chỉ trả phiếu nhập của NCC đó.
    """
    client.post("/api/goods-receipts", json=valid_receipt_payload(supplier_id=1), headers=keeper_headers)

    res = client.get("/api/goods-receipts?supplier_id=1", headers=keeper_headers)
    assert res.status_code == 200
    for item in res.json["data"]:
        assert item["supplier_id"] == 1


# ===========================================================================
# CA LỖI / BIÊN
# ===========================================================================

def test_create_receipt_invalid_quantity_zero(client, keeper_headers):
    """
    TC-GR-E01: quantity = 0 → 400 INVALID_QUANTITY.
    (Prompt.md mục 10 — ca lỗi/biên bắt buộc)
    """
    payload = valid_receipt_payload(quantity=0)
    res = client.post("/api/goods-receipts", json=payload, headers=keeper_headers)
    assert res.status_code == 400
    assert res.json["error_code"] == "INVALID_QUANTITY"


def test_create_receipt_invalid_quantity_negative(client, keeper_headers):
    """
    TC-GR-E02: quantity âm → 400 INVALID_QUANTITY.
    """
    payload = valid_receipt_payload(quantity=-5)
    res = client.post("/api/goods-receipts", json=payload, headers=keeper_headers)
    assert res.status_code == 400
    assert res.json["error_code"] == "INVALID_QUANTITY"


def test_create_receipt_negative_unit_price(client, keeper_headers):
    """
    TC-GR-E03: unit_price âm → 400 INVALID_UNIT_PRICE.
    """
    payload = valid_receipt_payload(unit_price=-100)
    res = client.post("/api/goods-receipts", json=payload, headers=keeper_headers)
    assert res.status_code == 400
    assert res.json["error_code"] == "INVALID_UNIT_PRICE"


def test_create_receipt_goods_not_found(client, keeper_headers):
    """
    TC-GR-E04: goods_id không tồn tại → 404 GOODS_NOT_FOUND.
    (Prompt.md mục 10 — ca lỗi/biên bắt buộc)
    """
    payload = valid_receipt_payload(goods_id=9999)
    res = client.post("/api/goods-receipts", json=payload, headers=keeper_headers)
    assert res.status_code == 404
    assert res.json["error_code"] == "GOODS_NOT_FOUND"


def test_create_receipt_supplier_not_found(client, keeper_headers):
    """
    TC-GR-E05: supplier_id không tồn tại → 404 SUPPLIER_NOT_FOUND.
    """
    payload = valid_receipt_payload(supplier_id=9999)
    res = client.post("/api/goods-receipts", json=payload, headers=keeper_headers)
    assert res.status_code == 404
    assert res.json["error_code"] == "SUPPLIER_NOT_FOUND"


def test_create_receipt_supplier_inactive(client, keeper_headers, app):
    """
    TC-GR-E06: supplier_id inactive → 400 SUPPLIER_INACTIVE.
    """
    # supplier_id=2 là NCC inactive (seed trong fixture)
    with app.app_context():
        sup = Supplier.query.filter_by(name="NCC Ngừng hợp tác").first()
        sup_id = sup.id

    payload = valid_receipt_payload(supplier_id=sup_id)
    res = client.post("/api/goods-receipts", json=payload, headers=keeper_headers)
    assert res.status_code == 400
    assert res.json["error_code"] == "SUPPLIER_INACTIVE"


def test_create_receipt_goods_inactive(client, keeper_headers, app):
    """
    TC-GR-E07: goods_id inactive → 400 GOODS_INACTIVE.
    """
    with app.app_context():
        g = Goods.query.filter_by(sku="GR999").first()
        g_id = g.id

    payload = valid_receipt_payload(goods_id=g_id)
    res = client.post("/api/goods-receipts", json=payload, headers=keeper_headers)
    assert res.status_code == 400
    assert res.json["error_code"] == "GOODS_INACTIVE"


def test_create_receipt_empty_items(client, keeper_headers):
    """
    TC-GR-E08: items rỗng [] → 400 MISSING_FIELDS.
    """
    payload = {"supplier_id": 1, "items": []}
    res = client.post("/api/goods-receipts", json=payload, headers=keeper_headers)
    assert res.status_code == 400
    assert res.json["error_code"] == "MISSING_FIELDS"


def test_create_receipt_missing_supplier_id(client, keeper_headers):
    """
    TC-GR-E09: Thiếu supplier_id → 400 MISSING_FIELDS.
    """
    payload = {"items": [{"goods_id": 1, "quantity": 10, "unit_price": 5000}]}
    res = client.post("/api/goods-receipts", json=payload, headers=keeper_headers)
    assert res.status_code == 400
    assert res.json["error_code"] == "MISSING_FIELDS"


def test_create_receipt_po_not_found(client, keeper_headers):
    """
    TC-GR-E10: po_id không tồn tại → 404 PO_NOT_FOUND.
    """
    payload = valid_receipt_payload(po_id=9999)
    res = client.post("/api/goods-receipts", json=payload, headers=keeper_headers)
    assert res.status_code == 404
    assert res.json["error_code"] == "PO_NOT_FOUND"


def test_create_receipt_po_supplier_mismatch(client, keeper_headers, app):
    """
    TC-GR-E11: po_id thuộc supplier khác → 400 PO_SUPPLIER_MISMATCH.
    Kịch bản: PO (po_id=1) thuộc supplier_id=1, nhưng yêu cầu dùng supplier_id=2.
    """
    with app.app_context():
        sup = Supplier.query.filter_by(name="NCC Ngừng hợp tác").first()
        # Tạm thời đổi sup sang active để test mismatch (không phải test inactive)
        sup.status = "active"
        db.session.commit()
        sup_id = sup.id

    # po_id=1 thuộc supplier_id=1, nhưng ta truyền supplier_id=sup_id(2) → mismatch
    payload = {"supplier_id": sup_id, "po_id": 1, "items": [
        {"goods_id": 1, "quantity": 10, "unit_price": 5000}
    ]}
    res = client.post("/api/goods-receipts", json=payload, headers=keeper_headers)
    assert res.status_code == 400
    assert res.json["error_code"] == "PO_SUPPLIER_MISMATCH"


# ===========================================================================
# PHÂN QUYỀN
# ===========================================================================

def test_manager_cannot_create_receipt(client, manager_headers):
    """
    TC-GR-P01: warehouse_manager gọi POST → 403 FORBIDDEN.
    (Chỉ warehouse_keeper được lập phiếu nhập — api_contract.md mục 5)
    """
    res = client.post(
        "/api/goods-receipts", json=valid_receipt_payload(), headers=manager_headers
    )
    assert res.status_code == 403
    assert res.json["error_code"] == "FORBIDDEN"


def test_no_token_returns_401(client):
    """
    TC-GR-P02: Không có token → 401 TOKEN_MISSING.
    """
    res = client.get("/api/goods-receipts")
    assert res.status_code == 401
    assert res.json["error_code"] == "TOKEN_MISSING"


def test_get_receipt_not_found(client, keeper_headers):
    """
    TC-GR-E12: GET chi tiết ID không tồn tại → 404 RECEIPT_NOT_FOUND.
    """
    res = client.get("/api/goods-receipts/9999", headers=keeper_headers)
    assert res.status_code == 404
    assert res.json["error_code"] == "RECEIPT_NOT_FOUND"
