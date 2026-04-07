"""
ingest.py — 통합 전처리 진입점
================================
raw/{project-name}/ 안의 파일을 확장자별로 분류하여
적절한 전처리 스크립트를 호출하고 결과를 정리합니다.

사용법:
    python scripts/ingest.py {project-name}

동작:
1. raw/{project-name}/ 내 파일 확장자별 분류
2. 엑셀/CSV → excel_to_sqlite.py
3. PDF     → pdf_to_chunks.py
4. 이미지   → image_catalog.py
5. 처리 결과 리포트 출력
6. projects/{project-name}/README.md 자동 생성 (없을 경우)
7. 최상위 CLAUDE.md의 프로젝트 목록 및 DB 스키마 자동 업데이트
"""

import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

# 스크립트 디렉토리를 path에 추가
sys.path.insert(0, str(Path(__file__).parent))

EXCEL_EXTENSIONS = {".xlsx", ".xls", ".csv"}
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp", ".heic", ".heif"}


def classify_files(raw_dir: Path) -> dict:
    """파일을 확장자별로 분류"""
    categories = {"excel": [], "pdf": [], "image": [], "other": []}
    for f in raw_dir.iterdir():
        if f.name.startswith(".") or not f.is_file():
            continue
        ext = f.suffix.lower()
        if ext in EXCEL_EXTENSIONS:
            categories["excel"].append(f)
        elif ext in PDF_EXTENSIONS:
            categories["pdf"].append(f)
        elif ext in IMAGE_EXTENSIONS:
            categories["image"].append(f)
        else:
            categories["other"].append(f)
    return categories


def run_excel(project_name: str) -> list:
    from excel_to_sqlite import ingest_project
    return ingest_project(project_name)


def run_pdf(project_name: str) -> list:
    from pdf_to_chunks import ingest_project
    return ingest_project(project_name)


def run_image(project_name: str) -> list:
    from image_catalog import ingest_project
    return ingest_project(project_name)


def ensure_readme(project_name: str, categories: dict):
    """projects/{name}/README.md 가 없으면 기본 템플릿 생성"""
    base = Path(__file__).parent.parent
    readme_path = base / "projects" / project_name / "README.md"
    readme_path.parent.mkdir(parents=True, exist_ok=True)
    if readme_path.exists():
        return

    file_list = []
    for cat, files in categories.items():
        for f in files:
            file_list.append(f"- `{f.name}` ({cat})")

    content = f"""# {project_name}

## 프로젝트 목적
(여기에 이 분석 프로젝트의 목적을 작성하세요)

## 소스 파일
{chr(10).join(file_list) if file_list else "- (없음)"}

## 생성일
{datetime.now().strftime("%Y-%m-%d")}

## 데이터 접근 방법
- 엑셀/CSV: `db/{project_name}.sqlite` 에 SQL 쿼리
- PDF: `projects/{project_name}/summaries/` 요약본 먼저 확인
- 이미지: `projects/{project_name}/index/image_catalog.json` 참조
"""
    readme_path.write_text(content, encoding="utf-8")
    print(f"  README.md 생성: projects/{project_name}/README.md")


def get_db_schema(project_name: str) -> dict:
    """SQLite DB에서 테이블 스키마 추출"""
    base = Path(__file__).parent.parent
    db_path = base / "db" / f"{project_name}.sqlite"
    if not db_path.exists():
        return {}
    schema = {}
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        cols = [(row[1], row[2]) for row in cursor.fetchall()]
        cursor.execute(f"SELECT COUNT(*) FROM [{table}]")
        row_count = cursor.fetchone()[0]
        schema[table] = {"columns": cols, "row_count": row_count}
    conn.close()
    return schema


