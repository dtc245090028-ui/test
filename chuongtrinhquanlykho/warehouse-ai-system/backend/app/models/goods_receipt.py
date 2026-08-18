"""
models/goods_receipt.py — Model GoodsReceipt & GoodsReceiptItem
================================================================
Ánh xạ hai bảng `goods_receipts` và `goods_receipt_items`
theo thiết kế mục 6.1 Prompt.md.

Bảng goods_receipts:
  - Phiếu nhập kho (header)
  - Liên kết tùy chọn với PurchaseOrder (po_id nullable):
      + Nếu có po_id → nhập theo đơn đặt hàng (có thể đối chiếu)
      + Nếu không   → nhập độc lập (mua lẻ, tặng, điều chỉnh...)
  - Liên kết bắt buộc với Supplier (supplier_id)
  - created_by → user lập phiếu (Thủ kho)

Bảng goods_receipt_items:
  - Từng dòng hàng hóa trong phiếu nhập
  - unit_price: GIÁ NHẬP RIÊNG TỪNG LẦN — KHÔNG lấy từ goods.
    Đây là nguồn dữ liệu duy nhất để tính giá vốn tồn kho.
    (Ràng buộc quan trọng — Prompt.md mục 6.2 & api_contract.md mục 5)

Ràng buộc nghiệp vụ quan trọng (Prompt.md mục 3.3 & 6.2):
  - quantity phải > 0 (chặn ở router)
  - unit_price phải >= 0 và được lưu cố định theo lần nhập
  - Cập nhật goods.quantity_on_hand qua DB transaction trong router
    để tránh sai lệch số liệu (xem routers/goods_receipts.py)
"""

from datetime import datetime
from app.extensions import db


class GoodsReceipt(db.Model):
    """
    Model tương ứng bảng `goods_receipts` — Phiếu nhập kho (header).

    Quan hệ:
      - supplier         : Nhà cung cấp giao hàng lần này
      - purchase_order   : PO tương ứng (nếu có) — nullable
      - creator          : Thủ kho lập phiếu
      - items            : Các dòng chi tiết hàng nhập (1..*)
    """

    __tablename__ = "goods_receipts"

    # ---- Khóa chính ----
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # ---- Khóa ngoại ----
    supplier_id = db.Column(
        db.Integer,
        db.ForeignKey("suppliers.id"),
        nullable=False,
    )
    """Nhà cung cấp giao hàng — bắt buộc"""

    po_id = db.Column(
        db.Integer,
        db.ForeignKey("purchase_orders.id"),
        nullable=True,
    )
    """
    Đơn đặt hàng liên quan (nullable).
    - Nếu có: cho phép đối chiếu số lượng đặt vs. thực nhận
    - Nếu không: nhập hàng độc lập (mua lẻ, điều chỉnh...)
    """

    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
    )
    """User (Thủ kho) lập phiếu nhập này"""

    # ---- Thông tin phiếu nhập ----
    received_date = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    """Ngày giờ thực tế nhận hàng (UTC). Mặc định lúc tạo phiếu."""

    note = db.Column(db.Text, nullable=True)
    """
    Ghi chú tự do (ví dụ: hàng thiếu so với PO, tình trạng đóng gói...).
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
    supplier = db.relationship("Supplier", back_populates="goods_receipts")
    """Nhà cung cấp giao hàng"""

    purchase_order = db.relationship("PurchaseOrder", back_populates="goods_receipts")
    """PO liên quan (nếu có)"""

    creator = db.relationship("User", foreign_keys=[created_by])
    """Thủ kho lập phiếu"""

    items = db.relationship(
        "GoodsReceiptItem",
        back_populates="receipt",
        cascade="all, delete-orphan",
    )
    """
    Danh sách chi tiết hàng nhập.
    cascade='all, delete-orphan': xóa phiếu → xóa theo các dòng items.
    """

    supplier_invoice = db.relationship(
        "SupplierInvoice",
        back_populates="receipt",
        uselist=False,  # quan hệ 1-1: 1 phiếu nhập → tối đa 1 hóa đơn
    )
    """
    Hóa đơn mua vào liên kết với phiếu nhập này (quan hệ 1-1).
    uselist=False: trả về object đơn lẻ, không phải danh sách.
    Nếu chưa tạo hóa đơn → trả None.
    """

    def to_dict(self, include_items: bool = False) -> dict:
        """
        Chuyển object thành dict JSON.
        Gọi to_dict(include_items=True) để lấy cả mảng items chi tiết.
        """
        data = {
            "id": self.id,
            "supplier_id": self.supplier_id,
            "po_id": self.po_id,
            "created_by": self.created_by,
            "received_date": (
                self.received_date.isoformat() if self.received_date else None
            ),
            "note": self.note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_items:
            data["items"] = [item.to_dict() for item in self.items]
        return data

    def __repr__(self) -> str:
        return (
            f"<GoodsReceipt id={self.id} supplier_id={self.supplier_id} "
            f"received={self.received_date}>"
        )


class GoodsReceiptItem(db.Model):
    """
    Model tương ứng bảng `goods_receipt_items` — Dòng chi tiết phiếu nhập.

    QUAN TRỌNG — unit_price:
      Giá nhập trong lần này. Phải lưu cố định (snapshot) tại thời điểm nhập.
      KHÔNG được tính runtime từ bảng goods.
      Lý do: đây là nguồn dữ liệu duy nhất để:
        1. Tính giá vốn tồn kho (COGS)
        2. Tra cứu lịch sử giá nhập theo từng lần giao dịch
        3. Đối chiếu với hóa đơn nhà cung cấp (SupplierInvoice)
      (Prompt.md mục 6.2, api_contract.md mục 5)
    """

    __tablename__ = "goods_receipt_items"

    # ---- Khóa chính ----
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # ---- Khóa ngoại ----
    receipt_id = db.Column(
        db.Integer,
        db.ForeignKey("goods_receipts.id"),
        nullable=False,
    )
    """Phiếu nhập cha (header)"""

    goods_id = db.Column(
        db.Integer,
        db.ForeignKey("goods.id"),
        nullable=False,
    )
    """Hàng hóa được nhập"""

    # ---- Dữ liệu giao dịch ----
    quantity = db.Column(db.Float, nullable=False)
    """
    Số lượng thực tế nhận.
    Ràng buộc: phải > 0 (chặn ở router trước khi lưu DB).
    """

    unit_price = db.Column(db.Float, nullable=False)
    """
    Giá nhập mỗi đơn vị trong lần nhập này (VND hoặc đơn vị tiền tệ dùng).

    SNAPSHOT — giá được ghi cố định tại thời điểm nhập, KHÔNG thay đổi
    dù sau này giá nhập của mặt hàng thay đổi.
    Ràng buộc: >= 0 (chặn ở router).
    """

    # ---- Relationships ----
    receipt = db.relationship("GoodsReceipt", back_populates="items")
    goods = db.relationship("Goods", back_populates="goods_receipt_items")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "receipt_id": self.receipt_id,
            "goods_id": self.goods_id,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
        }

    def __repr__(self) -> str:
        return (
            f"<GoodsReceiptItem id={self.id} goods_id={self.goods_id} "
            f"qty={self.quantity} price={self.unit_price}>"
        )
