"""
sheets_to_sqlite.py
===================
구글시트 URL → db/{project}.sqlite 자동 저장.

사용법:
    python scripts/sheets_to_sqlite.py {project-name}

동작:
- raw/{project}/sheets.txt 에 구글시트 URL 목록을 한 줄씩 기재
- 각 URL의 모든 시트를 CSV로 가져와 SQLite 테이블로 저장
- 공개 시트: 인증 불필요 (공유 링크 "링크가 있는 모든 사용자" 설정)
- 비공개 시트: GOOGLE_CREDENTIALS_PATH 환경변수로 서비스 계정 키 경로 지정

sheets.txt 예시:
    https://docs.google.com/spreadsheets/d/1abc.../edit
    https://docs.google.com/spreadsheets/d/1xyz.../edit#gid=0
    # 주석은 #으로 시작

의존성: requests, pandas
비공개 시트 추가 의존성: gspread, google-auth
"""

import sys
import os
import re
import io
import sqlite3
from pathlib import Path

import requests
import pandas as pd


# ── URL 파싱 ─────────────────────────────────────────────────────

def extract_sheet_id(url: str) -> str | None:
    """구글시트 URL에서 spreadsheet ID 추출"""
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    return match.group(1) if match else None


def extract_gid(url: str) -> str | None:
    """URL에서 특정 시트 gid 추출 (없으면 None → 전체 시트)"""
    match = re.search(r"[#&]gid=(\d+)", url)
    return match.group(1) if match else None


def get_sheet_title_from_url(url: str) -> str:
    """URL에서 사람이 읽을 수 있는 시트 식별자 생성"""
    sheet_id = extract_sheet_id(url)
    return sheet_id[:12] if sheet_id else "unknown"


# ── 공개 시트 가져오기 ────────────────────────────────────────────

def fetch_sheet_metadata(sheet_id: str) -> list[dict]:
    """
    Google Sheets API v4 (키 없이 공개 메타데이터 접근)
    실패 시 gid=0 단일 시트로 폴백
    """
    api_url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}?fields=sheets.properties"
    try:
        resp = requests.get(api_url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return [
                {
                    "title": s["properties"]["title"],
                    "gid": str(s["properties"]["sheetId"]),
                }
                for s in data.get("sheets", [])
            ]
    except Exception:
        pass
    # 폴백: gid=0만
    return [{"title": "Sheet1", "gid": "0"}]


def fetch_csv_public(sheet_id: str, gid: str) -> pd.DataFrame | None:
    """공개 구글시트 → CSV → DataFrame"""
    export_url = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        f"/export?format=csv&gid={gid}"
    )
    try:
        resp = requests.get(export_url, timeout=30)
        if resp.status_code == 200:
            return pd.read_csv(io.StringIO(resp.text))
        else:
            print(f"    [경고] HTTP {resp.status_code} — 비공개 시트이거나 접근 권한 없음")
            return None
    except Exception as e:
        print(f"    [오류] CSV 가져오기 실패: {e}")
        return None


# ── 비공개 시트 (서비스 계정) ─────────────────────────────────────

