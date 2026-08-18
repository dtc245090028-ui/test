"""
routers/supplier_invoices.py — Endpoint Công nợ phải trả (Supplier Invoices & Payments)
=========================================================================================
Triển khai 4 endpoint theo api_contract.md mục 8:

  GET    /api/supplier-invoices          Danh sách hóa đơn (phân trang, filter)
  POST   /api/supplier-invoices          Tạo hóa đơn từ phiếu nhập
  GET    /api/supplier-invoices/{id}     Chi tiết hóa đơn + lịch sử thanh toán
  POST   /api/supplier-payments          Ghi nhận thanh toán → tự cập nhật payment_status

Role cho phép:
  - GET danh sách/chi tiết hóa đơn    : warehouse_manager, admin
  - POST tạo hóa đơn                  : warehouse_keeper, warehouse_manager, admin
  - POST ghi nhận thanh toán          : warehouse_manager, admin

Ràng buộc nghiệp vụ cốt lõi (Prompt.md mục 3.6, 6.1):
  1. total_amount > 0.
  2. Mỗi receipt_id chỉ được liên kết với 1 hóa đơn duy nhất.
  3. receipt_id (nếu có) phải thuộc đúng supplier_id.
  4. amount thanh toán > 0.
  5. Tổng tiền thanh toán không vượt quá total_amount (chặn overpayment).
  6. Hóa đơn đã "đã thanh toán" → không cho thanh toán thêm.
  7. Sau khi ghi nhận thanh toán: nếu paid_amount >= total_amount
     → tự động đổi payment_status = "đã thanh toán" (trong transaction).
"""

from flask import Blueprint, request, jsonify
from datetime import datetime

from app.extensions import db
from app.models.supplier_invoice import SupplierInvoice, SupplierPayment
from app.models.supplier import Supplier
from app.models.goods_receipt import GoodsReceipt
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.auth.decorators import roles_required

# Blueprint — url_prefix theo chuẩn api_contract.md
supplier_invoices_bp = Blueprint(
    "supplier_invoices", __name__, url_prefix="/api/supplier-invoices"
)

supplier_payments_bp = Blueprint(
    "supplier_payments", __name__, url_prefix="/api/supplier-payments"
)


# ---------------------------------------------------------------------------
# Helper: Tính tổng paid_amount từ DB (tránh dùng ORM lazy load không nhất quán)
# ---------------------------------------------------------------------------
def _get_paid_amount(invoice_id: int) -> float:
    """
    Tính tổng tiền đã thanh toán cho hóa đơn bằng SQL SUM.
    Dùng db.session.execute để tính chính xác nhất, tránh cache ORM.
    """
    from sqlalchemy import func
    result = db.session.execute(
        db.select(func.coalesce(func.sum(SupplierPayment.amount), 0.0))
        .where(SupplierPayment.invoice_id == invoice_id)
    ).scalar()
    return float(result)


# ---------------------------------------------------------------------------
# GET /api/supplier-invoices — Danh sách hóa đơn (phân trang, filter)
# ---------------------------------------------------------------------------
@supplier_invoices_bp.route("", methods=["GET"])
@jwt_required()
@roles_required("warehouse_manager", "admin")
def get_supplier_invoices():
    """
    Lấy danh sách hóa đơn với phân trang và filter tùy chọn.

    Query params:
      page            : Trang hiện tại (mặc định 1)
      page_size       : Số bản ghi/trang (mặc định 20)
      supplier_id     : Lọc theo NCC
      payment_status  : Lọc theo trạng thái thanh toán

    Response 200: { total, page, page_size, data: [...] }
    Lưu ý: data không bao gồm mảng payments — gọi GET/{id} để lấy chi tiết.
    """
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)
    supplier_id = request.args.get("supplier_id", type=int)
    payment_status = request.args.get("payment_status")

    query = SupplierInvoice.query

    if supplier_id:
        query = query.filter(SupplierInvoice.supplier_id == supplier_id)
    if payment_status:
        query = query.filter(SupplierInvoice.payment_status == payment_status)

    pagination = query.order_by(SupplierInvoice.issue_date.desc()).paginate(
        page=page, per_page=page_size, error_out=False
    )

    return jsonify({
        "total": pagination.total,
        "page": pagination.page,
        "page_size": pagination.per_page,
        "data": [inv.to_dict() for inv in pagination.items],
    }), 200


