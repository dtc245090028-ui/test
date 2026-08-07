"""
models/user.py — Model User (bảng users trong CSDL)
=====================================================
Ánh xạ bảng `users` theo thiết kế mục 6 Prompt.md.

Các role hợp lệ:
  - 'admin'             : Ban điều hành — quyền cao nhất
  - 'warehouse_manager' : Quản lý kho — phê duyệt kiểm kê, xem báo cáo
  - 'warehouse_keeper'  : Thủ kho — nhập/xuất/kiểm kê hàng ngày

Lưu ý bảo mật:
  - KHÔNG bao giờ lưu password dạng plain text
  - Luôn dùng bcrypt để hash và verify (xem method set_password / check_password)
"""

from datetime import datetime
from app.extensions import db
import bcrypt


class User(db.Model):
    """
    Model tương ứng bảng `users`.
    SQLAlchemy tự tạo/ánh xạ bảng này khi gọi db.create_all().
    """

    __tablename__ = "users"

    # ---- Các cột (columns) ----

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    """Khóa chính, tự tăng"""

    username = db.Column(db.String(50), unique=True, nullable=False)
    """
    Tên đăng nhập — duy nhất trong hệ thống.
    Dùng để đăng nhập qua POST /api/auth/login.
    """

    full_name = db.Column(db.String(100), nullable=False)
    """Họ tên đầy đủ — hiển thị trên giao diện"""

    email = db.Column(db.String(150), unique=True, nullable=True)
    """Email (tùy chọn) — có thể dùng để thông báo sau này"""

    role = db.Column(
        db.Enum("admin", "warehouse_manager", "warehouse_keeper", name="user_role"),
        nullable=False,
    )
    """
    Vai trò người dùng — kiểm soát phân quyền.
    Enum giới hạn chỉ 3 giá trị hợp lệ, tầng CSDL cũng enforce.
    """

    password_hash = db.Column(db.String(255), nullable=False)
    """
    Password đã hash bằng bcrypt — KHÔNG lưu password gốc.
    bcrypt tự sinh salt ngẫu nhiên mỗi lần hash → cùng password,
    hash khác nhau mỗi lần → an toàn chống rainbow table attack.
    """

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    """
    Trạng thái tài khoản. Admin có thể deactivate để vô hiệu hóa
    mà không cần xóa user (giữ lại lịch sử thao tác).
    """

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    """Thời điểm tạo tài khoản (UTC)"""

    # ---- Methods ----

    def set_password(self, plain_password: str) -> None:
        """
        Hash password và lưu vào password_hash.

        Quy trình:
          1. Mã hóa password thành bytes (UTF-8)
          2. bcrypt.hashpw() tự sinh salt và hash → trả về bytes
          3. Decode sang str để lưu vào CSDL (TEXT column)

        Tham số:
          plain_password: password dạng text do người dùng nhập
        """
        # Encode sang bytes vì bcrypt yêu cầu bytes input
        password_bytes = plain_password.encode("utf-8")

        # bcrypt.gensalt() tạo salt ngẫu nhiên (mặc định cost=12)
        # Cost càng cao → hash càng chậm → brute-force càng khó
        salt = bcrypt.gensalt(rounds=12)

        # hashpw trả về bytes, decode về str để lưu DB
        self.password_hash = bcrypt.hashpw(password_bytes, salt).decode("utf-8")

    def check_password(self, plain_password: str) -> bool:
        """
        Xác minh password người dùng nhập có khớp hash trong DB không.

        Quy trình:
          1. Encode password nhập vào thành bytes
          2. Encode hash đang lưu trong DB thành bytes
          3. bcrypt.checkpw() so sánh — trả True/False

        Tham số:
          plain_password: password người dùng vừa nhập (chưa hash)

        Trả về:
          True nếu đúng password, False nếu sai
        """
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            self.password_hash.encode("utf-8"),
        )

    def to_dict(self) -> dict:
        """
        Chuyển object User thành dict để trả về trong response JSON.
        KHÔNG bao gồm password_hash — không bao giờ trả hash ra ngoài.
        """
        return {
            "id": self.id,
            "username": self.username,
            "full_name": self.full_name,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        """Hiển thị khi debug (print object)"""
        return f"<User id={self.id} username={self.username} role={self.role}>"
