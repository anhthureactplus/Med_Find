"""
crawler/spider.py
Crawl chiaki.vn - tích hợp logic từ crawl_final.py đã test hoạt động.
Dùng Playwright để render JS + requests.Session (cookie thật) để lấy comment.
"""

import time
import random
import logging
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from database.db import save_product, url_exists

log = logging.getLogger(__name__)

BASE = "https://chiaki.vn"

BLACKLIST = {
    "collagen","my-pham","son-moi","nuoc-hoa","kem-duong","sua-rua-mat","dau-xa",
    "dau-goi","thuc-pham-kho","sua-dinh-duong","thuc-pham-chuc-nang","giam-can",
    "tang-can","tang-chieu-cao","vitamin-tong-hop-va-khoang-chat","tao-bien",
    "yen-sao","nam-linh-chi","dong-trung-ha-thao","tieu-duong","ho-tro-tim-mach",
    "ho-tro-tieu-hoa","thuoc-bo-mat","thuoc-bo-gan","thuoc-bo-than-kinh",
    "tinh-chat-hau","mam-dau-nanh","can-bang-noi-tiet-to","no-nguc",
    "vien-uong-tri-mun","vien-uong-trang-da","vien-uong-chong-nang","glucosamine",
    "natrol","bio-island","blackmores","kirkland","orihiro","swisse","dhc","nike",
    "mac","dior","chanel","hermes","3ce","kiko","shiseido","laneige","innisfree",
    "cerave","la-roche-posay","tin-tuc","dang-nhap","dang-ky","apps","lien-he",
    "cham-soc-da-mat","cham-soc-co-the","cham-soc-ca-nhan","cham-soc-rang-mieng",
    "cham-soc-thu-cung","bo-tro-xuong-khop","dinh-duong-the-hinh","omega-3-6-9",
    "ho-tro-tang-de-khang","ho-tro-giac-ngu","ho-tro-giam-ho","nha-cua-doi-song",
    "thuc-uong-do-uong","thiet-bi-cham-soc-suc-khoe","thiet-bi-phong-chay-chua-chay",
}

PRODUCT_KEYWORDS = {
    "mg","ml","vien","hop","lo","chai","gam","kg","ong","tui","set",
    "cua-nhat","cua-my","cua-uc","cua-han","nhat-ban","han-quoc",
    "tang-cuong","bo-sung","ho-tro","dang-vien","dang-bot","dang-nuoc",
    "vitamin","omega","canxi","protein","probiotic","serum","capsule","tablet",
    "nuoc-uong","vien-uong",
}

COMPANY_SIGNALS = [
    "co-ltd","corporation","gmbh","s-r-o","sp-z","factory-of",
    "vien-han-lam","cong-ty","hoc-vien","xi-nghiep","company-limited",
    "laboratories","pharma","healthcare","science","institute",
]

# Danh mục mặc định để crawl
DEFAULT_CATEGORIES = [
    "https://chiaki.vn/vitamin-tong-hop-va-khoang-chat",
    "https://chiaki.vn/collagen",
    "https://chiaki.vn/sua-dinh-duong",
    "https://chiaki.vn/thuc-pham-chuc-nang",
    "https://chiaki.vn/giam-can",
]


# ── Kiểm tra URL có phải sản phẩm không ─────────────────────
def is_product(url: str) -> bool:
    path = url.split("chiaki.vn/")[-1].split("?")[0].strip("/")
    if "/" in path or not path or path.startswith("-"):
        return False
    if path in BLACKLIST:
        return False
    if any(x in path for x in COMPANY_SIGNALS):
        return False
    words = [w for w in path.split("-") if w]
    if len(words) < 4:
        return False
    if len(words) < 6:
        return any(kw in path for kw in PRODUCT_KEYWORDS)
    return True


# ── Tải trang bằng Playwright ────────────────────────────────
def get_html(page, url: str) -> str | None:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(800)
        return page.content()
    except Exception:
        log.warning("Timeout/lỗi: %s", url)
        return None


# ── Lấy link sản phẩm từ trang danh mục ─────────────────────
def parse_listing(html: str) -> tuple[list[str], str | None]:
    soup = BeautifulSoup(html, "html.parser")
    urls = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        full = href if href.startswith("http") else BASE + "/" + href.lstrip("/")
        if "chiaki.vn/" in full and is_product(full):
            urls.add(full.split("?")[0])
    # Trang tiếp theo
    nxt = None
    btn = soup.select_one("a.next, a[rel='next']")
    if btn and btn.get("href"):
        nxt = btn["href"] if btn["href"].startswith("http") else BASE + btn["href"]
    return list(urls), nxt


