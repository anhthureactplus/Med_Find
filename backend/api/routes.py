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
    Tìm kiếm sản phẩm theo tên hoặc mô tả.
    GET /search?q=paracetamol
    """
    if not q.strip():
        raise HTTPException(status_code=400, detail="Từ khóa không được để trống")

    results = search_products(keyword=q.strip())
    return {
        "keyword": q,
        "total": len(results),
        "data": results,
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


@router.get("/stats")
def stats():
    """
    Thống kê tổng quan database.
    GET /stats
    """
    return get_stats()