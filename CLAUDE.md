# claude-hub — 범용 컨텍스트 관리 시스템

## 이 프로젝트는 무엇인가
대용량 소스 파일(엑셀, PDF, 텍스트, 이미지 등)을 컨텍스트에 올리지 않고
효율적으로 분석하기 위한 범용 컨텍스트 관리 시스템.
여러 로컬 시스템의 코워크가 git 동기화로 세션을 이어간다.

## 세션 시작 시 반드시 할 것
1. `sessions/` 최근 파일 확인 → 직전 세션 맥락 파악 (가장 중요!)
2. `memory/progress.md` → 현재 진행 상황 파악
3. `memory/decisions.md` → 이전 판단 기준 확인
4. `memory/questions.md` → 미해결 이슈 확인
5. 작업 대상 프로젝트의 `projects/{name}/README.md` 확인

## 데이터 접근 규칙 (중요)
- 원본 파일(raw/)을 절대 통째로 읽지 않는다
- 엑셀/CSV → `db/` 의 SQLite에 SQL 쿼리로 접근
- PDF → `projects/{name}/summaries/` 요약본 먼저 확인,
  상세 필요 시 `index/page_index.json`으로 해당 페이지만 추출
- 이미지 → `index/image_catalog.json`으로 목록 확인 후 개별 접근
- 텍스트 → `summaries/` 요약본 우선, 필요 시 원본의 특정 부분만 읽기
- 새로운 요약이 생기면 반드시 `summaries/`에 저장

## 새 분석 프로젝트 추가 방법
1. `raw/{project-name}/` 에 원본 파일 배치
2. `python scripts/ingest.py {project-name}` 실행
3. `projects/{project-name}/README.md` 작성 (목적, 소스 설명)
4. 분석 시작

## 세션 종료 시 반드시 할 것
1. `sessions/YYYY-MM-DD_작업명.md` 세션 보고서 작성
2. `memory/progress.md` 업데이트
3. 새 판단 → `memory/decisions.md` 추가
4. 미해결 질문 → `memory/questions.md` 추가
5. 새 요약 → `projects/{name}/summaries/` 저장
6. `git add, commit, push`

## 현재 프로젝트 목록

| 프로젝트 | 추가일 | 상태 | DB |
|---------|-------|------|-----|
| `jokim to prison` | 2026-04-07 | 분석 진행중 | `db/jokim to prison.sqlite` |

## DB 스키마 — jokim to prison

| 테이블명 | 내용 | 원본 |
|---------|------|------|
| `acct_22991001751404` | 조대제 계좌 입출금 | 22991001751404_조대제_입출금내역_404.xlsx |
| `acct_22991001907204` | 메인계좌 입출금 | 22991001907204_메인계좌_입출금_204.xlsx |
| `acct_22991001951104` | 김상균 계좌 입출금 | 22991001951104_김상균_입출금내역_104.xlsx |
| `acct_22991002022504` | 송명욱 계좌 입출금 | 22991002022504_송명욱_입출금내역_504.xlsx |
| `fee_statement_조대제_김상균` | 수임금액명세서 (조대제+김상균) | 수임금액명세서_조대제+김상균.xlsx |
| `fee_statement_송명욱` | 수임금액명세서 (송명욱) | 수임금액명세서_송명욱.xlsx |
| `cash_sales_statement` | 현금매출명세서 9기간 (2016.2기~2018.2기) | 현금매출명세서_태율법인전체.xlsx |

## 디렉토리 구조
```
claude_hub/
├── CLAUDE.md           ← 이 파일 (세션 부팅 디스크)
├── db/                 ← SQLite DB (git 포함, 쿼리로 접근)
├── memory/             ← 세션 간 연속성 유지 (git 포함)
│   ├── progress.md     ← 진행 상황
│   ├── decisions.md    ← 판단 기준
│   └── questions.md    ← 미해결 이슈
├── sessions/           ← 세션 보고서 (날짜_작업명.md)
├── projects/           ← 프로젝트별 분석 결과물
├── raw/                ← 원본 파일 (git 제외, 로컬만)
└── scripts/            ← 전처리 스크립트
```

## Git 커밋 규칙
```bash
git pull origin main     # 세션 시작 전
git commit -m "[claude] 작업 내용 요약"
git push origin main     # 세션 종료 시
```
