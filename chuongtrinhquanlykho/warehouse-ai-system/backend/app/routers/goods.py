from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.models.goods import Goods
from app.auth.decorators import roles_required

goods_bp = Blueprint("goods", __name__, url_prefix="/api/goods")

@goods_bp.route("", methods=["GET"])
@jwt_required()
@roles_required("admin", "warehouse_manager", "warehouse_keeper")
def get_goods():
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)
    search = request.args.get("search", "")
    category_id = request.args.get("category_id", type=int)
    status = request.args.get("status", "")

    query = Goods.query

    if search:
        query = query.filter(Goods.name.ilike(f"%{search}%") | Goods.sku.ilike(f"%{search}%"))
    if category_id:
        query = query.filter(Goods.category_id == category_id)
    if status:
        query = query.filter(Goods.status == status)

    pagination = query.paginate(page=page, per_page=page_size, error_out=False)
    
    return jsonify({
        "total": pagination.total,
        "page": page,
        "page_size": page_size,
        "data": [g.to_dict() for g in pagination.items]
    }), 200

@goods_bp.route("/low-stock", methods=["GET"])
@jwt_required()
@roles_required("admin", "warehouse_manager", "warehouse_keeper")
def get_low_stock():
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)

    query = Goods.query.filter(Goods.quantity_on_hand < Goods.min_stock)
    
    pagination = query.paginate(page=page, per_page=page_size, error_out=False)
    
    return jsonify({
        "total": pagination.total,
        "page": page,
        "page_size": page_size,
        "data": [g.to_dict() for g in pagination.items]
    }), 200

@goods_bp.route("", methods=["POST"])
@jwt_required()
@roles_required("admin", "warehouse_manager")
def create_goods():
    data = request.get_json()
    if not data:
        return jsonify({"error_code": "BAD_REQUEST", "message": "Yêu cầu không hợp lệ"}), 400

    required_fields = ["sku", "name", "category_id", "unit"]
    for field in required_fields:
        if field not in data:
            return jsonify({"error_code": "MISSING_FIELDS", "message": f"Thiếu trường bắt buộc: {field}"}), 400

    existing_goods = Goods.query.filter_by(sku=data["sku"]).first()
    if existing_goods:
        return jsonify({"error_code": "SKU_EXISTS", "message": "Mã SKU đã tồn tại"}), 400

    new_goods = Goods(
        sku=data["sku"],
        name=data["name"],
        category_id=data["category_id"],
        preferred_supplier_id=data.get("preferred_supplier_id"),
        unit=data["unit"],
        min_stock=data.get("min_stock", 0.0),
        max_stock=data.get("max_stock"),
        selling_price=data.get("selling_price", 0.0),
        description=data.get("description"),
        image_url=data.get("image_url"),
        status=data.get("status", "active")
    )

    db.session.add(new_goods)
    db.session.commit()

    return jsonify(new_goods.to_dict()), 201

@goods_bp.route("/<int:goods_id>", methods=["GET"])
@jwt_required()
@roles_required("admin", "warehouse_manager", "warehouse_keeper")
def get_goods_detail(goods_id):
    goods = Goods.query.get(goods_id)
    if not goods:
        return jsonify({"error_code": "NOT_FOUND", "message": "Không tìm thấy hàng hóa"}), 404
    return jsonify(goods.to_dict()), 200

@goods_bp.route("/<int:goods_id>", methods=["PUT"])
@jwt_required()
@roles_required("admin", "warehouse_manager")
def update_goods(goods_id):
    goods = Goods.query.get(goods_id)
    if not goods:
        return jsonify({"error_code": "NOT_FOUND", "message": "Không tìm thấy hàng hóa"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error_code": "BAD_REQUEST", "message": "Yêu cầu không hợp lệ"}), 400

    if "sku" in data and data["sku"] != goods.sku:
        existing = Goods.query.filter_by(sku=data["sku"]).first()
        if existing:
            return jsonify({"error_code": "SKU_EXISTS", "message": "Mã SKU đã tồn tại"}), 400
        goods.sku = data["sku"]

    if "name" in data:
        goods.name = data["name"]
    if "category_id" in data:
        goods.category_id = data["category_id"]
    if "preferred_supplier_id" in data:
        goods.preferred_supplier_id = data["preferred_supplier_id"]
    if "unit" in data:
        goods.unit = data["unit"]
    if "min_stock" in data:
        goods.min_stock = data["min_stock"]
    if "max_stock" in data:
        goods.max_stock = data["max_stock"]
    if "selling_price" in data:
        goods.selling_price = data["selling_price"]
    if "description" in data:
        goods.description = data["description"]
    if "image_url" in data:
        goods.image_url = data["image_url"]
    if "status" in data:
        goods.status = data["status"]

    db.session.commit()
    return jsonify(goods.to_dict()), 200
