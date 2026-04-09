"""
system.py — ingest, sync, dashboard, health, search API
"""
import time
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from webapp.services.db import get_db, get_connection, rows_to_list
from webapp.config import DB_DIR, LEGACY_DB_DIR, RAW_DIR
from webapp.services.ingest import run_ingest
from webapp.services.git_sync import git_sync, git_status

router = APIRouter(prefix="/api", tags=["system"])

_start_time = time.time()


class SyncRequest(BaseModel):
    message: Optional[str] = None


@router.get("/health")
def health():
    """서버 상태 확인"""
    uptime_sec = int(time.time() - _start_time)
    hours, remainder = divmod(uptime_sec, 3600)
    minutes, _ = divmod(remainder, 60)

    db_ok = False
    try:
        with get_db() as conn:
            conn.execute("SELECT 1")
            db_ok = True
    except Exception:
        pass

    return {
        "status": "ok" if db_ok else "degraded",
        "db": "connected" if db_ok else "error",
        "uptime": f"{hours}h {minutes}m",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/dashboard")
def dashboard():
    """전체 현황 집계"""
    with get_db() as conn:
        # 의뢰인별 사건 집계
        clients = conn.execute("""
            SELECT c.client_id, c.name,
                   COUNT(ca.id) as case_count,
                   SUM(CASE WHEN ca.status = 'active' THEN 1 ELSE 0 END) as active_count
            FROM clients c
            LEFT JOIN cases ca ON c.client_id = ca.client_id
            GROUP BY c.client_id
            ORDER BY c.name
        """).fetchall()

        # 사건 목록 (의뢰인별 그룹)
        cases = conn.execute("""
            SELECT ca.*, c.name as client_name,
                   (SELECT COUNT(*) FROM evidence e WHERE e.client_id = ca.client_id AND e.case_slug = ca.case_slug) as evidence_count,
                   (SELECT COUNT(*) FROM evidence e WHERE e.client_id = ca.client_id AND e.case_slug = ca.case_slug AND e.submitted = 1) as submitted_count,
                   (SELECT COUNT(*) FROM documents d WHERE d.client_id = ca.client_id AND d.case_slug = ca.case_slug) as document_count
            FROM cases ca
            JOIN clients c ON ca.client_id = c.client_id
            ORDER BY c.name, ca.case_slug
        """).fetchall()

        total_cases = conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
        active_cases = conn.execute("SELECT COUNT(*) FROM cases WHERE status = 'active'").fetchone()[0]
        total_evidence = conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]

    return {
        "summary": {
            "total_clients": len(clients),
            "total_cases": total_cases,
            "active_cases": active_cases,
            "total_evidence": total_evidence,
        },
        "clients": rows_to_list(clients),
        "cases": rows_to_list(cases),
    }


@router.post("/ingest/{client_id}/{case_slug}")
def trigger_ingest(client_id: str, case_slug: str):
    """수동 ingest 실행"""
    result = run_ingest(client_id, case_slug)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.get("/sync/status")
def sync_status():
    """git 상태 확인"""
    return git_status()


@router.post("/sync")
def trigger_sync(data: SyncRequest = None):
    """git add + commit + push (커밋 메시지 필수)"""
    msg = data.message if data and data.message else None
    if not msg:
        raise HTTPException(status_code=400,
                            detail="커밋 메시지를 입력해주세요. 실수 방지를 위해 메시지 없이는 동기화할 수 없습니다.")
    result = git_sync(msg)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "동기화 실패"))
    return result


