from datetime import datetime
from app.extensions import db


class Stocktake(db.Model):
    """
    Model tương ứng bảng `stocktakes` — Phiếu kiểm kê kho (header).

    Quan hệ:
      - creator     : Thủ kho lập phiếu
      - approver    : Quản lý kho phê duyệt
      - items       : Các dòng chi tiết mặt hàng được kiểm kê (1..*)
    """

    __tablename__ = "stocktakes"

    # ---- Khóa chính ----
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # ---- Khóa ngoại ----
    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
    )
    """User (Thủ kho) lập phiếu kiểm kê này"""

    approved_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
    )
    """User (Quản lý kho) phê duyệt xử lý chênh lệch"""

    # ---- Thông tin phiếu kiểm kê ----
    stocktake_date = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    """Ngày giờ lập phiếu kiểm kê (UTC)"""

    status = db.Column(
        db.String(50),
        default="đang kiểm kê",
        nullable=False,
    )
    """
    Trạng thái luồng phê duyệt:
      - đang kiểm kê: mới tạo, đang đếm thực tế
      - chờ phê duyệt: Thủ kho đã chốt số và gửi đề xuất xử lý chênh lệch
      - đã phê duyệt: Quản lý kho duyệt → đã cập nhật chênh lệch vào tồn kho
      - đã hủy: hủy phiếu kiểm kê
    """

    note = db.Column(db.Text, nullable=True)
    """Ghi chú chung cho phiếu kiểm kê"""

    # ---- Audit timestamp ----
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # ---- Relationships ----
    creator = db.relationship("User", foreign_keys=[created_by])
    approver = db.relationship("User", foreign_keys=[approved_by])

    items = db.relationship(
        "StocktakeItem",
        back_populates="stocktake",
        cascade="all, delete-orphan",
    )

    def to_dict(self, include_items: bool = False) -> dict:
        data = {
            "id": self.id,
            "created_by": self.created_by,
            "approved_by": self.approved_by,
            "stocktake_date": self.stocktake_date.isoformat() if self.stocktake_date else None,
            "status": self.status,
            "note": self.note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_items:
            data["items"] = [item.to_dict() for item in self.items]
        return data

    def __repr__(self) -> str:
        return f"<Stocktake id={self.id} status={self.status}>"


class StocktakeItem(db.Model):
    """
    Model tương ứng bảng `stocktake_items` — Dòng chi tiết phiếu kiểm kê.
    """

    __tablename__ = "stocktake_items"

    # ---- Khóa chính ----
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # ---- Khóa ngoại ----
    stocktake_id = db.Column(
        db.Integer,
        db.ForeignKey("stocktakes.id"),
        nullable=False,
    )

    goods_id = db.Column(
        db.Integer,
        db.ForeignKey("goods.id"),
        nullable=False,
    )

    # ---- Dữ liệu kiểm kê ----
    system_quantity = db.Column(db.Float, nullable=False)
    """Tồn kho trên hệ thống tại thời điểm kiểm kê (snapshot)"""

    actual_quantity = db.Column(db.Float, nullable=False)
    """Tồn kho đếm được thực tế"""

    difference = db.Column(db.Float, nullable=False)
    """Chênh lệch (actual_quantity - system_quantity). >0 là thừa, <0 là thiếu"""

    action = db.Column(db.String(255), nullable=True)
    """
    Đề xuất xử lý chênh lệch (Thủ kho điền).
    Ví dụ: 'Thanh lý hàng hỏng', 'Cập nhật lại tồn', 'Tìm nguyên nhân'...
    """

    # ---- Relationships ----
    stocktake = db.relationship("Stocktake", back_populates="items")
    goods = db.relationship("Goods", back_populates="stocktake_items")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "stocktake_id": self.stocktake_id,
            "goods_id": self.goods_id,
            "system_quantity": self.system_quantity,
            "actual_quantity": self.actual_quantity,
            "difference": self.difference,
            "action": self.action,
        }

    def __repr__(self) -> str:
        return f"<StocktakeItem id={self.id} goods_id={self.goods_id} diff={self.difference}>"
