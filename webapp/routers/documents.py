"""
documents.py — 문서(산출물) CRUD API
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional

from webapp.services.db import get_db, rows_to_list
from webapp.services.file_manager import save_uploaded_file
from webapp.config import PROJECTS_DIR

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("/{client_id}/{case_slug}")
def list_documents(client_id: str, case_slug: str):
    """사건별 문서 목록"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM documents WHERE client_id = ? AND case_slug = ? ORDER BY created_at DESC",
            (client_id, case_slug)
        ).fetchall()
    return {"documents": rows_to_list(rows)}


@router.post("/{client_id}/{case_slug}", status_code=201)
async def create_document(
    client_id: str,
    case_slug: str,
    file: Optional[UploadFile] = File(None),
    title: str = Form(...),
    doc_type: str = Form(""),
    notes: str = Form(""),
):
    """문서 등록 + 파일 업로드"""
    file_path = None
    if file and file.filename:
        contents = await file.read()
        # 산출물은 projects/{client}/{case}/outputs/ 에 저장
        output_dir = PROJECTS_DIR / client_id / case_slug / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / file.filename
        if target.exists():
            stem = target.stem
            suffix = target.suffix
            i = 1
            while target.exists():
                target = output_dir / f"{stem}_v{i}{suffix}"
                i += 1
        target.write_bytes(contents)
        file_path = str(target.relative_to(PROJECTS_DIR.parent))

    with get_db() as conn:
        conn.execute(
            """INSERT INTO documents (client_id, case_slug, title, doc_type, file_path, notes)
               VALUES (?,?,?,?,?,?)""",
            (client_id, case_slug, title, doc_type, file_path, notes)
        )
        did = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    return {"message": "문서 등록 완료", "document_id": did, "file_path": file_path}