# ── Lấy comment qua requests.Session (cookie thật từ browser) ─
def fetch_comments(session: requests.Session, product_id: str, max_pages: int = 3) -> list[dict]:
    """
    Dùng requests.Session với cookie lấy từ Playwright browser
    để bypass 403 khi gọi API comment.
    """
    comments = []
    for page_id in range(max_pages):
        url = (
            "https://api.chiaki.vn/api/load-comment"
            "?embeds=images,replies"
            "&fields=id,user,content,evaluation,create_time,like_count"
            "&filters=target_id%3D" + str(product_id) + ",is_qa%3D0,"
            "type%3D%7Bproduct;review_order%7D,status%3Dactive,"
            "content!%3Dnull,evaluation%3E0"
            "&page_id=" + str(page_id) + "&page_size=20&sorts=-create_time"
        )
        try:
            r = session.get(url, timeout=10)
            if r.status_code != 200:
                break
            data = r.json()
            # API có thể trả về "result" hoặc "data"
            items = data.get("result") or data.get("data") or []
            if not items:
                break
            for item in items:
                user = item.get("user") or ""
                author = user if isinstance(user, str) else (user.get("name") or "")
                content = item.get("content") or ""
                if content.strip():
                    comments.append({
                        "author": author,
                        "rating": item.get("evaluation"),
                        "content": content.strip()[:300],
                        "date": item.get("create_time") or "",
                        "likes": item.get("like_count") or 0,
                    })
        except Exception as e:
            log.warning("Comment API lỗi pid=%s: %s", product_id, e)
            break
    return comments


# ── Parse chi tiết 1 trang sản phẩm ─────────────────────────
def parse_product(html: str, url: str, session: requests.Session) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")

    # Tên - selector đúng của chiaki.vn
    name_tag = soup.select_one("h1.product-detail-header-box")
    if not name_tag or len(name_tag.text.strip()) < 5:
        return None

    # Giá hiện tại và giá gốc
    price_tag     = soup.select_one("span#price-show") or soup.select_one("span.price-show")
    old_price_tag = soup.select_one("dell#sale-price-show")
    rating_tag    = soup.select_one("span.product-point-comment-value")
    rating_count  = soup.select_one("div.rating-count")

    # Ảnh - thử nhiều selector theo thứ tự ưu tiên
    image_url = ""
    img_selectors = [
        "img.product-detail-img-main",
        ".product-detail-img img",
        ".product-image-main img",
        ".product__media img",
        "img[class*='product-img']",
        "img[class*='main-img']",
        ".swiper-slide img",
        "img[src*='chiaki']",
        "img[src*='cdn']",
    ]
    for sel in img_selectors:
        img_tag = soup.select_one(sel)
        if img_tag:
            src = (img_tag.get("src") or img_tag.get("data-src")
                   or img_tag.get("data-lazy-src") or img_tag.get("data-original", ""))
            # Lọc bỏ ảnh placeholder/icon nhỏ
            if src and ("product" in src or "cdn" in src or "chiaki" in src
                        or src.endswith((".jpg",".jpeg",".png",".webp"))):
                if src.startswith("//"):
                    src = "https:" + src
                elif src.startswith("/"):
                    src = "https://chiaki.vn" + src
                image_url = src
                break

    # Fallback: lấy ảnh og:image từ meta tag
    if not image_url:
        og = soup.select_one('meta[property="og:image"]')
        if og and og.get("content"):
            image_url = og["content"]

    # ── Mô tả: chỉ lấy đoạn giới thiệu đầu, cắt tại section con ──
    desc_tag = soup.select_one("div#content-product")
    description = ""
    ingredients = ""
    usage       = ""

    if desc_tag:
        # Tìm các thẻ heading/section bên trong mô tả
        # Chiaki dùng <h2>, <h3>, <strong> để chia section
        full_text = desc_tag.get_text("\n", strip=True)

        # Các từ khóa đánh dấu bắt đầu section riêng
        CUT_KEYWORDS = [
            "thành phần", "hướng dẫn sử dụng", "cách dùng",
            "liều dùng", "đối tượng sử dụng", "lưu ý",
            "thực phẩm này không phải", "hiệu quả sử dụng tùy",
            "câu hỏi thường gặp", "về thương hiệu",
        ]

        lines = full_text.splitlines()
        desc_lines = []
        ing_lines  = []
        use_lines  = []
        mode = "desc"   # trạng thái đang đọc section nào

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            low = stripped.lower()

            # Phát hiện chuyển section
            if any(kw in low for kw in ["thành phần"]):
                mode = "ing"
                continue
            if any(kw in low for kw in ["hướng dẫn sử dụng", "cách dùng", "liều dùng"]):
                mode = "use"
                continue
            if any(kw in low for kw in [
                "đối tượng sử dụng", "lưu ý", "câu hỏi thường gặp",
                "về thương hiệu", "thực phẩm này không phải",
                "hiệu quả sử dụng tùy", "thông tin sản phẩm",
                "mua ", "giá ", "review "
            ]):
                mode = "skip"
                continue

            if mode == "desc":
                desc_lines.append(stripped)
            elif mode == "ing":
                ing_lines.append(stripped)
            elif mode == "use":
                use_lines.append(stripped)

        description = "\n".join(desc_lines).strip()[:2000]
        ingredients = "\n".join(ing_lines).strip()[:800]
        usage       = "\n".join(use_lines).strip()[:800]

    # ── Thông số kỹ thuật từ product-specs-row ─────────────────
    # Đây là bảng sidebar: Danh mục, Xuất xứ, Thương hiệu,...
    specifications = {}
    for row in soup.select("div.product-specs-row"):
        label = row.select_one(".product-specs-label")
        value = row.select_one(".product-specs-value")
        if not label or not value:
            continue
        key = label.text.strip()
        val = value.text.strip()
        specifications[key] = val
        key_low = key.lower()
        # Ưu tiên specs nếu mô tả không tìm thấy
        if not ingredients and any(kw in key_low for kw in ["thành phần", "hoạt chất"]):
            ingredients = val
        if not usage and any(kw in key_low for kw in ["cách dùng", "liều dùng"]):
            usage = val

    # Lấy product_id để gọi API comment
    pid_tag = soup.select_one("input#product-id")
    product_id = pid_tag["value"].strip() if pid_tag and pid_tag.get("value") else ""

    # Lấy comment qua requests.Session với cookie thật
    raw_comments = fetch_comments(session, product_id) if product_id else []

    # Chuyển comment thành list string để lưu DB
    # Format: "TênTác giả (5⭐): Nội dung"
    comment_texts = []
    for c in raw_comments:
        rating_str = f" ({c['rating']}⭐)" if c.get("rating") else ""
        author_str = f"{c['author']}: " if c.get("author") else ""
        comment_texts.append(f"{author_str}{c['content']}{rating_str}")

    return {
        "name":           name_tag.text.strip(),
        "url":            url,
        "price":          price_tag.text.strip() if price_tag else "",
        "original_price": old_price_tag.text.strip() if old_price_tag else "",
        "rating":         rating_tag.text.strip() if rating_tag else "",
        "description":    description,
        "ingredients":    ingredients,
        "usage":          usage,
        "image_url":      image_url,
        "specifications": specifications,
        "comments":       comment_texts,
    }


