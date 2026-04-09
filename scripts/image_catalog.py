"""
image_catalog.py (v2)
======================
raw/{client_id}/{case_slug}/ 내 이미지 파일의 메타데이터 카탈로그 생성.
OCR 기능 추가 (tesseract 또는 easyocr 사용 가능 시).

사용법:
    python scripts/image_catalog.py {client_id}/{case_slug}

출력물:
- projects/{client}/{case}/index/image_catalog.json
- master.sqlite image_ocr 테이블 (OCR 가능 시)

의존성: Pillow, (선택) pytesseract 또는 easyocr
"""

import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp", ".heic", ".heif"}


def get_pil():
    try:
        from PIL import Image, ExifTags
        return Image, ExifTags
    except ImportError:
        print("[ERROR] Pillow가 설치되지 않았습니다. 설치: pip install Pillow")
        sys.exit(1)


def get_ocr_engine():
    """사용 가능한 OCR 엔진 반환. 없으면 None."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return "tesseract"
    except Exception:
        pass
    try:
        import easyocr
        return "easyocr"
    except ImportError:
        pass
    return None


def run_ocr(filepath: Path, engine: str) -> tuple:
    """OCR 실행 → (텍스트, 신뢰도)"""
    if engine == "tesseract":
        import pytesseract
        from PIL import Image
        img = Image.open(filepath)
        text = pytesseract.image_to_string(img, lang="kor+eng")
        return text.strip(), 0.8  # tesseract는 기본 신뢰도 0.8
    elif engine == "easyocr":
        import easyocr
        reader = easyocr.Reader(["ko", "en"], gpu=False)
        results = reader.readtext(str(filepath))
        text = " ".join(r[1] for r in results)
        avg_conf = sum(r[2] for r in results) / len(results) if results else 0
        return text.strip(), avg_conf
    return "", 0


def extract_exif(img) -> dict:
    try:
        Image, ExifTags = get_pil()
        exif_data = img._getexif()
        if not exif_data:
            return {}
        exif = {}
        for tag_id, value in exif_data.items():
            tag = ExifTags.TAGS.get(tag_id, str(tag_id))
            if isinstance(value, (str, int, float)):
                exif[tag] = value
            elif isinstance(value, bytes):
                exif[tag] = value.hex()[:64]
        return exif
    except Exception:
        return {}


def catalog_image(filepath: Path, raw_dir: Path) -> dict:
    Image, _ = get_pil()
    stat = filepath.stat()
    entry = {
        "filename": filepath.name,
        "relative_path": str(filepath.relative_to(raw_dir.parent.parent.parent)),
        "size_bytes": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "format": filepath.suffix.lower().lstrip("."),
        "width": None, "height": None, "mode": None, "exif": {},
    }
    try:
        with Image.open(filepath) as img:
            entry["width"] = img.width
            entry["height"] = img.height
            entry["mode"] = img.mode
            entry["exif"] = extract_exif(img)
    except Exception as e:
        entry["error"] = str(e)
    return entry


def save_ocr_to_master(client_id: str, case_slug: str, source_file: str,
                        ocr_text: str, confidence: float, base: Path):
    """master.sqlite image_ocr 테이블에 저장"""
    master_path = base / "db" / "master.sqlite"
    if not master_path.exists():
        return
    conn = sqlite3.connect(master_path)
    conn.execute("DELETE FROM image_ocr WHERE client_id=? AND case_slug=? AND source_file=?",
                 (client_id, case_slug, source_file))
    conn.execute(
        "INSERT INTO image_ocr (client_id, case_slug, source_file, ocr_text, confidence) VALUES (?,?,?,?,?)",
        (client_id, case_slug, source_file, ocr_text, confidence)
    )
    conn.commit()
    conn.close()


def ingest_case(client_id: str, case_slug: str):
    base = Path(__file__).parent.parent
    raw_dir = base / "raw" / client_id / case_slug
    index_dir = base / "projects" / client_id / case_slug / "index"

    if not raw_dir.exists():
        print(f"[ERROR] raw/{client_id}/{case_slug}/ 디렉토리가 없습니다.")
        return []

    images = [f for f in raw_dir.rglob("*") if f.suffix.lower() in IMAGE_EXTENSIONS]
    if not images:
        print(f"[INFO] raw/{client_id}/{case_slug}/ 에 이미지 파일이 없습니다.")
        return []

    index_dir.mkdir(parents=True, exist_ok=True)
    Image, ExifTags = get_pil()

    ocr_engine = get_ocr_engine()
    if ocr_engine:
        print(f"  OCR 엔진: {ocr_engine}")
    else:
        print(f"  OCR 엔진 없음 (메타데이터만 수집)")

    catalog = []
    for filepath in sorted(images):
        print(f"  처리 중: {filepath.name}")
        entry = catalog_image(filepath, raw_dir)
        dim = f"{entry['width']}x{entry['height']}" if entry["width"] else "알 수 없음"
        print(f"    → {dim}, {entry['size_bytes']:,} bytes")

        # OCR 실행
        if ocr_engine:
            ocr_text, confidence = run_ocr(filepath, ocr_engine)
            if ocr_text:
                entry["ocr_text"] = ocr_text[:200]  # 카탈로그에는 짧게
                entry["ocr_confidence"] = confidence
                save_ocr_to_master(client_id, case_slug, filepath.name, ocr_text, confidence, base)
                print(f"    OCR: {ocr_text[:60]}... (신뢰도: {confidence:.2f})")

        catalog.append(entry)

    catalog_file = index_dir / "image_catalog.json"
    catalog_file.write_text(
        json.dumps({
            "client_id": client_id, "case_slug": case_slug,
            "total": len(catalog), "images": catalog
        }, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"\n[완료] 이미지 카탈로그: {catalog_file} ({len(catalog)}개)")
    return catalog


# 하위 호환
def ingest_project(project_name: str):
    if "/" in project_name:
        parts = project_name.split("/")
        return ingest_case(parts[0], parts[1])
    return []


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python scripts/image_catalog.py {client_id}/{case_slug}")
        sys.exit(1)
    arg = sys.argv[1]
    if "/" in arg:
        parts = arg.split("/")
        ingest_case(parts[0], parts[1])
    else:
        ingest_project(arg)
