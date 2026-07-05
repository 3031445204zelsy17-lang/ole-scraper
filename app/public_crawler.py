"""HKMU 官网公开信息爬虫 — sitemap 发现 → httpx 抓 → trafilatura 抽正文 → 缓存

用法:
    python3 -m app.public_crawler crawl          # 抓取并缓存(已缓存则跳过,可续抓)
    python3 -m app.public_crawler crawl --force  # 强制重抓
    python3 -m app.public_crawler status         # 缓存摘要

产物(ole-data/public/,gitignored,均可重建):
    html/<sha1>.html   原始 HTML(供日后重建索引,不必重抓)
    html/<sha1>.txt    抽取的正文(trafilatura,去导航/页脚)
    manifest.json      [{url, title, subsite, html_path, txt_path, fetched_at}, ...]

合规姿态(对齐官网 robots 的 content-signal `use=reference`):
  - 仅抓精选公开子站(主站+招生+7 学院+图书馆+新闻),明确排除个人门户
    (current-students / alumni / tutors / ft-staff / research-students 等)
  - 仅英文(过滤 WPML 的 /sc/ /tc/ 变体)
  - 礼貌限速(请求间隔 REQUEST_DELAY)、诚实 UA、不伪装训练爬虫
  - trafilatura 只抽主正文 → 片段化引用,不全文复现
  - 缓存仅本地个人自用,不外发不重分发
"""
import asyncio
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree as ET

import httpx
import trafilatura
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).parent.parent
PUBLIC_DIR = PROJECT_ROOT / "ole-data" / "public"
HTML_DIR = PUBLIC_DIR / "html"
MANIFEST_PATH = PUBLIC_DIR / "manifest.json"

BASE_URL = "https://www.hkmu.edu.hk"

# 精选公开子站(空串=主站)。排除:个人门户 / 会议微站 / 行政处。
ALLOWED_SUBSITES = ["", "as", "ba", "el", "nhs", "st", "sol", "lipace", "lib", "news"]

# 高价值落地页(无论 sitemap 是否抓到都纳入;sitemap 被 Cloudflare 挑战时的兜底)
SEED_URLS = [
    f"{BASE_URL}/",
    f"{BASE_URL}/admissions/",
    f"{BASE_URL}/academics/",
    f"{BASE_URL}/research/",
    f"{BASE_URL}/about-hkmu/",
    f"{BASE_URL}/news/",
    f"{BASE_URL}/as/",
    f"{BASE_URL}/ba/",
    f"{BASE_URL}/el/",
    f"{BASE_URL}/nhs/",
    f"{BASE_URL}/st/",
    f"{BASE_URL}/sol/",
    f"{BASE_URL}/lipace/",
    f"{BASE_URL}/lib/",
]

USER_AGENT = "OLE-Agent/0.1 (personal local use; HKMU student reference RAG)"
REQUEST_DELAY = 0.5   # sitemap 发现时的请求间隔(秒)
TIMEOUT = 20.0
RETRY_STATUS = {429, 500, 502, 503, 504}
MIN_TEXT_LEN = 40     # 短于此大概率是导航/占位页,丢弃
MAX_PER_SUBSITE = 400  # 每子站上限(news 等高量子站会被截,见日志)
CONCURRENCY = 5       # 页面抓取并发(网络等待重叠;峰值 ~2 req/s,礼貌不破)


# ── URL 分类 / 过滤 ─────────────────────────────────────────

def _subsite_of(url: str) -> str:
    """从 URL 提取子站前缀(主站返回 "main")。"""
    rest = url[len(BASE_URL):] if url.startswith(BASE_URL) else ""
    rest = rest.lstrip("/")
    if not rest:
        return "main"
    first = rest.split("/", 1)[0]
    return first if first in ALLOWED_SUBSITES and first != "" else "main"


def _is_english(url: str) -> bool:
    """过滤非英文页面:WPML 路径 /sc/ /tc/ 或 ?lang=,以及 CJK slug
    (主站也混有中文页面,如 %e5%9b%be…图书馆,不带 /sc/ 前缀)。"""
    low = url.lower()
    if "/sc/" in low or "/tc/" in low or low.endswith("/sc") or low.endswith("/tc"):
        return False
    if "lang=sc" in low or "lang=tc" in low:
        return False
    try:
        path = url.split(BASE_URL, 1)[-1] if url.startswith(BASE_URL) else url
        decoded = unquote(path)
    except Exception:
        decoded = url
    # 含 CJK(0x2E80+)等非拉丁字符 → 中文/其他语种页面,丢弃
    if any(ord(ch) > 0x2E80 for ch in decoded):
        return False
    return True


def _is_content_url(url: str) -> bool:
    """排除附件 / feed / 分页等非内容 URL。"""
    low = url.lower()
    if "/wp-content/uploads/" in low:
        return False
    if re.search(r"/feed/?$|/page/\d+/?$|/amp/?$", low):
        return False
    return True


