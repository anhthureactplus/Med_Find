"""
cleanup_db.py
Clean up existing rows in SQLite database:
- trim url/name fields
- remove known noisy text patterns from description/usage/ingredients/comments
- backfill *_norm columns for better Vietnamese search + dedupe

Usage:
  python backend/cleanup_db.py
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from database.db import DB_PATH, _normalize_text  # type: ignore


_NOISE_PATTERNS = [
    r"nhập mật khẩu để tiếp tục",
    r"tạo mật khẩu để tiếp tục",
    r"đã bán",
    r"sản phẩm bán chạy",
    r"trang chủ",
    r"đăng nhập",
    r"đăng ký",
]


def _clean_text(text: str | None, max_len: int) -> str:
    if not text:
        return ""
    t = str(text).replace("\u00a0", " ")
    lines = [ln.strip() for ln in t.splitlines()]
    lines = [ln for ln in lines if ln]
    out_lines: list[str] = []
    for ln in lines:
        low = ln.lower()
        if "{{" in ln or "}}" in ln:
            continue
        if any(re.search(pat, low) for pat in _NOISE_PATTERNS):
            continue
        if re.search(r"\b\d{1,3}\.\d{3}đ\b", low) and ("đã bán" in low or "+" in low):
            continue
        if ln in (".", ","):
            continue
        out_lines.append(ln)
    out = "\n".join(out_lines)
    out = re.sub(r"[ \t]+", " ", out).strip()
    return out[:max_len]


def main():
    if not Path(DB_PATH).exists():
        print("[cleanup] DB not found:", DB_PATH)
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cols = {r[1] for r in conn.execute("PRAGMA table_info(products)").fetchall()}
    for col in ("name_norm", "description_norm", "image_url_norm"):
        if col not in cols:
            conn.execute(f"ALTER TABLE products ADD COLUMN {col} TEXT")

    rows = conn.execute("SELECT * FROM products").fetchall()
    # Deduplicate by trimmed url first to avoid UNIQUE constraint on update
    seen_urls: dict[str, int] = {}
    delete_ids: list[int] = []
    for r in rows:
        pid = r["id"]
        url_trim = (r["url"] or "").strip()
        if not url_trim:
            continue
        if url_trim in seen_urls:
            delete_ids.append(pid)
        else:
            seen_urls[url_trim] = pid
    if delete_ids:
        conn.executemany("DELETE FROM products WHERE id = ?", [(i,) for i in delete_ids])
        conn.commit()
        rows = conn.execute("SELECT * FROM products").fetchall()

    updated = 0

    for r in rows:
        pid = r["id"]
        name = (r["name"] or "").strip()
        url = (r["url"] or "").strip()
        price = (r["price"] or "").strip()
        image_url = (r["image_url"] or "").strip()
        description = _clean_text(r["description"], 2000)
        usage = _clean_text(r["usage"], 1200)
        ingredients = _clean_text(r["ingredients"], 1200)

        comments_raw = r["comments"] or "[]"
        try:
            comments = json.loads(comments_raw)
        except Exception:
            comments = []
        if isinstance(comments, list):
            comments = [_clean_text(c, 300) for c in comments]
            comments = [c for c in comments if c]
        else:
            comments = []

        conn.execute(
            """
            UPDATE products
            SET name = ?, url = ?, price = ?, image_url = ?,
                description = ?, usage = ?, ingredients = ?,
                comments = ?,
                name_norm = ?, description_norm = ?, image_url_norm = ?
            WHERE id = ?
            """,
            (
                name,
                url,
                price,
                image_url,
                description,
                usage,
                ingredients,
                json.dumps(comments, ensure_ascii=False),
                _normalize_text(name),
                _normalize_text(description),
                _normalize_text(image_url),
                pid,
            ),
        )
        updated += 1

    conn.commit()
    conn.close()
    print(f"[cleanup] deleted_duplicates={len(delete_ids)} updated_rows={updated}")


if __name__ == "__main__":
    main()