# ---------------------------------------------------------------------------
# POST /api/supplier-invoices — Tạo hóa đơn từ phiếu nhập
# ---------------------------------------------------------------------------
@supplier_invoices_bp.route("", methods=["POST"])
@jwt_required()
@roles_required("warehouse_keeper", "warehouse_manager", "admin")
def create_supplier_invoice():
    """
    Tạo hóa đơn mua vào từ nhà cung cấp.
    Hóa đơn có thể liên kết với phiếu nhập (receipt_id) hoặc không.

    Request body:
      {
        "supplier_id"    : int   (bắt buộc),
        "receipt_id"     : int   (tùy chọn),
        "invoice_number" : str   (bắt buộc),
        "issue_date"     : str   ISO 8601 (tùy chọn, mặc định now),
        "total_amount"   : float (bắt buộc, > 0)
      }

    Ràng buộc:
      - supplier phải active
      - receipt_id (nếu có): phải thuộc supplier_id, chưa có hóa đơn liên kết
      - total_amount > 0
      - invoice_number bắt buộc

    Response 201: chi tiết hóa đơn vừa tạo
    """
    data = request.get_json() or {}

    # ---- Validate trường bắt buộc ----
    supplier_id = data.get("supplier_id")
    invoice_number = data.get("invoice_number")
    total_amount = data.get("total_amount")

    if not supplier_id or not invoice_number or total_amount is None:
        return jsonify({
            "error_code": "MISSING_FIELDS",
            "message": "Thiếu supplier_id, invoice_number hoặc total_amount"
        }), 400

    if float(total_amount) <= 0:
        return jsonify({
            "error_code": "INVALID_AMOUNT",
            "message": "total_amount phải lớn hơn 0"
        }), 400

    # ---- Kiểm tra NCC tồn tại ----
    supplier = db.session.get(Supplier, supplier_id)
    if not supplier:
        return jsonify({
            "error_code": "SUPPLIER_NOT_FOUND",
            "message": f"Không tìm thấy nhà cung cấp ID={supplier_id}"
        }), 404

    # ---- Parse issue_date ----
    issue_date = datetime.utcnow()
    issue_date_str = data.get("issue_date")
    if issue_date_str:
        try:
            issue_date = datetime.fromisoformat(
                issue_date_str.replace("Z", "+00:00")
            ).replace(tzinfo=None)
        except ValueError:
            return jsonify({
                "error_code": "INVALID_DATE_FORMAT",
                "message": "issue_date phải theo chuẩn ISO 8601 (ví dụ: 2026-08-18T08:00:00Z)"
            }), 400

    # ---- Kiểm tra receipt_id nếu có ----
    receipt_id = data.get("receipt_id")
    if receipt_id:
        receipt = db.session.get(GoodsReceipt, receipt_id)
        if not receipt:
            return jsonify({
                "error_code": "RECEIPT_NOT_FOUND",
                "message": f"Không tìm thấy phiếu nhập ID={receipt_id}"
            }), 404

        # receipt phải thuộc đúng supplier_id đã chọn
        if receipt.supplier_id != supplier_id:
            return jsonify({
                "error_code": "RECEIPT_SUPPLIER_MISMATCH",
                "message": "Phiếu nhập không thuộc nhà cung cấp đã chọn"
            }), 400

        # 1 receipt chỉ được liên kết 1 hóa đơn (unique=True ở model)
        existing = SupplierInvoice.query.filter_by(receipt_id=receipt_id).first()
        if existing:
            return jsonify({
                "error_code": "RECEIPT_ALREADY_INVOICED",
                "message": f"Phiếu nhập ID={receipt_id} đã có hóa đơn liên kết (ID={existing.id})"
            }), 400

    # ---- Tạo hóa đơn ----
    try:
        invoice = SupplierInvoice(
            supplier_id=supplier_id,
            receipt_id=receipt_id,
            invoice_number=invoice_number,
            issue_date=issue_date,
            total_amount=float(total_amount),
            payment_status="chưa thanh toán",
        )
        db.session.add(invoice)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({
            "error_code": "DATABASE_ERROR",
            "message": "Có lỗi xảy ra khi tạo hóa đơn. Vui lòng thử lại."
        }), 500

    return jsonify(invoice.to_dict()), 201


# ---------------------------------------------------------------------------
# GET /api/supplier-invoices/<id> — Chi tiết hóa đơn + lịch sử thanh toán
# ---------------------------------------------------------------------------
@supplier_invoices_bp.route("/<int:invoice_id>", methods=["GET"])
@jwt_required()
@roles_required("warehouse_manager", "admin")
def get_supplier_invoice_detail(invoice_id):
    """
    Lấy chi tiết hóa đơn theo ID, bao gồm mảng payments (lịch sử thanh toán).

    Response 200: to_dict(include_payments=True)
    Response 404: INVOICE_NOT_FOUND nếu không tồn tại
    """
    invoice = db.session.get(SupplierInvoice, invoice_id)
    if not invoice:
        return jsonify({
            "error_code": "INVOICE_NOT_FOUND",
            "message": f"Không tìm thấy hóa đơn ID={invoice_id}"
        }), 404

    return jsonify(invoice.to_dict(include_payments=True)), 200