def _is_content_sitemap(loc: str) -> bool:
    """只取内容型子 sitemap(page/post),跳过 image/archive/category/post_tag。"""
    low = loc.lower()
    if "image-sitemap" in low:
        return False
    return "page-sitemap" in low or "post-sitemap" in low


# ── 抓取 / 解析 ─────────────────────────────────────────────

async def _fetch(client: httpx.AsyncClient, url: str) -> tuple[int, str | None]:
    """GET + 退避重试(429/5xx)。返回 (status, text|None)。403/404 不重试。"""
    for attempt in range(3):
        try:
            r = await client.get(url, timeout=TIMEOUT)
            if r.status_code == 200:
                return 200, r.text
            if r.status_code in RETRY_STATUS:
                wait = 2 ** attempt
                print(f"  [{r.status_code}] {url},等 {wait}s 重试", flush=True)
                await asyncio.sleep(wait)
                continue
            return r.status_code, None
        except httpx.RequestError as e:
            wait = 2 ** attempt
            print(f"  [网络错误] {e.__class__.__name__} {url},等 {wait}s", flush=True)
            await asyncio.sleep(wait)
    return 0, None


def _parse_locs(xml_text: str) -> list[str]:
    """解析 sitemapindex,返回子 sitemap 的 <loc> 列表。"""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    out = []
    for el in root.iter():
        if el.tag.endswith("loc") and el.text:
            t = el.text.strip()
            if t:
                out.append(t)
    return out


def _parse_url_entries(xml_text: str) -> list[tuple[str, str]]:
    """解析 urlset,返回 [(loc, lastmod)](无 lastmod 则空串)。"""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    out = []
    for url_el in root.iter():
        if not url_el.tag.endswith("url"):
            continue
        loc = lastmod = ""
        for child in url_el:
            if child.tag.endswith("loc") and child.text:
                loc = child.text.strip()
            elif child.tag.endswith("lastmod") and child.text:
                lastmod = child.text.strip()
        if loc:
            out.append((loc, lastmod))
    return out


async def discover_urls(client: httpx.AsyncClient) -> list[str]:
    """逐子站抓 sitemap_index → 内容型子 sitemap → URL。
    每子站按 <lastmod> 取最新 MAX_PER_SUBSITE 个;种子 URL 始终保留。"""
    seed_set = set(SEED_URLS)
    by_sub: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for s in SEED_URLS:
        by_sub[_subsite_of(s)].append((s, ""))  # 种子无 lastmod → 排序沉底,但下面单独保

    for sub in ALLOWED_SUBSITES:
        idx_url = f"{BASE_URL}/{sub}/sitemap_index.xml" if sub else f"{BASE_URL}/sitemap_index.xml"
        status, text = await _fetch(client, idx_url)
        if status != 200 or not text or "<sitemapindex" not in text[:1000]:
            print(f"[sitemap 跳过] {idx_url} (status={status},可能被 Cloudflare 挑战;种子兜底)",
                  flush=True)
            continue
        children = _parse_locs(text)
        keep = [c for c in children if _is_content_sitemap(c)]
        print(f"[sitemap] {sub or '主站'}:{len(children)} 子 sitemap → 取 {len(keep)} 内容型",
              flush=True)
        for sm in keep:
            await asyncio.sleep(REQUEST_DELAY)
            s_status, s_text = await _fetch(client, sm)
            if s_status != 200 or not s_text:
                continue
            for loc, lm in _parse_url_entries(s_text):
                if loc.startswith(BASE_URL) and _is_english(loc) and _is_content_url(loc):
                    by_sub[_subsite_of(loc)].append((loc, lm))

    # 每子站:种子必留 + 其余按 lastmod 取最新(不静默,见日志)
    capped: list[str] = []
    for sub, lst in by_sub.items():
        seen: set[str] = set()
        seeds, discovered = [], []
        for loc, lm in lst:
            if loc in seen:
                continue
            seen.add(loc)
            (seeds if loc in seed_set else discovered).append((loc, lm))
        discovered.sort(key=lambda t: t[1] or "", reverse=True)  # 最新在前,无 lastmod 沉底
        if len(discovered) > MAX_PER_SUBSITE:
            print(f"[cap] {sub or '主站'}:{len(discovered)} 发现 → 取最新 {MAX_PER_SUBSITE}"
                  f"(丢弃 {len(discovered) - MAX_PER_SUBSITE})", flush=True)
        for loc, _ in seeds:
            capped.append(loc)
        for loc, _ in discovered[:MAX_PER_SUBSITE]:
            capped.append(loc)
    return sorted(set(capped))


_CONSENT_RE = re.compile(r"gdpr|cookie|consent|moove|modal|popup|newsletter", re.I)


def _is_consent(tag) -> bool:
    """标签的 id/class 是否属于 cookie consent / 弹窗类(会盖住正文,需剥离)。"""
    for attr in ("id", "class"):
        val = tag.get(attr)
        if val and _CONSENT_RE.search(str(val)):
            return True
    return False


