"""
models/supplier_invoice.py — Model SupplierInvoice & SupplierPayment
=====================================================================
Ánh xạ 2 bảng `supplier_invoices` và `supplier_payments`
theo thiết kế mục 6.1 Prompt.md.

Nghiệp vụ công nợ (Prompt.md mục 3.6):
  - Khi nhập hàng từ NCC → phát sinh hóa đơn → công nợ phải trả.
  - Ghi nhận từng lần thanh toán (có thể thanh toán nhiều đợt).
  - Tra cứu công nợ còn lại theo NCC.

Ràng buộc quan trọng:
  - paid_amount KHÔNG lưu cột riêng — tính tổng động từ supplier_payments.
  - payment_status tự cập nhật khi thanh toán đủ (trong router transaction).
  - 1 receipt_id chỉ được liên kết với 1 hóa đơn duy nhất.
"""

from datetime import datetime
from app.extensions import db


class SupplierInvoice(db.Model):
    """
    Model tương ứng bảng `supplier_invoices` — Hóa đơn mua vào từ NCC.

    Quan hệ:
      - supplier  : Nhà cung cấp xuất hóa đơn
      - receipt   : Phiếu nhập kho tương ứng (1-1, tùy chọn)
      - payments  : Danh sách các lần thanh toán (1..*)
    """

    __tablename__ = "supplier_invoices"

    # ---- Khóa chính ----
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # ---- Khóa ngoại ----
    supplier_id = db.Column(
        db.Integer,
        db.ForeignKey("suppliers.id"),
        nullable=False,
    )
    """Nhà cung cấp xuất hóa đơn này"""

    receipt_id = db.Column(
        db.Integer,
        db.ForeignKey("goods_receipts.id"),
        nullable=True,
        unique=True,  # Mỗi phiếu nhập chỉ được tạo 1 hóa đơn
    )
    """
    Phiếu nhập kho liên kết (tùy chọn).
    unique=True đảm bảo 1 phiếu nhập → chỉ 1 hóa đơn.
    """

    # ---- Thông tin hóa đơn ----
    invoice_number = db.Column(db.String(100), nullable=False)
    """Số hóa đơn do NCC cấp (ví dụ: INV-2026-001)"""

    issue_date = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    """Ngày phát hành hóa đơn"""

    total_amount = db.Column(db.Float, nullable=False)
    """
    Tổng số tiền hóa đơn (> 0).
    Đây là số cố định khi tạo — không thay đổi sau đó.
    """

    payment_status = db.Column(
        db.String(50),
        default="chưa thanh toán",
        nullable=False,
    )
    """
    Trạng thái thanh toán (tự động cập nhật):
      - chưa thanh toán   : paid_amount = 0
      - thanh toán một phần : 0 < paid_amount < total_amount
      - đã thanh toán     : paid_amount >= total_amount
    """

    # ---- Audit timestamp ----
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # ---- Relationships ----
    supplier = db.relationship("Supplier", back_populates="supplier_invoices")
    """Nhà cung cấp"""

    receipt = db.relationship("GoodsReceipt", back_populates="supplier_invoice")
    """Phiếu nhập kho liên kết (quan hệ 1-1)"""

    payments = db.relationship(
        "SupplierPayment",
        back_populates="invoice",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    """Lịch sử các lần thanh toán"""

    @property
    def paid_amount(self) -> float:
        """
        Tính tổng tiền đã thanh toán từ bảng supplier_payments.
        Dùng property thay vì cột riêng để đảm bảo luôn nhất quán
        với dữ liệu thực tế trong bảng payments.
        """
        return sum(p.amount for p in self.payments)

    def to_dict(self, include_payments: bool = False) -> dict:
        """
        Chuyển object thành dict JSON.
        include_payments=True: thêm mảng lịch sử thanh toán chi tiết.
        """
        data = {
            "id": self.id,
            "supplier_id": self.supplier_id,
            "receipt_id": self.receipt_id,
            "invoice_number": self.invoice_number,
            "issue_date": self.issue_date.isoformat() if self.issue_date else None,
            "total_amount": self.total_amount,
            "paid_amount": self.paid_amount,
            "payment_status": self.payment_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_payments:
            data["payments"] = [p.to_dict() for p in self.payments]
        return data

    def __repr__(self) -> str:
        return (
            f"<SupplierInvoice id={self.id} "
            f"invoice_number={self.invoice_number} "
            f"status={self.payment_status}>"
        )


class SupplierPayment(db.Model):
    """
    Model tương ứng bảng `supplier_payments` — Lịch sử thanh toán.

    Mỗi bản ghi là 1 lần ghi nhận thanh toán cho 1 hóa đơn.
    Công nợ còn lại = invoice.total_amount - SUM(payments.amount).

    QUAN TRỌNG: Không cho sửa/xóa sau khi đã tạo.
    Nếu cần hoàn tiền → tạo bút toán điều chỉnh riêng (ngoài phạm vi MVP).
    """

    __tablename__ = "supplier_payments"

    # ---- Khóa chính ----
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # ---- Khóa ngoại ----
    invoice_id = db.Column(
        db.Integer,
        db.ForeignKey("supplier_invoices.id"),
        nullable=False,
    )
    """Hóa đơn được thanh toán"""

    # ---- Dữ liệu thanh toán ----
    amount = db.Column(db.Float, nullable=False)
    """Số tiền thanh toán lần này (> 0)"""

    payment_date = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    """Ngày giờ thực hiện thanh toán"""

    method = db.Column(db.String(100), nullable=True)
    """
    Hình thức thanh toán (tùy chọn).
    Ví dụ: 'tiền mặt', 'chuyển khoản', 'ủy nhiệm chi'...
    """

    # ---- Relationships ----
    invoice = db.relationship("SupplierInvoice", back_populates="payments")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "invoice_id": self.invoice_id,
            "amount": self.amount,
            "payment_date": self.payment_date.isoformat() if self.payment_date else None,
            "method": self.method,
        }

    def __repr__(self) -> str:
        return f"<SupplierPayment id={self.id} invoice_id={self.invoice_id} amount={self.amount}>"
