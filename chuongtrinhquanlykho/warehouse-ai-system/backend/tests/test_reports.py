"""
tests/test_reports.py — Test cases cho module Reports (Thống kê/Báo cáo)
=========================================================================
Bao gồm đầy đủ các ca theo mục 10 Prompt.md:

Ca ĐÚNG:
  TC01 - inventory-value: Trả giá trị tồn kho đúng (tính avg_cost từ goods_receipt_items)
  TC02 - inventory-value: Filter theo category_id → chỉ trả hàng thuộc danh mục đó
  TC03 - inventory-value: Hàng chưa có lần nhập nào → avg_cost = 0, inventory_value = 0
  TC04 - turnover: Tính vòng quay đúng; is_slow_moving đúng theo threshold
  TC05 - turnover: Hàng tồn = 0 → turnover_rate = None
  TC06 - top-goods: Top nhập đúng thứ hạng theo tổng qty giảm dần
  TC07 - top-goods: type="issue" chỉ trả top_issue, không có top_receipt
  TC08 - top-goods: top_n=2 → chỉ trả 2 kết quả dù DB có nhiều hàng hơn
  TC09 - stocktake-diff: Chỉ lấy phiếu "đã phê duyệt", bỏ qua "đang kiểm kê"
  TC10 - stocktake-diff: Filter has_diff=true → chỉ trả dòng chênh lệch ≠ 0
  TC11 - stocktake-diff: summary tính đúng total_shortage, total_surplus

Ca LỖI / biên:
  TC12 - date_from sai định dạng → 400 INVALID_DATE_FORMAT
  TC13 - top_n=0 → 400 INVALID_PARAM
  TC14 - type="abc" → 400 INVALID_PARAM
  TC15 - slow_moving_threshold không phải số → 400 INVALID_PARAM

Phân quyền:
  TC16 - warehouse_keeper gọi → 403 FORBIDDEN
  TC17 - Không có token → 401 TOKEN_MISSING
"""