def fetch_csv_private(sheet_id: str, sheet_title: str) -> pd.DataFrame | None:
    """
    서비스 계정으로 비공개 구글시트 접근.
    환경변수 GOOGLE_CREDENTIALS_PATH 에 서비스 계정 JSON 경로 지정 필요.
    """
    cred_path = os.environ.get("GOOGLE_CREDENTIALS_PATH")
    if not cred_path:
        print("    [오류] GOOGLE_CREDENTIALS_PATH 환경변수가 설정되지 않았습니다.")
        print("    비공개 시트 접근을 위해 서비스 계정 키 경로를 설정해주세요.")
        return None
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        creds = Credentials.from_service_account_file(cred_path, scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(sheet_id)
        ws = sh.worksheet(sheet_title)
        records = ws.get_all_records()
        return pd.DataFrame(records)
    except ImportError:
        print("    [오류] gspread 미설치: pip install gspread google-auth")
        return None
    except Exception as e:
        print(f"    [오류] 비공개 시트 접근 실패: {e}")
        return None


# ── 정규화 (excel_to_sqlite.py 와 동일 로직) ─────────────────────

def is_date_column(series: pd.Series) -> bool:
    import re as _re
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    sample = series.dropna().astype(str).head(20)
    pat = _re.compile(r"\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2}|\d{1,2}[-/\.]\d{1,2}[-/\.]\d{4}")
    hits = sample.apply(lambda v: bool(pat.search(v))).sum()
    return hits >= len(sample) * 0.7


def is_amount_column(col_name: str, series: pd.Series) -> bool:
    import re as _re
    keywords = ["금액", "가격", "비용", "수수료", "매출", "amount", "price", "cost", "fee", "revenue"]
    if any(k in col_name.lower() for k in keywords):
        return True
    sample = series.dropna().astype(str).head(20)
    pat = _re.compile(r"^[\-]?[\₩\$\¥€]?\s?\d[\d,\.]+$")
    return sample.apply(lambda v: bool(pat.match(v.strip()))).sum() >= len(sample) * 0.7


def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        if is_date_column(df[col]):
            parsed = pd.to_datetime(df[col], errors="coerce")
            df[col] = parsed.dt.strftime("%Y-%m-%d").where(parsed.notna(), other=None)
        elif is_amount_column(col, df[col]):
            cleaned = df[col].astype(str).str.replace(r"[₩\$¥€,\s]", "", regex=True)
            df[col] = pd.to_numeric(cleaned, errors="coerce")
    return df


def make_table_name(sheet_id: str, sheet_title: str) -> str:
    import re as _re
    raw = f"{sheet_id[:8]}_{sheet_title}"
    name = _re.sub(r"[^\w가-힣]", "_", raw)
    name = _re.sub(r"_+", "_", name).strip("_")
    return ("t_" + name) if name[0].isdigit() else name


# ── 메인 ─────────────────────────────────────────────────────────

def load_urls(project_name: str) -> list[str]:
    base = Path(__file__).parent.parent
    sheets_file = base / "raw" / project_name / "sheets.txt"
    if not sheets_file.exists():
        print(f"[오류] raw/{project_name}/sheets.txt 파일이 없습니다.")
        print("  파일을 만들고 구글시트 URL을 한 줄씩 입력해주세요.")
        sys.exit(1)
    urls = []
    for line in sheets_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def ingest_project(project_name: str) -> list:
    base = Path(__file__).parent.parent
    db_dir = base / "db"
    db_dir.mkdir(exist_ok=True)
    db_path = db_dir / f"{project_name}.sqlite"

    urls = load_urls(project_name)
    if not urls:
        print(f"[정보] sheets.txt에 URL이 없습니다.")
        return []

    conn = sqlite3.connect(db_path)
    summary = []

    for url in urls:
        sheet_id = extract_sheet_id(url)
        if not sheet_id:
            print(f"  [경고] 유효하지 않은 URL, 건너뜀: {url}")
            continue

        specific_gid = extract_gid(url)
        print(f"\n  처리 중: {url[:60]}...")

        # 시트 목록 결정
        if specific_gid:
            sheets = [{"title": f"gid_{specific_gid}", "gid": specific_gid}]
        else:
            sheets = fetch_sheet_metadata(sheet_id)
            print(f"    시트 {len(sheets)}개 발견: {[s['title'] for s in sheets]}")

        for sheet in sheets:
            title = sheet["title"]
            gid = sheet["gid"]
            print(f"    시트: {title} (gid={gid})")

            df = fetch_csv_public(sheet_id, gid)
            if df is None:
                print(f"    → 공개 접근 실패, 서비스 계정으로 재시도...")
                df = fetch_csv_private(sheet_id, title)
            if df is None or df.empty:
                print(f"    → 데이터 없음, 건너뜀")
                continue

            df = normalize_df(df)
            table_name = make_table_name(sheet_id, title)
            df.to_sql(table_name, conn, if_exists="replace", index=False)

            print(f"    → 테이블: {table_name}, {len(df)}행, {len(df.columns)}컬럼")
            summary.append({
                "url": url,
                "sheet": title,
                "table": table_name,
                "rows": len(df),
                "columns": list(df.columns),
            })

    conn.close()
    print(f"\n[완료] 구글시트 → db/{project_name}.sqlite ({len(summary)}개 시트)")
    return summary


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python scripts/sheets_to_sqlite.py {project-name}")
        sys.exit(1)
    ingest_project(sys.argv[1])
