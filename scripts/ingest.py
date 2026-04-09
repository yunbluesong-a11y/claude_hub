"""
ingest.py — 통합 전처리 진입점 (v2)
====================================
raw/{client_id}/{case_slug}/ 안의 파일을 확장자별로 분류하여
적절한 전처리 스크립트를 호출하고 결과를 정리합니다.

사용법:
    python scripts/ingest.py {client_id}/{case_slug}

예시:
    python scripts/ingest.py yumyunggeun/honor-defamation

동작:
1. raw/{client_id}/{case_slug}/ 내 파일 확장자별 분류
2. 엑셀/CSV → excel_to_sqlite.py → db/{client_id}_{case_slug}.sqlite + master.sqlite 메타
3. PDF     → pdf_to_chunks.py → summaries/ + master.sqlite pages
4. docx    → docx_to_summary.py → summaries/ + master.sqlite pages
5. 이미지   → image_catalog.py → index/ + master.sqlite image_ocr
6. 영상     → 영상메모 템플릿 생성
7. master.sqlite evidence 테이블에 파일 자동 등록
8. 처리 결과 리포트 출력
"""

import sys
import sqlite3
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

EXCEL_EXTENSIONS = {".xlsx", ".xls", ".csv"}
PDF_EXTENSIONS = {".pdf"}
DOCX_EXTENSIONS = {".docx", ".doc"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp", ".heic", ".heif"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv"}


def parse_path(path_arg: str) -> tuple:
    """'client_id/case_slug' 파싱"""
    parts = path_arg.strip("/").split("/")
    if len(parts) != 2:
        print(f"[ERROR] 형식: client_id/case_slug (입력: {path_arg})")
        sys.exit(1)
    return parts[0], parts[1]


def classify_files(raw_dir: Path) -> dict:
    """파일을 확장자별로 분류 (하위 폴더 포함)"""
    categories = {"excel": [], "pdf": [], "docx": [], "image": [], "video": [], "other": []}
    for f in raw_dir.rglob("*"):
        if f.name.startswith(".") or not f.is_file():
            continue
        ext = f.suffix.lower()
        if ext in EXCEL_EXTENSIONS:
            categories["excel"].append(f)
        elif ext in PDF_EXTENSIONS:
            categories["pdf"].append(f)
        elif ext in DOCX_EXTENSIONS:
            categories["docx"].append(f)
        elif ext in IMAGE_EXTENSIONS:
            categories["image"].append(f)
        elif ext in VIDEO_EXTENSIONS:
            categories["video"].append(f)
        else:
            categories["other"].append(f)
    return categories


def register_evidence_auto(client_id: str, case_slug: str, categories: dict, base: Path):
    """master.sqlite evidence 테이블에 파일 자동 등록"""
    db_path = base / "db" / "master.sqlite"
    if not db_path.exists():
        return
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    type_map = {
        "excel": "xlsx", "pdf": "pdf", "docx": "docx",
        "image": "image", "video": "video",
    }
    for cat, files in categories.items():
        if cat == "other":
            continue
        ft = type_map.get(cat, cat)
        for f in files:
            rel = str(f.relative_to(base))
            existing = c.execute(
                "SELECT id FROM evidence WHERE client_id=? AND case_slug=? AND file_path=?",
                (client_id, case_slug, rel)
            ).fetchone()
            if not existing:
                c.execute(
                    "INSERT INTO evidence (client_id, case_slug, label, description, file_type, file_path) VALUES (?,?,?,?,?,?)",
                    (client_id, case_slug, f"(미분류)", f.name, ft, rel)
                )
    conn.commit()
    conn.close()


def create_video_memo(video_path: Path, client_id: str, case_slug: str, project_dir: Path):
    """영상메모 템플릿 생성"""
    memo_dir = project_dir / "index"
    memo_dir.mkdir(parents=True, exist_ok=True)
    memo_path = memo_dir / f"{video_path.stem}_영상메모.md"
    if memo_path.exists():
        return

    stat = video_path.stat()
    size_mb = stat.st_size / (1024 * 1024)

    content = f"""# 영상메모: {video_path.name}
# 사건: {client_id}/{case_slug}
# 생성일: {datetime.now().strftime("%Y-%m-%d")}

## 영상 정보
- 파일: {video_path.name}
- 크기: {size_mb:.1f} MB
- URL: (온라인 영상인 경우 URL 기입)

## 타임스탬프별 내용
| 시간 | 내용 | 비고 |
|------|------|------|
| 0:00~ | | |
| | | |

## 핵심 구간
-

## 법적 관련성
-
"""
    memo_path.write_text(content, encoding="utf-8")
    print(f"    영상메모 템플릿 생성: {memo_path.name}")


def run_excel(client_id: str, case_slug: str) -> list:
    from excel_to_sqlite import ingest_case
    return ingest_case(client_id, case_slug)


def run_pdf(client_id: str, case_slug: str) -> list:
    from pdf_to_chunks import ingest_case
    return ingest_case(client_id, case_slug)


