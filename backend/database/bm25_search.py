"""
database/bm25_search.py

BM25 (Best Match 25) xét 2 yếu tố:
  - TF  (Term Frequency):  từ xuất hiện nhiều lần trong doc → score cao
  - IDF (Inverse Doc Freq): từ hiếm gặp trong toàn bộ corpus → score cao

Cài: pip install rank-bm25 underthesea
"""

import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

# Cache index trong RAM
_bm25_index  = None   # BM25 object
_product_ids = []     # Map: index → product id trong SQLite


def _tokenize_vi(text: str) -> list[str]:
    """
    Tokenize tiếng Việt.
    Thử dùng underthesea (tốt hơn), fallback về split đơn giản.
    """
    if not text:
        return []
    text = text.lower().strip()

    try:
        from underthesea import word_tokenize
        tokens = word_tokenize(text, format="text").split()
    except ImportError:
        # Fallback: tách theo khoảng trắng và dấu câu
        tokens = re.split(r"[\s\-_/,;.()\[\]]+", text)

    # Lọc token rỗng và quá ngắn
    return [t for t in tokens if len(t) >= 2]


def build_index(products: list[dict]) -> bool:
    """
    Build BM25 index từ danh sách sản phẩm.
    Gọi 1 lần khi khởi động server hoặc sau khi crawl thêm.

    products: list dict có keys: id, name, description, ingredients, usage
    """
    global _bm25_index, _product_ids

    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        log.warning("[BM25] Chưa cài rank-bm25. Chạy: pip install rank-bm25")
        return False

    if not products:
        log.warning("[BM25] Không có sản phẩm để index")
        return False

    log.info("[BM25] Đang build index cho %d sản phẩm...", len(products))

    corpus      = []  # List token list cho từng sản phẩm
    _product_ids = []

    for p in products:
        # Ghép các field quan trọng, ưu tiên tên (nhân đôi để tăng weight)
        text = " ".join([
            p.get("name", "") * 2,          # Tên nhân đôi → ưu tiên hơn
            p.get("description", "")[:300],
            p.get("ingredients", "")[:200],
            p.get("usage", "")[:100],
        ])

        tokens = _tokenize_vi(text)
        corpus.append(tokens)
        _product_ids.append(p.get("id"))

    _bm25_index = BM25Okapi(corpus)
    log.info("[BM25] Build index xong: %d documents", len(corpus))
    return True


def bm25_search(query: str, limit: int = 20) -> list[dict]:
    """
    Tìm kiếm BM25.
    Trả về list product_id theo thứ tự score giảm dần.
    """
    global _bm25_index, _product_ids

    if _bm25_index is None:
        log.warning("[BM25] Index chưa được build")
        return []

    # Tokenize query
    query_tokens = _tokenize_vi(query)
    if not query_tokens:
        return []

    # Tính BM25 score cho toàn bộ corpus
    scores = _bm25_index.get_scores(query_tokens)

    # Sắp xếp theo score giảm dần
    ranked = sorted(
        enumerate(scores),
        key=lambda x: x[1],
        reverse=True
    )

    # Lấy top kết quả có score > 0
    results = []
    for idx, score in ranked[:limit]:
        if score <= 0:
            break
        pid = _product_ids[idx]
        if pid is not None:
            results.append({"id": pid, "score": round(float(score), 4)})

    return results


def is_ready() -> bool:
    """Kiểm tra BM25 index đã sẵn sàng chưa"""
    return _bm25_index is not None