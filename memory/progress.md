# 진행 상황 (progress.md)

> 간결하게 유지 — 100줄 이내

## 현재 상태

- 날짜: 2026-04-09
- 상태: DB 구조 마이그레이션 완료 (v2 의뢰인/사건 계층 체계)
- 마지막 작업: CLAUDE.md, 스크립트, master.sqlite 전면 개편

## 진행 중인 작업

- jokim/to-prison — 고소장 v3 완성(신동훈 피고소인3 추가), 추가 분석 가능
- 새 의뢰인 사건 raw/ 파일 배치 대기

## 완료된 작업

- [x] claude-hub 시스템 최초 구축
- [x] GitHub 원격 연결 (yunbluesong-a11y/claude_hub)
- [x] 은행 거래내역 4개 ingest (조대제/메인/김상균/송명욱)
- [x] 수임금액명세서 2개 ingest
- [x] 현금매출명세서 ingest
- [x] 조대제·김상균 수임금액명세서 ↔ 계좌 교차대조
- [x] jokim/to-prison 고소장 v1 → v2(보강) → v3(신동훈 추가)
- [x] 범죄일람표 엑셀 (별지1~3 + 총괄)
- [x] 자금흐름도 SVG
- [x] **DB 구조 마이그레이션 (2026-04-09)**:
  - 의뢰인→사건 2계층 디렉토리 구조 생성
  - master.sqlite 단일 DB (clients, cases, evidence, documents, transactions_meta, pages, image_ocr)
  - client_id + case_slug 분리 스키마
  - legacy DB 보존 (db/legacy/jokim-to-prison.sqlite)
  - 스크립트 v2: ingest.py, excel_to_sqlite.py, pdf_to_chunks.py, image_catalog.py
  - 신규 스크립트: docx_to_summary.py, register_evidence.py
  - CLAUDE.md 전면 개편 (라우팅 규칙, 데이터 접근 계층, 증거 관리)

## 다음 단계

1. OneDrive 밖으로 repo 이동 (로컬 작업 — C:\dev\claude_hub 권장)
2. 각 사건 raw/ 폴더에 원본 파일 배치 후 ingest 실행
3. jokim/to-prison: 송명욱 수임금액명세서 ↔ 계좌 교차대조 (미실시)
4. yumyunggeun 사건들 분석 시작
5. 기존 `projects/jokim to prison/`, `db/jokim to prison.sqlite` 정리 (마이그레이션 확인 후)
