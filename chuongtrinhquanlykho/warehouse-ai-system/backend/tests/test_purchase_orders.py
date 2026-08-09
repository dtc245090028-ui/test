import pytest
from app.main import create_app
from app.extensions import db
from app.models.user import User
from app.models.goods import Goods
from app.models.category import Category
from app.models.supplier import Supplier
from app.models.purchase_order import PurchaseOrder

@pytest.fixture
def app():
    test_app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "JWT_EXPIRE_MINUTES": "60",
        "SECRET_KEY": "test-secret-po-key-for-pytest!",
        "JWT_SECRET_KEY": "test-secret-po-key-for-pytest!",
    })
    
    with test_app.app_context():
        db.create_all()

        keeper_user = User(
            username="keeper_po", full_name="Keeper Test", email="keeper@test.local", role="warehouse_keeper", is_active=True
        )
        keeper_user.set_password("Password@123")
        db.session.add(keeper_user)

        category = Category(name="Electronics")
        db.session.add(category)
        
        supplier = Supplier(name="Tech Supplier", status="active")
        db.session.add(supplier)
        db.session.commit()
        
        goods1 = Goods(
            sku="SKU001", name="Laptop", category_id=category.id, 
            unit="Cái", min_stock=10, quantity_on_hand=5,
            status="active"
        )
        db.session.add(goods1)
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
    res = client.post("/api/auth/login", json={"username": "keeper_po", "password": "Password@123"})
    return res.json["access_token"]

@pytest.fixture
def keeper_headers(keeper_token):
    return {"Authorization": f"Bearer {keeper_token}"}


def test_create_po_success(client, keeper_headers):
    data = {
        "supplier_id": 1,
        "items": [
            {
                "goods_id": 1,
                "quantity_ordered": 50,
                "unit_price": 1000.0
            }
        ]
    }
    res = client.post("/api/purchase-orders", json=data, headers=keeper_headers)
    assert res.status_code == 201
    assert res.json["status"] == "chờ xác nhận"
    assert res.json["items"][0]["quantity_ordered"] == 50

def test_create_po_invalid_quantity(client, keeper_headers):
    data = {
        "supplier_id": 1,
        "items": [
            {
                "goods_id": 1,
                "quantity_ordered": 0,  # Lỗi ở đây
                "unit_price": 1000.0
            }
        ]
    }
    res = client.post("/api/purchase-orders", json=data, headers=keeper_headers)
    assert res.status_code == 400
    assert res.json["error_code"] == "INVALID_QUANTITY"

def test_status_transitions(client, keeper_headers, app):
    # Tạo PO
    data = {
        "supplier_id": 1,
        "items": [{"goods_id": 1, "quantity_ordered": 50, "unit_price": 1000.0}]
    }
    res = client.post("/api/purchase-orders", json=data, headers=keeper_headers)
    po_id = res.json["id"]

    # Chờ xác nhận -> Đã xác nhận
    res = client.put(f"/api/purchase-orders/{po_id}/status", json={"status": "đã xác nhận"}, headers=keeper_headers)
    assert res.status_code == 200

    # Đã xác nhận -> Đang giao
    res = client.put(f"/api/purchase-orders/{po_id}/status", json={"status": "đang giao"}, headers=keeper_headers)
    assert res.status_code == 200

    # Đang giao -> Đã nhận
    res = client.put(f"/api/purchase-orders/{po_id}/status", json={"status": "đã nhận"}, headers=keeper_headers)
    assert res.status_code == 200

def test_invalid_status_transition(client, keeper_headers):
    # Tạo PO
    data = {
        "supplier_id": 1,
        "items": [{"goods_id": 1, "quantity_ordered": 50, "unit_price": 1000.0}]
    }
    res = client.post("/api/purchase-orders", json=data, headers=keeper_headers)
    po_id = res.json["id"]

    # Chờ xác nhận -> Đã nhận (Nhảy cóc)
    res = client.put(f"/api/purchase-orders/{po_id}/status", json={"status": "đã nhận"}, headers=keeper_headers)
    assert res.status_code == 400
    assert res.json["error_code"] == "INVALID_STATE_TRANSITION"
