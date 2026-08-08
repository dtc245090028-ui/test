from app.extensions import db

class Category(db.Model):
    """
    Model tương ứng bảng `categories`.
    """
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)

    goods = db.relationship("Goods", back_populates="category", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name
        }