def _clean_html(html: str) -> tuple[str | None, str]:
    """bs4 预清理:去 script/style/noscript + cookie consent 块。
    HKMU 用 Elementor(无 <article>/<main>),GDPR consent 文本会盖住正文,
    必须先剥才能让 trafilatura 抓到真内容。返回 (title, cleaned_html)。"""
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    for el in soup.find_all(_is_consent):
        el.decompose()
    return title, str(soup)


def _doc_get(doc, key):
    """bare_extraction 在不同 trafilatura 版本返回 dict 或 Document 对象,统一取值。"""
    if isinstance(doc, dict):
        return doc.get(key)
    return getattr(doc, key, None)


def _extract(html: str) -> tuple[str | None, str | None]:
    """bs4 预清理(剥 cookie consent)→ trafilatura 抽正文(favor_recall)。
    返回 (title, text);无有效正文返回 (None, None)。"""
    title, cleaned = _clean_html(html)
    try:
        doc = trafilatura.bare_extraction(
            cleaned, include_links=False, include_tables=True,
            include_images=False, favor_recall=True,
        )
    except Exception:
        return None, None
    if doc:
        t2 = (_doc_get(doc, "title") or "").strip()
        if t2:
            title = t2  # trafilatura 的 title 更准则覆盖
        text = (_doc_get(doc, "text") or "").strip()
    else:
        text = ""
    if len(text) < MIN_TEXT_LEN:
        return None, None
    return title, text


# ── manifest 持久化 ─────────────────────────────────────────

def _url_key(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_manifest() -> list[dict]:
    if MANIFEST_PATH.exists():
        try:
            with open(MANIFEST_PATH, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_manifest(m: list[dict]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)


# ── 主流程 ──────────────────────────────────────────────────

async def crawl(force: bool = False) -> dict:
    """发现 + 抓取 + 抽取 + 缓存。已缓存且非 force 则跳过(可续抓)。"""
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    HTML_DIR.mkdir(parents=True, exist_ok=True)

    manifest = [] if force else load_manifest()
    done = {m["url"] for m in manifest}

    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        urls = await discover_urls(client)
        print(f"[发现] {len(urls)} 个候选 URL(含种子);已缓存 {len(done)}", flush=True)

        todo = [u for u in urls if u not in done]
        cached = len(urls) - len(todo)

        async def worker(url):
            """抓取 + 抽取 + 落盘,返回 (kind, status, entry_or_None)。"""
            status, html = await _fetch(client, url)
            if status != 200 or not html:
                return ("fail", status, None)
            title, text = _extract(html)
            if not text:
                return ("skip", status, None)
            key = _url_key(url)
            (HTML_DIR / f"{key}.html").write_text(html, encoding="utf-8")
            (HTML_DIR / f"{key}.txt").write_text(text, encoding="utf-8")
            return ("ok", status, {
                "url": url,
                "title": title,
                "subsite": _subsite_of(url),
                "html_path": f"html/{key}.html",
                "txt_path": f"html/{key}.txt",
                "fetched_at": _now_iso(),
            })

        new_ok = skip_new = failed = 0
        n = len(todo)
        for start in range(0, n, CONCURRENCY):
            batch = todo[start:start + CONCURRENCY]
            results = await asyncio.gather(*[worker(u) for u in batch])
            for kind, _status, entry in results:
                if kind == "ok":
                    manifest.append(entry)
                    new_ok += 1
                elif kind == "skip":
                    skip_new += 1
                else:
                    failed += 1
            if start % 30 == 0:  # 每 ~30 页落盘,防中断丢失
                _save_manifest(manifest)
            ok_now = sum(1 for r in results if r[0] == "ok")
            print(f"  [{start + len(batch)}/{n}] +{ok_now} ok "
                  f"(累计缓存 {len(manifest)})", flush=True)

    _save_manifest(manifest)
    return {
        "candidates": len(urls),
        "new": new_ok,
        "skipped": cached + skip_new,
        "failed": failed,
        "total_cached": len(manifest),
    }


def status() -> dict:
    """缓存摘要:已抓页数 + 子站分布。"""
    manifest = load_manifest()
    by_sub = Counter(m["subsite"] for m in manifest)
    return {
        "cached_pages": len(manifest),
        "by_subsite": dict(by_sub),
        "manifest_path": str(MANIFEST_PATH),
    }


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("crawl", "status"):
        print("用法:")
        print("  python3 -m app.public_crawler crawl [--force]  抓取并缓存(可续抓)")
        print("  python3 -m app.public_crawler status           查看缓存摘要")
        sys.exit(1 if not args else 0)
    if args[0] == "status":
        print(json.dumps(status(), ensure_ascii=False, indent=2))
        return
    force = "--force" in args[1:]
    result = asyncio.run(crawl(force=force))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
