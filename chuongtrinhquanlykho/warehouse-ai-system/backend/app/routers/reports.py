"""
routers/reports.py — Endpoint Thống kê / Báo cáo kho
=====================================================
Triển khai 4 endpoint theo api_contract.md mục 9:

  GET  /api/reports/inventory-value    Giá trị tồn kho (theo ngày hoặc hiện tại)
  GET  /api/reports/turnover           Vòng quay tồn kho & danh sách slow-moving
  GET  /api/reports/top-goods          Top hàng nhập / xuất nhiều nhất
  GET  /api/reports/stocktake-diff     Chênh lệch kiểm kê theo kỳ

Role được phép:
  Cả 4 endpoint: warehouse_manager, admin
  (Prompt.md mục 3.1 — Ban điều hành & Quản lý kho xem báo cáo)

Nguồn dữ liệu (Prompt.md mục 3.7 & 8.3):
  - goods                : tồn kho hiện tại, min_stock, selling_price
  - goods_receipt_items  : số lượng & giá nhập theo từng lần (nguồn giá vốn)
  - goods_issue_items    : số lượng xuất
  - stocktakes           : phiếu kiểm kê
  - stocktake_items      : chi tiết chênh lệch

Lưu ý hiệu năng (Prompt.md mục 4):
  - Các query tổng hợp dùng func.sum / func.count của SQLAlchemy
    để tính ở tầng DB, không load toàn bộ rows về Python.
  - Kết hợp filter date_from / date_to để tránh full-table scan.
"""

from flask import Blueprint, request, jsonify
from sqlalchemy import func
from datetime import datetime

from app.extensions import db
from app.models.goods import Goods
from app.models.goods_receipt import GoodsReceiptItem, GoodsReceipt
from app.models.goods_issue import GoodsIssueItem, GoodsIssue
from app.models.stocktake import Stocktake, StocktakeItem
from flask_jwt_extended import jwt_required
from app.auth.decorators import roles_required

# Blueprint đặt url_prefix chuẩn theo api_contract.md
reports_bp = Blueprint("reports", __name__, url_prefix="/api/reports")


# ---------------------------------------------------------------------------
# Helper: parse ngày từ query param
# ---------------------------------------------------------------------------
def _parse_date(value: str, param_name: str):
    """
    Parse chuỗi ngày ISO 8601 từ query param.
    Hỗ trợ:  YYYY-MM-DD  hoặc  YYYY-MM-DDTHH:mm:ssZ
    Trả về datetime object hoặc raise ValueError nếu sai định dạng.
    """
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(
        f"Tham số `{param_name}` sai định dạng. Dùng YYYY-MM-DD hoặc YYYY-MM-DDTHH:mm:ssZ"
    )