# ---------------------------------------------------------------------------
# POST /api/supplier-payments — Ghi nhận thanh toán
# ---------------------------------------------------------------------------
@supplier_payments_bp.route("", methods=["POST"])
@jwt_required()
@roles_required("warehouse_manager", "admin")
def create_supplier_payment():
    """
    Ghi nhận 1 lần thanh toán công nợ cho 1 hóa đơn.

    Request body:
      {
        "invoice_id"   : int   (bắt buộc),
        "amount"       : float (bắt buộc, > 0),
        "payment_date" : str   ISO 8601 (tùy chọn, mặc định now),
        "method"       : str   (tùy chọn, ví dụ: 'chuyển khoản', 'tiền mặt')
      }

    Ràng buộc:
      - amount > 0
      - Hóa đơn phải tồn tại
      - Hóa đơn chưa ở trạng thái "đã thanh toán"
      - paid_amount + amount <= total_amount (chặn overpayment)
      - Sau khi thanh toán: nếu paid_amount_mới >= total_amount
        → tự động đổi payment_status = "đã thanh toán" (trong transaction)

    Response 201: chi tiết lần thanh toán vừa tạo + invoice_payment_status
    """
    data = request.get_json() or {}

    invoice_id = data.get("invoice_id")
    amount = data.get("amount")

    if not invoice_id or amount is None:
        return jsonify({
            "error_code": "MISSING_FIELDS",
            "message": "Thiếu invoice_id hoặc amount"
        }), 400

    if float(amount) <= 0:
        return jsonify({
            "error_code": "INVALID_AMOUNT",
            "message": "Số tiền thanh toán phải lớn hơn 0"
        }), 400

    # ---- Kiểm tra hóa đơn tồn tại ----
    invoice = db.session.get(SupplierInvoice, invoice_id)
    if not invoice:
        return jsonify({
            "error_code": "INVOICE_NOT_FOUND",
            "message": f"Không tìm thấy hóa đơn ID={invoice_id}"
        }), 404

    # ---- Hóa đơn đã thanh toán đủ rồi ----
    if invoice.payment_status == "đã thanh toán":
        return jsonify({
            "error_code": "INVOICE_ALREADY_PAID",
            "message": "Hóa đơn này đã được thanh toán đủ, không thể thanh toán thêm"
        }), 400

    # ---- Kiểm tra overpayment ----
    current_paid = _get_paid_amount(invoice_id)
    new_amount = float(amount)
    if current_paid + new_amount > invoice.total_amount:
        remaining = invoice.total_amount - current_paid
        return jsonify({
            "error_code": "OVERPAYMENT",
            "message": (
                f"Số tiền thanh toán ({new_amount:,.0f}) vượt quá "
                f"công nợ còn lại ({remaining:,.0f}). "
                f"Tổng hóa đơn: {invoice.total_amount:,.0f}, "
                f"Đã thanh toán: {current_paid:,.0f}."
            )
        }), 400

    # ---- Parse payment_date ----
    payment_date = datetime.utcnow()
    payment_date_str = data.get("payment_date")
    if payment_date_str:
        try:
            payment_date = datetime.fromisoformat(
                payment_date_str.replace("Z", "+00:00")
            ).replace(tzinfo=None)
        except ValueError:
            return jsonify({
                "error_code": "INVALID_DATE_FORMAT",
                "message": "payment_date phải theo chuẩn ISO 8601 (ví dụ: 2026-08-20T10:00:00Z)"
            }), 400

    # ---- Ghi nhận thanh toán + cập nhật payment_status (transaction) ----
    try:
        payment = SupplierPayment(
            invoice_id=invoice_id,
            amount=new_amount,
            payment_date=payment_date,
            method=data.get("method"),
        )
        db.session.add(payment)

        # Tính lại tổng đã thanh toán sau khi thêm lần này
        new_paid_total = current_paid + new_amount

        # Cập nhật payment_status tự động dựa trên so sánh với total_amount
        if new_paid_total >= invoice.total_amount:
            invoice.payment_status = "đã thanh toán"
        elif new_paid_total > 0:
            invoice.payment_status = "thanh toán một phần"
        # (trường hợp = 0 không xảy ra vì đã validate amount > 0)

        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({
            "error_code": "DATABASE_ERROR",
            "message": "Có lỗi xảy ra khi ghi nhận thanh toán. Vui lòng thử lại."
        }), 500

    # Trả về kèm invoice_payment_status để frontend biết ngay trạng thái mới
    result = payment.to_dict()
    result["invoice_payment_status"] = invoice.payment_status
    return jsonify(result), 201
