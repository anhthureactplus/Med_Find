"""
api/routes.py
Định nghĩa các API endpoint dùng FastAPI
"""

from fastapi import APIRouter, HTTPException, Query

from database.db import (
    search_products,
    get_product_by_id,
    get_products_by_ids,
    get_all_products,
    get_stats,
)

router = APIRouter()


@router.get("/products")
def list_products(limit: int = 20, offset: int = 0):
    """
    Lấy danh sách sản phẩm có phân trang.
    GET /products?limit=20&offset=0
    """
    products = get_all_products(limit=limit, offset=offset)
    return {"data": products, "count": len(products)}


@router.get("/search")
def search(q: str = Query(..., min_length=1, description="Từ khóa tìm kiếm")):
    """
    Tìm kiếm sản phẩm dùng BM25 (nếu sẵn sàng) hoặc LIKE (fallback).
    BM25 cho kết quả tốt hơn vì xét tần suất từ và độ hiếm.
    GET /search?q=vitamin c
    """
    if not q.strip():
        raise HTTPException(status_code=400, detail="Từ khóa không được để trống")

    keyword = q.strip()

    # Thử BM25 trước
    try:
        from database.bm25_search import bm25_search, is_ready
        if is_ready():
            bm25_results = bm25_search(query=keyword, limit=40)
            if bm25_results:
                # Lấy full product info từ SQLite theo id đã rank
                ids = [r["id"] for r in bm25_results]
                products = get_products_by_ids(ids)

                # Giữ đúng thứ tự rank của BM25
                id_order = {pid: i for i, pid in enumerate(ids)}
                products.sort(key=lambda p: id_order.get(p["id"], 999))

                return {
                    "keyword": keyword,
                    "total":   len(products),
                    "data":    products,
                    "mode":    "bm25",
                }
    except Exception as e:
        pass  # Fallback về SQLite LIKE

    # Fallback: SQLite LIKE search
    results = search_products(keyword=keyword)
    return {
        "keyword": keyword,
        "total":   len(results),
        "data":    results,
        "mode":    "keyword",
    }


@router.get("/product/{product_id}")
def get_product(product_id: int):
    """
    Lấy chi tiết 1 sản phẩm theo ID.
    GET /product/1
    """
    product = get_product_by_id(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy sản phẩm ID={product_id}")
    return product


@router.get("/compare")
def compare_products(ids: str = Query(..., description="Danh sách ID cách nhau bởi dấu phẩy. VD: 1,2,3")):
    """
    So sánh nhiều sản phẩm cùng lúc.
    GET /compare?ids=1,2,3
    """
    try:
        # Parse danh sách ID từ string "1,2,3"
        id_list = [int(i.strip()) for i in ids.split(",") if i.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="IDs không hợp lệ. Dùng dạng: 1,2,3")

    if len(id_list) < 2:
        raise HTTPException(status_code=400, detail="Cần ít nhất 2 sản phẩm để so sánh")

    if len(id_list) > 5:
        raise HTTPException(status_code=400, detail="Tối đa so sánh 5 sản phẩm cùng lúc")

    products = get_products_by_ids(id_list)

    # Cấu trúc dữ liệu so sánh theo tiêu chí
    comparison = {
        "products": products,
        "criteria": ["name", "price", "ingredients", "usage", "description"],
    }
    return comparison


@router.get("/semantic-search")
def semantic_search_route(q: str = Query(..., min_length=1, description="Câu tìm kiếm ngữ nghĩa")):
    """
    Tìm kiếm theo ngữ nghĩa dùng ChromaDB + sentence-transformers.
    Hiểu được ý nghĩa câu hỏi, không chỉ khớp từ khóa.
    VD: "thuốc bổ mắt" → tìm được Vitamin A, Lutein dù không có từ đó trong tên
    GET /semantic-search?q=thuoc bo mat
    """
    try:
        from database.vector_db import semantic_search, is_available
        if not is_available():
            # Fallback về SQLite nếu ChromaDB chưa cài
            results = search_products(keyword=q.strip())
            return {"keyword": q, "total": len(results), "data": results,
                    "mode": "keyword", "note": "ChromaDB chưa sẵn sàng, dùng tìm kiếm từ khóa"}

        results = semantic_search(query=q.strip())

        # Nếu ChromaDB không có kết quả tốt → fallback SQLite
        if not results:
            results = search_products(keyword=q.strip())
            return {"keyword": q, "total": len(results), "data": results, "mode": "keyword"}

        return {"keyword": q, "total": len(results), "data": results, "mode": "semantic"}

    except Exception as e:
        # Fallback an toàn
        results = search_products(keyword=q.strip())
        return {"keyword": q, "total": len(results), "data": results, "mode": "keyword"}


@router.get("/stats")
def stats():
    """
    Thống kê tổng quan database.
    GET /stats
    """
    from database.vector_db import get_stats as chroma_stats
    sqlite_stats = get_stats()
    try:
        chroma = chroma_stats()
    except Exception:
        chroma = {"available": False}
    return {**sqlite_stats, "chromadb": chroma}