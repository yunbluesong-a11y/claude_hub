"""
pdf_to_chunks.py
================
raw/{project}/ 내 .pdf 파일을 청크 분할 + 요약 + 페이지 인덱스 생성.

사용법:
    python scripts/pdf_to_chunks.py {project-name}

출력물:
- projects/{project}/summaries/{pdf_stem}_chunk_{n}.txt  (10페이지 단위 요약)
- projects/{project}/summaries/{pdf_stem}_overview.txt   (전체 문서 요약 ~1페이지)
- projects/{project}/index/page_index.json               (페이지별 키워드 인덱스)

제공 함수:
- search_pages(project, keyword)     → 키워드 포함 페이지 번호 목록
- get_page_text(project, pdf_stem, page_num) → 특정 페이지 원본 텍스트

의존성: PyMuPDF (fitz)
"""

import sys
import json
import re
from pathlib import Path
from collections import defaultdict


def get_fitz():
    try:
        import fitz
        return fitz
    except ImportError:
        print("[ERROR] PyMuPDF가 설치되지 않았습니다. 설치: pip install PyMuPDF")
        sys.exit(1)


def extract_keywords(text: str, top_n: int = 15) -> list[str]:
    """간단한 키워드 추출: 불용어 제거 후 빈도 상위 단어"""
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
    """텍스트 요약 (단순 앞부분 + 키워드 나열)"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    preview = " ".join(lines[:30])[:max_chars]
    keywords = extract_keywords(text)
    return f"{preview}\n\n[주요 키워드] {', '.join(keywords)}"


def process_pdf(pdf_path: Path, project_dir: Path) -> dict:
    """PDF 1개 처리 → 청크 요약, 전체 요약, 페이지 인덱스"""
    fitz = get_fitz()
    summaries_dir = project_dir / "summaries"
    index_dir = project_dir / "index"
    summaries_dir.mkdir(parents=True, exist_ok=True)
    index_dir.mkdir(parents=True, exist_ok=True)

    stem = pdf_path.stem
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    print(f"    페이지 수: {total_pages}")

    # 페이지별 텍스트 추출
    pages_text = []
    for i, page in enumerate(doc):
        text = page.get_text("text")
        pages_text.append(text)

    # 10페이지 단위 청크 요약
    chunk_size = 10
    num_chunks = (total_pages + chunk_size - 1) // chunk_size
    chunk_summaries = []
    for c in range(num_chunks):
        start = c * chunk_size
        end = min(start + chunk_size, total_pages)
        chunk_text = "\n".join(pages_text[start:end])
        summary = summarize_text(chunk_text)
        chunk_file = summaries_dir / f"{stem}_chunk_{c+1:03d}.txt"
        chunk_file.write_text(
            f"# {stem} — 청크 {c+1}/{num_chunks} (p.{start+1}~{end})\n\n{summary}",
            encoding="utf-8"
        )
        chunk_summaries.append(summary)
        print(f"      청크 {c+1}/{num_chunks} 저장: {chunk_file.name}")

    # 전체 요약 (~1페이지)
    all_text = "\n".join(pages_text)
    overview = summarize_text(all_text, max_chars=1500)
    overview_file = summaries_dir / f"{stem}_overview.txt"
    overview_file.write_text(
        f"# {stem} — 전체 요약\n총 {total_pages}페이지\n\n{overview}",
        encoding="utf-8"
    )
    print(f"      전체 요약 저장: {overview_file.name}")

    # 페이지별 키워드 인덱스 갱신
    index_file = index_dir / "page_index.json"
    if index_file.exists():
        page_index = json.loads(index_file.read_text(encoding="utf-8"))
    else:
        page_index = {}

    page_index[stem] = {}
    for i, text in enumerate(pages_text):
        keywords = extract_keywords(text, top_n=10)
        page_index[stem][str(i + 1)] = keywords

    index_file.write_text(json.dumps(page_index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"      페이지 인덱스 저장: {index_file.name}")

    doc.close()
    return {
        "file": pdf_path.name,
        "pages": total_pages,
        "chunks": num_chunks,
        "overview": str(overview_file.relative_to(project_dir.parent.parent)),
    }


def ingest_project(project_name: str):
    base = Path(__file__).parent.parent
    raw_dir = base / "raw" / project_name
    project_dir = base / "projects" / project_name

    if not raw_dir.exists():
        print(f"[ERROR] raw/{project_name}/ 디렉토리가 없습니다.")
        sys.exit(1)

    pdfs = list(raw_dir.glob("*.pdf")) + list(raw_dir.glob("*.PDF"))
    if not pdfs:
        print(f"[INFO] raw/{project_name}/ 에 PDF 파일이 없습니다.")
        return []

    results = []
    for pdf_path in pdfs:
        print(f"  처리 중: {pdf_path.name}")
        result = process_pdf(pdf_path, project_dir)
        results.append(result)

    print(f"\n[완료] PDF {len(results)}개 처리 완료")
    return results


# ── 검색 유틸리티 함수 ────────────────────────────────────────────

def search_pages(project_name: str, keyword: str) -> dict[str, list[int]]:
    """
    키워드가 포함된 페이지 번호 반환.
    반환: {"pdf_stem": [page_num, ...], ...}
    """
    base = Path(__file__).parent.parent
    index_file = base / "projects" / project_name / "index" / "page_index.json"
    if not index_file.exists():
        print(f"[ERROR] 인덱스 없음: {index_file}")
        return {}

    page_index = json.loads(index_file.read_text(encoding="utf-8"))
    keyword_lower = keyword.lower()
    results = {}
    for stem, pages in page_index.items():
        matched = [int(p) for p, kws in pages.items() if any(keyword_lower in k.lower() for k in kws)]
        if matched:
            results[stem] = sorted(matched)
    return results


def get_page_text(project_name: str, pdf_stem: str, page_num: int) -> str:
    """특정 PDF의 특정 페이지 원본 텍스트 반환 (1-based)"""
    fitz = get_fitz()
    base = Path(__file__).parent.parent
    pdf_path = base / "raw" / project_name / f"{pdf_stem}.pdf"
    if not pdf_path.exists():
        return f"[ERROR] 파일 없음: {pdf_path}"
    doc = fitz.open(str(pdf_path))
    if page_num < 1 or page_num > len(doc):
        return f"[ERROR] 페이지 범위 초과: {page_num} / {len(doc)}"
    text = doc[page_num - 1].get_text("text")
    doc.close()
    return text


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python scripts/pdf_to_chunks.py {project-name}")
        sys.exit(1)
    ingest_project(sys.argv[1])