# ===========================================================================
# 1. GET /api/reports/inventory-value — Giá trị tồn kho
# ===========================================================================
@reports_bp.route("/inventory-value", methods=["GET"])
@jwt_required()
@roles_required("warehouse_manager", "admin")
def inventory_value():
    """
    Báo cáo giá trị tồn kho hiện tại và theo kỳ.

    Cách tính giá vốn tồn kho (Prompt.md mục 3.2, 6.1):
      - Giá trị tồn = SUM(quantity_on_hand * giá nhập bình quân)
      - Giá nhập bình quân = tổng tiền nhập / tổng số lượng nhập
        (lấy từ goods_receipt_items — snapshot giá từng lần nhập)
      - Với hàng chưa có lần nhập nào → avg_cost = 0

    Query params:
      date_from   : Từ ngày (lọc phiếu nhập để tính giá bình quân trong kỳ)
      date_to     : Đến ngày
      category_id : Lọc theo danh mục hàng

    Response 200:
    {
      "generated_at": "...",
      "filters": { "date_from": ..., "date_to": ..., "category_id": ... },
      "summary": {
        "total_items": 10,
        "total_inventory_value": 12500000.0,
        "total_quantity_on_hand": 350.0
      },
      "items": [
        {
          "goods_id": 1, "sku": "SP001", "name": "Sản phẩm A",
          "category_id": 2, "unit": "Cái", "quantity_on_hand": 50.0,
          "avg_cost": 25000.0, "inventory_value": 1250000.0,
          "min_stock": 10, "max_stock": 100
        }
      ]
    }
    """
    # ---- Parse query params ----
    date_from_str = request.args.get("date_from")
    date_to_str   = request.args.get("date_to")
    category_id   = request.args.get("category_id", type=int)

    date_from = date_to = None
    try:
        if date_from_str:
            date_from = _parse_date(date_from_str, "date_from")
        if date_to_str:
            date_to = _parse_date(date_to_str, "date_to")
    except ValueError as e:
        return jsonify({"error_code": "INVALID_DATE_FORMAT", "message": str(e)}), 400

    # ---- Tính giá nhập bình quân cho từng mặt hàng ----
    # Subquery: (goods_id, tổng tiền nhập, tổng số lượng nhập) từ goods_receipt_items
    # Nối với goods_receipts để filter theo ngày nhập nếu có
    receipt_q = (
        db.session.query(
            GoodsReceiptItem.goods_id,
            func.sum(GoodsReceiptItem.quantity * GoodsReceiptItem.unit_price).label("total_cost"),
            func.sum(GoodsReceiptItem.quantity).label("total_qty_in"),
        )
        .join(GoodsReceipt, GoodsReceiptItem.receipt_id == GoodsReceipt.id)
    )
    # Filter theo ngày nhập nếu người dùng truyền vào
    if date_from:
        receipt_q = receipt_q.filter(GoodsReceipt.received_date >= date_from)
    if date_to:
        receipt_q = receipt_q.filter(GoodsReceipt.received_date <= date_to)

    # Group by goods_id → ra dict: goods_id → (total_cost, total_qty_in)
    receipt_agg = receipt_q.group_by(GoodsReceiptItem.goods_id).all()
    cost_map = {
        row.goods_id: (row.total_cost or 0.0, row.total_qty_in or 0.0)
        for row in receipt_agg
    }

    # ---- Lấy danh sách hàng hóa (active) ----
    goods_q = Goods.query.filter_by(status="active")
    if category_id:
        goods_q = goods_q.filter_by(category_id=category_id)
    all_goods = goods_q.order_by(Goods.id).all()

    # ---- Tính giá trị tồn cho từng mặt hàng ----
    items = []
    total_inventory_value = 0.0
    total_quantity_on_hand = 0.0

    for g in all_goods:
        total_cost, total_qty_in = cost_map.get(g.id, (0.0, 0.0))
        # Giá nhập bình quân trong kỳ — tránh chia 0
        avg_cost = (total_cost / total_qty_in) if total_qty_in > 0 else 0.0
        inv_value = round(g.quantity_on_hand * avg_cost, 2)

        total_inventory_value += inv_value
        total_quantity_on_hand += g.quantity_on_hand

        items.append({
            "goods_id": g.id,
            "sku": g.sku,
            "name": g.name,
            "category_id": g.category_id,
            "unit": g.unit,
            "quantity_on_hand": g.quantity_on_hand,
            "avg_cost": round(avg_cost, 2),
            "inventory_value": inv_value,
            "min_stock": g.min_stock,
            "max_stock": g.max_stock,
        })

    return jsonify({
        "generated_at": datetime.utcnow().isoformat(),
        "filters": {
            "date_from": date_from_str,
            "date_to": date_to_str,
            "category_id": category_id,
        },
        "summary": {
            "total_items": len(items),
            "total_inventory_value": round(total_inventory_value, 2),
            "total_quantity_on_hand": total_quantity_on_hand,
        },
        "items": items,
    }), 200


