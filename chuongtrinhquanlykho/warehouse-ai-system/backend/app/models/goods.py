from datetime import datetime
from app.extensions import db

class Goods(db.Model):
    """
    Model tương ứng bảng `goods`.
    """
    __tablename__ = "goods"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    preferred_supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)

    sku = db.Column(db.String(50), nullable=False, unique=True)
    name = db.Column(db.String(200), nullable=False)
    unit = db.Column(db.String(50), nullable=False)
    min_stock = db.Column(db.Float, nullable=False, default=0.0)
    max_stock = db.Column(db.Float, nullable=True)
    quantity_on_hand = db.Column(db.Float, nullable=False, default=0.0)
    selling_price = db.Column(db.Float, nullable=False, default=0.0)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(500), nullable=True)

    status = db.Column(
        db.Enum("active", "inactive", name="goods_status"),
        nullable=False,
        default="active"
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    category = db.relationship("Category", back_populates="goods")
    preferred_supplier = db.relationship("Supplier", back_populates="preferred_goods")
    purchase_order_items = db.relationship("PurchaseOrderItem", back_populates="goods", lazy="dynamic")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sku": self.sku,
            "name": self.name,
            "category_id": self.category_id,
            "preferred_supplier_id": self.preferred_supplier_id,
            "unit": self.unit,
            "min_stock": self.min_stock,
            "max_stock": self.max_stock,
            "quantity_on_hand": self.quantity_on_hand,
            "selling_price": self.selling_price,
            "description": self.description,
            "image_url": self.image_url,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
