import pytest
from app.main import create_app
from app.extensions import db
from app.models.user import User
from app.models.goods import Goods
from app.models.category import Category

@pytest.fixture
def app():
    test_app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "JWT_EXPIRE_MINUTES": "60",
        "SECRET_KEY": "test-secret-goods-key-for-pytest!",
        "JWT_SECRET_KEY": "test-secret-goods-key-for-pytest!",
    })
    
    with test_app.app_context():
        db.create_all()

        admin_user = User(
            username="admin_goods", full_name="Admin Test", email="admin@test.local", role="admin", is_active=True
        )
        admin_user.set_password("Password@123")
        
        manager_user = User(
            username="manager_goods", full_name="Manager Test", email="manager@test.local", role="warehouse_manager", is_active=True
        )
        manager_user.set_password("Password@123")
        
        keeper_user = User(
            username="keeper_goods", full_name="Keeper Test", email="keeper@test.local", role="warehouse_keeper", is_active=True
        )
        keeper_user.set_password("Password@123")
        
        db.session.add_all([admin_user, manager_user, keeper_user])

        category = Category(name="Electronics")
        db.session.add(category)
        db.session.commit()
        
        goods1 = Goods(
            sku="SKU001", name="Laptop", category_id=category.id, 
            unit="Cái", min_stock=10, quantity_on_hand=5,
            status="active"
        )
        goods2 = Goods(
            sku="SKU002", name="Mouse", category_id=category.id, 
            unit="Cái", min_stock=5, quantity_on_hand=10,
            status="active"
        )
        db.session.add_all([goods1, goods2])
        db.session.commit()
        
    yield test_app

    with test_app.app_context():
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def _login(client, username: str, password: str = "Password@123") -> str:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    return resp.get_json()["access_token"]

def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}

def test_get_goods(client, app):
    token = _login(client, "admin_goods")
    res = client.get("/api/goods", headers=_auth_header(token))
    assert res.status_code == 200
    assert res.json["total"] == 2

def test_get_low_stock(client, app):
    token = _login(client, "admin_goods")
    res = client.get("/api/goods/low-stock", headers=_auth_header(token))
    assert res.status_code == 200
    assert res.json["total"] == 1
    assert res.json["data"][0]["sku"] == "SKU001"

def test_create_goods(client, app):
    token = _login(client, "manager_goods")
    
    with app.app_context():
        cat = Category.query.first()
        cat_id = cat.id

    payload = {
        "sku": "SKU003",
        "name": "Keyboard",
        "category_id": cat_id,
        "unit": "Cái"
    }
    res = client.post("/api/goods", json=payload, headers=_auth_header(token))
    assert res.status_code == 201
    assert res.json["sku"] == "SKU003"
    
    res_dup = client.post("/api/goods", json=payload, headers=_auth_header(token))
    assert res_dup.status_code == 400
    assert res_dup.json["error_code"] == "SKU_EXISTS"

def test_create_goods_forbidden(client, app):
    token = _login(client, "keeper_goods")
    
    with app.app_context():
        cat = Category.query.first()
        cat_id = cat.id

    payload = {
        "sku": "SKU004",
        "name": "Monitor",
        "category_id": cat_id,
        "unit": "Cái"
    }
    res = client.post("/api/goods", json=payload, headers=_auth_header(token))
    assert res.status_code == 403
    assert res.json["error_code"] == "FORBIDDEN"

def test_update_goods(client, app):
    token = _login(client, "admin_goods")
    
    with app.app_context():
        goods = Goods.query.first()
        goods_id = goods.id
    
    update_payload = {"name": "Laptop Pro"}
    res_update = client.put(f"/api/goods/{goods_id}", json=update_payload, headers=_auth_header(token))
    assert res_update.status_code == 200
    assert res_update.json["name"] == "Laptop Pro"

def test_get_goods_detail(client, app):
    token = _login(client, "keeper_goods")
    
    with app.app_context():
        goods = Goods.query.first()
        goods_id = goods.id
    
    res_detail = client.get(f"/api/goods/{goods_id}", headers=_auth_header(token))
    assert res_detail.status_code == 200
    assert res_detail.json["id"] == goods_id
