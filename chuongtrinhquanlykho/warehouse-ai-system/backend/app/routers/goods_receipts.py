"""
routers/goods_receipts.py — Endpoint Phiếu nhập kho
=====================================================
Triển khai 3 endpoint theo api_contract.md mục 5:

  GET    /api/goods-receipts          Danh sách, filter ngày/NCC (phân trang)
  POST   /api/goods-receipts          Lập phiếu nhập (transaction, cập nhật tồn)
  GET    /api/goods-receipts/{id}     Chi tiết phiếu nhập

Role cho phép:
  - GET (danh sách + chi tiết): warehouse_keeper, warehouse_manager
  - POST (lập phiếu):           warehouse_keeper

Ràng buộc nghiệp vụ cốt lõi (Prompt.md mục 3.3, 6.2):
  1. quantity > 0 cho mọi dòng items.
  2. unit_price >= 0 — lưu cố định (snapshot) theo lần nhập, không đổi sau này.
  3. Cập nhật goods.quantity_on_hand qua DB transaction:
       db.session.flush() để lấy receipt.id → thêm items → commit()
     Nếu bất kỳ bước nào thất bại, rollback toàn bộ (transaction integrity).
  4. Nếu có po_id: kiểm tra PO tồn tại và thuộc đúng supplier_id.
  5. Supplier phải có status='active'.
  6. Goods phải có status='active'.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime

from app.extensions import db
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.supplier import Supplier
from app.models.goods import Goods
from app.models.purchase_order import PurchaseOrder
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.auth.decorators import roles_required

# Blueprint đặt url_prefix chuẩn theo api_contract.md
goods_receipts_bp = Blueprint(
    "goods_receipts", __name__, url_prefix="/api/goods-receipts"
)


# ---------------------------------------------------------------------------
# GET /api/goods-receipts — Danh sách phiếu nhập (phân trang, filter)
# ---------------------------------------------------------------------------
@goods_receipts_bp.route("", methods=["GET"])
@jwt_required()
@roles_required("warehouse_keeper", "warehouse_manager")
def get_goods_receipts():
    """
    Lấy danh sách phiếu nhập với phân trang và filter tùy chọn.

    Query params:
      page        : Trang hiện tại (mặc định 1)
      page_size   : Số bản ghi mỗi trang (mặc định 20)
      supplier_id : Lọc theo NCC
      date_from   : Lọc từ ngày (ISO 8601, ví dụ: 2026-08-01)
      date_to     : Lọc đến ngày (ISO 8601)
      po_id       : Lọc theo PO liên quan

    Response 200 (phân trang — cấu trúc chuẩn api_contract.md):
      { "total": int, "page": int, "page_size": int, "data": [...] }
    """
    # ---- Tham số phân trang ----
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)

    # ---- Tham số filter ----
    supplier_id = request.args.get("supplier_id", type=int)
    po_id_filter = request.args.get("po_id", type=int)
    date_from_str = request.args.get("date_from")
    date_to_str = request.args.get("date_to")

    # Bắt đầu query tất cả phiếu nhập
    query = GoodsReceipt.query

    # Lọc theo NCC
    if supplier_id:
        query = query.filter(GoodsReceipt.supplier_id == supplier_id)

    # Lọc theo PO liên quan
    if po_id_filter:
        query = query.filter(GoodsReceipt.po_id == po_id_filter)

    # Lọc theo khoảng ngày nhận hàng
    if date_from_str:
        try:
            date_from = datetime.fromisoformat(date_from_str)
            query = query.filter(GoodsReceipt.received_date >= date_from)
        except ValueError:
            return jsonify({
                "error_code": "INVALID_DATE_FORMAT",
                "message": "date_from phải theo định dạng ISO 8601 (ví dụ: 2026-08-01)"
            }), 400

    if date_to_str:
        try:
            date_to = datetime.fromisoformat(date_to_str)
            query = query.filter(GoodsReceipt.received_date <= date_to)
        except ValueError:
            return jsonify({
                "error_code": "INVALID_DATE_FORMAT",
                "message": "date_to phải theo định dạng ISO 8601 (ví dụ: 2026-08-31)"
            }), 400

    # Sắp xếp mới nhất trước, phân trang
    pagination = query.order_by(GoodsReceipt.received_date.desc()).paginate(
        page=page, per_page=page_size, error_out=False
    )

    return jsonify({
        "total": pagination.total,
        "page": pagination.page,
        "page_size": pagination.per_page,
        "data": [receipt.to_dict() for receipt in pagination.items],
    }), 200


# ---------------------------------------------------------------------------
# POST /api/goods-receipts — Lập phiếu nhập kho (transaction)
# ---------------------------------------------------------------------------
@goods_receipts_bp.route("", methods=["POST"])
@jwt_required()
@roles_required("warehouse_keeper")
def create_goods_receipt():
    """
    Lập phiếu nhập kho — cập nhật tồn kho theo transaction.

    Request body:
      {
        "supplier_id":    int (bắt buộc),
        "po_id":          int (tùy chọn — nếu nhập theo đơn đặt hàng),
        "received_date":  string ISO 8601 (tùy chọn, mặc định now),
        "note":           string (tùy chọn),
        "items": [
          {
            "goods_id":   int   (bắt buộc),
            "quantity":   float (bắt buộc, > 0),
            "unit_price": float (bắt buộc, >= 0)
          },
          ...
        ]
      }

    Ràng buộc:
      - items không được rỗng
      - quantity > 0 mỗi dòng (Prompt.md mục 10)
      - unit_price >= 0 mỗi dòng (snapshot — lưu cố định, không đổi sau)
      - supplier phải active
      - goods phải active
      - Nếu có po_id: PO phải tồn tại, supplier_id phải khớp với PO
      - Cập nhật goods.quantity_on_hand qua transaction an toàn

    Response 201: chi tiết phiếu nhập vừa tạo (kèm items)
    """
    data = request.get_json()
    if not data:
        return jsonify({
            "error_code": "INVALID_JSON",
            "message": "Body request không phải JSON hợp lệ"
        }), 400

    # ---- Validate trường bắt buộc ----
    supplier_id = data.get("supplier_id")
    items_data = data.get("items", [])

    if not supplier_id:
        return jsonify({
            "error_code": "MISSING_FIELDS",
            "message": "Thiếu supplier_id"
        }), 400

    if not items_data:
        return jsonify({
            "error_code": "MISSING_FIELDS",
            "message": "Phiếu nhập phải có ít nhất 1 dòng hàng hóa (items)"
        }), 400

    # ---- Kiểm tra Supplier ----
    supplier = Supplier.query.get(supplier_id)
    if not supplier:
        return jsonify({
            "error_code": "SUPPLIER_NOT_FOUND",
            "message": f"Không tìm thấy nhà cung cấp ID {supplier_id}"
        }), 404
    if supplier.status == "inactive":
        return jsonify({
            "error_code": "SUPPLIER_INACTIVE",
            "message": "Nhà cung cấp này đã ngừng hợp tác, không thể lập phiếu nhập"
        }), 400

    # ---- Kiểm tra PO (nếu có po_id) ----
    po_id = data.get("po_id")
    if po_id is not None:
        po = PurchaseOrder.query.get(po_id)
        if not po:
            return jsonify({
                "error_code": "PO_NOT_FOUND",
                "message": f"Không tìm thấy đơn đặt hàng ID {po_id}"
            }), 404
        if po.supplier_id != supplier_id:
            return jsonify({
                "error_code": "PO_SUPPLIER_MISMATCH",
                "message": "PO không thuộc nhà cung cấp đã chọn"
            }), 400

    # ---- Parse received_date ----
    received_date_str = data.get("received_date")
    received_date = datetime.utcnow()
    if received_date_str:
        try:
            # Hỗ trợ cả "Z" (UTC) và "+HH:MM"
            received_date = datetime.fromisoformat(
                received_date_str.replace("Z", "+00:00")
            ).replace(tzinfo=None)
        except ValueError:
            return jsonify({
                "error_code": "INVALID_DATE_FORMAT",
                "message": "received_date phải theo chuẩn ISO 8601 (ví dụ: 2026-08-12T10:00:00Z)"
            }), 400

    # ---- Validate từng dòng items ----
    # Dùng dict để tra cứu nhanh goods theo id (tránh query lặp)
    goods_map: dict[int, Goods] = {}
    for idx, item in enumerate(items_data, start=1):
        goods_id = item.get("goods_id")
        quantity = item.get("quantity")
        unit_price = item.get("unit_price")

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
                "message": f"Dòng {idx}: số lượng phải lớn hơn 0"
            }), 400

        # Kiểm tra unit_price >= 0 (snapshot — bắt buộc lưu lại)
        if unit_price is None or float(unit_price) < 0:
            return jsonify({
                "error_code": "INVALID_UNIT_PRICE",
                "message": f"Dòng {idx}: đơn giá không được âm"
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

    # ---- Tạo phiếu nhập + cập nhật tồn kho (transaction) ----
    # Dùng try/except để đảm bảo rollback nếu có lỗi bất ngờ
    user_id = int(get_jwt_identity())
    try:
        receipt = GoodsReceipt(
            supplier_id=supplier_id,
            po_id=po_id,
            created_by=user_id,
            received_date=received_date,
            note=data.get("note"),
        )
        db.session.add(receipt)
        # flush() để SQLAlchemy gán receipt.id mà chưa commit
        # Cần receipt.id để tạo GoodsReceiptItem
        db.session.flush()

        for item in items_data:
            goods_id = item["goods_id"]
            quantity = float(item["quantity"])
            unit_price = float(item["unit_price"])

            # Tạo dòng chi tiết — unit_price được snapshot cố định ở đây
            receipt_item = GoodsReceiptItem(
                receipt_id=receipt.id,
                goods_id=goods_id,
                quantity=quantity,
                unit_price=unit_price,  # Lưu cố định, KHÔNG thay đổi sau này
            )
            db.session.add(receipt_item)

            # Cộng tồn kho — cập nhật trực tiếp cột quantity_on_hand
            # Dùng đối tượng Goods đã load sẵn trong goods_map (tránh query lại)
            goods_obj = goods_map[goods_id]
            goods_obj.quantity_on_hand += quantity

        # Commit toàn bộ transaction một lần duy nhất
        # → nếu thất bại, SQLAlchemy tự rollback toàn bộ (atomic)
        db.session.commit()

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "Lỗi khi lưu phiếu nhập. Vui lòng thử lại.",
        }), 500

    # Trả về phiếu nhập vừa tạo (kèm items chi tiết)
    return jsonify(receipt.to_dict(include_items=True)), 201


# ---------------------------------------------------------------------------
# GET /api/goods-receipts/<id> — Chi tiết phiếu nhập
# ---------------------------------------------------------------------------
@goods_receipts_bp.route("/<int:id>", methods=["GET"])
@jwt_required()
@roles_required("warehouse_keeper", "warehouse_manager")
def get_goods_receipt_detail(id):
    """
    Lấy chi tiết phiếu nhập theo ID, bao gồm mảng items đầy đủ.

    Response 200: to_dict(include_items=True)
    Response 404: RECEIPT_NOT_FOUND nếu không tồn tại
    """
    receipt = GoodsReceipt.query.get(id)
    if not receipt:
        return jsonify({
            "error_code": "RECEIPT_NOT_FOUND",
            "message": f"Không tìm thấy phiếu nhập ID {id}"
        }), 404

    return jsonify(receipt.to_dict(include_items=True)), 200
