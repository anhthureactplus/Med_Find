# MedFind – Hệ thống tra cứu dược phẩm

Ứng dụng tra cứu thông tin thuốc và thực phẩm chức năng, dữ liệu crawl từ chiaki.vn.

---

## Cấu trúc thư mục

```
Med_Find/
├── backend/
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py          # FastAPI endpoints
│   ├── crawler/
│   │   ├── __init__.py
│   │   └── spider.py          # Playwright crawler
│   ├── database/
│   │   ├── __init__.py
│   │   └── db.py              # SQLite queries
│   ├── data/                  # Tự tạo khi chạy (chứa products.db)
│   ├── crawl.py               # CLI chạy crawler
│   ├── main.py                # Khởi động API server
│   └── requirements.txt
├── frontend/
│   ├── css/
│   │   └── style.css
│   ├── .stylelintrc.json
│   ├── index.html             # Trang chủ
│   ├── search.html            # Tìm kiếm + bộ lọc
│   └── compare.html           # So sánh sản phẩm
├── .dockerignore
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── README.md
```

---

## Cài đặt

### Yêu cầu
- Python 3.11+
- Google Chrome đã cài trên máy

### Cài thư viện

```bash
# Cách 1 - dùng requirements.txt
cd backend
pip install -r requirements.txt

# Cách 2 - dùng pyproject.toml (từ thư mục gốc)
pip install -e .

# Cài Playwright Chromium (bắt buộc, chỉ cần làm 1 lần)
playwright install chromium
```

---

## Cách 1 — Chạy thủ công

### Bước 1 — Crawl dữ liệu
```bash
cd backend
python crawl.py --max-pages 50
```
> Playwright mở Chrome ẩn, tự động crawl sản phẩm từ chiaki.vn.
> Dữ liệu lưu vào `backend/data/products.db`.

### Bước 2 — Chạy API server
```bash
cd backend
python main.py
# API chạy tại:  http://localhost:8000
# Swagger docs:  http://localhost:8000/docs
```

### Bước 3 — Chạy Frontend
Mở terminal mới:
```bash
cd frontend
python -m http.server 5500
# Mở trình duyệt: http://localhost:5500
```

---

## Cách 2 — Docker Compose (đơn giản nhất)

### Bước 1 — Crawl dữ liệu trước (bắt buộc, chạy trên máy local)
```bash
cd backend
pip install -r requirements.txt && playwright install chromium
python crawl.py --max-pages 100
```

### Bước 2 — Build và chạy
```bash
docker-compose up --build
```
Mở trình duyệt: `http://localhost:5500`

### Dừng ứng dụng
```bash
docker-compose down
```

---

## Cách 3 — Docker thủ công

```bash
# Build image
docker build -t medfind .

# Chạy container, mount DB ra ngoài để crawl thêm không cần rebuild
docker run -p 8000:8000 -v ./backend/data:/app/backend/data medfind
```

---

## Crawl thêm dữ liệu

```bash
# Mặc định (5 category, tối đa 50 sản phẩm)
python crawl.py

# Tùy chỉnh số lượng
python crawl.py --max-pages 100

# Crawl category cụ thể
python crawl.py --categories https://chiaki.vn/collagen https://chiaki.vn/omega-3-6-9

# Tùy chỉnh độ sâu và delay
python crawl.py --max-pages 50 --max-depth 3 --delay 2.0
```

> **Lưu ý:** Nếu bị chặn, tăng `--delay` lên 2.0–3.0 giây.

---

## API Endpoints

| Method | URL | Mô tả |
|--------|-----|-------|
| GET | `/products?limit=20&offset=0` | Danh sách sản phẩm |
| GET | `/search?q=vitamin` | Tìm kiếm theo từ khóa |
| GET | `/product/{id}` | Chi tiết 1 sản phẩm |
| GET | `/compare?ids=1,2,3` | So sánh nhiều sản phẩm |
| GET | `/stats` | Thống kê database |
| GET | `/docs` | Swagger UI |

---

## Tính năng

- **Crawl tự động** — Playwright + BFS, visited set tránh crawl trùng
- **Tìm kiếm** — theo tên, thành phần, mô tả
- **Bộ lọc** — xuất xứ, danh mục, khoảng giá
- **Phân trang** — 16 sản phẩm/trang
- **So sánh** — tối đa 4 sản phẩm cạnh nhau
- **Đánh giá** — hiển thị comment từ người dùng thật
- **Đóng gói** — Docker + Docker Compose