def run_docx(client_id: str, case_slug: str) -> list:
    try:
        from docx_to_summary import ingest_case
        return ingest_case(client_id, case_slug)
    except ImportError as e:
        print(f"  [SKIP] docx 처리 의존성 없음: {e}")
        return []


def run_image(client_id: str, case_slug: str) -> list:
    from image_catalog import ingest_case
    return ingest_case(client_id, case_slug)


def ensure_readme(client_id: str, case_slug: str, categories: dict, base: Path):
    """사건 README.md 가 없으면 기본 템플릿 생성"""
    readme_path = base / "projects" / client_id / case_slug / "README.md"
    readme_path.parent.mkdir(parents=True, exist_ok=True)
    if readme_path.exists():
        return

    file_list = []
    for cat in ("excel", "pdf", "docx", "image", "video", "other"):
        for f in categories.get(cat, []):
            file_list.append(f"- `{f.name}` ({cat})")

    content = f"""# {client_id}/{case_slug}

## 프로젝트 목적
(여기에 이 사건의 분석 목적을 작성하세요)

## 소스 파일
{chr(10).join(file_list) if file_list else "- (없음)"}

## 생성일
{datetime.now().strftime("%Y-%m-%d")}

## 데이터 접근 방법
- 엑셀/CSV: `db/{client_id}_{case_slug}.sqlite` 에 SQL 쿼리
- PDF/docx: `projects/{client_id}/{case_slug}/summaries/` 요약본 먼저 확인
- 이미지: `projects/{client_id}/{case_slug}/index/image_catalog.json` 참조
- 영상: `projects/{client_id}/{case_slug}/index/*_영상메모.md` 참조
"""
    readme_path.write_text(content, encoding="utf-8")
    print(f"  README.md 생성: projects/{client_id}/{case_slug}/README.md")


def print_report(client_id: str, case_slug: str, categories: dict, results: dict):
    """처리 결과 리포트"""
    print("\n" + "=" * 50)
    print(f"  ingest 완료: {client_id}/{case_slug}")
    print("=" * 50)
    for cat, label in [("excel","엑셀/CSV"), ("pdf","PDF"), ("docx","docx"),
                       ("image","이미지"), ("video","영상"), ("other","기타")]:
        cnt = len(categories.get(cat, []))
        print(f"  ├─ {label:8s} : {cnt}개")
    print()
    if results.get("excel"):
        print(f"  엑셀/CSV  → {len(results['excel'])}개 테이블 → db/{client_id}_{case_slug}.sqlite")
    if results.get("pdf"):
        print(f"  PDF 요약  → {sum(r.get('chunks',0) for r in results['pdf'])}개 청크")
    if results.get("docx"):
        print(f"  docx 요약 → {len(results['docx'])}개 문서")
    if results.get("image"):
        print(f"  이미지    → {len(results['image'])}개 카탈로그")
    print("=" * 50)


def main():
    if len(sys.argv) < 2:
        print("사용법: python scripts/ingest.py {client_id}/{case_slug}")
        print("예시:   python scripts/ingest.py yumyunggeun/honor-defamation")
        sys.exit(1)

    client_id, case_slug = parse_path(sys.argv[1])
    base = Path(__file__).parent.parent
    raw_dir = base / "raw" / client_id / case_slug

    if not raw_dir.exists():
        print(f"[ERROR] raw/{client_id}/{case_slug}/ 디렉토리가 없습니다.")
        print(f"  먼저 raw/{client_id}/{case_slug}/ 폴더를 만들고 파일을 넣어주세요.")
        sys.exit(1)

    categories = classify_files(raw_dir)
    project_dir = base / "projects" / client_id / case_slug
    file_total = sum(len(v) for v in categories.values())

    if file_total == 0:
        print(f"[WARNING] raw/{client_id}/{case_slug}/ 에 처리할 파일이 없습니다.")
        sys.exit(0)

    print(f"\n[ingest] {client_id}/{case_slug}")
    sources = []
    for cat, label in [("excel","엑셀/CSV"), ("pdf","PDF"), ("docx","docx"),
                       ("image","이미지"), ("video","영상")]:
        if categories[cat]:
            sources.append(f"{label} {len(categories[cat])}개")
    print(f"  소스: {' / '.join(sources)}\n")

    results = {}

    if categories["excel"]:
        print("─── 엑셀/CSV 처리 ───")
        results["excel"] = run_excel(client_id, case_slug)

    if categories["pdf"]:
        print("─── PDF 처리 ───")
        results["pdf"] = run_pdf(client_id, case_slug)

    if categories["docx"]:
        print("─── docx 처리 ───")
        results["docx"] = run_docx(client_id, case_slug)

    if categories["image"]:
        print("─── 이미지 처리 ───")
        results["image"] = run_image(client_id, case_slug)

    if categories["video"]:
        print("─── 영상 메모 템플릿 ───")
        for v in categories["video"]:
            create_video_memo(v, client_id, case_slug, project_dir)

    # master.sqlite에 증거 자동 등록
    register_evidence_auto(client_id, case_slug, categories, base)

    ensure_readme(client_id, case_slug, categories, base)

    print_report(client_id, case_slug, categories, results)


if __name__ == "__main__":
    main()
