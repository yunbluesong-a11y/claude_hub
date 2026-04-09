"""
cases.py — 사건 CRUD API
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from webapp.services.db import get_db, rows_to_list, dict_from_row
from webapp.services.file_manager import ensure_case_dirs

router = APIRouter(prefix="/api/cases", tags=["cases"])


class CaseCreate(BaseModel):
    client_id: str = Field(..., min_length=2)
    case_slug: str = Field(..., pattern=r"^[a-z][a-z0-9\-]*$", min_length=2, max_length=80,
                           description="영문 소문자+숫자+하이픈, 예: honor-defamation")
    title: str = Field(..., min_length=1, max_length=200)
    type: str = Field(default="civil", description="civil, criminal, trademark 등")
    case_number: Optional[str] = None
    court: Optional[str] = None
    opponent: Optional[str] = None
    status: str = Field(default="active")
    notes: Optional[str] = None


class CaseUpdate(BaseModel):
    title: Optional[str] = None
    type: Optional[str] = None
    case_number: Optional[str] = None
    court: Optional[str] = None
    opponent: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


@router.get("")
def list_cases(status: Optional[str] = None, client_id: Optional[str] = None):
    """전체 사건 목록 (필터 가능)"""
    query = """
        SELECT ca.*, c.name as client_name,
               (SELECT COUNT(*) FROM evidence e WHERE e.client_id = ca.client_id AND e.case_slug = ca.case_slug) as evidence_count,
               (SELECT COUNT(*) FROM documents d WHERE d.client_id = ca.client_id AND d.case_slug = ca.case_slug) as document_count
        FROM cases ca
        JOIN clients c ON ca.client_id = c.client_id
        WHERE 1=1
    """
    params = []
    if status:
        query += " AND ca.status = ?"
        params.append(status)
    if client_id:
        query += " AND ca.client_id = ?"
        params.append(client_id)
    query += " ORDER BY c.name, ca.created_at DESC"

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
    return {"cases": rows_to_list(rows)}


@router.get("/{client_id}/{case_slug}")
def get_case(client_id: str, case_slug: str):
    """사건 상세 (증거·문서 목록 포함)"""
    with get_db() as conn:
        case = conn.execute(
            """SELECT ca.*, c.name as client_name
               FROM cases ca JOIN clients c ON ca.client_id = c.client_id
               WHERE ca.client_id = ? AND ca.case_slug = ?""",
            (client_id, case_slug)
        ).fetchone()
        if not case:
            raise HTTPException(status_code=404,
                                detail=f"사건 '{client_id}/{case_slug}'를 찾을 수 없습니다.")
        evidence = conn.execute(
            "SELECT * FROM evidence WHERE client_id = ? AND case_slug = ? ORDER BY label",
            (client_id, case_slug)
        ).fetchall()
        documents = conn.execute(
            "SELECT * FROM documents WHERE client_id = ? AND case_slug = ? ORDER BY created_at DESC",
            (client_id, case_slug)
        ).fetchall()
    return {
        "case": dict_from_row(case),
        "evidence": rows_to_list(evidence),
        "documents": rows_to_list(documents),
    }


@router.post("", status_code=201)
def create_case(data: CaseCreate):
    """신규 사건 등록 → 디렉토리 자동 생성"""
    with get_db() as conn:
        # 의뢰인 존재 확인
        client = conn.execute(
            "SELECT client_id FROM clients WHERE client_id = ?", (data.client_id,)
        ).fetchone()
        if not client:
            raise HTTPException(status_code=404, detail=f"의뢰인 '{data.client_id}'가 존재하지 않습니다.")
        # 중복 확인
        existing = conn.execute(
            "SELECT id FROM cases WHERE client_id = ? AND case_slug = ?",
            (data.client_id, data.case_slug)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409,
                                detail=f"사건 '{data.client_id}/{data.case_slug}'가 이미 존재합니다.")
        conn.execute(
            """INSERT INTO cases (client_id, case_slug, title, type, case_number, court, opponent, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (data.client_id, data.case_slug, data.title, data.type,
             data.case_number, data.court, data.opponent, data.status, data.notes)
        )
    # 디렉토리 생성
    ensure_case_dirs(data.client_id, data.case_slug)
    return {"message": "사건 등록 완료", "client_id": data.client_id, "case_slug": data.case_slug}


@router.put("/{client_id}/{case_slug}")
def update_case(client_id: str, case_slug: str, data: CaseUpdate):
    """사건 정보 수정"""
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM cases WHERE client_id = ? AND case_slug = ?",
            (client_id, case_slug)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404,
                                detail=f"사건 '{client_id}/{case_slug}'를 찾을 수 없습니다.")
        updates = {k: v for k, v in data.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="수정할 항목이 없습니다.")
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        conn.execute(
            f"UPDATE cases SET {set_clause} WHERE client_id = ? AND case_slug = ?",
            (*updates.values(), client_id, case_slug)
        )
    return {"message": "사건 정보 수정 완료"}
