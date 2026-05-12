"""
main.py - Entry point để chạy API server

Cách dùng:
    python main.py
    # Sau đó mở: http://localhost:8000
    # Docs API:   http://localhost:8000/docs
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database.db import init_db
from api.routes import router

# Khởi tạo ứng dụng FastAPI
app = FastAPI(
    title="Drug Search API",
    description="Hệ thống tìm kiếm và so sánh thuốc",
    version="1.0.0",
)

# Cho phép frontend (chạy trên file:// hoặc localhost) gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cho phép tất cả origin
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký các route
app.include_router(router)


@app.on_event("startup")
def startup():
    """Chạy khi server khởi động - khởi tạo database và BM25 index"""
    init_db()

    # Build BM25 index từ toàn bộ sản phẩm trong DB
    try:
        from database.bm25_search import build_index
        from database.db import get_all_products, get_stats
        stats = get_stats()
        total = stats["total_products"]
        if total > 0:
            # Lấy tất cả sản phẩm để build index
            products = get_all_products(limit=total)
            ok = build_index(products)
            if ok:
                print(f"[BM25] Index sẵn sàng: {total} sản phẩm")
        else:
            print("[BM25] DB trống, chưa build index")
    except Exception as e:
        print(f"[BM25] Không build được index: {e}")

    print("[SERVER] API server đã sẵn sàng tại http://localhost:8000")
    print("[SERVER] Xem docs tại: http://localhost:8000/docs")


@app.get("/")
def root():
    return {
        "message": "Drug Search API đang chạy!",
        "endpoints": {
            "search": "/search?q=<từ khóa>",
            "list": "/products",
            "detail": "/product/<id>",
            "compare": "/compare?ids=1,2,3",
            "stats": "/stats",
            "docs": "/docs",
        }
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)