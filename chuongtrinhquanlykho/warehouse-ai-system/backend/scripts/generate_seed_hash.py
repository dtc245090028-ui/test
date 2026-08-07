"""
scripts/generate_seed_hash.py — Script sinh bcrypt hash cho seed_data.sql
==========================================================================
Chạy script này một lần để lấy hash đúng cho password "Password@123",
sau đó copy vào seed_data.sql.

Cách chạy (từ thư mục backend/):
  python scripts/generate_seed_hash.py
"""

import bcrypt

password = "Password@123"
password_bytes = password.encode("utf-8")

# Tạo hash với cost=12 (phù hợp cho production)
hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=12))
hash_str = hashed.decode("utf-8")

print(f"Password gốc : {password}")
print(f"bcrypt hash  : {hash_str}")
print()
print("Copy dòng trên vào seed_data.sql thay cho placeholder hash.")
print()

# Verify ngay để đảm bảo hash hợp lệ
is_valid = bcrypt.checkpw(password_bytes, hashed)
print(f"✅ Verify: {is_valid}")
