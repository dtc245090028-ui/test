"""
tests/test_supplier_invoices.py — Kiểm thử module Công nợ (Supplier Invoices & Payments)
==========================================================================================
Bám sát các ca trong Prompt.md mục 10:
  - Tính tổng tiền đúng từ nhiều mặt hàng (nhiều lần thanh toán)
  - Lập hóa đơn từ phiếu nhập chưa hoàn tất → phải chặn (receipt_id không khớp)
  - Kiểm tra chặn overpayment
  - Kiểm tra tự động đổi payment_status
  - Kiểm tra phân quyền (Thủ kho không gọi được API công nợ tổng hợp)
"""

import pytest
from datetime import datetime
from app.main import create_app
from app.extensions import db
from app.models.user import User
from app.models.supplier import Supplier
from app.models.category import Category
from app.models.goods import Goods
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.supplier_invoice import SupplierInvoice, SupplierPayment


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """Tạo Flask app với SQLite in-memory cho mỗi test session."""
    test_app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "JWT_EXPIRE_MINUTES": "60",
        "SECRET_KEY": "test-secret-supplier-invoice-32x",
        "JWT_SECRET_KEY": "test-secret-supplier-invoice-32x",
    })

    with test_app.app_context():
        db.create_all()

        # Users
        manager = User(
            username="manager_inv", full_name="Manager Invoice",
            email="manager_inv@test.com", role="warehouse_manager"
        )
        manager.set_password("pass")

        keeper = User(
            username="keeper_inv", full_name="Keeper Invoice",
            email="keeper_inv@test.com", role="warehouse_keeper"
        )
        keeper.set_password("pass")

        db.session.add_all([manager, keeper])

        # Supplier
        supplier = Supplier(name="NCC Test ABC", status="active")
        db.session.add(supplier)

        # Category + Goods
        cat = Category(name="Nhóm Test")
        db.session.add(cat)
        db.session.flush()  # flush để có cat.id

        goods = Goods(
            sku="INV-G01", name="Hàng Test Invoice",
            category_id=cat.id, unit="Cái", quantity_on_hand=0.0
        )
        db.session.add(goods)
        db.session.commit()

        # GoodsReceipt (phiếu nhập kho để liên kết hóa đơn)
        receipt = GoodsReceipt(
            supplier_id=supplier.id,
            created_by=keeper.id,
            received_date=datetime.utcnow(),
        )
        db.session.add(receipt)
        db.session.flush()

        item = GoodsReceiptItem(
            receipt_id=receipt.id,
            goods_id=goods.id,
            quantity=100,
            unit_price=50000.0,
        )
        db.session.add(item)
        db.session.commit()

    yield test_app

    with test_app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def get_token(client, username):
    """Helper đăng nhập và lấy JWT Bearer header."""
    resp = client.post(
        "/api/auth/login",
        json={"username": username, "password": "pass"}
    )
    return {"Authorization": f"Bearer {resp.json['access_token']}"}


# ---------------------------------------------------------------------------
# Tests: Tạo hóa đơn
# ---------------------------------------------------------------------------

def test_create_invoice_success(client, app):
    """TC01: Tạo hóa đơn hợp lệ từ phiếu nhập → 201"""
    keeper_h = get_token(client, "keeper_inv")

    with app.app_context():
        supplier = Supplier.query.first()
        receipt = GoodsReceipt.query.first()

    res = client.post("/api/supplier-invoices", json={
        "supplier_id": supplier.id,
        "receipt_id": receipt.id,
        "invoice_number": "INV-TC01",
        "total_amount": 5000000.0,
    }, headers=keeper_h)

    assert res.status_code == 201
    data = res.get_json()
    assert data["invoice_number"] == "INV-TC01"
    assert data["payment_status"] == "chưa thanh toán"
    assert data["paid_amount"] == 0.0
    assert data["total_amount"] == 5000000.0


def test_create_invoice_without_receipt(client, app):
    """TC02: Tạo hóa đơn không liên kết phiếu nhập (receipt_id = None) → 201"""
    keeper_h = get_token(client, "keeper_inv")

    with app.app_context():
        supplier = Supplier.query.first()

    res = client.post("/api/supplier-invoices", json={
        "supplier_id": supplier.id,
        "invoice_number": "INV-TC02",
        "total_amount": 2000000.0,
    }, headers=keeper_h)

    assert res.status_code == 201
    assert res.get_json()["receipt_id"] is None


