"""
excel_to_sqlite.py
==================
raw/{project}/ 내 .xlsx, .xls, .csv 파일을 db/{project}.sqlite 에 저장.

사용법:
    python scripts/excel_to_sqlite.py {project-name}

특징:
- 은행 거래내역 등 상단 메타 정보가 있는 양식 자동 감지 (헤더 행 자동 탐색)
- 날짜/시간 컬럼 ISO 8601 정규화
- 금액 컬럼 숫자 타입 변환
- ASCII 안전 테이블명 (계좌번호 또는 파일 순번 기반)
- 멱등성 보장 (재실행 시 덮어쓰기)

의존성: pandas, openpyxl
"""

import sys
import re
import sqlite3
from pathlib import Path

import pandas as pd


# ── 헤더 행 자동 탐색 ─────────────────────────────────────────────

HEADER_KEYWORDS = [
    "No.", "번호", "날짜", "일자", "거래일", "거래일자",
    "date", "Date", "DATE", "항목", "내용", "적요",
]

def find_header_row(filepath: Path, sheet_name) -> int:
    """
    상단 메타 정보를 건너뛰고 실제 컬럼 헤더가 있는 행 번호 반환.
    못 찾으면 0 반환 (첫 행이 헤더).
    """
    df_raw = pd.read_excel(filepath, sheet_name=sheet_name, header=None,
                           nrows=30, engine="openpyxl")
    for i, row in df_raw.iterrows():
        row_vals = row.dropna().astype(str).tolist()
        if any(kw in val for kw in HEADER_KEYWORDS for val in row_vals):
            return i
    return 0


# ── 테이블명 생성 ─────────────────────────────────────────────────

def make_table_name(filepath: Path, sheet_name: str, idx: int) -> str:
    """
    파일명에서 계좌번호(숫자열) 추출 → 테이블명으로 사용.
    없으면 file_{idx} 형식 사용.
    """
    # 파일명에서 첫 번째 긴 숫자열 추출 (계좌번호)
    numbers = re.findall(r"\d{8,}", filepath.stem)
    if numbers:
        base = f"acct_{numbers[0]}"
    else:
        base = f"file_{idx:03d}"

    # 시트가 여러 개일 경우 시트명 추가 (ASCII 부분만)
    sheet_ascii = re.sub(r"[^\w]", "_", sheet_name)
    sheet_ascii = re.sub(r"_+", "_", sheet_ascii).strip("_")
    if sheet_ascii and sheet_ascii.lower() not in ("sheet1", "sheet", "시트1"):
        base = f"{base}_{sheet_ascii}"

    return base


# ── 컬럼명 정리 ──────────────────────────────────────────────────

def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    """빈 컬럼명 제거, 중복 방지, NaN 행 제거"""
    new_cols = []
    seen = {}
    for i, col in enumerate(df.columns):
        col_str = str(col).strip()
        if col_str in ("", "nan", "None"):
            col_str = f"col_{i}"
        # 중복 컬럼명 처리
        if col_str in seen:
            seen[col_str] += 1
            col_str = f"{col_str}_{seen[col_str]}"
        else:
            seen[col_str] = 0
        new_cols.append(col_str)
    df.columns = new_cols
    # 모든 값이 NaN인 행 제거
    df = df.dropna(how="all")
    return df


# ── 날짜 / 금액 정규화 ────────────────────────────────────────────

