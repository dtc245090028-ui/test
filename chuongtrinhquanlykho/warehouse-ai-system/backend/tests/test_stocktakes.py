import pytest
from app.main import create_app
from app.extensions import db
from app.models.user import User
from app.models.goods import Goods
from app.models.category import Category
from app.models.stocktake import Stocktake, StocktakeItem

@pytest.fixture
def app():
    test_app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "JWT_EXPIRE_MINUTES": "60",
        "SECRET_KEY": "test-secret",
        "JWT_SECRET_KEY": "test-secret",
    })
    
    with test_app.app_context():
        db.create_all()

        manager = User(username="manager", full_name="Manager", email="manager@test.com", role="warehouse_manager")
        manager.set_password("pass")
        keeper = User(username="keeper", full_name="Keeper", email="keeper@test.com", role="warehouse_keeper")
        keeper.set_password("pass")
        
        db.session.add_all([manager, keeper])
        
        cat = Category(name="Cat 1")
        db.session.add(cat)
        db.session.commit()
        
        goods = Goods(sku="ST-01", name="Hàng ST", category_id=cat.id, unit="Cái", quantity_on_hand=50.0)
        db.session.add(goods)
        db.session.commit()
        
    yield test_app

    with test_app.app_context():
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def get_token(client, username):
    resp = client.post("/api/auth/login", json={"username": username, "password": "pass"})
    return {"Authorization": f"Bearer {resp.json['access_token']}"}

def test_create_stocktake_success(client, app):
    """TC01: Lập phiếu kiểm kê hợp lệ, tính difference đúng"""
    keeper_headers = get_token(client, "keeper")

    with app.app_context():
        goods = Goods.query.first()
        goods_id = goods.id

    payload = {
        "note": "Kiểm kê đầu tháng",
        "items": [{"goods_id": goods_id, "actual_quantity": 48.0}]
    }

    res = client.post("/api/stocktakes", json=payload, headers=keeper_headers)
    assert res.status_code == 201
    data = res.get_json()
    assert data["status"] == "đang kiểm kê"
    
    items = data["items"]
    assert len(items) == 1
    assert items[0]["system_quantity"] == 50.0
    assert items[0]["difference"] == -2.0

def test_create_stocktake_missing_actual_quantity(client, app):
    """TC02: Kiểm kê thiếu actual_quantity cho 1 mặt hàng → báo lỗi rõ ràng, không cho lưu"""
    keeper_headers = get_token(client, "keeper")

    with app.app_context():
        goods = Goods.query.first()
        goods_id = goods.id

    payload = {
        "items": [{"goods_id": goods_id}]
    }

    res = client.post("/api/stocktakes", json=payload, headers=keeper_headers)
    assert res.status_code == 400
    assert res.get_json()["error_code"] == "MISSING_FIELDS"

def test_propose_and_approve_stocktake(client, app):
    """TC03: Thủ kho đề xuất xử lý, sau đó Quản lý kho phê duyệt cập nhật tồn"""
    keeper_headers = get_token(client, "keeper")
    manager_headers = get_token(client, "manager")

    with app.app_context():
        goods = Goods.query.first()
        goods_id = goods.id

    res1 = client.post("/api/stocktakes", json={
        "items": [{"goods_id": goods_id, "actual_quantity": 90.0}]
    }, headers=keeper_headers)
    st_id = res1.get_json()["id"]
    st_item_id = res1.get_json()["items"][0]["id"]

    res2 = client.put(f"/api/stocktakes/{st_id}/propose", json={
        "items": [{"id": st_item_id, "action": "Thanh lý do hư hỏng"}]
    }, headers=keeper_headers)
    assert res2.status_code == 200
    assert res2.get_json()["status"] == "chờ phê duyệt"

    res_forbidden = client.put(f"/api/stocktakes/{st_id}/approve", headers=keeper_headers)
    assert res_forbidden.status_code == 403

    res3 = client.put(f"/api/stocktakes/{st_id}/approve", headers=manager_headers)
    assert res3.status_code == 200
    assert res3.get_json()["status"] == "đã phê duyệt"

    with app.app_context():
        updated_goods = Goods.query.get(goods_id)
        assert updated_goods.quantity_on_hand == 90.0

def test_create_stocktake_negative_quantity(client, app):
    """TC04: Số lượng kiểm kê âm → báo lỗi"""
    keeper_headers = get_token(client, "keeper")
    
    with app.app_context():
        goods = Goods.query.first()
        goods_id = goods.id

    res = client.post("/api/stocktakes", json={
        "items": [{"goods_id": goods_id, "actual_quantity": -5}]
    }, headers=keeper_headers)
    
    assert res.status_code == 400
    assert res.get_json()["error_code"] == "INVALID_QUANTITY"

def test_get_stocktakes(client, app):
    """TC05: Lấy danh sách phiếu kiểm kê"""
    manager_headers = get_token(client, "manager")
    res = client.get("/api/stocktakes", headers=manager_headers)
    assert res.status_code == 200
    assert "data" in res.get_json()
    assert "total" in res.get_json()
