"""RAG 索引构建 — PDF → 分块 → bge 嵌入 → numpy 存储

用法:
    python3 -m app.rag_index build                     # 扫描 downloads/ 建索引
    python3 -m app.rag_index build downloads/STAT1510SEF   # 指定目录

产物(ole-data/rag/,gitignored,均可重建):
    embeddings.npy   (N, 512) float32,已 L2 归一化
    chunks.json      [{id, pdf, page, text}, ...]
"""
import os
import json
import sys
from pathlib import Path

# 模型缓存到项目目录(尊重已设的 HF_HOME)
os.environ.setdefault("HF_HOME", str(Path(__file__).parent.parent / ".hf_cache"))

import numpy as np
import pymupdf
from sentence_transformers import SentenceTransformer

PROJECT_ROOT = Path(__file__).parent.parent
INDEX_DIR = PROJECT_ROOT / "ole-data" / "rag"
DEFAULT_PDF_DIR = PROJECT_ROOT / "downloads"
MODEL_NAME = "BAAI/bge-small-zh-v1.5"

CHUNK_CHARS = 350   # 每块约 350 字(bge-small max 512 token,中英混合留余量)
OVERLAP_CHARS = 60  # 块间重叠,避免切断语义


def extract_pdf_text(pdf_path: Path) -> list[dict]:
    """逐页抽取文本(保留页码)。扫描 PDF(无文本层)返回空列表。"""
    pages = []
    doc = pymupdf.open(pdf_path)
    try:
        for i, page in enumerate(doc):
            text = page.get_text("text").strip()
            if text:
                pages.append({"page": i + 1, "text": text})
    finally:
        doc.close()
    return pages


def chunk_pages(pages: list[dict], pdf_name: str) -> list[dict]:
    """按字符滑窗切块,带 overlap,每块标注来源(pdf + page)。"""
    chunks = []
    for p in pages:
        text = p["text"]
        n = len(text)
        start = 0
        while start < n:
            piece = text[start:start + CHUNK_CHARS]
            chunks.append({"pdf": pdf_name, "page": p["page"], "text": piece})
            if start + CHUNK_CHARS >= n:
                break
            start += CHUNK_CHARS - OVERLAP_CHARS
    return chunks


def build_index(pdf_dir: Path = DEFAULT_PDF_DIR, out_dir: Path = INDEX_DIR) -> dict:
    """扫描 pdf_dir 下所有 PDF(递归),构建向量索引。"""
    pdf_dir = Path(pdf_dir)
    pdfs = sorted(pdf_dir.rglob("*.pdf"))
    if not pdfs:
        return {"pdfs": 0, "chunks": 0, "message": f"{pdf_dir} 下无 PDF"}

    all_chunks: list[dict] = []
    skipped: list[str] = []
    for pdf in pdfs:
        try:
            pages = extract_pdf_text(pdf)
            if not pages:
                skipped.append(pdf.name)
                continue
            all_chunks.extend(chunk_pages(pages, pdf.name))
        except Exception as e:
            skipped.append(f"{pdf.name}({e.__class__.__name__})")

    if not all_chunks:
        return {"pdfs": len(pdfs), "chunks": 0, "skipped": skipped,
                "message": "未抽到文本(可能全是扫描 PDF,需 OCR)"}

    print(f"嵌入 {len(all_chunks)} 个块(CPU,首次加载模型 ~2s)...", flush=True)
    model = SentenceTransformer(MODEL_NAME, device="cpu")
    emb = model.encode(
        [c["text"] for c in all_chunks],
        normalize_embeddings=True,
        convert_to_numpy=True,
        batch_size=32,
        show_progress_bar=True,
    ).astype(np.float32)

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    np.save(Path(out_dir) / "embeddings.npy", emb)
    with open(Path(out_dir) / "chunks.json", "w", encoding="utf-8") as f:
        json.dump([{"id": i, **c} for i, c in enumerate(all_chunks)], f, ensure_ascii=False, indent=2)

    return {"pdfs": len(pdfs) - len(skipped), "chunks": len(all_chunks),
            "emb_shape": list(emb.shape), "skipped": skipped, "out_dir": str(out_dir)}


def load_index(index_dir: Path = INDEX_DIR):
    """加载已建索引,返回 (embeddings, chunks) 或 None(未建)。供检索用。"""
    index_dir = Path(index_dir)
    emb_path = index_dir / "embeddings.npy"
    chunks_path = index_dir / "chunks.json"
    if not emb_path.exists() or not chunks_path.exists():
        return None
    emb = np.load(emb_path)
    with open(chunks_path, encoding="utf-8") as f:
        chunks = json.load(f)
    return emb, chunks


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "build":
        pdf_dir = sys.argv[2] if len(sys.argv) >= 3 else str(DEFAULT_PDF_DIR)
        result = build_index(Path(pdf_dir))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("用法:python3 -m app.rag_index build [pdf_dir]")
        print(f"  默认扫描 {DEFAULT_PDF_DIR}")
        sys.exit(1)


if __name__ == "__main__":
    main()