def is_date_column(series: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    sample = series.dropna().astype(str).head(20)
    if len(sample) == 0:
        return False
    date_pat = re.compile(
        r"\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2}|\d{1,2}[-/\.]\d{1,2}[-/\.]\d{4}"
    )
    hits = sample.apply(lambda v: bool(date_pat.search(v))).sum()
    return hits >= len(sample) * 0.7


def is_amount_column(col_name: str, series: pd.Series) -> bool:
    amount_keywords = [
        "금액", "가격", "비용", "수수료", "매출", "잔액", "출금", "입금",
        "amount", "price", "cost", "fee", "revenue", "balance",
    ]
    if any(kw in col_name for kw in amount_keywords):
        return True
    sample = series.dropna().astype(str).head(20)
    if len(sample) == 0:
        return False
    amount_pat = re.compile(r"^-?[\₩\$\¥€]?\s?\d[\d,\.]+$")
    hits = sample.apply(lambda v: bool(amount_pat.match(v.strip()))).sum()
    return hits >= len(sample) * 0.7


def normalize_date(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce")
    return parsed.dt.strftime("%Y-%m-%d").where(parsed.notna(), other=None)


def normalize_amount(series: pd.Series) -> pd.Series:
    cleaned = series.astype(str).str.replace(r"[₩\$¥€,\s]", "", regex=True)
    return pd.to_numeric(cleaned, errors="coerce")


def process_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        try:
            if is_date_column(df[col]):
                df[col] = normalize_date(df[col])
            elif is_amount_column(col, df[col]):
                df[col] = normalize_amount(df[col])
        except Exception:
            pass  # 정규화 실패 시 원본 유지
    return df


# ── 메인 ─────────────────────────────────────────────────────────

def load_file(filepath: Path) -> dict[str, pd.DataFrame]:
    """파일 → {시트명: DataFrame} dict"""
    ext = filepath.suffix.lower()

    if ext == ".csv":
        try:
            df = pd.read_csv(filepath, encoding="utf-8-sig", encoding_errors="replace")
        except Exception:
            df = pd.read_csv(filepath, encoding="cp949", encoding_errors="replace")
        return {filepath.stem: df}

    elif ext in (".xlsx", ".xls"):
        engine = "openpyxl" if ext == ".xlsx" else None
        xf = pd.ExcelFile(filepath, engine=engine)
        result = {}
        for sheet in xf.sheet_names:
            header_row = find_header_row(filepath, sheet)
            df = pd.read_excel(filepath, sheet_name=sheet,
                               header=header_row, engine=engine)
            result[sheet] = df
        return result

    return {}


def ingest_project(project_name: str):
    base = Path(__file__).parent.parent
    raw_dir = base / "raw" / project_name
    db_dir = base / "db"
    db_dir.mkdir(exist_ok=True)
    db_path = db_dir / f"{project_name}.sqlite"

    if not raw_dir.exists():
        print(f"[ERROR] raw/{project_name}/ 디렉토리가 없습니다.")
        sys.exit(1)

    files = (list(raw_dir.glob("*.xlsx")) +
             list(raw_dir.glob("*.xls")) +
             list(raw_dir.glob("*.csv")))
    if not files:
        print(f"[INFO] raw/{project_name}/ 에 엑셀/CSV 파일이 없습니다.")
        return []

    conn = sqlite3.connect(db_path)
    summary = []

    for idx, filepath in enumerate(files):
        print(f"  처리 중: {filepath.name}")
        sheets = load_file(filepath)

        for sheet_name, df in sheets.items():
            df = clean_columns(df)
            df = process_dataframe(df)

            table_name = make_table_name(filepath, sheet_name, idx)

            try:
                df.to_sql(table_name, conn, if_exists="replace", index=False)
            except Exception as e:
                print(f"    [경고] 저장 실패 ({table_name}): {e}")
                continue

            # 기간 파악
            date_cols = [c for c in df.columns if is_date_column(df[c])]
            period = ""
            if date_cols:
                dates = pd.to_datetime(df[date_cols[0]], errors="coerce").dropna()
                if not dates.empty:
                    period = f"{dates.min().date()} ~ {dates.max().date()}"

            summary.append({
                "file": filepath.name,
                "table": table_name,
                "rows": len(df),
                "columns": list(df.columns),
                "period": period,
            })
            print(f"    → 테이블: {table_name}, {len(df)}행, {len(df.columns)}컬럼"
                  + (f", 기간: {period}" if period else ""))

    conn.close()
    print(f"\n[완료] DB 저장: db/{project_name}.sqlite ({len(summary)}개 테이블)")
    return summary


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python scripts/excel_to_sqlite.py {project-name}")
        sys.exit(1)
    ingest_project(sys.argv[1])
