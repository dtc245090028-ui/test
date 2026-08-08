"""
models/__init__.py — Export tất cả models
==========================================
Import tại đây để SQLAlchemy biết các model tồn tại
khi gọi db.create_all() trong main.py.

Nếu không import ở đây, db.create_all() sẽ không tạo
bảng dù file model đã được viết xong.
"""

from app.models.user import User
from app.models.supplier import Supplier
from app.models.category import Category
from app.models.goods import Goods
