from datetime import datetime
from app.extensions import db

class PurchaseOrder(db.Model):
    __tablename__ = "purchase_orders"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    
    order_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    status = db.Column(
        db.Enum("chờ xác nhận", "đã xác nhận", "đang giao", "đã nhận", "hủy", name="purchase_order_status"),
        nullable=False,
        default="chờ xác nhận",
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    supplier = db.relationship("Supplier", back_populates="purchase_orders")
    creator = db.relationship("User", foreign_keys=[created_by])
    items = db.relationship("PurchaseOrderItem", back_populates="purchase_order", cascade="all, delete-orphan")
    goods_receipts = db.relationship("GoodsReceipt", back_populates="purchase_order", lazy="dynamic")
    """Các phiếu nhập liên kết với PO này — dùng đối chiếu số lượng đặt vs. thực nhận"""

    def to_dict(self, include_items=False) -> dict:
        data = {
            "id": self.id,
            "supplier_id": self.supplier_id,
            "created_by": self.created_by,
            "order_date": self.order_date.isoformat() if self.order_date else None,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_items:
            data["items"] = [item.to_dict() for item in self.items]
        return data


class PurchaseOrderItem(db.Model):
    __tablename__ = "purchase_order_items"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    po_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), nullable=False)
    goods_id = db.Column(db.Integer, db.ForeignKey("goods.id"), nullable=False)
    
    quantity_ordered = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=True)

    # Relationships
    purchase_order = db.relationship("PurchaseOrder", back_populates="items")
    goods = db.relationship("Goods", back_populates="purchase_order_items")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "po_id": self.po_id,
            "goods_id": self.goods_id,
            "quantity_ordered": self.quantity_ordered,
            "unit_price": self.unit_price,
        }
