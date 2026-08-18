from flask import Blueprint, request, jsonify
from app.extensions import db
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.auth.decorators import roles_required
from app.models.stocktake import Stocktake, StocktakeItem
from app.models.goods import Goods

stocktakes_bp = Blueprint("stocktakes", __name__, url_prefix="/api/stocktakes")

@stocktakes_bp.route("", methods=["GET"])
@jwt_required()
@roles_required("admin", "warehouse_manager", "warehouse_keeper")
def get_stocktakes():
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)

    query = Stocktake.query.order_by(Stocktake.created_at.desc())
    paginated = query.paginate(page=page, per_page=page_size, error_out=False)

    return jsonify({
        "total": paginated.total,
        "page": paginated.page,
        "page_size": paginated.per_page,
        "data": [st.to_dict() for st in paginated.items]
    }), 200

@stocktakes_bp.route("", methods=["POST"])
@jwt_required()
@roles_required("warehouse_keeper")
def create_stocktake():
    data = request.get_json() or {}
    items_data = data.get("items", [])

    if not items_data:
        return jsonify({
            "error_code": "MISSING_FIELDS",
            "message": "Danh sách items không được để trống"
        }), 400

    note = data.get("note")

    new_stocktake = Stocktake(
        created_by=int(get_jwt_identity()),
        note=note,
        status="đang kiểm kê"
    )
    db.session.add(new_stocktake)

    try:
        for item_data in items_data:
            goods_id = item_data.get("goods_id")
            actual_quantity = item_data.get("actual_quantity")

            if goods_id is None or actual_quantity is None:
                db.session.rollback()
                return jsonify({
                    "error_code": "MISSING_FIELDS",
                    "message": "Thiếu goods_id hoặc actual_quantity trong items"
                }), 400

            if actual_quantity < 0:
                db.session.rollback()
                return jsonify({
                    "error_code": "INVALID_QUANTITY",
                    "message": "Số lượng thực tế không được nhỏ hơn 0"
                }), 400

            goods = Goods.query.get(goods_id)
            if not goods:
                db.session.rollback()
                return jsonify({
                    "error_code": "GOODS_NOT_FOUND",
                    "message": f"Không tìm thấy hàng hóa ID={goods_id}"
                }), 404
            
            if goods.status != "active":
                db.session.rollback()
                return jsonify({
                    "error_code": "GOODS_INACTIVE",
                    "message": f"Hàng hóa ID={goods_id} đã ngừng kinh doanh"
                }), 400

            system_quantity = goods.quantity_on_hand
            difference = actual_quantity - system_quantity

            st_item = StocktakeItem(
                stocktake=new_stocktake,
                goods_id=goods_id,
                system_quantity=system_quantity,
                actual_quantity=actual_quantity,
                difference=difference
            )
            db.session.add(st_item)
            
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error_code": "DATABASE_ERROR",
            "message": "Có lỗi xảy ra khi lưu phiếu kiểm kê"
        }), 500

    return jsonify(new_stocktake.to_dict(include_items=True)), 201

@stocktakes_bp.route("/<int:stocktake_id>/propose", methods=["PUT"])
@jwt_required()
@roles_required("warehouse_keeper")
def propose_stocktake(stocktake_id):
    stocktake = Stocktake.query.get(stocktake_id)
    if not stocktake:
        return jsonify({
            "error_code": "STOCKTAKE_NOT_FOUND",
            "message": "Không tìm thấy phiếu kiểm kê"
        }), 404

    if stocktake.status != "đang kiểm kê":
        return jsonify({
            "error_code": "INVALID_STATUS",
            "message": "Chỉ có thể đề xuất khi phiếu đang ở trạng thái 'đang kiểm kê'"
        }), 400

    data = request.get_json() or {}
    items_data = data.get("items", [])
    
    if not items_data:
        return jsonify({
            "error_code": "MISSING_FIELDS",
            "message": "Danh sách items rỗng hoặc thiếu"
        }), 400

    items_map = {item.id: item for item in stocktake.items}

    try:
        for item_data in items_data:
            item_id = item_data.get("id")
            action = item_data.get("action")
            
            if item_id is None or action is None:
                db.session.rollback()
                return jsonify({
                    "error_code": "MISSING_FIELDS",
                    "message": "Thiếu id hoặc action trong items"
                }), 400

            if item_id not in items_map:
                db.session.rollback()
                return jsonify({
                    "error_code": "INVALID_ITEM",
                    "message": f"Chi tiết kiểm kê ID={item_id} không thuộc phiếu này"
                }), 400
                
            items_map[item_id].action = action

        stocktake.status = "chờ phê duyệt"
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error_code": "DATABASE_ERROR",
            "message": "Có lỗi xảy ra khi cập nhật đề xuất"
        }), 500

    return jsonify(stocktake.to_dict(include_items=True)), 200

@stocktakes_bp.route("/<int:stocktake_id>/approve", methods=["PUT"])
@jwt_required()
@roles_required("admin", "warehouse_manager")
def approve_stocktake(stocktake_id):
    stocktake = Stocktake.query.get(stocktake_id)
    if not stocktake:
        return jsonify({
            "error_code": "STOCKTAKE_NOT_FOUND",
            "message": "Không tìm thấy phiếu kiểm kê"
        }), 404

    if stocktake.status != "chờ phê duyệt":
        return jsonify({
            "error_code": "INVALID_STATUS",
            "message": "Chỉ có thể phê duyệt khi phiếu đang ở trạng thái 'chờ phê duyệt'"
        }), 400

    try:
        for item in stocktake.items:
            goods = Goods.query.get(item.goods_id)
            if goods:
                goods.quantity_on_hand = item.actual_quantity
        
        stocktake.status = "đã phê duyệt"
        stocktake.approved_by = int(get_jwt_identity())
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error_code": "DATABASE_ERROR",
            "message": "Có lỗi xảy ra khi cập nhật tồn kho"
        }), 500

    return jsonify(stocktake.to_dict(include_items=True)), 200
