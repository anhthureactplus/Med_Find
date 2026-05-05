"""
database/db.py - SQLite database cho hệ thống tìm kiếm thuốc
"""

import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "products.db"


def get_connection():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            name           TEXT NOT NULL,
            url            TEXT UNIQUE NOT NULL,
            price          TEXT,
            original_price TEXT,
            rating         TEXT,
            description    TEXT,
            ingredients    TEXT,
            usage          TEXT,
            image_url      TEXT,
            specifications TEXT,
            comments       TEXT,
            created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    print("[DB] Khởi tạo database OK")


def save_product(product: dict):
    conn = get_connection()
    conn.execute("""
        INSERT OR IGNORE INTO products
            (name, url, price, original_price, rating, description, ingredients, usage, image_url, specifications, comments)
        VALUES
            (:name, :url, :price, :original_price, :rating, :description, :ingredients, :usage, :image_url, :specifications, :comments)
    """, {
        **product,
        "original_price": product.get("original_price", ""),
        "rating":         product.get("rating", ""),
        "specifications": json.dumps(product.get("specifications", {}), ensure_ascii=False),
        "comments":       json.dumps(product.get("comments", []), ensure_ascii=False)
    })
    conn.commit()
    conn.close()


def url_exists(url: str) -> bool:
    """Kiểm tra URL đã có trong DB chưa - tránh lưu trùng"""
    conn = get_connection()
    row = conn.execute("SELECT 1 FROM products WHERE url = ?", (url,)).fetchone()
    conn.close()
    return row is not None


def search_products(keyword: str, limit: int = 40) -> list[dict]:
    """Tìm kiếm theo tên, mô tả, thành phần"""
    conn = get_connection()
    kw = f"%{keyword}%"
    rows = conn.execute("""
        SELECT id, name, url, price, original_price, rating, image_url, description, specifications
        FROM products
        WHERE name LIKE ? OR description LIKE ? OR ingredients LIKE ?
        ORDER BY
            CASE WHEN name LIKE ? THEN 0 ELSE 1 END,
            name
        LIMIT ?
    """, (kw, kw, kw, kw, limit)).fetchall()
    conn.close()
    result = []
    for r in rows:
        p = dict(r)
        p["specifications"] = json.loads(p.get("specifications") or "{}")
        result.append(p)
    return result


def get_product_by_id(product_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    if row:
        p = dict(row)
        p["comments"]       = json.loads(p["comments"]       or "[]")
        p["specifications"] = json.loads(p["specifications"] or "{}")
        return p
    return None


def get_products_by_ids(ids: list[int]) -> list[dict]:
    if not ids:
        return []
    placeholders = ",".join("?" * len(ids))
    conn = get_connection()
    rows = conn.execute(
        f"SELECT * FROM products WHERE id IN ({placeholders})", ids
    ).fetchall()
    conn.close()
    result = []
    for row in rows:
        p = dict(row)
        p["comments"]       = json.loads(p["comments"]       or "[]")
        p["specifications"] = json.loads(p["specifications"] or "{}")
        result.append(p)
    return result


def get_all_products(limit: int = 40, offset: int = 0) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name, url, price, original_price, rating, image_url, description, specifications FROM products ORDER BY id DESC LIMIT ? OFFSET ?",
        (limit, offset)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats() -> dict:
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    conn.close()
    return {"total_products": total}