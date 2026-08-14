"""
routers/goods_issues.py — Endpoint Phiếu xuất kho
====================================================
Triển khai 3 endpoint theo api_contract.md mục 6:

  GET    /api/goods-issues          Danh sách, filter ngày (phân trang)
  POST   /api/goods-issues          Lập phiếu xuất (transaction, chặn xuất vượt tồn)
  GET    /api/goods-issues/{id}     Chi tiết phiếu xuất

Role cho phép:
  - GET (danh sách + chi tiết): warehouse_keeper, warehouse_manager
  - POST (lập phiếu):           warehouse_keeper

Ràng buộc nghiệp vụ cốt lõi (Prompt.md mục 3.3, 10):
  1. quantity > 0 cho mọi dòng items.
  2. quantity ≤ goods.quantity_on_hand → không cho xuất vượt tồn (tồn kho âm).
  3. Cập nhật goods.quantity_on_hand qua DB transaction:
       db.session.flush() để lấy issue.id → thêm items → trừ tồn → commit()
     Nếu bất kỳ bước nào thất bại, rollback toàn bộ (transaction integrity).
  4. Goods phải có status='active'.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime

from app.extensions import db
from app.models.goods_issue import GoodsIssue, GoodsIssueItem
from app.models.goods import Goods
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.auth.decorators import roles_required

# Blueprint đặt url_prefix chuẩn theo api_contract.md
goods_issues_bp = Blueprint(
    "goods_issues", __name__, url_prefix="/api/goods-issues"
)


# ---------------------------------------------------------------------------
# GET /api/goods-issues — Danh sách phiếu xuất (phân trang, filter)
# ---------------------------------------------------------------------------
@goods_issues_bp.route("", methods=["GET"])
@jwt_required()
@roles_required("warehouse_keeper", "warehouse_manager")
def get_goods_issues():
    """
    Lấy danh sách phiếu xuất với phân trang và filter tùy chọn.

    Query params:
      page        : Trang hiện tại (mặc định 1)
      page_size   : Số bản ghi mỗi trang (mặc định 20)
      date_from   : Lọc từ ngày (ISO 8601, ví dụ: 2026-08-01)
      date_to     : Lọc đến ngày (ISO 8601)

    Response 200 (phân trang — cấu trúc chuẩn api_contract.md):
      { "total": int, "page": int, "page_size": int, "data": [...] }
    Lưu ý: mảng items KHÔNG trả trong danh sách — gọi GET/{id} để lấy chi tiết.
    """
    # ---- Tham số phân trang ----
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)

    # ---- Tham số filter ----
    date_from_str = request.args.get("date_from")
    date_to_str = request.args.get("date_to")

    # Bắt đầu query tất cả phiếu xuất
    query = GoodsIssue.query

    # Lọc theo khoảng ngày xuất hàng
    if date_from_str:
        try:
            date_from = datetime.fromisoformat(date_from_str)
            query = query.filter(GoodsIssue.issued_date >= date_from)
        except ValueError:
            return jsonify({
                "error_code": "INVALID_DATE_FORMAT",
                "message": "date_from phải theo định dạng ISO 8601 (ví dụ: 2026-08-01)"
            }), 400

    if date_to_str:
        try:
            date_to = datetime.fromisoformat(date_to_str)
            query = query.filter(GoodsIssue.issued_date <= date_to)
        except ValueError:
            return jsonify({
                "error_code": "INVALID_DATE_FORMAT",
                "message": "date_to phải theo định dạng ISO 8601 (ví dụ: 2026-08-31)"
            }), 400

    # Sắp xếp mới nhất trước, phân trang
    pagination = query.order_by(GoodsIssue.issued_date.desc()).paginate(
        page=page, per_page=page_size, error_out=False
    )

    return jsonify({
        "total": pagination.total,
        "page": pagination.page,
        "page_size": pagination.per_page,
        # include_items=False → không trả mảng items trong danh sách
        "data": [issue.to_dict() for issue in pagination.items],
    }), 200


# ---------------------------------------------------------------------------
# POST /api/goods-issues — Lập phiếu xuất kho (transaction)
# ---------------------------------------------------------------------------
@goods_issues_bp.route("", methods=["POST"])
@jwt_required()
@roles_required("warehouse_keeper")
def create_goods_issue():
    """
    Lập phiếu xuất kho — trừ tồn kho theo transaction.

    Request body:
      {
        "issued_date":  string ISO 8601 (tùy chọn, mặc định now),
        "note":         string (tùy chọn),
        "items": [
          {
            "goods_id":  int   (bắt buộc),
            "quantity":  float (bắt buộc, > 0)
          },
          ...
        ]
      }

    Ràng buộc (Prompt.md mục 3.3, 10):
      - items không được rỗng
      - quantity > 0 mỗi dòng
      - quantity ≤ goods.quantity_on_hand → chặn xuất vượt tồn
        (tồn kho KHÔNG được âm — Prompt.md mục 6.2)
      - goods phải active
      - Cập nhật goods.quantity_on_hand qua transaction an toàn

    Response 201: chi tiết phiếu xuất vừa tạo (kèm items)
    """
    data = request.get_json()
    if not data:
        return jsonify({
            "error_code": "INVALID_JSON",
            "message": "Body request không phải JSON hợp lệ"
        }), 400

    # ---- Validate trường bắt buộc ----
    items_data = data.get("items", [])

    if not items_data:
        return jsonify({
            "error_code": "MISSING_FIELDS",
            "message": "Phiếu xuất phải có ít nhất 1 dòng hàng hóa (items)"
        }), 400

    # ---- Parse issued_date ----
    issued_date_str = data.get("issued_date")
    issued_date = datetime.utcnow()
    if issued_date_str:
        try:
            # Hỗ trợ cả "Z" (UTC) và "+HH:MM"
            issued_date = datetime.fromisoformat(
                issued_date_str.replace("Z", "+00:00")
            ).replace(tzinfo=None)
        except ValueError:
            return jsonify({
                "error_code": "INVALID_DATE_FORMAT",
                "message": "issued_date phải theo chuẩn ISO 8601 (ví dụ: 2026-08-14T08:00:00Z)"
            }), 400

    # ---- Validate từng dòng items ----
    # Dùng dict để tra cứu nhanh goods theo id (tránh query lặp)
    # Đồng thời kiểm tra tổng số lượng xuất cho từng mặt hàng
    # (đề phòng cùng goods_id xuất hiện 2 lần trong cùng 1 phiếu)
    goods_map: dict[int, Goods] = {}
    quantity_total_per_goods: dict[int, float] = {}  # tổng quantity cho mỗi goods_id trong phiếu này

    for idx, item in enumerate(items_data, start=1):
        goods_id = item.get("goods_id")
        quantity = item.get("quantity")

        # Kiểm tra goods_id
        if goods_id is None:
            return jsonify({
                "error_code": "MISSING_FIELDS",
                "message": f"Dòng {idx}: thiếu goods_id"
            }), 400

        # Kiểm tra quantity > 0 (Prompt.md mục 10 — ca lỗi/biên)
        if quantity is None or float(quantity) <= 0:
            return jsonify({
                "error_code": "INVALID_QUANTITY",
                "message": f"Dòng {idx}: số lượng xuất phải lớn hơn 0"
            }), 400

        # Kiểm tra hàng hóa tồn tại và active
        if goods_id not in goods_map:
            goods = Goods.query.get(goods_id)
            if not goods:
                return jsonify({
                    "error_code": "GOODS_NOT_FOUND",
                    "message": f"Dòng {idx}: không tìm thấy hàng hóa ID {goods_id}"
                }), 404
            if goods.status == "inactive":
                return jsonify({
                    "error_code": "GOODS_INACTIVE",
                    "message": f"Dòng {idx}: hàng hóa '{goods.name}' đã ngừng kinh doanh"
                }), 400
            goods_map[goods_id] = goods
            quantity_total_per_goods[goods_id] = 0.0

        # Cộng dồn tổng quantity cho goods_id này (hỗ trợ nhiều dòng cùng goods_id)
        quantity_total_per_goods[goods_id] += float(quantity)

    # ---- Kiểm tra tổng xuất KHÔNG vượt tồn kho (chặn xuất âm) ----
    # Phải kiểm tra TRƯỚC khi vào transaction để trả lỗi rõ ràng,
    # tránh rollback giữa chừng mà không có thông báo chi tiết.
    # (Prompt.md mục 3.3: "kiểm tra số lượng còn — không cho xuất vượt tồn")
    for goods_id, total_qty in quantity_total_per_goods.items():
        goods_obj = goods_map[goods_id]
        if total_qty > goods_obj.quantity_on_hand:
            return jsonify({
                "error_code": "INSUFFICIENT_STOCK",
                "message": (
                    f"Hàng hóa '{goods_obj.name}' (SKU: {goods_obj.sku}): "
                    f"số lượng xuất yêu cầu ({total_qty} {goods_obj.unit}) "
                    f"vượt quá tồn kho hiện tại ({goods_obj.quantity_on_hand} {goods_obj.unit})"
                )
            }), 400

    # ---- Tạo phiếu xuất + cập nhật tồn kho (transaction) ----
    # Dùng try/except để đảm bảo rollback nếu có lỗi bất ngờ
    user_id = int(get_jwt_identity())
    try:
        issue = GoodsIssue(
            created_by=user_id,
            issued_date=issued_date,
            note=data.get("note"),
        )
        db.session.add(issue)
        # flush() để SQLAlchemy gán issue.id mà chưa commit
        # Cần issue.id để tạo GoodsIssueItem
        db.session.flush()

        for item in items_data:
            goods_id = item["goods_id"]
            quantity = float(item["quantity"])

            # Tạo dòng chi tiết phiếu xuất
            issue_item = GoodsIssueItem(
                issue_id=issue.id,
                goods_id=goods_id,
                quantity=quantity,
            )
            db.session.add(issue_item)

            # Trừ tồn kho — cập nhật trực tiếp cột quantity_on_hand
            # Dùng đối tượng Goods đã load sẵn trong goods_map (tránh query lại)
            # Ràng buộc không âm đã được kiểm tra ở bước trên,
            # nhưng vẫn guard thêm một lần nữa để an toàn hoàn toàn
            goods_obj = goods_map[goods_id]
            goods_obj.quantity_on_hand -= quantity

            # Guard cuối — không bao giờ cho tồn kho âm (defensive programming)
            if goods_obj.quantity_on_hand < 0:
                raise ValueError(
                    f"Tồn kho không đủ cho hàng hóa ID {goods_id} "
                    f"(tồn sau xuất = {goods_obj.quantity_on_hand})"
                )

        # Commit toàn bộ transaction một lần duy nhất
        # → nếu thất bại, SQLAlchemy tự rollback toàn bộ (atomic)
        db.session.commit()

    except ValueError as ve:
        # Trường hợp guard tồn kho âm phát hiện lỗi bất ngờ
        db.session.rollback()
        return jsonify({
            "error_code": "INSUFFICIENT_STOCK",
            "message": str(ve),
        }), 400

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "Lỗi khi lưu phiếu xuất. Vui lòng thử lại.",
        }), 500

    # Trả về phiếu xuất vừa tạo (kèm items chi tiết)
    return jsonify(issue.to_dict(include_items=True)), 201


# ---------------------------------------------------------------------------
# GET /api/goods-issues/<id> — Chi tiết phiếu xuất
# ---------------------------------------------------------------------------
@goods_issues_bp.route("/<int:id>", methods=["GET"])
@jwt_required()
@roles_required("warehouse_keeper", "warehouse_manager")
def get_goods_issue_detail(id):
    """
    Lấy chi tiết phiếu xuất theo ID, bao gồm mảng items đầy đủ.

    Response 200: to_dict(include_items=True)
    Response 404: ISSUE_NOT_FOUND nếu không tồn tại
    """
    issue = GoodsIssue.query.get(id)
    if not issue:
        return jsonify({
            "error_code": "ISSUE_NOT_FOUND",
            "message": f"Không tìm thấy phiếu xuất ID {id}"
        }), 404

    return jsonify(issue.to_dict(include_items=True)), 200
