"""
excel_to_sqlite.py
==================
raw/{project}/ 내 .xlsx, .xls, .csv 파일을 db/{project}.sqlite 에 저장.

사용법:
    python scripts/excel_to_sqlite.py {project-name}

동작:
- 각 파일 → 별도 테이블 (파일명 기반)
- 날짜 컬럼 → ISO 8601 정규화
- 금액 컬럼 → 콤마/기호 제거 후 숫자 타입
- 멱등성 보장: 같은 파일 재실행 시 테이블 덮어쓰기

의존성: pandas, openpyxl
"""

import sys
import re
import sqlite3
from pathlib import Path

import pandas as pd


def normalize_table_name(filename: str) -> str:
    """파일명 → SQLite 테이블명 (영숫자+언더스코어만)"""
    stem = Path(filename).stem
    name = re.sub(r"[^\w가-힣]", "_", stem)
    name = re.sub(r"_+", "_", name).strip("_")
    if name[0].isdigit():
        name = "t_" + name
    return name


def is_date_column(series: pd.Series) -> bool:
    """컬럼이 날짜 형식인지 추론"""
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    sample = series.dropna().astype(str).head(20)
    date_pattern = re.compile(
        r"\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2}|\d{1,2}[-/\.]\d{1,2}[-/\.]\d{4}"
    )
    hits = sample.apply(lambda v: bool(date_pattern.search(v))).sum()
    return hits >= len(sample) * 0.7


def is_amount_column(col_name: str, series: pd.Series) -> bool:
    """컬럼이 금액인지 추론 (컬럼명 + 값 패턴)"""
    amount_keywords = ["금액", "가격", "비용", "수수료", "매출", "amount", "price", "cost", "fee", "revenue", "pay"]
    if any(kw in col_name.lower() for kw in amount_keywords):
        return True
    sample = series.dropna().astype(str).head(20)
    amount_pattern = re.compile(r"^[\-]?[\₩\$\¥€]?\s?\d[\d,\.]+$")
    hits = sample.apply(lambda v: bool(amount_pattern.match(v.strip()))).sum()
    return hits >= len(sample) * 0.7


def normalize_amount(series: pd.Series) -> pd.Series:
    """금액 문자열 → 숫자 (콤마, 통화기호 제거)"""
    cleaned = series.astype(str).str.replace(r"[₩\$¥€,\s]", "", regex=True)
    return pd.to_numeric(cleaned, errors="coerce")


def normalize_date(series: pd.Series) -> pd.Series:
    """날짜 → ISO 8601 문자열"""
    parsed = pd.to_datetime(series, errors="coerce", infer_datetime_format=True)
    return parsed.dt.strftime("%Y-%m-%d").where(parsed.notna(), other=None)


def load_file(filepath: Path) -> dict[str, pd.DataFrame]:
    """파일 확장자에 따라 DataFrame dict 반환 (시트별)"""
    ext = filepath.suffix.lower()
    if ext == ".csv":
        df = pd.read_csv(filepath, encoding_errors="replace")
        return {filepath.stem: df}
    elif ext in (".xlsx", ".xls"):
        xf = pd.ExcelFile(filepath, engine="openpyxl" if ext == ".xlsx" else None)
        result = {}
        for sheet in xf.sheet_names:
            df = pd.read_excel(xf, sheet_name=sheet)
            key = f"{filepath.stem}__{sheet}" if len(xf.sheet_names) > 1 else filepath.stem
            result[key] = df
        return result
    else:
        return {}


def process_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """날짜/금액 정규화 적용"""
    df = df.copy()
    for col in df.columns:
        if is_date_column(df[col]):
            df[col] = normalize_date(df[col])
        elif is_amount_column(col, df[col]):
            df[col] = normalize_amount(df[col])
    return df


def ingest_project(project_name: str):
    base = Path(__file__).parent.parent
    raw_dir = base / "raw" / project_name
    db_dir = base / "db"
    db_dir.mkdir(exist_ok=True)
    db_path = db_dir / f"{project_name}.sqlite"

    if not raw_dir.exists():
        print(f"[ERROR] raw/{project_name}/ 디렉토리가 없습니다.")
        sys.exit(1)

    files = list(raw_dir.glob("*.xlsx")) + list(raw_dir.glob("*.xls")) + list(raw_dir.glob("*.csv"))
    if not files:
        print(f"[INFO] raw/{project_name}/ 에 엑셀/CSV 파일이 없습니다.")
        return []

    conn = sqlite3.connect(db_path)
    summary = []

    for filepath in files:
        print(f"  처리 중: {filepath.name}")
        sheets = load_file(filepath)
        for sheet_key, df in sheets.items():
            table_name = normalize_table_name(sheet_key)
            df = process_dataframe(df)
            df.to_sql(table_name, conn, if_exists="replace", index=False)

            # 기간 파악 시도
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
            print(f"    → 테이블: {table_name}, 행 수: {len(df)}, 컬럼: {len(df.columns)}개{', 기간: '+period if period else ''}")

    conn.close()
    print(f"\n[완료] DB 저장: db/{project_name}.sqlite ({len(summary)}개 테이블)")
    return summary


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python scripts/excel_to_sqlite.py {project-name}")
        sys.exit(1)
    ingest_project(sys.argv[1])
