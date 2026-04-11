# 진행 상황 (progress.md)

> 간결하게 유지 — 100줄 이내

## 현재 상태

- 날짜: 2026-04-12
- 상태: jokim 프로젝트 분리 완료, 새 의뢰인 사건 대기
- 마지막 작업: jokim/to-prison → 독립 프로젝트(jokimtoprison)로 분리

## 진행 중인 작업

- 새 의뢰인 사건 raw/ 파일 배치 대기

## 완료된 작업

- [x] claude-hub 시스템 최초 구축
- [x] GitHub 원격 연결 (yunbluesong-a11y/claude_hub)
- [x] 은행 거래내역 4개 ingest
- [x] 수임금액명세서 2개 + 현금매출명세서 ingest
- [x] 조대제·김상균 수임금액명세서 ↔ 계좌 교차대조
- [x] DB 구조 마이그레이션 (2026-04-09)
- [x] jokim/to-prison → 독립 프로젝트(jokimtoprison)로 분리 (2026-04-12)
  - DB 3개 → jokim.sqlite 통합
  - claude_hub에서 jokim 관련 데이터·레코드 전부 제거

## 다음 단계

1. **git commit & push** (2026-04-12 작업분)
2. yumyunggeun 사건들 분석 시작
3. 새 의뢰인 사건 배치
