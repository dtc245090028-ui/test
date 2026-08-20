from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.auth.decorators import roles_required
from app.models.goods import Goods
from app.models.goods_issue import GoodsIssueItem, GoodsIssue
from app.models.goods_receipt import GoodsReceiptItem, GoodsReceipt
from app.ai.inventory_report_service import generate_inventory_report
from app.ai.reorder_suggestion_service import generate_reorder_suggestion
from app.extensions import db
from datetime import datetime, timedelta, timezone
from sqlalchemy import func

ai_features_bp = Blueprint('ai_features', __name__, url_prefix='/api/ai')

@ai_features_bp.route('/inventory-report', methods=['POST'])
@jwt_required()
@roles_required("admin", "warehouse_manager")
def get_inventory_report():
    user_id = int(get_jwt_identity())
    # Tổng hợp dữ liệu tồn kho để gửi cho AI
    goods = Goods.query.filter_by(status='active').all()
    inventory_data = []
    
    for item in goods:
        inventory_data.append({
            "sku": item.sku,
            "name": item.name,
            "quantity_on_hand": item.quantity_on_hand,
            "min_stock": item.min_stock,
            "max_stock": item.max_stock
        })
    
    report = generate_inventory_report(inventory_data, user_id=user_id)
    if "error" in report:
        return jsonify({"error_code": "AI_SERVICE_ERROR", "message": report["error"]}), 500
        
    return jsonify(report), 200

@ai_features_bp.route('/reorder-suggestion', methods=['POST'])
@jwt_required()
@roles_required("admin", "warehouse_manager", "warehouse_keeper")
def get_reorder_suggestion():
    user_id = int(get_jwt_identity())
    # Lấy dữ liệu tồn kho hiện tại và số lượng xuất trong 30 ngày gần nhất
    goods = Goods.query.filter_by(status='active').all()
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    
    reorder_data = []
    for item in goods:
        # Tính tổng số lượng xuất trong 30 ngày qua
        total_issued = db.session.query(func.sum(GoodsIssueItem.quantity)).join(
            GoodsIssue, GoodsIssueItem.issue_id == GoodsIssue.id
        ).filter(
            GoodsIssueItem.goods_id == item.id,
            GoodsIssue.issued_date >= thirty_days_ago
        ).scalar() or 0
        
        reorder_data.append({
            "sku": item.sku,
            "name": item.name,
            "quantity_on_hand": item.quantity_on_hand,
            "min_stock": item.min_stock,
            "30_days_issue_qty": float(total_issued)
        })
        
    suggestion = generate_reorder_suggestion(reorder_data, user_id=user_id)
    if "error" in suggestion:
        return jsonify({"error_code": "AI_SERVICE_ERROR", "message": suggestion["error"]}), 500
        
    return jsonify(suggestion), 200
