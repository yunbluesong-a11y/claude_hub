"""
docx_to_summary.py (신규)
==========================
raw/{client_id}/{case_slug}/ 내 .docx 파일의 텍스트를 추출하여
요약본 생성 + master.sqlite pages 테이블에 저장.

사용법:
    python scripts/docx_to_summary.py {client_id}/{case_slug}

출력물:
- projects/{client}/{case}/summaries/{docx_stem}_summary.md
- master.sqlite pages 테이블

처리 방식:
- python-docx로 텍스트 추출 (pandoc 불필요)
- 문서 구조 파악 (제목, 본문)
- 요약본 자동 생성 (1페이지 이내)
- 페이지 단위(~3000자) 텍스트를 master.sqlite에 저장

의존성: python-docx
"""

import sys
import re
import sqlite3
from pathlib import Path
from collections import defaultdict


def get_docx():
    try:
        import docx
        return docx
    except ImportError:
        print("[ERROR] python-docx가 설치되지 않았습니다. 설치: pip install python-docx")
        sys.exit(1)


def extract_keywords(text: str, top_n: int = 15) -> list:
    stopwords = {
        "의", "을", "를", "이", "가", "은", "는", "에", "서", "로", "와", "과",
        "도", "에서", "으로", "그", "것", "수", "등", "및", "또한", "하여",
        "있다", "하는", "위", "대한", "같은", "된", "한", "할", "함",
    }
    words = re.findall(r"[가-힣a-zA-Z]{2,}", text.lower())
    freq = defaultdict(int)
    for w in words:
        if w not in stopwords:
            freq[w] += 1
    return [w for w, _ in sorted(freq.items(), key=lambda x: -x[1])[:top_n]]


def extract_text_from_docx(filepath: Path) -> tuple:
    """docx에서 텍스트 추출 → (전체텍스트, 구조화된_섹션들)"""
    docx_mod = get_docx()
    doc = docx_mod.Document(str(filepath))

    full_text = []
    sections = []
    current_section = {"title": "(본문)", "paragraphs": []}

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        full_text.append(text)

        # 제목 감지 (스타일 또는 볼드)
        is_heading = (
            para.style.name.startswith("Heading") or
            (para.runs and all(r.bold for r in para.runs if r.text.strip()))
        )
        if is_heading and len(text) < 100:
            if current_section["paragraphs"]:
                sections.append(current_section)
            current_section = {"title": text, "paragraphs": []}
        else:
            current_section["paragraphs"].append(text)

    if current_section["paragraphs"]:
        sections.append(current_section)

    return "\n".join(full_text), sections


def create_summary(filepath: Path, full_text: str, sections: list) -> str:
    """요약본 생성 (1페이지 이내)"""
    keywords = extract_keywords(full_text)
    total_chars = len(full_text)

    lines = [
        f"# {filepath.stem} — 문서 요약",
        f"",
        f"**원본**: {filepath.name}",
        f"**분량**: 약 {total_chars:,}자, {len(sections)}개 섹션",
        f"**주요 키워드**: {', '.join(keywords[:10])}",
        f"",
        f"## 문서 구조",
    ]

    for i, sec in enumerate(sections[:20]):
        preview = " ".join(sec["paragraphs"][:3])[:150]
        lines.append(f"- **{sec['title']}** ({len(sec['paragraphs'])}단락): {preview}...")

    # 첫 500자 미리보기
    lines.extend([
        f"",
        f"## 본문 미리보기 (첫 500자)",
        f"",
        full_text[:500],
    ])

    return "\n".join(lines)


def save_pages_to_master(client_id: str, case_slug: str, source_file: str,
                          full_text: str, base: Path):
    """master.sqlite pages 테이블에 ~3000자 단위로 저장"""
    master_path = base / "db" / "master.sqlite"
    if not master_path.exists():
        return

    conn = sqlite3.connect(master_path)
    c = conn.cursor()
    c.execute("DELETE FROM pages WHERE client_id=? AND case_slug=? AND source_file=?",
              (client_id, case_slug, source_file))

    # 3000자 단위로 분할 (가상 페이지)
    chunk_size = 3000
    page_num = 1
    for i in range(0, len(full_text), chunk_size):
        chunk = full_text[i:i + chunk_size]
        keywords = ", ".join(extract_keywords(chunk, top_n=10))
        c.execute(
            "INSERT INTO pages (client_id, case_slug, source_file, file_type, page_number, content, keywords) VALUES (?,?,?,?,?,?,?)",
            (client_id, case_slug, source_file, "docx", page_num, chunk, keywords)
        )
        page_num += 1

    conn.commit()
    conn.close()


def process_docx(filepath: Path, project_dir: Path, client_id: str, case_slug: str, base: Path) -> dict:
    """docx 1개 처리"""
    summaries_dir = project_dir / "summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)

    full_text, sections = extract_text_from_docx(filepath)
    print(f"    텍스트: {len(full_text):,}자, {len(sections)}개 섹션")

    # 요약본 저장
    summary_content = create_summary(filepath, full_text, sections)
    summary_file = summaries_dir / f"{filepath.stem}_summary.md"
    summary_file.write_text(summary_content, encoding="utf-8")
    print(f"    요약본 저장: {summary_file.name}")

    # master.sqlite에 페이지 텍스트 저장
    save_pages_to_master(client_id, case_slug, filepath.name, full_text, base)

    return {
        "file": filepath.name,
        "chars": len(full_text),
        "sections": len(sections),
        "summary": str(summary_file.name),
    }


def ingest_case(client_id: str, case_slug: str):
    base = Path(__file__).parent.parent
    raw_dir = base / "raw" / client_id / case_slug
    project_dir = base / "projects" / client_id / case_slug

    if not raw_dir.exists():
        print(f"[ERROR] raw/{client_id}/{case_slug}/ 디렉토리가 없습니다.")
        return []

    docx_files = list(raw_dir.glob("*.docx")) + list(raw_dir.glob("*.DOCX"))
    if not docx_files:
        print(f"[INFO] raw/{client_id}/{case_slug}/ 에 docx 파일이 없습니다.")
        return []

    results = []
    for filepath in docx_files:
        print(f"  처리 중: {filepath.name}")
        result = process_docx(filepath, project_dir, client_id, case_slug, base)
        results.append(result)

    print(f"\n[완료] docx {len(results)}개 처리 완료")
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python scripts/docx_to_summary.py {client_id}/{case_slug}")
        sys.exit(1)
    arg = sys.argv[1]
    if "/" in arg:
        parts = arg.split("/")
        ingest_case(parts[0], parts[1])
    else:
        print("사용법: python scripts/docx_to_summary.py {client_id}/{case_slug}")
