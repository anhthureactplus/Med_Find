"""
build_index.py - Index toàn bộ sản phẩm từ SQLite vào ChromaDB.
Chạy 1 lần sau khi đã crawl xong data.

Cách dùng:
    pip install chromadb sentence-transformers
    python build_index.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from database.vector_db import index_all_from_sqlite, get_stats

if __name__ == "__main__":
    print("=" * 50)
    print("Build ChromaDB index từ SQLite")
    print("=" * 50)

    total = index_all_from_sqlite()

    stats = get_stats()
    print(f"\nKết quả:")
    print(f"  - Đã index: {stats['total']} sản phẩm")
    print(f"  - Model:    {stats['model']}")
    print(f"  - Lưu tại:  {stats['path']}")
    print("\nXong! Giờ semantic search đã hoạt động.")