"""
models/supplier.py — Model Supplier (bảng suppliers trong CSDL)
================================================================
Ánh xạ bảng `suppliers` theo thiết kế mục 6.1 Prompt.md.

Các trường (Prompt.md mục 3.2 & bảng 6.1):
  name, contact_person, phone, email, address,
  tax_code, notes, status

Giá trị status hợp lệ:
  - 'active'   : Đang hợp tác
  - 'inactive' : Ngừng hợp tác (soft-delete — KHÔNG xóa cứng)

Ràng buộc nghiệp vụ (AGENTS.md mục 7):
  DELETE không xóa cứng — chỉ đổi status = 'inactive'
  để giữ lại lịch sử đơn hàng / phiếu nhập liên quan.
"""

from datetime import datetime
from app.extensions import db


class Supplier(db.Model):
    """
    Model tương ứng bảng `suppliers`.
    SQLAlchemy tự tạo/ánh xạ bảng này khi gọi db.create_all().

    Quan hệ:
      - purchase_orders   : 1 NCC có nhiều đơn đặt hàng
      - goods_receipts    : 1 NCC có nhiều phiếu nhập
      - supplier_invoices : 1 NCC có nhiều hóa đơn
      - goods             : 1 NCC có thể là preferred_supplier của nhiều mặt hàng
    """

    __tablename__ = "suppliers"

    # ---- Khóa chính ----

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    """Khóa chính, tự tăng"""

    # ---- Thông tin cơ bản ----

    name = db.Column(db.String(200), nullable=False)
    """
    Tên nhà cung cấp — bắt buộc, không trùng (unique).
    Ví dụ: 'Công ty TNHH Thương mại ABC'
    """

    contact_person = db.Column(db.String(100), nullable=True)
    """
    Người đại diện / liên hệ chính của NCC.
    Tùy chọn — không phải mọi NCC đều có đầu mối cố định.
    """

    phone = db.Column(db.String(20), nullable=True)
    """
    Số điện thoại liên hệ.
    Lưu dạng chuỗi để hỗ trợ cả định dạng quốc tế (+84...) và nội địa.
    """

    email = db.Column(db.String(150), nullable=True)
    """Email liên hệ của NCC"""

    address = db.Column(db.String(500), nullable=True)
    """Địa chỉ trụ sở / địa chỉ giao hàng của NCC"""

    tax_code = db.Column(db.String(20), nullable=True, unique=True)
    """
    Mã số thuế (MST) — tùy chọn, nếu có thì phải duy nhất.
    unique=True để tránh nhập trùng cùng NCC với tên khác nhau.
    """

    notes = db.Column(db.Text, nullable=True)
    """
    Ghi chú tự do về NCC.
    Ví dụ: điều khoản thanh toán đặc biệt, lưu ý khi đặt hàng...
    """

    # ---- Trạng thái ----

    status = db.Column(
        db.Enum("active", "inactive", name="supplier_status"),
        nullable=False,
        default="active",
    )
    """
    Trạng thái hợp tác:
      - 'active'   : Đang hợp tác bình thường
      - 'inactive' : Ngừng hợp tác (tương đương soft-delete)

    QUAN TRỌNG: Khi người dùng DELETE một NCC, backend chỉ
    đổi trường này thành 'inactive', KHÔNG xóa dòng khỏi CSDL.
    Lý do: giữ nguyên lịch sử mua hàng, đơn đặt hàng liên quan.
    """

    # ---- Audit timestamp ----

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    """Thời điểm tạo bản ghi (UTC)"""

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    """
    Thời điểm cập nhật gần nhất (UTC).
    SQLAlchemy tự cập nhật khi gọi db.session.commit() sau khi sửa.
    """

    # ---- Relationships (back-references, lazy load) ----
    #
    # CÁC RELATIONSHIP BÊN DƯỚI còn comment vì model tương ứng chưa được sinh.
    # Uncomment từng relationship khi module liên quan được tạo:
    #   - PurchaseOrder  → module purchase_orders
    #   - GoodsReceipt   → module goods_receipts
    #   - SupplierInvoice → module supplier_invoices
    #   - Goods          → module goods

    purchase_orders = db.relationship(
        "PurchaseOrder",
        back_populates="supplier",
        lazy="dynamic",
    )
    """Các đơn đặt hàng gửi cho NCC này"""

    goods_receipts = db.relationship(
        "GoodsReceipt",
        back_populates="supplier",
        lazy="dynamic",
    )
    """Các phiếu nhập từ NCC này"""

    supplier_invoices = db.relationship(
        "SupplierInvoice",
        back_populates="supplier",
        lazy="dynamic",
    )
    """Các hóa đơn mua vào từ NCC này"""

    preferred_goods = db.relationship(
        "Goods",
        back_populates="preferred_supplier",
        lazy="dynamic",
        foreign_keys="Goods.preferred_supplier_id",
    )
    """Các mặt hàng mà NCC này là nhà cung cấp ưu tiên"""

    # ---- Methods ----

    def to_dict(self) -> dict:
        """
        Chuyển object Supplier thành dict để trả về trong response JSON.

        Tuân theo AGENTS.md mục 5: field dùng snake_case.
        Ngày giờ theo ISO 8601 (api_contract.md chuẩn chung).
        """
        return {
            "id": self.id,
            "name": self.name,
            "contact_person": self.contact_person,
            "phone": self.phone,
            "email": self.email,
            "address": self.address,
            "tax_code": self.tax_code,
            "notes": self.notes,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        """Hiển thị khi debug (print object)"""
        return f"<Supplier id={self.id} name={self.name!r} status={self.status}>"
