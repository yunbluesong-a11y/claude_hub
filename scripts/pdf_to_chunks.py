"""
pdf_to_chunks.py (v2)
======================
raw/{client_id}/{case_slug}/ 내 .pdf 파일을 청크 분할 + 요약 + 페이지 인덱스 생성.
페이지별 텍스트를 master.sqlite pages 테이블에도 저장.

사용법:
    python scripts/pdf_to_chunks.py {client_id}/{case_slug}

출력물:
- projects/{client}/{case}/summaries/{pdf_stem}_chunk_{n}.txt
- projects/{client}/{case}/summaries/{pdf_stem}_overview.txt
- projects/{client}/{case}/index/page_index.json
- master.sqlite pages 테이블

의존성: PyMuPDF (fitz)
"""

import sys
import json
import re
import sqlite3
from pathlib import Path
from collections import defaultdict


def get_fitz():
    try:
        import fitz
        return fitz
    except ImportError:
        print("[ERROR] PyMuPDF가 설치되지 않았습니다. 설치: pip install PyMuPDF")
        sys.exit(1)


def extract_keywords(text: str, top_n: int = 15) -> list:
    stopwords = {
        "의", "을", "를", "이", "가", "은", "는", "에", "서", "로", "와", "과",
        "도", "에서", "으로", "그", "이", "것", "수", "등", "및", "또한", "하여",
        "the", "a", "an", "and", "or", "of", "in", "to", "for", "is", "are",
        "was", "were", "be", "been", "have", "has", "with", "that", "this",
    }
    words = re.findall(r"[가-힣a-zA-Z]{2,}", text.lower())
    freq = defaultdict(int)
    for w in words:
        if w not in stopwords:
            freq[w] += 1
    return [w for w, _ in sorted(freq.items(), key=lambda x: -x[1])[:top_n]]


def summarize_text(text: str, max_chars: int = 800) -> str:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    preview = " ".join(lines[:30])[:max_chars]
    keywords = extract_keywords(text)
    return f"{preview}\n\n[주요 키워드] {', '.join(keywords)}"


def save_pages_to_master(client_id: str, case_slug: str, source_file: str,
                          pages_text: list, base: Path):
    """master.sqlite pages 테이블에 페이지별 텍스트 저장"""
    master_path = base / "db" / "master.sqlite"
    if not master_path.exists():
        return
    conn = sqlite3.connect(master_path)
    c = conn.cursor()
    # 기존 데이터 삭제 (멱등성)
    c.execute("DELETE FROM pages WHERE client_id=? AND case_slug=? AND source_file=?",
              (client_id, case_slug, source_file))
    for i, text in enumerate(pages_text):
        keywords = ", ".join(extract_keywords(text, top_n=10))
        c.execute(
            "INSERT INTO pages (client_id, case_slug, source_file, file_type, page_number, content, keywords) VALUES (?,?,?,?,?,?,?)",
            (client_id, case_slug, source_file, "pdf", i + 1, text, keywords)
        )
    conn.commit()
    conn.close()


