"""
crawl.py - Entry point để chạy crawler từ command line

Cách dùng:
    python crawl.py
    python crawl.py --max-depth 3 --max-pages 100
    python crawl.py --url https://chiaki.vn/
"""

import argparse
import sys
import os

# Thêm thư mục backend vào Python path
sys.path.insert(0, os.path.dirname(__file__))

from database.db import init_db
from crawler.spider import crawl


def main():
    # Cấu hình tham số dòng lệnh
    parser = argparse.ArgumentParser(description="Crawl sản phẩm từ chiaki.vn")
    parser.add_argument(
        "--url",
        default="https://chiaki.vn",
        help="URL bắt đầu crawl (mặc định: https://chiaki.vn)"
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=2,
        help="Độ sâu crawl tối đa (mặc định: 2)"
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=50,
        help="Số trang tối đa (mặc định: 50)"
    )
    parser.add_argument(
        "--include-external",
        action="store_true",
        help="Có crawl sang domain ngoài không (mặc định: False)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Thời gian chờ giữa 2 request tính bằng giây (mặc định: 1.0)"
    )

    args = parser.parse_args()

    # Bước 1: Khởi tạo database
    print("[SETUP] Initializing database...")
    init_db()

    # Bước 2: Bắt đầu crawl
    total = crawl(
        start_url=args.url,
        max_depth=args.max_depth,
        max_pages=args.max_pages,
        include_external=args.include_external,
        delay=args.delay,
    )

    print(f"[DONE] Total saved products (this run): {total}")


if __name__ == "__main__":
    main()