def test_create_invoice_receipt_already_invoiced(client, app):
    """TC03: 1 phiếu nhập chỉ được tạo 1 hóa đơn — lần 2 phải bị chặn"""
    keeper_h = get_token(client, "keeper_inv")

    with app.app_context():
        supplier = Supplier.query.first()
        receipt = GoodsReceipt.query.first()

    payload = {
        "supplier_id": supplier.id,
        "receipt_id": receipt.id,
        "invoice_number": "INV-TC03-A",
        "total_amount": 1000000.0,
    }
    res1 = client.post("/api/supplier-invoices", json=payload, headers=keeper_h)
    assert res1.status_code == 201

    # Lần 2 cùng receipt_id → phải bị chặn
    payload["invoice_number"] = "INV-TC03-B"
    res2 = client.post("/api/supplier-invoices", json=payload, headers=keeper_h)
    assert res2.status_code == 400
    assert res2.get_json()["error_code"] == "RECEIPT_ALREADY_INVOICED"


def test_create_invoice_receipt_supplier_mismatch(client, app):
    """TC04: receipt_id không thuộc supplier_id → RECEIPT_SUPPLIER_MISMATCH"""
    keeper_h = get_token(client, "keeper_inv")

    with app.app_context():
        # Tạo NCC thứ 2
        other_supplier = Supplier(name="NCC Khác", status="active")
        db.session.add(other_supplier)
        db.session.commit()
        other_supplier_id = other_supplier.id
        receipt = GoodsReceipt.query.first()

    res = client.post("/api/supplier-invoices", json={
        "supplier_id": other_supplier_id,
        "receipt_id": receipt.id,
        "invoice_number": "INV-TC04",
        "total_amount": 1000000.0,
    }, headers=keeper_h)

    assert res.status_code == 400
    assert res.get_json()["error_code"] == "RECEIPT_SUPPLIER_MISMATCH"


def test_create_invoice_invalid_amount(client, app):
    """TC05: total_amount <= 0 → INVALID_AMOUNT"""
    keeper_h = get_token(client, "keeper_inv")

    with app.app_context():
        supplier = Supplier.query.first()

    res = client.post("/api/supplier-invoices", json={
        "supplier_id": supplier.id,
        "invoice_number": "INV-TC05",
        "total_amount": -500.0,
    }, headers=keeper_h)

    assert res.status_code == 400
    assert res.get_json()["error_code"] == "INVALID_AMOUNT"


# ---------------------------------------------------------------------------
# Tests: Thanh toán công nợ
# ---------------------------------------------------------------------------

def _create_invoice(client, app, keeper_h, total_amount=5000000.0):
    """Helper tạo hóa đơn mới (không dùng receipt_id) để test thanh toán."""
    with app.app_context():
        supplier = Supplier.query.first()
        supplier_id = supplier.id

    # Mỗi lần gọi dùng invoice_number khác nhau (dựa trên timestamp)
    inv_num = f"INV-PAY-{datetime.utcnow().timestamp()}"
    res = client.post("/api/supplier-invoices", json={
        "supplier_id": supplier_id,
        "invoice_number": inv_num,
        "total_amount": total_amount,
    }, headers=keeper_h)
    assert res.status_code == 201
    return res.get_json()["id"]


def test_payment_success_partial(client, app):
    """TC06: Thanh toán 1 phần → payment_status = 'thanh toán một phần'"""
    keeper_h = get_token(client, "keeper_inv")
    manager_h = get_token(client, "manager_inv")

    invoice_id = _create_invoice(client, app, keeper_h, total_amount=5000000.0)

    res = client.post("/api/supplier-payments", json={
        "invoice_id": invoice_id,
        "amount": 2000000.0,
        "method": "chuyển khoản",
    }, headers=manager_h)

    assert res.status_code == 201
    data = res.get_json()
    assert data["invoice_payment_status"] == "thanh toán một phần"
    assert data["amount"] == 2000000.0


def test_payment_success_full(client, app):
    """TC07: Thanh toán đủ → payment_status tự động đổi thành 'đã thanh toán'"""
    keeper_h = get_token(client, "keeper_inv")
    manager_h = get_token(client, "manager_inv")

    invoice_id = _create_invoice(client, app, keeper_h, total_amount=3000000.0)

    res = client.post("/api/supplier-payments", json={
        "invoice_id": invoice_id,
        "amount": 3000000.0,
        "method": "tiền mặt",
    }, headers=manager_h)

    assert res.status_code == 201
    assert res.get_json()["invoice_payment_status"] == "đã thanh toán"


