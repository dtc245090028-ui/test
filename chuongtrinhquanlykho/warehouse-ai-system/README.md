# Hệ thống quản lý kho có tích hợp AI

Đồ án môn học — Hệ thống quản lý hàng hóa, nhà cung cấp, phiếu nhập/xuất và tồn kho, tích hợp AI sinh báo cáo và gợi ý nhập hàng.

## Stack

| Lớp | Công nghệ |
|---|---|
| Backend | Flask (Python 3.10+) |
| Frontend | HTML/JS + Bootstrap (hoặc React) |
| CSDL | SQLite (dev/demo) |
| AI | Gemini API |

## Cài đặt & Chạy

### 1. Clone project và vào thư mục backend

```bash
cd backend/
```

### 2. Tạo virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / Mac
source venv/bin/activate
```

### 3. Cài thư viện

```bash
pip install -r requirements.txt
```

### 4. Tạo file .env

```bash
cp .env.example .env
# Sau đó mở .env và điền SECRET_KEY + GEMINI_API_KEY
```

### 5. Chạy server

```bash
# Cách 1: Flask CLI
flask --app app run --debug

# Cách 2: Python trực tiếp
python -m app.main
```

Server chạy tại: http://localhost:5000

### 6. Seed dữ liệu mẫu

```bash
# SQLite
sqlite3 warehouse.db < ../database/seed_data.sql
```

> **Lưu ý**: File `seed_data.sql` yêu cầu các bảng đã được tạo sẵn (đã tự tạo khi chạy app lần đầu).
> Password mẫu của cả 3 tài khoản: `Password@123`

### 7. Chạy test

```bash
cd backend/
pytest tests/ -v
```

## Tài khoản mẫu (sau khi seed)

| Username | Password | Role |
|---|---|---|
| `admin01` | `Password@123` | Ban điều hành |
| `manager01` | `Password@123` | Quản lý kho |
| `keeper01` | `Password@123` | Thủ kho |

## Cấu trúc thư mục

```
warehouse-ai-system/
├── backend/
│   ├── app/
│   │   ├── models/          # SQLAlchemy models
│   │   ├── routers/         # Router từng nghiệp vụ
│   │   ├── auth/            # JWT + phân quyền
│   │   ├── ai/              # Tích hợp Gemini API
│   │   │   └── prompts/     # Tách prompt ra file riêng
│   │   ├── schemas/         # Marshmallow validate
│   │   ├── extensions.py    # db, jwt, ma instances
│   │   └── main.py          # Application factory
│   ├── tests/
│   ├── .env.example
│   └── requirements.txt
├── frontend/
├── database/
│   └── seed_data.sql
└── docs/
    ├── api_contract.md
    ├── ai_prompt_log.md
    └── test_report.md
```

## API nhanh (curl)

```bash
# Đăng nhập
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin01","password":"Password@123"}'

# Lấy thông tin user (thay <token> bằng token từ bước trên)
curl http://localhost:5000/api/auth/me \
  -H "Authorization: Bearer <token>"
```

---

## 🐳 Triển khai bằng Docker (Khuyến nghị)

> Yêu cầu: [Docker Desktop](https://www.docker.com/products/docker-desktop/) đã được cài đặt.

### Bước 1 — Tạo file `.env`

```bash
cd backend
cp .env.example .env
# Mở .env và điền các giá trị thật:
#   SECRET_KEY=<chuỗi ngẫu nhiên dài>
#   GEMINI_API_KEY=<key Gemini của bạn>
```

### Bước 2 — Build và chạy toàn hệ thống

```bash
# Chạy từ thư mục warehouse-ai-system/
docker compose up --build
```

Sau khi khởi động xong:
| Dịch vụ | Địa chỉ |
|---|---|
| **Frontend (Giao diện web)** | http://localhost |
| **API Backend trực tiếp** | http://localhost:5000/api/... |

### Bước 3 — Seed dữ liệu mẫu (lần đầu)

```bash
docker exec warehouse-backend sh /app/scripts/seed_docker.sh
```

### Bước 4 — Dừng hệ thống

```bash
docker compose down          # Dừng, giữ lại dữ liệu DB
docker compose down -v       # Dừng VÀ xóa DB (reset hoàn toàn)
```

### Cấu trúc Docker

```
warehouse-ai-system/
├── backend/
│   ├── Dockerfile           # Python:3.11-slim, chạy Flask
│   └── .dockerignore
├── frontend/
│   ├── Dockerfile           # Nginx:alpine, serve static + proxy /api
│   ├── nginx.conf           # Reverse proxy /api → backend:5000
│   └── .dockerignore
└── docker-compose.yml       # Gộp 2 services + volume SQLite
```

> **Lưu ý bảo mật**: File `backend/.env` chứa API key và SECRET_KEY thật — **không bao giờ commit** lên Git.
