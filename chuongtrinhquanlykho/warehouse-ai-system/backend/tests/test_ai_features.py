import pytest
from unittest.mock import patch
from app.models.ai_interaction_log import AIInteractionLog
from app.models.goods import Goods
from app.models.user import User
from app.main import create_app
from app.extensions import db

@pytest.fixture
def app():
    test_app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "JWT_EXPIRE_MINUTES": "60",
        "SECRET_KEY": "test-secret-key-for-pytest!",
        "JWT_SECRET_KEY": "test-secret-key-for-pytest!",
    })
    
    with test_app.app_context():
        db.create_all()
        
        admin_user = User(username="admin_sup", full_name="Admin", email="admin@test.com", role="admin", is_active=True)
        admin_user.set_password("Password@123")
        db.session.add(admin_user)
        
        keeper_user = User(username="keeper_sup", full_name="Keeper", email="keeper@test.com", role="warehouse_keeper", is_active=True)
        keeper_user.set_password("Password@123")
        db.session.add(keeper_user)
        
        db.session.commit()
        
    yield test_app
    
    with test_app.app_context():
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def _login(client, username):
    resp = client.post("/api/auth/login", json={"username": username, "password": "Password@123"})
    return resp.get_json()["access_token"]

def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def mock_gemini():
    with patch('app.ai.inventory_report_service._call_gemini_api') as mock_api1:
        with patch('app.ai.reorder_suggestion_service._call_gemini_api') as mock_api2:
            yield mock_api1, mock_api2

def test_inventory_report_success(client, app, mock_gemini):
    mock_api1, mock_api2 = mock_gemini
    admin_token = _login(client, "admin_sup")
    # Setup mock return value
    mock_api1.return_value = (
        '{"summary": "Test", "low_stock_items": [], "notable_changes": []}',
        'gemini-1.5-flash'
    )

    response = client.post(
        '/api/ai/inventory-report',
        headers=_auth_header(admin_token)
    )

    assert response.status_code == 200
    data = response.get_json()
    assert "summary" in data
    assert data["summary"] == "Test"
    
    # Check if logged in DB
    with app.app_context():
        log = AIInteractionLog.query.filter_by(feature_type="inventory_report").first()
        assert log is not None
        assert "Test" in log.ai_response

def test_reorder_suggestion_success(client, app, mock_gemini):
    mock_api1, mock_api2 = mock_gemini
    admin_token = _login(client, "admin_sup")
    # Setup mock return value
    mock_api2.return_value = (
        '{"reorder_suggestions": [{"sku": "SP001", "suggested_quantity": 50, "reason": "Low stock"}]}',
        'gemini-1.5-flash'
    )

    response = client.post(
        '/api/ai/reorder-suggestion',
        headers=_auth_header(admin_token)
    )

    if response.status_code != 200:
        print(response.get_json())
    assert response.status_code == 200
    data = response.get_json()
    assert "reorder_suggestions" in data
    assert len(data["reorder_suggestions"]) == 1
    assert data["reorder_suggestions"][0]["sku"] == "SP001"
    
    with app.app_context():
        log = AIInteractionLog.query.filter_by(feature_type="reorder_suggestion").first()
        assert log is not None
        assert "SP001" in log.ai_response

def test_ai_features_unauthorized(client):
    response = client.post('/api/ai/inventory-report')
    assert response.status_code == 401

def test_inventory_report_forbidden_keeper(client):
    keeper_token = _login(client, "keeper_sup")
    # Warehouse keeper should not have access to inventory report, only admin/manager
    response = client.post(
        '/api/ai/inventory-report',
        headers=_auth_header(keeper_token)
    )
    assert response.status_code == 403