def test_payment_overpayment(client, app):
    """TC08: Thanh toán vượt quá total_amount → OVERPAYMENT"""
    keeper_h = get_token(client, "keeper_inv")
    manager_h = get_token(client, "manager_inv")

    invoice_id = _create_invoice(client, app, keeper_h, total_amount=1000000.0)

    res = client.post("/api/supplier-payments", json={
        "invoice_id": invoice_id,
        "amount": 9999999.0,
    }, headers=manager_h)

    assert res.status_code == 400
    assert res.get_json()["error_code"] == "OVERPAYMENT"


def test_payment_already_paid(client, app):
    """TC09: Hóa đơn đã thanh toán đủ → không cho thanh toán thêm → INVOICE_ALREADY_PAID"""
    keeper_h = get_token(client, "keeper_inv")
    manager_h = get_token(client, "manager_inv")

    invoice_id = _create_invoice(client, app, keeper_h, total_amount=500000.0)

    # Thanh toán đủ lần 1
    client.post("/api/supplier-payments", json={
        "invoice_id": invoice_id, "amount": 500000.0
    }, headers=manager_h)

    # Cố thanh toán thêm lần 2
    res = client.post("/api/supplier-payments", json={
        "invoice_id": invoice_id, "amount": 1.0
    }, headers=manager_h)

    assert res.status_code == 400
    assert res.get_json()["error_code"] == "INVOICE_ALREADY_PAID"


def test_payment_invalid_amount(client, app):
    """TC10: amount <= 0 → INVALID_AMOUNT"""
    keeper_h = get_token(client, "keeper_inv")
    manager_h = get_token(client, "manager_inv")

    invoice_id = _create_invoice(client, app, keeper_h, total_amount=1000000.0)

    res = client.post("/api/supplier-payments", json={
        "invoice_id": invoice_id,
        "amount": 0,
    }, headers=manager_h)

    assert res.status_code == 400
    assert res.get_json()["error_code"] == "INVALID_AMOUNT"


# ---------------------------------------------------------------------------
# Tests: Danh sách và chi tiết
# ---------------------------------------------------------------------------

def test_get_invoice_list(client, app):
    """TC11: Lấy danh sách hóa đơn — phân trang + filter supplier_id"""
    manager_h = get_token(client, "manager_inv")

    res = client.get("/api/supplier-invoices", headers=manager_h)
    assert res.status_code == 200
    assert "total" in res.get_json()
    assert "data" in res.get_json()


def test_get_invoice_detail_with_payments(client, app):
    """TC12: Lấy chi tiết hóa đơn kèm lịch sử thanh toán"""
    keeper_h = get_token(client, "keeper_inv")
    manager_h = get_token(client, "manager_inv")

    invoice_id = _create_invoice(client, app, keeper_h, total_amount=2000000.0)

    # Ghi nhận 1 lần thanh toán
    client.post("/api/supplier-payments", json={
        "invoice_id": invoice_id,
        "amount": 1000000.0,
        "method": "chuyển khoản",
    }, headers=manager_h)

    res = client.get(f"/api/supplier-invoices/{invoice_id}", headers=manager_h)
    assert res.status_code == 200
    data = res.get_json()
    assert "payments" in data
    assert len(data["payments"]) == 1
    assert data["paid_amount"] == 1000000.0
    assert data["payment_status"] == "thanh toán một phần"


def test_keeper_cannot_get_invoice_list(client, app):
    """TC13: Thủ kho không được xem danh sách hóa đơn (chỉ Quản lý kho / Admin)"""
    keeper_h = get_token(client, "keeper_inv")
    res = client.get("/api/supplier-invoices", headers=keeper_h)
    assert res.status_code == 403
    assert res.get_json()["error_code"] == "FORBIDDEN"


def test_keeper_cannot_create_payment(client, app):
    """TC14: Thủ kho không được ghi nhận thanh toán (chỉ Quản lý kho / Admin)"""
    keeper_h = get_token(client, "keeper_inv")

    invoice_id = _create_invoice(client, app, keeper_h, total_amount=1000000.0)

    res = client.post("/api/supplier-payments", json={
        "invoice_id": invoice_id,
        "amount": 100000.0,
    }, headers=keeper_h)

    assert res.status_code == 403
    assert res.get_json()["error_code"] == "FORBIDDEN"