import pytest
from app.main import create_app
from app.extensions import db
from app.models.user import User
from app.models.goods import Goods
from app.models.category import Category
from app.models.supplier import Supplier
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.goods_issue import GoodsIssue, GoodsIssueItem
from app.models.stocktake import Stocktake, StocktakeItem


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """
    Tạo Flask app riêng cho test — dùng SQLite in-memory.
    Seed sẵn:
      - 1 user admin        (username='admin_rpt')
      - 1 user manager      (username='manager_rpt')
      - 1 user keeper       (username='keeper_rpt')
      - 1 category (Cat A)
      - 1 supplier active
      - 3 goods:
          g1 (sku=RPT001) quantity_on_hand=100
          g2 (sku=RPT002) quantity_on_hand=50
          g3 (sku=RPT003) quantity_on_hand=0  ← hàng tồn = 0
      - 2 phiếu nhập:
          receipt1 → g1: qty=60, unit_price=10000; g2: qty=30, unit_price=20000
          receipt2 → g1: qty=40, unit_price=12000
      - 2 phiếu xuất:
          issue1 → g1: qty=20; g2: qty=10
          issue2 → g1: qty=5
      - 1 stocktake "đã phê duyệt":
          item: g1 system=100, actual=98, diff=-2
          item: g2 system=50,  actual=50, diff=0
      - 1 stocktake "đang kiểm kê" (không được tính vào report)
    """
    test_app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "JWT_EXPIRE_MINUTES": "60",
        "SECRET_KEY": "test-secret-rpt-key!",
        "JWT_SECRET_KEY": "test-secret-rpt-key!",
    })

    with test_app.app_context():
        db.create_all()

        # ---- Users ----
        admin = User(
            username="admin_rpt", full_name="Admin Test",
            email="admin_rpt@test.local", role="admin", is_active=True,
        )
        admin.set_password("Password@123")

        manager = User(
            username="manager_rpt", full_name="Manager Test",
            email="manager_rpt@test.local", role="warehouse_manager", is_active=True,
        )
        manager.set_password("Password@123")

        keeper = User(
            username="keeper_rpt", full_name="Keeper Test",
            email="keeper_rpt@test.local", role="warehouse_keeper", is_active=True,
        )
        keeper.set_password("Password@123")

        db.session.add_all([admin, manager, keeper])
        db.session.flush()

        # ---- Category & Supplier ----
        cat = Category(name="Cat A")
        sup = Supplier(
            name="Supplier Test", contact_person="NV Test",
            phone="0900000001", email="sup@test.local",
            address="HCM", tax_code="0000000001", status="active",
        )
        db.session.add_all([cat, sup])
        db.session.flush()

        # ---- Goods ----
        g1 = Goods(
            sku="RPT001", name="Hàng A", category_id=cat.id,
            unit="Cái", min_stock=10, max_stock=200,
            quantity_on_hand=100, selling_price=15000, status="active",
        )
        g2 = Goods(
            sku="RPT002", name="Hàng B", category_id=cat.id,
            unit="Hộp", min_stock=5, max_stock=100,
            quantity_on_hand=50, selling_price=25000, status="active",
        )
        g3 = Goods(
            sku="RPT003", name="Hàng C", category_id=cat.id,
            unit="Kg", min_stock=0, max_stock=50,
            quantity_on_hand=0, selling_price=5000, status="active",
        )
        db.session.add_all([g1, g2, g3])
        db.session.flush()

        # ---- Goods Receipts ----
        # receipt1: g1 nhập 60 @ 10000, g2 nhập 30 @ 20000
        r1 = GoodsReceipt(
            supplier_id=sup.id, created_by=keeper.id,
            received_date=__import__("datetime").datetime(2026, 8, 1, 8, 0, 0),
            note="Nhập lần 1",
        )
        db.session.add(r1)
        db.session.flush()
        db.session.add_all([
            GoodsReceiptItem(receipt_id=r1.id, goods_id=g1.id, quantity=60, unit_price=10000),
            GoodsReceiptItem(receipt_id=r1.id, goods_id=g2.id, quantity=30, unit_price=20000),
        ])

        # receipt2: g1 nhập thêm 40 @ 12000
        r2 = GoodsReceipt(
            supplier_id=sup.id, created_by=keeper.id,
            received_date=__import__("datetime").datetime(2026, 8, 10, 8, 0, 0),
            note="Nhập lần 2",
        )
        db.session.add(r2)
        db.session.flush()
        db.session.add(
            GoodsReceiptItem(receipt_id=r2.id, goods_id=g1.id, quantity=40, unit_price=12000)
        )

        # ---- Goods Issues ----
        # issue1: g1 xuất 20, g2 xuất 10
        i1 = GoodsIssue(
            created_by=keeper.id,
            issued_date=__import__("datetime").datetime(2026, 8, 5, 10, 0, 0),
        )
        db.session.add(i1)
        db.session.flush()
        db.session.add_all([
            GoodsIssueItem(issue_id=i1.id, goods_id=g1.id, quantity=20),
            GoodsIssueItem(issue_id=i1.id, goods_id=g2.id, quantity=10),
        ])

        # issue2: g1 xuất 5
        i2 = GoodsIssue(
            created_by=keeper.id,
            issued_date=__import__("datetime").datetime(2026, 8, 15, 10, 0, 0),
        )
        db.session.add(i2)
        db.session.flush()
        db.session.add(
            GoodsIssueItem(issue_id=i2.id, goods_id=g1.id, quantity=5)
        )

        # ---- Stocktakes ----
        # st_approved: đã phê duyệt
        st_approved = Stocktake(
            created_by=keeper.id, approved_by=manager.id,
            stocktake_date=__import__("datetime").datetime(2026, 8, 18, 8, 0, 0),
            status="đã phê duyệt", note="KK tháng 8",
        )
        db.session.add(st_approved)
        db.session.flush()
        db.session.add_all([
            StocktakeItem(
                stocktake_id=st_approved.id, goods_id=g1.id,
                system_quantity=100, actual_quantity=98, difference=-2,
                action="Điều chỉnh tồn",
            ),
            StocktakeItem(
                stocktake_id=st_approved.id, goods_id=g2.id,
                system_quantity=50, actual_quantity=50, difference=0,
                action=None,
            ),
        ])

        # st_pending: đang kiểm kê (không được tính vào report)
        st_pending = Stocktake(
            created_by=keeper.id,
            stocktake_date=__import__("datetime").datetime(2026, 8, 20, 8, 0, 0),
            status="đang kiểm kê",
        )
        db.session.add(st_pending)
        db.session.flush()
        db.session.add(
            StocktakeItem(
                stocktake_id=st_pending.id, goods_id=g3.id,
                system_quantity=0, actual_quantity=5, difference=5,
            )
        )

        db.session.commit()
        yield test_app

        # Teardown
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Flask test client"""
    return app.test_client()


def _login(client, username, password="Password@123"):
    """Helper: đăng nhập, trả về JWT access token"""
    rv = client.post("/api/auth/login", json={"username": username, "password": password})
    assert rv.status_code == 200, f"Login thất bại cho {username}: {rv.get_json()}"
    return rv.get_json()["access_token"]


def _auth_headers(token):
    """Helper: tạo header Authorization"""
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# TC01 — inventory-value: tính avg_cost đúng từ goods_receipt_items
# ===========================================================================
def test_tc01_inventory_value_correct_avg_cost(client, app):
    """
    g1 nhập: 60 @ 10000 + 40 @ 12000 → avg_cost = (60*10000 + 40*12000) / (60+40)
           = (600000 + 480000) / 100 = 10800
    g1 qty_on_hand=100 → inventory_value = 100 * 10800 = 1080000
    """
    token = _login(client, "manager_rpt")
    rv = client.get("/api/reports/inventory-value", headers=_auth_headers(token))
    assert rv.status_code == 200
    data = rv.get_json()

    assert "items" in data
    assert "summary" in data
    assert data["summary"]["total_items"] == 3

    # Tìm g1 trong kết quả
    g1_item = next((i for i in data["items"] if i["sku"] == "RPT001"), None)
    assert g1_item is not None, "Không tìm thấy RPT001 trong kết quả"
    assert g1_item["avg_cost"] == 10800.0
    assert g1_item["inventory_value"] == 1080000.0


# ===========================================================================
# TC02 — inventory-value: filter category_id → chỉ trả hàng thuộc danh mục
# ===========================================================================
def test_tc02_inventory_value_filter_category(client, app):
    """
    Tất cả hàng trong test đều thuộc cat.id=1.
    Truyền category_id=999 (không tồn tại) → items rỗng.
    """
    token = _login(client, "admin_rpt")
    rv = client.get(
        "/api/reports/inventory-value?category_id=999",
        headers=_auth_headers(token),
    )
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["summary"]["total_items"] == 0
    assert data["items"] == []


# ===========================================================================
# TC03 — inventory-value: hàng chưa nhập → avg_cost = 0, inventory_value = 0
# ===========================================================================
def test_tc03_inventory_value_no_receipt(client, app):
    """
    g3 (RPT003) chưa có phiếu nhập nào → avg_cost phải = 0.
    quantity_on_hand=0 → inventory_value = 0.
    """
    token = _login(client, "manager_rpt")
    rv = client.get("/api/reports/inventory-value", headers=_auth_headers(token))
    assert rv.status_code == 200
    data = rv.get_json()

    g3_item = next((i for i in data["items"] if i["sku"] == "RPT003"), None)
    assert g3_item is not None
    assert g3_item["avg_cost"] == 0.0
    assert g3_item["inventory_value"] == 0.0


# ===========================================================================
# TC04 — turnover: tính vòng quay đúng; is_slow_moving đúng theo threshold
# ===========================================================================
def test_tc04_turnover_correct_rate(client, app):
    """
    g1: tổng xuất = 20 + 5 = 25, qty_on_hand = 100
        → turnover_rate = 25/100 = 0.25
        → threshold mặc định 0.5 → is_slow_moving = True
    g2: tổng xuất = 10, qty_on_hand = 50
        → turnover_rate = 10/50 = 0.2 → is_slow_moving = True
    """
    token = _login(client, "manager_rpt")
    rv = client.get("/api/reports/turnover", headers=_auth_headers(token))
    assert rv.status_code == 200
    data = rv.get_json()

    assert "items" in data
    assert data["slow_moving_threshold"] == 0.5

    g1 = next((i for i in data["items"] if i["sku"] == "RPT001"), None)
    assert g1 is not None
    assert g1["turnover_rate"] == 0.25
    assert g1["is_slow_moving"] is True

    g2 = next((i for i in data["items"] if i["sku"] == "RPT002"), None)
    assert g2 is not None
    assert g2["turnover_rate"] == 0.2
    assert g2["is_slow_moving"] is True


# ===========================================================================
# TC05 — turnover: hàng tồn = 0 → turnover_rate = None
# ===========================================================================
def test_tc05_turnover_zero_stock(client, app):
    """
    g3 (RPT003): quantity_on_hand = 0 → turnover_rate phải là None (không xác định).
    is_slow_moving = False (vì None không so sánh được với threshold).
    """
    token = _login(client, "manager_rpt")
    rv = client.get("/api/reports/turnover", headers=_auth_headers(token))
    assert rv.status_code == 200
    data = rv.get_json()

    g3 = next((i for i in data["items"] if i["sku"] == "RPT003"), None)
    assert g3 is not None
    assert g3["turnover_rate"] is None
    assert g3["is_slow_moving"] is False


# ===========================================================================
# TC06 — top-goods: top nhập đúng thứ hạng theo tổng qty giảm dần
# ===========================================================================
def test_tc06_top_goods_receipt_ranking(client, app):
    """
    g1 tổng nhập = 60 + 40 = 100 → rank 1
    g2 tổng nhập = 30 → rank 2
    """
    token = _login(client, "manager_rpt")
    rv = client.get(
        "/api/reports/top-goods?type=receipt",
        headers=_auth_headers(token),
    )
    assert rv.status_code == 200
    data = rv.get_json()

    assert "top_receipt" in data
    assert "top_issue" not in data  # type=receipt không trả top_issue

    top_receipt = data["top_receipt"]
    assert len(top_receipt) >= 2
    assert top_receipt[0]["sku"] == "RPT001"
    assert top_receipt[0]["rank"] == 1
    assert top_receipt[0]["total_qty"] == 100.0
    assert top_receipt[1]["sku"] == "RPT002"
    assert top_receipt[1]["rank"] == 2
    assert top_receipt[1]["total_qty"] == 30.0


# ===========================================================================
# TC07 — top-goods: type="issue" chỉ trả top_issue
# ===========================================================================
def test_tc07_top_goods_issue_only(client, app):
    """
    type="issue" → response chỉ có top_issue, không có top_receipt.
    g1 tổng xuất = 25 → rank 1
    g2 tổng xuất = 10 → rank 2
    """
    token = _login(client, "admin_rpt")
    rv = client.get(
        "/api/reports/top-goods?type=issue",
        headers=_auth_headers(token),
    )
    assert rv.status_code == 200
    data = rv.get_json()

    assert "top_issue" in data
    assert "top_receipt" not in data

    top_issue = data["top_issue"]
    assert top_issue[0]["sku"] == "RPT001"
    assert top_issue[0]["total_qty"] == 25.0


# ===========================================================================
# TC08 — top-goods: top_n=1 → chỉ trả 1 kết quả
# ===========================================================================
def test_tc08_top_goods_limit_topn(client, app):
    """
    top_n=1 → chỉ trả hàng nhập nhiều nhất (rank 1 mỗi loại).
    """
    token = _login(client, "manager_rpt")
    rv = client.get(
        "/api/reports/top-goods?type=both&top_n=1",
        headers=_auth_headers(token),
    )
    assert rv.status_code == 200
    data = rv.get_json()
    assert len(data["top_receipt"]) == 1
    assert len(data["top_issue"]) == 1


# ===========================================================================
# TC09 — stocktake-diff: chỉ lấy "đã phê duyệt", bỏ "đang kiểm kê"
# ===========================================================================
def test_tc09_stocktake_diff_approved_only(client, app):
    """
    Có 1 phiếu "đã phê duyệt" và 1 phiếu "đang kiểm kê".
    → Kết quả phải chỉ có 1 phiếu (đã phê duyệt).
    """
    token = _login(client, "manager_rpt")
    rv = client.get("/api/reports/stocktake-diff", headers=_auth_headers(token))
    assert rv.status_code == 200
    data = rv.get_json()

    assert data["summary"]["total_stocktakes"] == 1
    assert data["stocktakes"][0]["status"] == "đã phê duyệt"


# ===========================================================================
# TC10 — stocktake-diff: filter has_diff=true → chỉ dòng chênh lệch ≠ 0
# ===========================================================================
def test_tc10_stocktake_diff_has_diff_filter(client, app):
    """
    Phiếu đã phê duyệt có:
      - g1: difference = -2 (≠ 0)
      - g2: difference =  0 (= 0)
    Với has_diff=true → chỉ trả dòng g1.
    """
    token = _login(client, "manager_rpt")
    rv = client.get(
        "/api/reports/stocktake-diff?has_diff=true",
        headers=_auth_headers(token),
    )
    assert rv.status_code == 200
    data = rv.get_json()

    assert data["summary"]["total_items_checked"] == 1
    assert data["summary"]["items_with_diff"] == 1
    items = data["stocktakes"][0]["items"]
    assert len(items) == 1
    assert items[0]["difference"] == -2.0


# ===========================================================================
# TC11 — stocktake-diff: summary tính đúng total_shortage, total_surplus
# ===========================================================================
def test_tc11_stocktake_diff_summary(client, app):
    """
    g1: difference = -2 → total_shortage = -2
    g2: difference =  0 → total_surplus  =  0
    """
    token = _login(client, "admin_rpt")
    rv = client.get("/api/reports/stocktake-diff", headers=_auth_headers(token))
    assert rv.status_code == 200
    data = rv.get_json()

    summary = data["summary"]
    assert summary["total_items_checked"] == 2
    assert summary["items_with_diff"] == 1
    assert summary["total_shortage"] == -2.0
    assert summary["total_surplus"] == 0.0


# ===========================================================================
# TC12 — Lỗi: date_from sai định dạng → 400 INVALID_DATE_FORMAT
# ===========================================================================
def test_tc12_invalid_date_format(client, app):
    """
    Truyền date_from="not-a-date" → 400 với error_code INVALID_DATE_FORMAT.
    Kiểm tra trên cả 3 endpoint có filter ngày.
    """
    token = _login(client, "manager_rpt")
    headers = _auth_headers(token)

    for endpoint in (
        "/api/reports/inventory-value?date_from=not-a-date",
        "/api/reports/turnover?date_from=not-a-date",
        "/api/reports/top-goods?date_from=not-a-date",
        "/api/reports/stocktake-diff?date_from=not-a-date",
    ):
        rv = client.get(endpoint, headers=headers)
        assert rv.status_code == 400, f"Expected 400 nhưng nhận {rv.status_code} ở {endpoint}"
        assert rv.get_json()["error_code"] == "INVALID_DATE_FORMAT"


# ===========================================================================
# TC13 — Lỗi: top_n=0 → 400 INVALID_PARAM
# ===========================================================================
def test_tc13_invalid_topn(client, app):
    """top_n phải là số nguyên dương."""
    token = _login(client, "manager_rpt")
    rv = client.get(
        "/api/reports/top-goods?top_n=0",
        headers=_auth_headers(token),
    )
    assert rv.status_code == 400
    assert rv.get_json()["error_code"] == "INVALID_PARAM"


# ===========================================================================
# TC14 — Lỗi: type="abc" → 400 INVALID_PARAM
# ===========================================================================
def test_tc14_invalid_type_param(client, app):
    """type phải là 'receipt', 'issue' hoặc 'both'."""
    token = _login(client, "manager_rpt")
    rv = client.get(
        "/api/reports/top-goods?type=abc",
        headers=_auth_headers(token),
    )
    assert rv.status_code == 400
    assert rv.get_json()["error_code"] == "INVALID_PARAM"


# ===========================================================================
# TC15 — Lỗi: slow_moving_threshold không phải số → 400 INVALID_PARAM
# ===========================================================================
def test_tc15_invalid_threshold(client, app):
    """slow_moving_threshold phải là số thực."""
    token = _login(client, "manager_rpt")
    rv = client.get(
        "/api/reports/turnover?slow_moving_threshold=abc",
        headers=_auth_headers(token),
    )
    assert rv.status_code == 400
    assert rv.get_json()["error_code"] == "INVALID_PARAM"


# ===========================================================================
# TC16 — Phân quyền: warehouse_keeper gọi → 403 FORBIDDEN
# ===========================================================================
def test_tc16_keeper_forbidden(client, app):
    """
    warehouse_keeper không có quyền xem báo cáo.
    Kiểm tra tất cả 4 endpoint đều trả 403.
    """
    token = _login(client, "keeper_rpt")
    headers = _auth_headers(token)

    for endpoint in (
        "/api/reports/inventory-value",
        "/api/reports/turnover",
        "/api/reports/top-goods",
        "/api/reports/stocktake-diff",
    ):
        rv = client.get(endpoint, headers=headers)
        assert rv.status_code == 403, f"Expected 403 nhưng nhận {rv.status_code} ở {endpoint}"
        assert rv.get_json()["error_code"] == "FORBIDDEN"


# ===========================================================================
# TC17 — Phân quyền: Không có token → 401 TOKEN_MISSING
# ===========================================================================
def test_tc17_no_token(client, app):
    """Gọi không có Authorization header → 401 TOKEN_MISSING."""
    for endpoint in (
        "/api/reports/inventory-value",
        "/api/reports/turnover",
        "/api/reports/top-goods",
        "/api/reports/stocktake-diff",
    ):
        rv = client.get(endpoint)
        assert rv.status_code == 401, f"Expected 401 nhưng nhận {rv.status_code} ở {endpoint}"
        assert rv.get_json()["error_code"] == "TOKEN_MISSING"
