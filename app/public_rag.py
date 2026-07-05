"""HKMU 官网公开信息 RAG — 从 public_crawler 缓存构建索引 + 检索

用法:
    python3 -m app.public_rag crawl [--force]   # 抓取官网页面并缓存(委托 public_crawler)
    python3 -m app.public_rag build              # 从缓存构建 RAG 索引
    python3 -m app.public_rag status             # 查看索引/缓存状态

产物(ole-data/public/,gitignored,均可重建):
    embeddings.npy   (N, 512) float32,L2 归一化
    chunks.json      [{id, url, title, text}, ...]

复用 Phase 3 的 bge-small-zh-v1.5 模型 + 共享 _search_index 检索逻辑。
来源用外链(官网 URL),前端 Md 组件已 target=_blank,无需新端点。
"""
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

from .public_crawler import PUBLIC_DIR as INDEX_DIR, load_manifest
from .rag_index import CHUNK_CHARS, OVERLAP_CHARS, _search_index, get_model

MIN_TEXT_LEN = 40  # 与 public_crawler 一致,过短的页跳过


def build_public_index() -> dict:
    """读 manifest 缓存 → 按 URL 分块 → bge 嵌入 → 写 embeddings.npy + chunks.json。"""
    manifest = load_manifest()
    if not manifest:
        return {"built": False, "message": "无缓存。先运行:python -m app.public_rag crawl"}

    chunks: list[dict] = []
    skipped = 0
    for m in manifest:
        txt = INDEX_DIR / m["txt_path"]
        if not txt.exists():
            skipped += 1
            continue
        text = txt.read_text(encoding="utf-8").strip()
        if len(text) < MIN_TEXT_LEN:
            skipped += 1
            continue
        url = m["url"]
        title = m.get("title") or url
        # 字符滑窗(与 rag_index.chunk_pages 同款,字段换为 url/title)
        n = len(text)
        start = 0
        while start < n:
            piece = text[start:start + CHUNK_CHARS]
            chunks.append({"url": url, "title": title, "text": piece})
            if start + CHUNK_CHARS >= n:
                break
            start += CHUNK_CHARS - OVERLAP_CHARS

    if not chunks:
        return {"built": False, "pages": len(manifest), "skipped": skipped, "message": "无有效文本"}

    print(f"嵌入 {len(chunks)} 个块(来自 {len(manifest) - skipped} 页,CPU)...", flush=True)
    model = get_model()
    emb = model.encode(
        [c["text"] for c in chunks],
        normalize_embeddings=True,
        convert_to_numpy=True,
        batch_size=32,
        show_progress_bar=True,
    ).astype(np.float32)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    np.save(INDEX_DIR / "embeddings.npy", emb)
    with open(INDEX_DIR / "chunks.json", "w", encoding="utf-8") as f:
        json.dump([{"id": i, **c} for i, c in enumerate(chunks)], f, ensure_ascii=False, indent=2)

    return {
        "built": True,
        "pages": len(manifest) - skipped,
        "chunks": len(chunks),
        "emb_shape": list(emb.shape),
        "skipped": skipped,
        "out_dir": str(INDEX_DIR),
    }


def retrieve_public(query: str, top_k: int = 5) -> list[dict]:
    """检索官网索引,返回 top_k 命中(含 url/title/text/score + 外链 source)。索引未建返回 []。"""
    hits = _search_index(INDEX_DIR, query, top_k)
    if not hits:
        return []
    out = []
    for h in hits:
        url = h.get("url", "")
        title = h.get("title") or url
        out.append({
            "url": url,
            "title": title,
            "text": h["text"],
            "score": h["score"],
            "source_url": url,
            "source": f"[🔗 {title}]({url})",
        })
    return out


def index_public_status() -> dict:
    """索引 + 缓存状态。不依赖 rag_index.index_status(HTML chunk 无 pdf 字段)。"""
    emb_path = INDEX_DIR / "embeddings.npy"
    chunks_path = INDEX_DIR / "chunks.json"
    out: dict = {"built": False}
    if emb_path.exists() and chunks_path.exists():
        emb = np.load(emb_path)
        with open(chunks_path, encoding="utf-8") as f:
            chunks = json.load(f)
        urls = sorted({c["url"] for c in chunks})
        out = {
            "built": True,
            "chunks": len(chunks),
            "page_count": len(urls),
            "emb_shape": list(emb.shape),
            "sample_pages": urls[:8],
        }
    manifest = load_manifest()
    out["cached_pages"] = len(manifest)
    out["cached_by_subsite"] = dict(Counter(m["subsite"] for m in manifest))
    if not out["built"]:
        out["message"] = "索引未建。先运行:python -m app.public_rag crawl && python -m app.public_rag build"
    return out


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("crawl", "build", "status"):
        print("用法:")
        print("  python -m app.public_rag crawl [--force]  抓取官网页面并缓存")
        print("  python -m app.public_rag build            从缓存构建 RAG 索引")
        print("  python -m app.public_rag status           查看索引/缓存状态")
        sys.exit(1 if not args else 0)
    cmd = args[0]
    if cmd == "crawl":
        from .public_crawler import crawl
        result = asyncio.run(crawl(force="--force" in args[1:]))
    elif cmd == "build":
        result = build_public_index()
    else:  # status
        result = index_public_status()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
