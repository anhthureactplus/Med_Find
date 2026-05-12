"""
database/vector_db.py
ChromaDB - semantic search cho sản phẩm thuốc.
Dùng sentence-transformers (model tiếng Việt) để tạo vector embedding.

Cài đặt:
    pip install chromadb sentence-transformers
"""

import os
import logging
from pathlib import Path

log = logging.getLogger(__name__)

# Thư mục lưu ChromaDB
CHROMA_PATH = Path(__file__).parent.parent / "data" / "chroma"

# Model embedding - paraphrase-multilingual hỗ trợ tiếng Việt tốt
EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# Biến global - khởi tạo 1 lần, dùng nhiều lần
_client     = None
_collection = None
_embedder   = None


def _get_embedder():
    """Lazy load model embedding - chỉ tải khi cần"""
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            log.info("[ChromaDB] Đang tải model embedding %s...", EMBED_MODEL)
            _embedder = SentenceTransformer(EMBED_MODEL)
            log.info("[ChromaDB] Tải model xong")
        except ImportError:
            log.error("[ChromaDB] Chưa cài sentence-transformers. Chạy: pip install sentence-transformers")
            return None
    return _embedder


def _get_collection():
    """Lazy init ChromaDB collection"""
    global _client, _collection
    if _collection is None:
        try:
            import chromadb
            CHROMA_PATH.mkdir(parents=True, exist_ok=True)
            _client     = chromadb.PersistentClient(path=str(CHROMA_PATH))
            _collection = _client.get_or_create_collection(
                name="products",
                metadata={"hnsw:space": "cosine"}  # Cosine similarity
            )
            log.info("[ChromaDB] Khởi tạo collection OK, %d documents", _collection.count())
        except ImportError:
            log.error("[ChromaDB] Chưa cài chromadb. Chạy: pip install chromadb")
            return None
    return _collection


def is_available() -> bool:
    """Kiểm tra ChromaDB có sẵn sàng không"""
    return _get_collection() is not None and _get_embedder() is not None


def index_product(product: dict) -> bool:
    """
    Thêm 1 sản phẩm vào ChromaDB.
    Text được embed = tên + mô tả + thành phần (ghép lại).
    """
    col = _get_collection()
    emb = _get_embedder()
    if col is None or emb is None:
        return False

    try:
        product_id = str(product.get("id") or product.get("url", ""))
        if not product_id:
            return False

        # Ghép text để embed - càng nhiều context càng tìm kiếm tốt
        text_parts = [
            product.get("name", ""),
            product.get("description", "")[:500],   # Giới hạn để không quá dài
            product.get("ingredients", "")[:300],
            product.get("usage", "")[:200],
        ]
        text = " ".join(p for p in text_parts if p).strip()
        if not text:
            return False

        # Tạo vector embedding
        vector = emb.encode(text).tolist()

        # Lưu vào ChromaDB kèm metadata để filter
        col.upsert(  # upsert = update nếu đã có, insert nếu chưa
            ids=[product_id],
            embeddings=[vector],
            documents=[text],
            metadatas=[{
                "name":      product.get("name", ""),
                "price":     product.get("price", ""),
                "image_url": product.get("image_url", ""),
                "url":       product.get("url", ""),
                "db_id":     str(product.get("id", "")),
            }]
        )
        return True
    except Exception as e:
        log.error("[ChromaDB] Lỗi index sản phẩm: %s", e)
        return False


def semantic_search(query: str, limit: int = 20) -> list[dict]:
    """
    Tìm kiếm theo ngữ nghĩa.
    VD: "thuốc bổ mắt" → tìm sản phẩm chứa Vitamin A, Lutein dù không có từ đó

    Trả về list dict giống format của SQLite search để frontend dùng được.
    """
    col = _get_collection()
    emb = _get_embedder()
    if col is None or emb is None:
        return []

    try:
        # Embed câu query
        query_vector = emb.encode(query).tolist()

        # Tìm sản phẩm gần nhất theo cosine similarity
        results = col.query(
            query_embeddings=[query_vector],
            n_results=min(limit, col.count() or 1),
            include=["metadatas", "distances", "documents"]
        )

        products = []
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for meta, dist in zip(metadatas, distances):
            # distance trong cosine: 0 = giống nhau, 2 = khác nhau
            # Chuyển thành score: 1 = giống, 0 = khác
            score = round(1 - dist / 2, 3)

            # Chỉ lấy kết quả có độ tương đồng > 0.3
            if score < 0.3:
                continue

            products.append({
                "id":        int(meta.get("db_id", 0)) if meta.get("db_id") else None,
                "name":      meta.get("name", ""),
                "price":     meta.get("price", ""),
                "image_url": meta.get("image_url", ""),
                "url":       meta.get("url", ""),
                "score":     score,   # Thêm score để frontend hiển thị
            })

        return products

    except Exception as e:
        log.error("[ChromaDB] Lỗi semantic search: %s", e)
        return []


def index_all_from_sqlite():
    """
    Index toàn bộ sản phẩm từ SQLite vào ChromaDB.
    Chạy 1 lần sau khi crawl xong hoặc khi cần rebuild index.
    """
    from database.db import get_all_products, get_product_by_id, get_stats

    stats   = get_stats()
    total   = stats["total_products"]
    indexed = 0

    print(f"\n[ChromaDB] Bắt đầu index {total} sản phẩm...")

    # Lấy từng batch 50 sản phẩm
    batch_size = 50
    offset     = 0

    while offset < total:
        products = get_all_products(limit=batch_size, offset=offset)
        if not products:
            break

        for p in products:
            # Lấy full detail (có description, ingredients)
            full = get_product_by_id(p["id"])
            if full and index_product(full):
                indexed += 1

        offset += batch_size
        print(f"  [{indexed}/{total}] đã index...")

    print(f"[ChromaDB] Hoàn thành: {indexed}/{total} sản phẩm\n")
    return indexed


def get_stats() -> dict:
    """Thống kê ChromaDB"""
    col = _get_collection()
    if col is None:
        return {"available": False, "total": 0}
    return {
        "available": True,
        "total":     col.count(),
        "model":     EMBED_MODEL,
        "path":      str(CHROMA_PATH),
    }