@router.get("/search")
def search_evidence(
    q: str = Query(..., min_length=1, description="검색 키워드"),
    client_id: Optional[str] = None,
    case_slug: Optional[str] = None,
):
    """증거·페이지·OCR 통합 검색"""
    results = {"evidence": [], "pages": [], "ocr": []}

    with get_db() as conn:
        # 증거 검색
        eq = "SELECT * FROM evidence WHERE (label LIKE ? OR description LIKE ? OR notes LIKE ?)"
        params = [f"%{q}%", f"%{q}%", f"%{q}%"]
        if client_id:
            eq += " AND client_id = ?"
            params.append(client_id)
        if case_slug:
            eq += " AND case_slug = ?"
            params.append(case_slug)
        eq += " LIMIT 50"
        results["evidence"] = rows_to_list(conn.execute(eq, params).fetchall())

        # 페이지 검색
        pq = "SELECT client_id, case_slug, source_file, page_number, keywords FROM pages WHERE (content LIKE ? OR keywords LIKE ?)"
        pparams = [f"%{q}%", f"%{q}%"]
        if client_id:
            pq += " AND client_id = ?"
            pparams.append(client_id)
        if case_slug:
            pq += " AND case_slug = ?"
            pparams.append(case_slug)
        pq += " LIMIT 50"
        results["pages"] = rows_to_list(conn.execute(pq, pparams).fetchall())

        # OCR 검색
        oq = "SELECT client_id, case_slug, source_file FROM image_ocr WHERE ocr_text LIKE ?"
        oparams = [f"%{q}%"]
        if client_id:
            oq += " AND client_id = ?"
            oparams.append(client_id)
        if case_slug:
            oq += " AND case_slug = ?"
            oparams.append(case_slug)
        oq += " LIMIT 50"
        results["ocr"] = rows_to_list(conn.execute(oq, oparams).fetchall())

    total = sum(len(v) for v in results.values())
    return {"query": q, "total": total, **results}


@router.get("/db-status-all")
def db_status_all():
    """전체 의뢰인·사건 DB 현황 트리 (네비게이션 미러링)"""
    import sqlite3
    from pathlib import Path

    with get_db() as conn:
        clients = conn.execute("SELECT client_id, name FROM clients ORDER BY name").fetchall()
        cases = conn.execute("SELECT client_id, case_slug, title, status FROM cases ORDER BY client_id, case_slug").fetchall()

    tree = []
    for cl in clients:
        cid = cl[0]
        cl_cases = [c for c in cases if c[0] == cid]
        case_list = []
        for ca in cl_cases:
            slug = ca[1]
            info = _get_case_db_info(cid, slug)
            case_list.append({
                "case_slug": slug, "title": ca[2], "status": ca[3],
                **info,
            })
        tree.append({
            "client_id": cid, "name": cl[1],
            "cases": case_list,
        })
    return {"tree": tree}


