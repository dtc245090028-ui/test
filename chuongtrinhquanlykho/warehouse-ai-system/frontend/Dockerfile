# ============================================================
# Dockerfile — Frontend (Nginx static server)
# ============================================================
# Frontend là thuần HTML/JS/CSS — không cần Node.js để build.
# Dùng Nginx để serve static files, nhỏ gọn và nhanh.
#
# Build:
#   docker build -t warehouse-frontend .
#
# Run (standalone):
#   docker run -p 80:80 warehouse-frontend
# ============================================================

# --- Base image ---
# nginx:1.25-alpine — rất nhỏ (~15MB) và đủ dùng để serve static
FROM nginx:1.25-alpine

# --- Xóa config mặc định của Nginx ---
RUN rm /etc/nginx/conf.d/default.conf

# --- Copy cấu hình Nginx tùy chỉnh ---
# File này cấu hình reverse proxy từ /api → backend:5000
COPY nginx.conf /etc/nginx/conf.d/default.conf

# --- Copy toàn bộ source frontend ---
COPY . /usr/share/nginx/html

# Expose port 80 (HTTP)
EXPOSE 80

# Nginx tự start khi container khởi động — không cần CMD thêm
