# 판단 기준 / 결론 누적 (decisions.md)

> 간결하게 유지 — 100줄 이내

## 데이터 접근 원칙

- **원본 파일 직접 읽기 금지**: raw/ 파일을 컨텍스트에 통째로 올리지 않는다
- **쿼리 우선**: 엑셀/CSV는 SQLite에 SQL로 접근
- **요약 우선**: PDF/텍스트는 summaries/ 먼저 확인, 필요 시 특정 페이지만 추출
- **인덱스 활용**: 이미지는 image_catalog.json으로 목록 파악 후 개별 접근

## 전처리 결정사항

- SQLite DB는 git에 포함 (분석 재현성 확보, 다른 시스템 즉시 사용)
- raw/ 원본 파일은 git 제외 (용량, 민감정보)
- 스크립트는 멱등성 보장 (중복 실행 안전)
- 날짜 → ISO 8601, 금액 → 콤마/기호 제거 후 숫자 타입 저장

## 구조 결정사항

- **의뢰인/사건 2계층**: projects/{client_id}/{case_slug}/ (2026-04-09 마이그레이션)
- **단일 DB**: master.sqlite 하나에 메타+pages+OCR 통합 (3분할 안 함)
- **사건ID 구분**: client_id + case_slug 두 컬럼 (슬래시 구분자 안 씀)
- memory/ 파일은 세션 간 연속성 유지용 — 간결하게 유지 (각 100줄 이내)
- sessions/ 에 세션 보고서 남김 — 다음 세션에서 맥락 이어받기용
- outputs/ 폴더: 코워크 산출물 (소장, 고소장, 분석 엑셀 등) 별도 보관

## 교훈 (2026-04-08)

- **은행 엑셀 헤더 탐지**: "번호" 키워드 사용 시 "계좌번호" 행에 오매칭 → "No." 정확 매칭 필요
- **pandas infer_datetime_format**: deprecated 파라미터, 최신 버전에서 제거 필요
- **빈 컬럼명**: SQLite 저장 시 빈/NaN 컬럼명 → "col_N"으로 정규화 필수
- **금액 교차대조**: ±7일 window로 먼저 시도, 실패 시 키워드 변형 검색 (예: 재규어랜드로버 → JAGUAR LA)
- **sqlite journal 잔존**: disk I/O error 발생 시 journal 파일 삭제 후 재시도
- **Windows 한글 경로**: CMD 대신 Git Bash, 경로는 forward slash (C:/...) 사용