def _get_case_db_info(client_id: str, case_slug: str):
    """사건 하나의 DB 요약 정보"""
    import sqlite3

    tables = []
    # 사건별 sqlite
    case_db = DB_DIR / f"{client_id}_{case_slug}.sqlite"
    if case_db.exists() and case_db.stat().st_size > 0:
        try:
            conn = sqlite3.connect(str(case_db))
            for (tname,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
                rows = conn.execute(f"SELECT COUNT(*) FROM [{tname}]").fetchone()[0]
                cols = [d[1] for d in conn.execute(f"PRAGMA table_info([{tname}])").fetchall()]
                tables.append({"db": case_db.name, "table": tname, "rows": rows, "columns": len(cols), "col_names": cols[:8]})
            conn.close()
        except Exception:
            pass

    # legacy DB
    if LEGACY_DB_DIR.exists():
        for lf in LEGACY_DB_DIR.glob("*.sqlite"):
            if f"{client_id}-{case_slug}" in lf.stem:
                try:
                    conn = sqlite3.connect(str(lf))
                    for (tname,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
                        rows = conn.execute(f"SELECT COUNT(*) FROM [{tname}]").fetchone()[0]
                        cols = [d[1] for d in conn.execute(f"PRAGMA table_info([{tname}])").fetchall()]
                        tables.append({"db": lf.name, "table": tname, "rows": rows, "columns": len(cols), "col_names": cols[:8]})
                    conn.close()
                except Exception:
                    pass

    # master.sqlite 집계
    with get_db() as conn:
        pages = conn.execute("SELECT COUNT(*) FROM pages WHERE client_id=? AND case_slug=?", (client_id, case_slug)).fetchone()[0]
        ocr = conn.execute("SELECT COUNT(*) FROM image_ocr WHERE client_id=? AND case_slug=?", (client_id, case_slug)).fetchone()[0]
        evidence = conn.execute("SELECT COUNT(*) FROM evidence WHERE client_id=? AND case_slug=?", (client_id, case_slug)).fetchone()[0]

    # raw 파일
    raw_dir = RAW_DIR / client_id / case_slug
    raw_files = sum(1 for f in raw_dir.rglob("*") if f.is_file() and not f.name.startswith(".")) if raw_dir.exists() else 0

    return {
        "tables": tables, "raw_files": raw_files,
        "pages": pages, "ocr": ocr, "evidence": evidence,
        "db_files": evidence,
    }


@router.get("/db-status/{client_id}/{case_slug}")
def db_status(client_id: str, case_slug: str):
    """사건별 DB 현황: 테이블 목록, 행 수, pages, raw 파일 수"""
    import sqlite3
    from pathlib import Path

    result = {"tables": [], "master": {}, "raw_files": 0, "db_files": 0}

    # 1. 사건별 sqlite (신규 체계)
    case_db = DB_DIR / f"{client_id}_{case_slug}.sqlite"
    if case_db.exists() and case_db.stat().st_size > 0:
        try:
            conn = sqlite3.connect(str(case_db))
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
            for (tname,) in tables:
                row_count = conn.execute(f"SELECT COUNT(*) FROM [{tname}]").fetchone()[0]
                cols = [desc[1] for desc in conn.execute(f"PRAGMA table_info([{tname}])").fetchall()]
                result["tables"].append({"db": case_db.name, "table": tname, "rows": row_count, "columns": len(cols), "col_names": cols[:10]})
            conn.close()
        except Exception as e:
            result["tables"].append({"db": case_db.name, "error": str(e)})

    # 2. legacy DB (jokim-to-prison 등)
    if LEGACY_DB_DIR.exists():
        for legacy_file in LEGACY_DB_DIR.glob("*.sqlite"):
            # slug 매칭: jokim-to-prison.sqlite → client_id=jokim, case_slug=to-prison
            fname = legacy_file.stem
            if f"{client_id}-{case_slug}" in fname or fname == f"{client_id}-{case_slug}":
                try:
                    conn = sqlite3.connect(str(legacy_file))
                    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
                    for (tname,) in tables:
                        try:
                            row_count = conn.execute(f"SELECT COUNT(*) FROM [{tname}]").fetchone()[0]
                            cols = [desc[1] for desc in conn.execute(f"PRAGMA table_info([{tname}])").fetchall()]
                            result["tables"].append({"db": legacy_file.name, "table": tname, "rows": row_count, "columns": len(cols), "col_names": cols[:10]})
                        except Exception:
                            pass
                    conn.close()
                except Exception as e:
                    result["tables"].append({"db": legacy_file.name, "error": str(e)})

    # 3. master.sqlite에서 해당 사건 데이터
    with get_db() as conn:
        pages_count = conn.execute("SELECT COUNT(*) FROM pages WHERE client_id=? AND case_slug=?", (client_id, case_slug)).fetchone()[0]
        ocr_count = conn.execute("SELECT COUNT(*) FROM image_ocr WHERE client_id=? AND case_slug=?", (client_id, case_slug)).fetchone()[0]
        evidence_count = conn.execute("SELECT COUNT(*) FROM evidence WHERE client_id=? AND case_slug=?", (client_id, case_slug)).fetchone()[0]
        meta_rows = conn.execute("SELECT table_name, source_file, row_count FROM transactions_meta WHERE client_id=? AND case_slug=?", (client_id, case_slug)).fetchall()
        result["master"] = {
            "pages": pages_count,
            "ocr": ocr_count,
            "evidence": evidence_count,
            "transactions_meta": rows_to_list(meta_rows),
        }

    # 4. raw 파일 수
    raw_dir = RAW_DIR / client_id / case_slug
    if raw_dir.exists():
        result["raw_files"] = sum(1 for f in raw_dir.rglob("*") if f.is_file() and not f.name.startswith("."))
    result["db_files"] = evidence_count

    return result
