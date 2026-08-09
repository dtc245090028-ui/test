from flask import Blueprint, request, jsonify
from datetime import datetime
from typing import Dict, List, Any

from app.extensions import db
from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem
from app.models.supplier import Supplier
from app.models.goods import Goods
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.auth.decorators import roles_required

bp = Blueprint("purchase_orders", __name__, url_prefix="/api/purchase-orders")

# Luồng trạng thái hợp lệ
VALID_TRANSITIONS = {
    "chờ xác nhận": ["đã xác nhận", "hủy"],
    "đã xác nhận": ["đang giao", "hủy"],
    "đang giao": ["đã nhận", "hủy"],
    "đã nhận": [],
    "hủy": []
}

@bp.route("", methods=["GET"])
@jwt_required()
@roles_required("warehouse_keeper", "warehouse_manager")
def get_purchase_orders():
    """Lấy danh sách PO (phân trang, filter)"""
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)
    status_filter = request.args.get("status")
    supplier_id_filter = request.args.get("supplier_id", type=int)

    query = PurchaseOrder.query

    if status_filter:
        query = query.filter(PurchaseOrder.status == status_filter)
    if supplier_id_filter:
        query = query.filter(PurchaseOrder.supplier_id == supplier_id_filter)

    pagination = query.order_by(PurchaseOrder.created_at.desc()).paginate(
        page=page, per_page=page_size, error_out=False
    )

    return jsonify({
        "total": pagination.total,
        "page": pagination.page,
        "page_size": pagination.per_page,
        "data": [po.to_dict() for po in pagination.items]
    }), 200

@bp.route("", methods=["POST"])
@jwt_required()
@roles_required("warehouse_keeper")
def create_purchase_order():
    """Tạo mới Purchase Order"""
    data = request.get_json()
    if not data:
        return jsonify({"error_code": "INVALID_JSON", "message": "Dữ liệu không hợp lệ"}), 400

    supplier_id = data.get("supplier_id")
    items_data = data.get("items", [])

    if not supplier_id or not items_data:
        return jsonify({"error_code": "MISSING_FIELDS", "message": "Thiếu supplier_id hoặc items"}), 400

    supplier = Supplier.query.get(supplier_id)
    if not supplier or supplier.status == 'inactive':
        return jsonify({"error_code": "INVALID_SUPPLIER", "message": "Nhà cung cấp không tồn tại hoặc đã ngừng hợp tác"}), 400

    # Validate items
    for item in items_data:
        qty = item.get("quantity_ordered")
        if qty is None or float(qty) <= 0:
            return jsonify({"error_code": "INVALID_QUANTITY", "message": "Số lượng đặt hàng phải lớn hơn 0"}), 400
        
        goods = Goods.query.get(item.get("goods_id"))
        if not goods or goods.status == 'inactive':
            return jsonify({"error_code": "INVALID_GOODS", "message": f"Hàng hóa ID {item.get('goods_id')} không tồn tại hoặc ngừng kinh doanh"}), 400

    # Lấy user_id
    user_id = int(get_jwt_identity())

    # Parse order_date nếu có
    order_date_str = data.get("order_date")
    order_date = datetime.utcnow()
    if order_date_str:
        try:
            # Xử lý chuỗi ISO 8601 (có thể chứa Z)
            order_date = datetime.fromisoformat(order_date_str.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return jsonify({"error_code": "INVALID_DATE_FORMAT", "message": "order_date phải chuẩn ISO 8601"}), 400

    po = PurchaseOrder(
        supplier_id=supplier_id,
        created_by=user_id,
        order_date=order_date,
        status="chờ xác nhận"
    )
    db.session.add(po)
    db.session.flush() # Lấy PO id

    for item in items_data:
        po_item = PurchaseOrderItem(
            po_id=po.id,
            goods_id=item.get("goods_id"),
            quantity_ordered=item.get("quantity_ordered"),
            unit_price=item.get("unit_price")
        )
        db.session.add(po_item)

    db.session.commit()

    return jsonify(po.to_dict(include_items=True)), 201

@bp.route("/<int:id>", methods=["GET"])
@jwt_required()
@roles_required("warehouse_keeper", "warehouse_manager")
def get_purchase_order_details(id):
    """Lấy chi tiết PO"""
    po = PurchaseOrder.query.get(id)
    if not po:
        return jsonify({"error_code": "PO_NOT_FOUND", "message": "Không tìm thấy Purchase Order"}), 404

    return jsonify(po.to_dict(include_items=True)), 200

@bp.route("/<int:id>/status", methods=["PUT"])
@jwt_required()
@roles_required("warehouse_keeper")
def update_purchase_order_status(id):
    """Cập nhật trạng thái PO"""
    data = request.get_json()
    if not data or not data.get("status"):
        return jsonify({"error_code": "MISSING_FIELDS", "message": "Thiếu status"}), 400

    new_status = data.get("status")
    if new_status not in VALID_TRANSITIONS:
        return jsonify({"error_code": "INVALID_STATUS", "message": "Trạng thái không hợp lệ"}), 400

    po = PurchaseOrder.query.get(id)
    if not po:
        return jsonify({"error_code": "PO_NOT_FOUND", "message": "Không tìm thấy Purchase Order"}), 404

    current_status = po.status
    allowed_next_states = VALID_TRANSITIONS.get(current_status, [])

    if new_status not in allowed_next_states:
        return jsonify({
            "error_code": "INVALID_STATE_TRANSITION",
            "message": f"Không thể chuyển trạng thái từ '{current_status}' sang '{new_status}'"
        }), 400

    po.status = new_status
    db.session.commit()

    return jsonify(po.to_dict(include_items=True)), 200
