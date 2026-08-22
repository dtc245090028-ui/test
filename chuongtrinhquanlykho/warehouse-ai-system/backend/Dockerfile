# ============================================================
# Dockerfile — Backend (Flask)
# ============================================================
# Multi-stage không cần thiết ở đây vì Flask không compile binary.
# Dùng image slim để giảm kích thước.
#
# Build:
#   docker build -t warehouse-backend .
#
# Run (standalone):
#   docker run -p 5000:5000 --env-file .env warehouse-backend
# ============================================================

# --- Base image ---
# python:3.11-slim cân bằng giữa kích thước nhỏ và tương thích tốt
FROM python:3.11-slim

# Đặt thư mục làm việc trong container
WORKDIR /app

# --- Cài đặt hệ thống (nếu cần) ---
# gcc cần cho bcrypt; ca-certificates cho requests HTTPS
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# --- Cài thư viện Python ---
# Copy requirements TRƯỚC code để tận dụng Docker layer cache.
# Nếu code thay đổi nhưng requirements không đổi → bước này không chạy lại.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Copy mã nguồn ---
COPY . .

# --- Tạo thư mục lưu SQLite DB (được mount từ volume ở docker-compose) ---
RUN mkdir -p /data

# --- Biến môi trường mặc định ---
# Sẽ bị override bởi docker-compose hoặc --env-file
ENV DATABASE_URL=sqlite:////data/warehouse.db \
    FLASK_ENV=production \
    FLASK_PORT=5000

# Expose port Flask
EXPOSE 5000

# --- Lệnh khởi động ---
# Dùng python -m app.main thay vì flask run để đảm bảo chạy được qua __main__
CMD ["python", "-m", "app.main"]