# ===========================================================================
# 2. GET /api/reports/turnover — Vòng quay tồn kho & Slow-moving
# ===========================================================================
@reports_bp.route("/turnover", methods=["GET"])
@jwt_required()
@roles_required("warehouse_manager", "admin")
def inventory_turnover():
    """
    Báo cáo vòng quay tồn kho và danh sách hàng chậm luân chuyển (slow-moving).

    Công thức (Prompt.md mục 3.7):
      - Tổng xuất trong kỳ = SUM(goods_issue_items.quantity) trong [date_from, date_to]
      - Tồn kho bình quân = quantity_on_hand (snapshot hiện tại)
        (đơn giản hóa phù hợp scope đồ án)
      - Vòng quay = tổng xuất / tồn kho bình quân  (None nếu tồn = 0)
      - Slow-moving: vòng quay < ngưỡng threshold (mặc định 0.5)

    Query params:
      date_from              : Từ ngày
      date_to                : Đến ngày
      slow_moving_threshold  : Ngưỡng vòng quay slow-moving (mặc định 0.5)
      category_id            : Lọc theo danh mục

    Response 200:
    {
      "generated_at": "...",
      "filters": { ... },
      "slow_moving_threshold": 0.5,
      "summary": {
        "total_items": 10, "slow_moving_count": 3, "total_issued_qty": 500.0
      },
      "items": [
        {
          "goods_id": 1, "sku": "SP001", "name": "...", "unit": "Cái",
          "quantity_on_hand": 100.0, "total_issued_qty": 20.0,
          "turnover_rate": 0.2, "is_slow_moving": true, "min_stock": 10
        }
      ]
    }
    """
    # ---- Parse query params ----
    date_from_str = request.args.get("date_from")
    date_to_str   = request.args.get("date_to")
    category_id   = request.args.get("category_id", type=int)
    try:
        threshold = float(request.args.get("slow_moving_threshold", 0.5))
    except (ValueError, TypeError):
        return jsonify({
            "error_code": "INVALID_PARAM",
            "message": "slow_moving_threshold phải là số thực."
        }), 400

    date_from = date_to = None
    try:
        if date_from_str:
            date_from = _parse_date(date_from_str, "date_from")
        if date_to_str:
            date_to = _parse_date(date_to_str, "date_to")
    except ValueError as e:
        return jsonify({"error_code": "INVALID_DATE_FORMAT", "message": str(e)}), 400

    # ---- Tổng số lượng xuất theo goods_id trong kỳ ----
    issue_q = (
        db.session.query(
            GoodsIssueItem.goods_id,
            func.sum(GoodsIssueItem.quantity).label("total_issued"),
        )
        .join(GoodsIssue, GoodsIssueItem.issue_id == GoodsIssue.id)
    )
    if date_from:
        issue_q = issue_q.filter(GoodsIssue.issued_date >= date_from)
    if date_to:
        issue_q = issue_q.filter(GoodsIssue.issued_date <= date_to)

    issue_agg = issue_q.group_by(GoodsIssueItem.goods_id).all()
    issue_map = {row.goods_id: row.total_issued or 0.0 for row in issue_agg}

    # ---- Lấy hàng hóa active ----
    goods_q = Goods.query.filter_by(status="active")
    if category_id:
        goods_q = goods_q.filter_by(category_id=category_id)
    all_goods = goods_q.order_by(Goods.id).all()

    # ---- Tính vòng quay cho từng mặt hàng ----
    items = []
    total_issued_qty = 0.0
    slow_moving_count = 0

    for g in all_goods:
        total_issued = issue_map.get(g.id, 0.0)
        # Tránh chia 0 khi tồn kho bằng 0
        if g.quantity_on_hand > 0:
            turnover_rate = round(total_issued / g.quantity_on_hand, 4)
        else:
            turnover_rate = None  # Không xác định được khi tồn = 0

        is_slow_moving = (turnover_rate is not None) and (turnover_rate < threshold)
        if is_slow_moving:
            slow_moving_count += 1
        total_issued_qty += total_issued

        items.append({
            "goods_id": g.id,
            "sku": g.sku,
            "name": g.name,
            "unit": g.unit,
            "quantity_on_hand": g.quantity_on_hand,
            "total_issued_qty": total_issued,
            "turnover_rate": turnover_rate,
            "is_slow_moving": is_slow_moving,
            "min_stock": g.min_stock,
        })

    # Sắp xếp: slow-moving lên đầu, rồi theo turnover_rate tăng dần
    items.sort(
        key=lambda x: (
            not x["is_slow_moving"],
            x["turnover_rate"] if x["turnover_rate"] is not None else 999,
        )
    )

    return jsonify({
        "generated_at": datetime.utcnow().isoformat(),
        "filters": {
            "date_from": date_from_str,
            "date_to": date_to_str,
            "category_id": category_id,
        },
        "slow_moving_threshold": threshold,
        "summary": {
            "total_items": len(items),
            "slow_moving_count": slow_moving_count,
            "total_issued_qty": total_issued_qty,
        },
        "items": items,
    }), 200


