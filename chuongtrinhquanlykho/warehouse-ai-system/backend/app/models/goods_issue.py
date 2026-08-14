"""
models/goods_issue.py — Model GoodsIssue & GoodsIssueItem
==========================================================
Ánh xạ hai bảng `goods_issues` và `goods_issue_items`
theo thiết kế mục 6.1 Prompt.md.

Bảng goods_issues:
  - Phiếu xuất kho (header)
  - created_by → user lập phiếu (Thủ kho)
  - issued_date → ngày giờ xuất kho thực tế
  - note → ghi chú tự do (bộ phận nhận, lý do xuất...)

Bảng goods_issue_items:
  - Từng dòng hàng hóa trong phiếu xuất
  - quantity: số lượng xuất — KHÔNG có unit_price (phiếu xuất
    không lưu giá; giá vốn tính sau từ goods_receipt_items)

Ràng buộc nghiệp vụ quan trọng (Prompt.md mục 3.3, 6.2, 10):
  - quantity phải > 0 (chặn ở router)
  - quantity KHÔNG được vượt quá goods.quantity_on_hand
    → chặn xuất vượt tồn, không cho tồn kho về âm
  - Cập nhật goods.quantity_on_hand qua DB transaction trong router
    → rollback toàn bộ nếu bất kỳ bước nào thất bại
"""

from datetime import datetime
from app.extensions import db


class GoodsIssue(db.Model):
    """
    Model tương ứng bảng `goods_issues` — Phiếu xuất kho (header).

    Quan hệ:
      - creator  : Thủ kho lập phiếu
      - items    : Các dòng chi tiết hàng xuất (1..*)
    """

    __tablename__ = "goods_issues"

    # ---- Khóa chính ----
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # ---- Khóa ngoại ----
    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
    )
    """User (Thủ kho) lập phiếu xuất này"""

    # ---- Thông tin phiếu xuất ----
    issued_date = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    """Ngày giờ thực tế xuất hàng (UTC). Mặc định lúc tạo phiếu."""

    note = db.Column(db.Text, nullable=True)
    """
    Ghi chú tự do (ví dụ: bộ phận nhận hàng, lý do xuất kho, số lệnh sản xuất...).
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
    creator = db.relationship("User", foreign_keys=[created_by])
    """Thủ kho lập phiếu"""

    items = db.relationship(
        "GoodsIssueItem",
        back_populates="issue",
        cascade="all, delete-orphan",
    )
    """
    Danh sách chi tiết hàng xuất.
    cascade='all, delete-orphan': xóa phiếu → xóa theo các dòng items.
    """

    def to_dict(self, include_items: bool = False) -> dict:
        """
        Chuyển object thành dict JSON.
        Gọi to_dict(include_items=True) để lấy cả mảng items chi tiết.
        """
        data = {
            "id": self.id,
            "created_by": self.created_by,
            "issued_date": (
                self.issued_date.isoformat() if self.issued_date else None
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
            f"<GoodsIssue id={self.id} created_by={self.created_by} "
            f"issued={self.issued_date}>"
        )


class GoodsIssueItem(db.Model):
    """
    Model tương ứng bảng `goods_issue_items` — Dòng chi tiết phiếu xuất.

    QUAN TRỌNG — KHÔNG có unit_price:
      Phiếu xuất chỉ ghi số lượng. Giá vốn hàng xuất được tính
      về sau từ bảng goods_receipt_items (FIFO/LIFO/bình quân)
      khi cần lập báo cáo giá vốn hàng bán (COGS).
      (Thiết kế theo Prompt.md mục 6.1)

    QUAN TRỌNG — chặn xuất vượt tồn:
      quantity phải ≤ goods.quantity_on_hand tại thời điểm xuất.
      Ràng buộc này được kiểm tra và thực thi ở tầng router
      trong một DB transaction duy nhất để đảm bảo tính nhất quán.
      (Prompt.md mục 3.3, 10)
    """

    __tablename__ = "goods_issue_items"

    # ---- Khóa chính ----
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # ---- Khóa ngoại ----
    issue_id = db.Column(
        db.Integer,
        db.ForeignKey("goods_issues.id"),
        nullable=False,
    )
    """Phiếu xuất cha (header)"""

    goods_id = db.Column(
        db.Integer,
        db.ForeignKey("goods.id"),
        nullable=False,
    )
    """Hàng hóa được xuất"""

    # ---- Dữ liệu giao dịch ----
    quantity = db.Column(db.Float, nullable=False)
    """
    Số lượng thực tế xuất.
    Ràng buộc:
      - phải > 0 (chặn ở router)
      - phải ≤ goods.quantity_on_hand tại thời điểm xuất (chặn xuất vượt tồn)
    """

    # ---- Relationships ----
    issue = db.relationship("GoodsIssue", back_populates="items")
    goods = db.relationship("Goods", back_populates="goods_issue_items")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "issue_id": self.issue_id,
            "goods_id": self.goods_id,
            "quantity": self.quantity,
        }

    def __repr__(self) -> str:
        return (
            f"<GoodsIssueItem id={self.id} goods_id={self.goods_id} "
            f"qty={self.quantity}>"
        )
