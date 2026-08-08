"""
routers/suppliers.py — Endpoints quản lý Nhà cung cấp (Suppliers)
===================================================================
Triển khai 5 endpoint theo api_contract.md mục 2:

  GET    /api/suppliers          Danh sách, filter ?search=&status=&page=&page_size=
  POST   /api/suppliers          Tạo mới NCC
  GET    /api/suppliers/{id}     Chi tiết 1 NCC
  PUT    /api/suppliers/{id}     Cập nhật NCC
  DELETE /api/suppliers/{id}     Ngừng hợp tác (soft-delete, đổi status='inactive')

Phân quyền (api_contract.md mục 2):
  GET    danh sách   : warehouse_manager, admin
  POST   tạo mới    : warehouse_manager, admin
  GET    chi tiết   : warehouse_keeper, warehouse_manager, admin
  PUT    cập nhật   : warehouse_manager, admin
  DELETE ngừng HT   : admin (Ban điều hành)

Response lỗi theo chuẩn AGENTS.md mục 8:
  {"error_code": "SCREAMING_SNAKE_CASE", "message": "Tiếng Việt, rõ ràng"}
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy import or_

from app.auth.decorators import roles_required
from app.extensions import db
from app.models.supplier import Supplier

# Blueprint đặt tên "suppliers", prefix "/api/suppliers"
# Tất cả route trong file này sẽ có prefix này
suppliers_bp = Blueprint("suppliers", __name__, url_prefix="/api/suppliers")

# ---- Hằng số phân trang ----
DEFAULT_PAGE_SIZE = 20   # Số bản ghi mặc định mỗi trang
MAX_PAGE_SIZE = 100       # Giới hạn tối đa để tránh query quá lớn


# ========================================================
# GET /api/suppliers — Danh sách NCC
# ========================================================

@suppliers_bp.route("", methods=["GET"])
@jwt_required()                                          # Bước 1: token hợp lệ?
@roles_required("admin", "warehouse_manager")            # Bước 2: đúng role?
def list_suppliers():
    """
    Trả về danh sách nhà cung cấp, hỗ trợ:
      - Tìm kiếm tự do: ?search=<tên|điện thoại|email>
      - Lọc theo trạng thái: ?status=active|inactive
      - Phân trang: ?page=1&page_size=20

    Chỉ warehouse_manager và admin được xem danh sách.
    (Thủ kho chỉ được xem chi tiết 1 NCC — theo api_contract.md mục 2)

    Response 200:
    {
      "data": [ { ...supplier fields... }, ... ],
      "pagination": { "page": 1, "page_size": 20, "total": 50, "total_pages": 3 }
    }
    """
    # ---- Đọc query params ----
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()

    # Phân trang — validate để tránh giá trị âm hoặc quá lớn
    try:
        page = max(1, int(request.args.get("page", 1)))
        page_size = min(
            MAX_PAGE_SIZE,
            max(1, int(request.args.get("page_size", DEFAULT_PAGE_SIZE)))
        )
    except ValueError:
        return jsonify({
            "error_code": "INVALID_PAGINATION",
            "message": "Tham số phân trang (page, page_size) phải là số nguyên dương",
        }), 400

    # ---- Xây dựng query ----
    query = Supplier.query

    # Lọc theo từ khóa tìm kiếm (tên, người đại diện, SĐT, email)
    if search:
        like_pattern = f"%{search}%"  # SQL LIKE pattern
        query = query.filter(
            or_(
                Supplier.name.ilike(like_pattern),           # ilike: case-insensitive
                Supplier.contact_person.ilike(like_pattern),
                Supplier.phone.ilike(like_pattern),
                Supplier.email.ilike(like_pattern),
            )
        )

    # Lọc theo trạng thái nếu có
    if status_filter in ("active", "inactive"):
        query = query.filter(Supplier.status == status_filter)
    elif status_filter:
        # Truyền status không hợp lệ → báo lỗi rõ ràng
        return jsonify({
            "error_code": "INVALID_STATUS",
            "message": "Tham số status chỉ chấp nhận 'active' hoặc 'inactive'",
        }), 400

    # Sắp xếp theo tên A→Z, bản mới nhất lên đầu nếu trùng tên
    query = query.order_by(Supplier.name.asc(), Supplier.created_at.desc())

    # ---- Phân trang ----
    # paginate() của SQLAlchemy trả về Pagination object
    pagination = query.paginate(page=page, per_page=page_size, error_out=False)

    return jsonify({
        "data": [s.to_dict() for s in pagination.items],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": pagination.total,             # Tổng bản ghi khớp filter
            "total_pages": pagination.pages,       # Tổng số trang
        },
    }), 200


# ========================================================
# POST /api/suppliers — Tạo mới NCC
# ========================================================

@suppliers_bp.route("", methods=["POST"])
@jwt_required()
@roles_required("admin", "warehouse_manager")
def create_supplier():
    """
    Tạo mới nhà cung cấp.

    Request body (JSON):
    {
      "name": "Công ty ABC",          # bắt buộc
      "contact_person": "Nguyễn A",   # tùy chọn
      "phone": "0901234567",           # tùy chọn
      "email": "abc@example.com",      # tùy chọn
      "address": "123 Đường XYZ",     # tùy chọn
      "tax_code": "0123456789",        # tùy chọn
      "notes": "Ghi chú...",           # tùy chọn
      "status": "active"               # tùy chọn, mặc định 'active'
    }

    Response 201: supplier vừa tạo dạng dict
    """
    data = request.get_json(silent=True)

    # Kiểm tra body có tồn tại và đúng Content-Type
    if not data:
        return jsonify({
            "error_code": "MISSING_BODY",
            "message": "Request body không hợp lệ hoặc thiếu Content-Type: application/json",
        }), 400

    # ---- Validate field bắt buộc ----
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({
            "error_code": "MISSING_FIELDS",
            "message": "Trường 'name' (tên nhà cung cấp) là bắt buộc",
        }), 400

    # ---- Validate status nếu được cung cấp ----
    status = data.get("status", "active")
    if status not in ("active", "inactive"):
        return jsonify({
            "error_code": "INVALID_STATUS",
            "message": "Trường status chỉ chấp nhận 'active' hoặc 'inactive'",
        }), 400

    # ---- Kiểm tra trùng tên NCC (case-insensitive) ----
    existing = Supplier.query.filter(Supplier.name.ilike(name)).first()
    if existing:
        return jsonify({
            "error_code": "SUPPLIER_NAME_DUPLICATE",
            "message": f"Nhà cung cấp với tên '{name}' đã tồn tại trong hệ thống",
        }), 409

    # ---- Kiểm tra trùng mã số thuế ----
    tax_code = (data.get("tax_code") or "").strip() or None
    if tax_code:
        existing_tax = Supplier.query.filter_by(tax_code=tax_code).first()
        if existing_tax:
            return jsonify({
                "error_code": "TAX_CODE_DUPLICATE",
                "message": f"Mã số thuế '{tax_code}' đã được đăng ký cho NCC khác",
            }), 409

    # ---- Tạo bản ghi mới ----
    supplier = Supplier(
        name=name,
        contact_person=(data.get("contact_person") or "").strip() or None,
        phone=(data.get("phone") or "").strip() or None,
        email=(data.get("email") or "").strip() or None,
        address=(data.get("address") or "").strip() or None,
        tax_code=tax_code,
        notes=(data.get("notes") or "").strip() or None,
        status=status,
    )

    db.session.add(supplier)
    db.session.commit()  # Commit để lấy id được gán từ CSDL

    return jsonify(supplier.to_dict()), 201


# ========================================================
# GET /api/suppliers/<id> — Chi tiết 1 NCC
# ========================================================

@suppliers_bp.route("/<int:supplier_id>", methods=["GET"])
@jwt_required()
@roles_required("admin", "warehouse_manager", "warehouse_keeper")  # Thủ kho được xem
def get_supplier(supplier_id: int):
    """
    Trả về thông tin chi tiết của 1 nhà cung cấp.

    Path param:
      supplier_id: ID của NCC (số nguyên)

    Response 200: dict đầy đủ thông tin NCC
    Response 404: NCC không tồn tại
    """
    # get_or_404 tự trả 404 nếu không tìm thấy, khớp với error handler trong main.py
    supplier = db.session.get(Supplier, supplier_id)

    if supplier is None:
        return jsonify({
            "error_code": "SUPPLIER_NOT_FOUND",
            "message": f"Không tìm thấy nhà cung cấp với ID={supplier_id}",
        }), 404

    return jsonify(supplier.to_dict()), 200


# ========================================================
# PUT /api/suppliers/<id> — Cập nhật NCC
# ========================================================

@suppliers_bp.route("/<int:supplier_id>", methods=["PUT"])
@jwt_required()
@roles_required("admin", "warehouse_manager")
def update_supplier(supplier_id: int):
    """
    Cập nhật thông tin nhà cung cấp.

    Chỉ cập nhật các field được gửi lên (PATCH semantics trong PUT).
    Field không có trong body → giữ nguyên giá trị cũ.

    Request body (JSON) — tất cả tùy chọn:
    {
      "name": "...",
      "contact_person": "...",
      "phone": "...",
      "email": "...",
      "address": "...",
      "tax_code": "...",
      "notes": "...",
      "status": "active" | "inactive"
    }

    Response 200: supplier đã cập nhật
    """
    # Tìm NCC theo ID
    supplier = db.session.get(Supplier, supplier_id)
    if supplier is None:
        return jsonify({
            "error_code": "SUPPLIER_NOT_FOUND",
            "message": f"Không tìm thấy nhà cung cấp với ID={supplier_id}",
        }), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({
            "error_code": "MISSING_BODY",
            "message": "Request body không hợp lệ hoặc thiếu Content-Type: application/json",
        }), 400

    # ---- Cập nhật từng field nếu được cung cấp trong body ----

    if "name" in data:
        new_name = (data["name"] or "").strip()
        if not new_name:
            return jsonify({
                "error_code": "MISSING_FIELDS",
                "message": "Trường 'name' không được để trống",
            }), 400
        # Kiểm tra trùng tên với NCC khác (không phải chính mình)
        duplicate = Supplier.query.filter(
            Supplier.name.ilike(new_name),
            Supplier.id != supplier_id,
        ).first()
        if duplicate:
            return jsonify({
                "error_code": "SUPPLIER_NAME_DUPLICATE",
                "message": f"Nhà cung cấp với tên '{new_name}' đã tồn tại",
            }), 409
        supplier.name = new_name

    if "status" in data:
        if data["status"] not in ("active", "inactive"):
            return jsonify({
                "error_code": "INVALID_STATUS",
                "message": "Trường status chỉ chấp nhận 'active' hoặc 'inactive'",
            }), 400
        supplier.status = data["status"]

    if "tax_code" in data:
        new_tax = (data["tax_code"] or "").strip() or None
        if new_tax:
            # Kiểm tra trùng MST với NCC khác
            duplicate_tax = Supplier.query.filter(
                Supplier.tax_code == new_tax,
                Supplier.id != supplier_id,
            ).first()
            if duplicate_tax:
                return jsonify({
                    "error_code": "TAX_CODE_DUPLICATE",
                    "message": f"Mã số thuế '{new_tax}' đã được đăng ký cho NCC khác",
                }), 409
        supplier.tax_code = new_tax

    # Các field không cần validate phức tạp — cập nhật trực tiếp
    if "contact_person" in data:
        supplier.contact_person = (data["contact_person"] or "").strip() or None
    if "phone" in data:
        supplier.phone = (data["phone"] or "").strip() or None
    if "email" in data:
        supplier.email = (data["email"] or "").strip() or None
    if "address" in data:
        supplier.address = (data["address"] or "").strip() or None
    if "notes" in data:
        supplier.notes = (data["notes"] or "").strip() or None

    db.session.commit()  # updated_at tự cập nhật nhờ onupdate=datetime.utcnow

    return jsonify(supplier.to_dict()), 200


# ========================================================
# DELETE /api/suppliers/<id> — Ngừng hợp tác (Soft-delete)
# ========================================================

@suppliers_bp.route("/<int:supplier_id>", methods=["DELETE"])
@jwt_required()
@roles_required("admin")   # Chỉ Ban điều hành mới được ngừng hợp tác
def deactivate_supplier(supplier_id: int):
    """
    Ngừng hợp tác với nhà cung cấp (SOFT-DELETE).

    QUAN TRỌNG — Ràng buộc nghiệp vụ:
      Endpoint này KHÔNG xóa bản ghi khỏi CSDL.
      Chỉ đổi status = 'inactive' để giữ nguyên:
        - Lịch sử đơn đặt hàng đã gửi cho NCC
        - Phiếu nhập kho đã thực hiện
        - Hóa đơn và công nợ đã phát sinh

    Nếu NCC đang ở trạng thái 'inactive' → trả lỗi 409 để tránh
    gọi API thừa (idempotency).

    Response 200: { "message": "...", "supplier": { ...updated supplier... } }
    """
    supplier = db.session.get(Supplier, supplier_id)
    if supplier is None:
        return jsonify({
            "error_code": "SUPPLIER_NOT_FOUND",
            "message": f"Không tìm thấy nhà cung cấp với ID={supplier_id}",
        }), 404

    # Kiểm tra nếu đã ngừng hợp tác rồi → không cần làm gì thêm
    if supplier.status == "inactive":
        return jsonify({
            "error_code": "SUPPLIER_ALREADY_INACTIVE",
            "message": f"Nhà cung cấp '{supplier.name}' đã ở trạng thái ngừng hợp tác",
        }), 409

    # Soft-delete: chỉ đổi trạng thái, KHÔNG gọi db.session.delete()
    supplier.status = "inactive"
    db.session.commit()

    return jsonify({
        "message": f"Đã ngừng hợp tác với nhà cung cấp '{supplier.name}'",
        "supplier": supplier.to_dict(),
    }), 200
