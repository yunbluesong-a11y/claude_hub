"""
image_catalog.py
================
raw/{project}/ 내 이미지 파일의 메타데이터 카탈로그 생성.

사용법:
    python scripts/image_catalog.py {project-name}

출력물:
- projects/{project}/index/image_catalog.json

포함 정보:
- 파일명, 상대경로, 크기(bytes), 해상도(WxH), 포맷, EXIF(날짜/GPS 등)

의존성: Pillow
"""

import sys
import json
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


def extract_exif(img) -> dict:
    """EXIF 데이터 추출 (없으면 빈 dict)"""
    try:
        Image, ExifTags = get_pil()
        exif_data = img._getexif()
        if not exif_data:
            return {}
        exif = {}
        for tag_id, value in exif_data.items():
            tag = ExifTags.TAGS.get(tag_id, str(tag_id))
            # 직렬화 가능한 타입만 저장
            if isinstance(value, (str, int, float)):
                exif[tag] = value
            elif isinstance(value, bytes):
                exif[tag] = value.hex()[:64]  # 너무 긴 바이너리 제한
        return exif
    except Exception:
        return {}


def catalog_image(filepath: Path, raw_dir: Path) -> dict:
    """이미지 1개 메타데이터 추출"""
    Image, _ = get_pil()
    stat = filepath.stat()
    entry = {
        "filename": filepath.name,
        "relative_path": str(filepath.relative_to(raw_dir.parent.parent)),
        "size_bytes": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "format": filepath.suffix.lower().lstrip("."),
        "width": None,
        "height": None,
        "mode": None,
        "exif": {},
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


def ingest_project(project_name: str):
    base = Path(__file__).parent.parent
    raw_dir = base / "raw" / project_name
    index_dir = base / "projects" / project_name / "index"

    if not raw_dir.exists():
        print(f"[ERROR] raw/{project_name}/ 디렉토리가 없습니다.")
        sys.exit(1)

    images = [f for f in raw_dir.rglob("*") if f.suffix.lower() in IMAGE_EXTENSIONS]
    if not images:
        print(f"[INFO] raw/{project_name}/ 에 이미지 파일이 없습니다.")
        return []

    index_dir.mkdir(parents=True, exist_ok=True)
    Image, ExifTags = get_pil()

    catalog = []
    for filepath in sorted(images):
        print(f"  처리 중: {filepath.name}")
        entry = catalog_image(filepath, raw_dir)
        dim = f"{entry['width']}x{entry['height']}" if entry["width"] else "알 수 없음"
        print(f"    → {dim}, {entry['size_bytes']:,} bytes")
        catalog.append(entry)

    catalog_file = index_dir / "image_catalog.json"
    catalog_file.write_text(
        json.dumps({"project": project_name, "total": len(catalog), "images": catalog},
                   ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"\n[완료] 이미지 카탈로그 저장: {catalog_file} ({len(catalog)}개)")
    return catalog


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python scripts/image_catalog.py {project-name}")
        sys.exit(1)
    ingest_project(sys.argv[1])