def update_claude_md(project_name: str, schema: dict):
    """최상위 CLAUDE.md 의 프로젝트 목록 및 DB 스키마 섹션 업데이트"""
    base = Path(__file__).parent.parent
    claude_md_path = base / "CLAUDE.md"
    if not claude_md_path.exists():
        return

    content = claude_md_path.read_text(encoding="utf-8")
    today = datetime.now().strftime("%Y-%m-%d")

    # 프로젝트 목록 업데이트
    project_entry = f"- `{project_name}` — 추가일: {today}"
    if f"`{project_name}`" not in content:
        content = content.replace(
            "(ingest 실행 후 여기에 자동 기록)",
            f"{project_entry}\n(ingest 실행 후 여기에 자동 기록)"
        )

    # DB 스키마 업데이트
    if schema:
        schema_lines = [f"\n### {project_name} (`db/{project_name}.sqlite`)"]
        for table, info in schema.items():
            cols_str = ", ".join(f"{c[0]}({c[1]})" for c in info["columns"][:8])
            if len(info["columns"]) > 8:
                cols_str += f" ... (+{len(info['columns'])-8}개)"
            schema_lines.append(f"- `{table}`: {info['row_count']}행 | {cols_str}")
        schema_block = "\n".join(schema_lines)
        if f"### {project_name}" not in content:
            content = content.replace(
                "(ingest 실행 후 여기에 자동 기록)\n```",
                f"(ingest 실행 후 여기에 자동 기록)\n{schema_block}\n```"
            )

    claude_md_path.write_text(content, encoding="utf-8")
    print(f"  CLAUDE.md 업데이트 완료")


def print_report(project_name: str, categories: dict, results: dict):
    """처리 결과 리포트 출력"""
    total = sum(len(v) for v in categories.values())
    print("\n" + "=" * 50)
    print(f"  ingest 완료: {project_name}")
    print("=" * 50)
    print(f"  총 파일 수: {total}")
    print(f"  ├─ 엑셀/CSV : {len(categories['excel'])}개")
    print(f"  ├─ PDF      : {len(categories['pdf'])}개")
    print(f"  ├─ 이미지   : {len(categories['image'])}개")
    print(f"  └─ 기타     : {len(categories['other'])}개")
    if categories["other"]:
        for f in categories["other"]:
            print(f"       - {f.name} (미처리)")
    print()
    if results.get("excel"):
        print(f"  DB 테이블: {len(results['excel'])}개 → db/{project_name}.sqlite")
    if results.get("pdf"):
        print(f"  PDF 요약 : {sum(r['chunks'] for r in results['pdf'])}개 청크 → projects/{project_name}/summaries/")
    if results.get("image"):
        print(f"  이미지   : {len(results['image'])}개 → projects/{project_name}/index/image_catalog.json")
    print()
    print(f"  다음 단계: projects/{project_name}/README.md 목적 작성 후 분석 시작")
    print("=" * 50)


def main():
    if len(sys.argv) < 2:
        print("사용법: python scripts/ingest.py {project-name}")
        sys.exit(1)

    project_name = sys.argv[1]
    base = Path(__file__).parent.parent
    raw_dir = base / "raw" / project_name

    if not raw_dir.exists():
        print(f"[ERROR] raw/{project_name}/ 디렉토리가 없습니다.")
        print(f"  먼저 raw/{project_name}/ 폴더를 만들고 파일을 넣어주세요.")
        sys.exit(1)

    categories = classify_files(raw_dir)
    total = sum(len(v) for v in categories.values())
    if total == 0:
        print(f"[WARNING] raw/{project_name}/ 에 처리할 파일이 없습니다.")
        sys.exit(0)

    print(f"\n[ingest] 프로젝트: {project_name}")
    print(f"  파일 {total}개 발견 (엑셀:{len(categories['excel'])} / PDF:{len(categories['pdf'])} / 이미지:{len(categories['image'])} / 기타:{len(categories['other'])})\n")

    results = {}

    if categories["excel"]:
        print("─── 엑셀/CSV 처리 ───")
        results["excel"] = run_excel(project_name)

    if categories["pdf"]:
        print("─── PDF 처리 ───")
        results["pdf"] = run_pdf(project_name)

    if categories["image"]:
        print("─── 이미지 처리 ───")
        results["image"] = run_image(project_name)

    # README 자동 생성
    ensure_readme(project_name, categories)

    # CLAUDE.md 업데이트
    schema = get_db_schema(project_name)
    update_claude_md(project_name, schema)

    print_report(project_name, categories, results)


if __name__ == "__main__":
    main()
