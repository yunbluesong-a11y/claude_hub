"""
evidence.py — 증거 CRUD + 파일 업로드 API
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import re

from webapp.services.db import get_db, rows_to_list, dict_from_row
from webapp.services.file_manager import save_uploaded_file, get_raw_files
from webapp.services.ingest import run_ingest, classify_file_type
from webapp.config import MAX_UPLOAD_SIZE

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


class EvidenceUpdate(BaseModel):
    label: Optional[str] = None
    description: Optional[str] = None
    submitted: Optional[int] = None
    notes: Optional[str] = None


def _next_label(conn, client_id: str, case_slug: str, side: str = "갑") -> str:
    """다음 호증 번호 자동 제안"""
    rows = conn.execute(
        "SELECT label FROM evidence WHERE client_id = ? AND case_slug = ? AND label LIKE ?",
        (client_id, case_slug, f"{side} 제%")
    ).fetchall()
    max_num = 0
    for row in rows:
        m = re.search(r"제(\d+)호증", row["label"])
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f"{side} 제{max_num + 1}호증"


@router.get("/{client_id}/{case_slug}")
def list_evidence(client_id: str, case_slug: str):
    """사건별 증거 목록"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM evidence WHERE client_id = ? AND case_slug = ? ORDER BY label",
            (client_id, case_slug)
        ).fetchall()
    return {"evidence": rows_to_list(rows)}


@router.get("/{client_id}/{case_slug}/next")
def next_evidence_number(client_id: str, case_slug: str, side: str = "갑"):
    """다음 호증 번호 자동 제안"""
    with get_db() as conn:
        label = _next_label(conn, client_id, case_slug, side)
    return {"next_label": label}


@router.post("/{client_id}/{case_slug}", status_code=201)
async def create_evidence(
    client_id: str,
    case_slug: str,
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    label: str = Form(...),
    description: str = Form(""),
    submitted: int = Form(0),
    notes: str = Form(""),
):
    """증거 등록 + 파일 업로드 → 자동 ingest"""
    # 사건 존재 확인
    with get_db() as conn:
        case = conn.execute(
            "SELECT id FROM cases WHERE client_id = ? AND case_slug = ?",
            (client_id, case_slug)
        ).fetchone()
        if not case:
            raise HTTPException(status_code=404,
                                detail=f"사건 '{client_id}/{case_slug}'를 찾을 수 없습니다.")

    file_path = None
    file_type = None

    if file and file.filename:
        # 파일 크기 확인
        contents = await file.read()
        if len(contents) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413,
                                detail=f"파일 크기가 {MAX_UPLOAD_SIZE // (1024*1024)}MB를 초과합니다.")
        saved_path = save_uploaded_file(contents, file.filename, client_id, case_slug)
        file_path = str(saved_path.relative_to(saved_path.parents[3]))  # raw/client/case/file
        file_type = classify_file_type(file.filename)

        # 비동기 ingest (BackgroundTasks)
        background_tasks.add_task(run_ingest, client_id, case_slug)

    # DB 등록
    with get_db() as conn:
        conn.execute(
            """INSERT INTO evidence (client_id, case_slug, label, description, file_type, file_path, submitted, notes)
               VALUES (?,?,?,?,?,?,?,?)""",
            (client_id, case_slug, label, description, file_type, file_path, submitted, notes)
        )
        eid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    return {
        "message": "증거 등록 완료",
        "evidence_id": eid,
        "file_path": file_path,
        "ingest": "백그라운드 처리 중" if file else "파일 없음",
    }


@router.put("/{evidence_id}")
def update_evidence(evidence_id: int, data: EvidenceUpdate):
    """증거 정보 수정"""
    with get_db() as conn:
        existing = conn.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"증거 ID {evidence_id}를 찾을 수 없습니다.")
        updates = {k: v for k, v in data.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="수정할 항목이 없습니다.")
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        conn.execute(
            f"UPDATE evidence SET {set_clause} WHERE id = ?",
            (*updates.values(), evidence_id)
        )
    return {"message": "증거 정보 수정 완료"}


@router.delete("/{evidence_id}")
def delete_evidence(evidence_id: int):
    """증거 삭제 (DB에서만, 파일은 유지)"""
    with get_db() as conn:
        existing = conn.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"증거 ID {evidence_id}를 찾을 수 없습니다.")
        conn.execute("DELETE FROM evidence WHERE id = ?", (evidence_id,))
    return {"message": "증거 삭제 완료 (파일은 유지됨)"}
