#!/bin/sh
# ============================================================
# seed_docker.sh — Seed dữ liệu mẫu vào DB trong Docker
# ============================================================
# Chạy sau khi docker compose up:
#   docker exec warehouse-backend sh /app/scripts/seed_docker.sh
# ============================================================

echo "📦 Bắt đầu seed dữ liệu mẫu..."

# Kiểm tra DB đã tồn tại chưa
DB_PATH="/data/warehouse.db"

if [ ! -f "$DB_PATH" ]; then
    echo "❌ Không tìm thấy DB tại $DB_PATH. Đảm bảo backend đã khởi động xong."
    exit 1
fi

# Chạy seed qua SQLite CLI
sqlite3 "$DB_PATH" < /app/../database/seed_data.sql

if [ $? -eq 0 ]; then
    echo "✅ Seed dữ liệu mẫu thành công!"
    echo "📋 Tài khoản mẫu:"
    echo "   admin01    / Password@123  (Ban điều hành)"
    echo "   manager01  / Password@123  (Quản lý kho)"
    echo "   keeper01   / Password@123  (Thủ kho)"
else
    echo "❌ Seed thất bại. Kiểm tra lại file seed_data.sql"
    exit 1
fi
