"""
register_evidence.py (신규)
============================
master.sqlite evidence 테이블에 증거를 수동 등록하는 유틸리티.

사용법:
    python scripts/register_evidence.py {client_id}/{case_slug} \\
        --label "갑 제1호증" \\
        --description "식품명인지정서" \\
        --file-type pdf \\
        --file-path "raw/yumyunggeun/counterclaim/식품명인지정서.pdf" \\
        --submitted \\
        --submit-date "2026-04-06"

    # 일괄 등록 (JSON 파일)
    python scripts/register_evidence.py {client_id}/{case_slug} --batch evidence_list.json

evidence_list.json 형식:
[
    {"label": "갑 제1호증", "description": "소장", "file_type": "pdf", "file_path": "...", "submitted": true, "submit_date": "2026-04-01"},
    ...
]
"""

import sys
import json
import sqlite3
import argparse
from pathlib import Path


def get_master_conn(base: Path):
    db_path = base / "db" / "master.sqlite"
    if not db_path.exists():
        print(f"[ERROR] master.sqlite가 없습니다: {db_path}")
        sys.exit(1)
    return sqlite3.connect(db_path)


def register_one(conn, client_id: str, case_slug: str, label: str,
                  description: str = None, file_type: str = None,
                  file_path: str = None, submitted: bool = False,
                  submit_date: str = None, notes: str = None):
    """증거 1건 등록"""
    # 중복 확인
    existing = conn.execute(
        "SELECT id FROM evidence WHERE client_id=? AND case_slug=? AND label=?",
        (client_id, case_slug, label)
    ).fetchone()

    if existing:
        conn.execute(
            """UPDATE evidence SET description=?, file_type=?, file_path=?,
               submitted=?, submit_date=?, notes=?
               WHERE client_id=? AND case_slug=? AND label=?""",
            (description, file_type, file_path, int(submitted), submit_date, notes,
             client_id, case_slug, label)
        )
        print(f"  [업데이트] {label}: {description}")
    else:
        conn.execute(
            """INSERT INTO evidence (client_id, case_slug, label, description,
               file_type, file_path, submitted, submit_date, notes)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (client_id, case_slug, label, description, file_type, file_path,
             int(submitted), submit_date, notes)
        )
        print(f"  [등록] {label}: {description}")


def list_evidence(conn, client_id: str, case_slug: str):
    """등록된 증거 목록 출력"""
    rows = conn.execute(
        "SELECT label, description, file_type, submitted, submit_date FROM evidence WHERE client_id=? AND case_slug=? ORDER BY label",
        (client_id, case_slug)
    ).fetchall()

    if not rows:
        print(f"  등록된 증거 없음: {client_id}/{case_slug}")
        return

    print(f"\n  === {client_id}/{case_slug} 증거 목록 ({len(rows)}건) ===")
    for label, desc, ft, submitted, sdate in rows:
        status = "✓ 제출" if submitted else "  미제출"
        print(f"  {status} {label:15s} | {desc or '(설명 없음)':30s} | {ft or '?':5s} | {sdate or ''}")


def main():
    parser = argparse.ArgumentParser(description="증거 등록 유틸리티")
    parser.add_argument("case_path", help="client_id/case_slug")
    parser.add_argument("--label", help="증거 라벨 (예: '갑 제1호증')")
    parser.add_argument("--description", help="증거 설명")
    parser.add_argument("--file-type", help="파일 유형 (pdf, xlsx, docx, image, video)")
    parser.add_argument("--file-path", help="파일 경로 (raw/ 기준)")
    parser.add_argument("--submitted", action="store_true", help="제출 여부")
    parser.add_argument("--submit-date", help="제출일 (YYYY-MM-DD)")
    parser.add_argument("--notes", help="비고")
    parser.add_argument("--batch", help="일괄 등록 JSON 파일 경로")
    parser.add_argument("--list", action="store_true", help="등록된 증거 목록 출력")
    args = parser.parse_args()

    parts = args.case_path.strip("/").split("/")
    if len(parts) != 2:
        print("[ERROR] 형식: client_id/case_slug")
        sys.exit(1)
    client_id, case_slug = parts

    base = Path(__file__).parent.parent
    conn = get_master_conn(base)

    if args.list:
        list_evidence(conn, client_id, case_slug)
        conn.close()
        return

    if args.batch:
        batch_path = Path(args.batch)
        if not batch_path.exists():
            print(f"[ERROR] 파일 없음: {batch_path}")
            sys.exit(1)
        items = json.loads(batch_path.read_text(encoding="utf-8"))
        for item in items:
            register_one(conn, client_id, case_slug, **item)
        conn.commit()
        print(f"\n[완료] {len(items)}건 일괄 등록")
    elif args.label:
        register_one(conn, client_id, case_slug,
                      label=args.label,
                      description=args.description,
                      file_type=args.file_type,
                      file_path=args.file_path,
                      submitted=args.submitted,
                      submit_date=args.submit_date,
                      notes=args.notes)
        conn.commit()
        print(f"\n[완료] 증거 등록: {args.label}")
    else:
        print("[ERROR] --label 또는 --batch 또는 --list 중 하나를 지정하세요.")
        sys.exit(1)

    list_evidence(conn, client_id, case_slug)
    conn.close()


if __name__ == "__main__":
    main()
