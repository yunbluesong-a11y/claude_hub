"""
clients.py — 의뢰인 CRUD API
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from webapp.services.db import get_db, rows_to_list, dict_from_row

router = APIRouter(prefix="/api/clients", tags=["clients"])


class ClientCreate(BaseModel):
    client_id: str = Field(..., pattern=r"^[a-z][a-z0-9\-]*$", min_length=2, max_length=50,
                           description="영문 소문자+숫자+하이픈, 예: parkchulsu")
    name: str = Field(..., min_length=1, max_length=100)
    contact: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    contact: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


@router.get("")
def list_clients():
    """전체 의뢰인 목록 (사건 수 포함)"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT c.*, COUNT(ca.id) as case_count
            FROM clients c
            LEFT JOIN cases ca ON c.client_id = ca.client_id
            GROUP BY c.client_id
            ORDER BY c.name
        """).fetchall()
    return {"clients": rows_to_list(rows)}


@router.get("/{client_id}")
def get_client(client_id: str):
    """의뢰인 상세 (사건 목록 포함)"""
    with get_db() as conn:
        client = conn.execute(
            "SELECT * FROM clients WHERE client_id = ?", (client_id,)
        ).fetchone()
        if not client:
            raise HTTPException(status_code=404, detail=f"의뢰인 '{client_id}'를 찾을 수 없습니다.")
        cases = conn.execute(
            "SELECT * FROM cases WHERE client_id = ? ORDER BY created_at DESC", (client_id,)
        ).fetchall()
    return {"client": dict_from_row(client), "cases": rows_to_list(cases)}


@router.post("", status_code=201)
def create_client(data: ClientCreate):
    """신규 의뢰인 등록"""
    with get_db() as conn:
        existing = conn.execute(
            "SELECT client_id FROM clients WHERE client_id = ?", (data.client_id,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail=f"의뢰인 ID '{data.client_id}'가 이미 존재합니다.")
        conn.execute(
            "INSERT INTO clients (client_id, name, contact, address, notes) VALUES (?,?,?,?,?)",
            (data.client_id, data.name, data.contact, data.address, data.notes)
        )
    return {"message": "의뢰인 등록 완료", "client_id": data.client_id}


@router.put("/{client_id}")
def update_client(client_id: str, data: ClientUpdate):
    """의뢰인 정보 수정"""
    with get_db() as conn:
        existing = conn.execute(
            "SELECT * FROM clients WHERE client_id = ?", (client_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"의뢰인 '{client_id}'를 찾을 수 없습니다.")
        updates = {k: v for k, v in data.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="수정할 항목이 없습니다.")
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        conn.execute(
            f"UPDATE clients SET {set_clause} WHERE client_id = ?",
            (*updates.values(), client_id)
        )
    return {"message": "의뢰인 정보 수정 완료"}
