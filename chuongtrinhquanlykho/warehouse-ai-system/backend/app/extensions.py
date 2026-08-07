"""
extensions.py — Khởi tạo các extension Flask dùng chung
=========================================================
Tách ra file riêng để tránh circular import:
  - app/main.py  import extensions và đăng ký vào app
  - models/ và routers/ import extensions để dùng db, jwt...
  - Nếu models/ import từ main.py → circular import → lỗi

Pattern này gọi là "Application Factory" kết hợp "Extension Object".
"""

from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_marshmallow import Marshmallow

# SQLAlchemy instance — dùng để định nghĩa model và truy vấn CSDL
# Sẽ được khởi tạo thật sự (bind với app) trong main.py: db.init_app(app)
db = SQLAlchemy()

# JWTManager — quản lý việc tạo, kiểm tra, thu hồi JWT token
# Sẽ được bind với app trong main.py: jwt.init_app(app)
jwt = JWTManager()

# Marshmallow — validate dữ liệu đầu vào và serialize response
ma = Marshmallow()