# ===========================================================================
# 3. GET /api/reports/top-goods — Top hàng nhập/xuất nhiều nhất
# ===========================================================================
@reports_bp.route("/top-goods", methods=["GET"])
@jwt_required()
@roles_required("warehouse_manager", "admin")
def top_goods():
    """
    Top N hàng hóa nhập nhiều nhất và/hoặc xuất nhiều nhất trong kỳ.

    Query params:
      date_from   : Từ ngày
      date_to     : Đến ngày
      top_n       : Số lượng top (mặc định 10)
      type        : "receipt" | "issue" | "both" (mặc định "both")

    Response 200 (type="both"):
    {
      "generated_at": "...",
      "filters": { "date_from": ..., "date_to": ..., "top_n": 10, "type": "both" },
      "top_receipt": [
        { "rank": 1, "goods_id": 5, "sku": "SP005", "name": "...",
          "unit": "Cái", "total_qty": 500.0, "total_transactions": 3 }
      ],
      "top_issue": [
        { "rank": 1, "goods_id": 3, "sku": "SP003", "name": "...",
          "unit": "Cái", "total_qty": 200.0, "total_transactions": 8 }
      ]
    }
    """
    # ---- Parse query params ----
    date_from_str = request.args.get("date_from")
    date_to_str   = request.args.get("date_to")
    report_type   = request.args.get("type", "both")
    try:
        top_n = int(request.args.get("top_n", 10))
        if top_n <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({
            "error_code": "INVALID_PARAM",
            "message": "top_n phải là số nguyên dương."
        }), 400

    if report_type not in ("receipt", "issue", "both"):
        return jsonify({
            "error_code": "INVALID_PARAM",
            "message": "type phải là 'receipt', 'issue' hoặc 'both'."
        }), 400

    date_from = date_to = None
    try:
        if date_from_str:
            date_from = _parse_date(date_from_str, "date_from")
        if date_to_str:
            date_to = _parse_date(date_to_str, "date_to")
    except ValueError as e:
        return jsonify({"error_code": "INVALID_DATE_FORMAT", "message": str(e)}), 400

    result = {
        "generated_at": datetime.utcnow().isoformat(),
        "filters": {
            "date_from": date_from_str,
            "date_to": date_to_str,
            "top_n": top_n,
            "type": report_type,
        },
    }

    # ---- Top hàng nhập ----
    if report_type in ("receipt", "both"):
        receipt_q = (
            db.session.query(
                GoodsReceiptItem.goods_id,
                func.sum(GoodsReceiptItem.quantity).label("total_qty"),
                func.count(GoodsReceiptItem.id).label("total_transactions"),
            )
            .join(GoodsReceipt, GoodsReceiptItem.receipt_id == GoodsReceipt.id)
        )
        if date_from:
            receipt_q = receipt_q.filter(GoodsReceipt.received_date >= date_from)
        if date_to:
            receipt_q = receipt_q.filter(GoodsReceipt.received_date <= date_to)

        top_receipt_rows = (
            receipt_q
            .group_by(GoodsReceiptItem.goods_id)
            .order_by(func.sum(GoodsReceiptItem.quantity).desc())
            .limit(top_n)
            .all()
        )

        top_receipt = []
        for rank, row in enumerate(top_receipt_rows, start=1):
            g = db.session.get(Goods, row.goods_id)
            top_receipt.append({
                "rank": rank,
                "goods_id": row.goods_id,
                "sku": g.sku if g else None,
                "name": g.name if g else None,
                "unit": g.unit if g else None,
                "total_qty": row.total_qty or 0.0,
                "total_transactions": row.total_transactions or 0,
            })
        result["top_receipt"] = top_receipt

    # ---- Top hàng xuất ----
    if report_type in ("issue", "both"):
        issue_q = (
            db.session.query(
                GoodsIssueItem.goods_id,
                func.sum(GoodsIssueItem.quantity).label("total_qty"),
                func.count(GoodsIssueItem.id).label("total_transactions"),
            )
            .join(GoodsIssue, GoodsIssueItem.issue_id == GoodsIssue.id)
        )
        if date_from:
            issue_q = issue_q.filter(GoodsIssue.issued_date >= date_from)
        if date_to:
            issue_q = issue_q.filter(GoodsIssue.issued_date <= date_to)

        top_issue_rows = (
            issue_q
            .group_by(GoodsIssueItem.goods_id)
            .order_by(func.sum(GoodsIssueItem.quantity).desc())
            .limit(top_n)
            .all()
        )

        top_issue = []
        for rank, row in enumerate(top_issue_rows, start=1):
            g = db.session.get(Goods, row.goods_id)
            top_issue.append({
                "rank": rank,
                "goods_id": row.goods_id,
                "sku": g.sku if g else None,
                "name": g.name if g else None,
                "unit": g.unit if g else None,
                "total_qty": row.total_qty or 0.0,
                "total_transactions": row.total_transactions or 0,
            })
        result["top_issue"] = top_issue

    return jsonify(result), 200