# ── Hàm crawl chính ──────────────────────────────────────────
def crawl(
    start_url: str = "https://chiaki.vn",
    max_depth: int = 3,
    max_pages: int = 50,
    include_external: bool = False,
    delay: float = 1.0,
) -> int:
    print(f"\n{'='*55}")
    print("[CRAWLER] Khởi động Playwright + requests session...")
    print(f"[CRAWLER] Giới hạn: {max_pages} sản phẩm | {max_depth} trang/category")
    print(f"{'='*55}\n")

    visited: set[str] = set()
    total_saved = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="vi-VN",
        )
        page = ctx.new_page()

        # ── Lấy cookie thật từ chiaki.vn để dùng cho requests ──
        print("[SETUP] Lấy cookie từ chiaki.vn...")
        page.goto(BASE, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(1500)

        browser_cookies = ctx.cookies()
        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Referer": "https://chiaki.vn/",
            "Origin":  "https://chiaki.vn",
        })
        for c in browser_cookies:
            session.cookies.set(c["name"], c["value"], domain=c.get("domain", ""))
        print(f"[SETUP] Lấy được {len(browser_cookies)} cookies\n")

        for cat_url in DEFAULT_CATEGORIES:
            if total_saved >= max_pages:
                break

            print(f"\n[CATEGORY] {cat_url}")
            current_url = cat_url
            page_num = 1

            while current_url and page_num <= max_depth:
                print(f"  Trang {page_num}: {current_url}")
                html = get_html(page, current_url)
                if not html:
                    break

                prod_urls, next_url = parse_listing(html)
                print(f"  -> Tìm thấy {len(prod_urls)} link sản phẩm")

                for purl in prod_urls:
                    if total_saved >= max_pages:
                        break
                    if purl in visited:
                        continue
                    visited.add(purl)

                    if url_exists(purl):
                        print(f"  ⏭ Đã có: {purl.split('/')[-1][:45]}")
                        continue

                    time.sleep(random.uniform(delay, delay + 1.0))

                    phtml = get_html(page, purl)
                    if not phtml:
                        continue

                    product = parse_product(phtml, purl, session)
                    if not product:
                        print(f"  ✗ skip: {purl.split('/')[-1][:45]}")
                        continue

                    save_product(product)
                    total_saved += 1
                    print(f"  ✅ [{total_saved}/{max_pages}] {product['name'][:50]}")
                    print(f"     Giá: {product['price'] or 'N/A'} | "
                          f"Ảnh: {'có' if product['image_url'] else 'không'} | "
                          f"Comment: {len(product['comments'])}")

                current_url = next_url
                page_num += 1

        browser.close()

    print(f"\n{'='*55}")
    print(f"[DONE] Tổng sản phẩm đã lưu: {total_saved}")
    print(f"{'='*55}\n")
    return total_saved