def process_pdf(pdf_path: Path, project_dir: Path, client_id: str, case_slug: str, base: Path) -> dict:
    fitz = get_fitz()
    summaries_dir = project_dir / "summaries"
    index_dir = project_dir / "index"
    summaries_dir.mkdir(parents=True, exist_ok=True)
    index_dir.mkdir(parents=True, exist_ok=True)

    stem = pdf_path.stem
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    print(f"    페이지 수: {total_pages}")

    pages_text = []
    for page in doc:
        pages_text.append(page.get_text("text"))

    # 10페이지 단위 청크 요약
    chunk_size = 10
    num_chunks = (total_pages + chunk_size - 1) // chunk_size
    for c_idx in range(num_chunks):
        start = c_idx * chunk_size
        end = min(start + chunk_size, total_pages)
        chunk_text = "\n".join(pages_text[start:end])
        summary = summarize_text(chunk_text)
        chunk_file = summaries_dir / f"{stem}_chunk_{c_idx+1:03d}.txt"
        chunk_file.write_text(
            f"# {stem} — 청크 {c_idx+1}/{num_chunks} (p.{start+1}~{end})\n\n{summary}",
            encoding="utf-8"
        )
        print(f"      청크 {c_idx+1}/{num_chunks} 저장")

    # 전체 요약
    all_text = "\n".join(pages_text)
    overview = summarize_text(all_text, max_chars=1500)
    overview_file = summaries_dir / f"{stem}_overview.txt"
    overview_file.write_text(
        f"# {stem} — 전체 요약\n총 {total_pages}페이지\n\n{overview}",
        encoding="utf-8"
    )

    # 페이지별 키워드 인덱스
    index_file = index_dir / "page_index.json"
    page_index = {}
    if index_file.exists():
        page_index = json.loads(index_file.read_text(encoding="utf-8"))
    page_index[stem] = {
        str(i + 1): extract_keywords(text, top_n=10)
        for i, text in enumerate(pages_text)
    }
    index_file.write_text(json.dumps(page_index, ensure_ascii=False, indent=2), encoding="utf-8")

    # master.sqlite에 페이지 텍스트 저장
    save_pages_to_master(client_id, case_slug, pdf_path.name, pages_text, base)

    doc.close()
    return {"file": pdf_path.name, "pages": total_pages, "chunks": num_chunks}


def ingest_case(client_id: str, case_slug: str):
    base = Path(__file__).parent.parent
    raw_dir = base / "raw" / client_id / case_slug
    project_dir = base / "projects" / client_id / case_slug

    if not raw_dir.exists():
        print(f"[ERROR] raw/{client_id}/{case_slug}/ 디렉토리가 없습니다.")
        return []

    pdfs = list(raw_dir.glob("*.pdf")) + list(raw_dir.glob("*.PDF"))
    if not pdfs:
        print(f"[INFO] raw/{client_id}/{case_slug}/ 에 PDF 파일이 없습니다.")
        return []

    results = []
    for pdf_path in pdfs:
        print(f"  처리 중: {pdf_path.name}")
        result = process_pdf(pdf_path, project_dir, client_id, case_slug, base)
        results.append(result)

    print(f"\n[완료] PDF {len(results)}개 처리 완료")
    return results


# 하위 호환
def ingest_project(project_name: str):
    if "/" in project_name:
        parts = project_name.split("/")
        return ingest_case(parts[0], parts[1])
    return []


# ── 검색 유틸리티 ────────────────────────────────────────────────

def search_pages(client_id: str, case_slug: str, keyword: str) -> dict:
    """키워드 포함 페이지 번호 반환 (master.sqlite 기반)"""
    base = Path(__file__).parent.parent
    master_path = base / "db" / "master.sqlite"
    if not master_path.exists():
        return {}
    conn = sqlite3.connect(master_path)
    rows = conn.execute(
        "SELECT source_file, page_number FROM pages WHERE client_id=? AND case_slug=? AND (content LIKE ? OR keywords LIKE ?)",
        (client_id, case_slug, f"%{keyword}%", f"%{keyword}%")
    ).fetchall()
    conn.close()
    results = defaultdict(list)
    for source, page in rows:
        results[source].append(page)
    return dict(results)


def get_page_text(client_id: str, case_slug: str, source_file: str, page_num: int) -> str:
    """master.sqlite에서 특정 페이지 텍스트 반환"""
    base = Path(__file__).parent.parent
    master_path = base / "db" / "master.sqlite"
    if not master_path.exists():
        return "[ERROR] master.sqlite 없음"
    conn = sqlite3.connect(master_path)
    row = conn.execute(
        "SELECT content FROM pages WHERE client_id=? AND case_slug=? AND source_file=? AND page_number=?",
        (client_id, case_slug, source_file, page_num)
    ).fetchone()
    conn.close()
    return row[0] if row else f"[ERROR] 페이지 없음: {source_file} p.{page_num}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python scripts/pdf_to_chunks.py {client_id}/{case_slug}")
        sys.exit(1)
    arg = sys.argv[1]
    if "/" in arg:
        parts = arg.split("/")
        ingest_case(parts[0], parts[1])
    else:
        ingest_project(arg)