# ===========================================================================
# 4. GET /api/reports/stocktake-diff — Chênh lệch kiểm kê theo kỳ
# ===========================================================================
@reports_bp.route("/stocktake-diff", methods=["GET"])
@jwt_required()
@roles_required("warehouse_manager", "admin")
def stocktake_diff():
    """
    Báo cáo chênh lệch kiểm kê theo kỳ.

    Chỉ lấy phiếu kiểm kê trạng thái "đã phê duyệt"
    (phiếu chưa duyệt không phản ánh số liệu chính thức đã xác nhận).

    Query params:
      date_from   : Từ ngày (lọc theo stocktake_date)
      date_to     : Đến ngày
      goods_id    : Lọc theo mặt hàng cụ thể
      has_diff    : "true" → chỉ dòng có chênh lệch ≠ 0 | "false" → không chênh lệch

    Response 200:
    {
      "generated_at": "...",
      "filters": { "date_from": ..., "date_to": ..., "goods_id": ..., "has_diff": ... },
      "summary": {
        "total_stocktakes": 3, "total_items_checked": 30,
        "items_with_diff": 5, "total_shortage": -12.0, "total_surplus": 3.0
      },
      "stocktakes": [
        {
          "stocktake_id": 1,
          "stocktake_date": "2026-08-18T08:00:00",
          "status": "đã phê duyệt",
          "items": [
            {
              "goods_id": 5, "sku": "SP005", "name": "...", "unit": "Cái",
              "system_quantity": 50.0, "actual_quantity": 48.0,
              "difference": -2.0, "action": "Thanh lý hàng hỏng"
            }
          ]
        }
      ]
    }
    """
    # ---- Parse query params ----
    date_from_str   = request.args.get("date_from")
    date_to_str     = request.args.get("date_to")
    goods_id_filter = request.args.get("goods_id", type=int)
    has_diff_str    = request.args.get("has_diff")  # "true" | "false" | None

    date_from = date_to = None
    try:
        if date_from_str:
            date_from = _parse_date(date_from_str, "date_from")
        if date_to_str:
            date_to = _parse_date(date_to_str, "date_to")
    except ValueError as e:
        return jsonify({"error_code": "INVALID_DATE_FORMAT", "message": str(e)}), 400

    # ---- Lấy các phiếu kiểm kê đã phê duyệt trong kỳ ----
    st_q = Stocktake.query.filter_by(status="đã phê duyệt")
    if date_from:
        st_q = st_q.filter(Stocktake.stocktake_date >= date_from)
    if date_to:
        st_q = st_q.filter(Stocktake.stocktake_date <= date_to)
    stocktakes = st_q.order_by(Stocktake.stocktake_date.desc()).all()

    # ---- Tổng hợp kết quả ----
    total_items_checked = 0
    items_with_diff     = 0
    total_shortage      = 0.0
    total_surplus       = 0.0
    stocktake_list      = []

    for st in stocktakes:
        # Filter items theo goods_id nếu có
        items_raw = list(st.items)
        if goods_id_filter:
            items_raw = [i for i in items_raw if i.goods_id == goods_id_filter]

        # Filter theo has_diff
        if has_diff_str == "true":
            items_raw = [i for i in items_raw if i.difference != 0]
        elif has_diff_str == "false":
            items_raw = [i for i in items_raw if i.difference == 0]

        # Bỏ qua phiếu không có item thỏa filter (khi có filter cụ thể)
        if not items_raw and (goods_id_filter or has_diff_str):
            continue

        items_detail = []
        for si in items_raw:
            total_items_checked += 1
            if si.difference != 0:
                items_with_diff += 1
            if si.difference < 0:
                total_shortage += si.difference  # cộng dồn số âm
            elif si.difference > 0:
                total_surplus += si.difference

            g = si.goods
            items_detail.append({
                "goods_id": si.goods_id,
                "sku": g.sku if g else None,
                "name": g.name if g else None,
                "unit": g.unit if g else None,
                "system_quantity": si.system_quantity,
                "actual_quantity": si.actual_quantity,
                "difference": si.difference,
                "action": si.action,
            })

        stocktake_list.append({
            "stocktake_id": st.id,
            "stocktake_date": (
                st.stocktake_date.isoformat() if st.stocktake_date else None
            ),
            "status": st.status,
            "items": items_detail,
        })

    return jsonify({
        "generated_at": datetime.utcnow().isoformat(),
        "filters": {
            "date_from": date_from_str,
            "date_to": date_to_str,
            "goods_id": goods_id_filter,
            "has_diff": has_diff_str,
        },
        "summary": {
            "total_stocktakes": len(stocktake_list),
            "total_items_checked": total_items_checked,
            "items_with_diff": items_with_diff,
            "total_shortage": round(total_shortage, 2),
            "total_surplus": round(total_surplus, 2),
        },
        "stocktakes": stocktake_list,
    }), 200
