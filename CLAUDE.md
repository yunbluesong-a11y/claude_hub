# claude-hub — 범용 컨텍스트 관리 시스템

## 이 프로젝트는 무엇인가
대용량 소스 파일(엑셀, PDF, 텍스트, 이미지 등)을 컨텍스트에 올리지 않고
효율적으로 분석하기 위한 범용 컨텍스트 관리 시스템.
여러 로컬 시스템의 코워크가 git 동기화로 세션을 이어간다.
의뢰인 → 사건 → 문서/증거 계층 구조로 관리한다.

## 세션 시작 시 반드시 할 것
1. `sessions/` 최근 파일 확인 → 직전 세션 맥락 파악 (가장 중요!)
2. `memory/progress.md` → 현재 진행 상황 파악
3. `memory/decisions.md` → 이전 판단 기준 확인
4. `memory/questions.md` → 미해결 이슈 확인

## 세션 시작 시 라우팅

1. master.sqlite에서 의뢰인·사건 목록 조회:
```sql
SELECT c.client_id, c.name, ca.case_slug, ca.title, ca.status
FROM clients c JOIN cases ca ON c.client_id = ca.client_id
WHERE ca.status = 'active'
ORDER BY c.client_id, ca.case_slug;
```

2. 사용자에게 "어떤 사건을 작업하시겠습니까?" 확인
3. 해당 사건의 `projects/{client_id}/{case_slug}/README.md` 읽기
4. 해당 사건의 `summaries/` 필요한 것만 로드
5. 다른 사건 데이터는 명시적으로 요청받기 전까지 접근하지 않는다

## 데이터 접근 계층 (중요)

컨텍스트 소모를 최소화하는 순서:

① `db/master.sqlite` 쿼리 (메타데이터만, 최소 소모)
② `projects/{client}/{case}/summaries/` 요약본 (사건별 1페이지 이내)
③ `db/master.sqlite` pages 테이블 특정 페이지 검색 (키워드 기반)
④ `projects/{client}/{case}/index/` 인덱스 파일 (증거 목록, 이미지 카탈로그)
⑤ `raw/` 원본 개별 접근 (최후 수단, 특정 파일·페이지만)

**절대 규칙**:
- 원본 파일(raw/)을 절대 통째로 읽지 않는다
- 엑셀/CSV → `db/{client_id}_{case_slug}.sqlite`에 SQL 쿼리로 접근
- PDF/docx → summaries/ 요약본 먼저 확인, 상세 필요 시 pages 테이블 검색
- 이미지 → `index/image_catalog.json`으로 목록 확인 후 개별 접근
- 영상 → `index/*_영상메모.md` 사람이 작성한 메모만 참조

## 증거 번호 관리

증거 번호는 master.sqlite의 evidence 테이블에서 관리한다.
새 증거 추가 시 반드시 evidence 테이블에 등록한다.
번호 충돌 확인:
```sql
SELECT label FROM evidence WHERE client_id = '{client_id}' AND case_slug = '{case_slug}' ORDER BY label;
```

## 새 의뢰인·사건 추가 방법

1. master.sqlite에 의뢰인 등록 (없는 경우):
```sql
INSERT INTO clients (client_id, name) VALUES ('newclient', '새의뢰인');
```

2. master.sqlite에 사건 등록:
```sql
INSERT INTO cases (client_id, case_slug, title, type, status)
VALUES ('newclient', 'case-name', '사건명', 'civil', 'active');
```

3. `raw/{client_id}/{case_slug}/` 에 원본 파일 배치

4. `python scripts/ingest.py {client_id}/{case_slug}` 실행

5. `projects/{client_id}/{case_slug}/README.md` 작성 (목적, 소스 설명)

6. 분석 시작

## 세션 종료 시 반드시 할 것
1. `sessions/YYYY-MM-DD_작업명.md` 세션 보고서 작성
2. `memory/progress.md` 업데이트
3. 새 판단 → `memory/decisions.md` 추가
4. 미해결 질문 → `memory/questions.md` 추가
5. 새 요약 → `projects/{client}/{case}/summaries/` 저장
6. `git add, commit, push`

## 현재 의뢰인·사건 목록

| 의뢰인 | 사건 | 유형 | 상태 | DB |
|--------|------|------|------|-----|
| `jokim` | `to-prison` | criminal(횡령 고소) | active | `db/legacy/jokim-to-prison.sqlite` |
| `yumyunggeun` | `honor-defamation` | criminal(명예훼손) | active | (ingest 대기) |
| `yumyunggeun` | `danggeun-youtube` | criminal(당근·유튜브) | active | (ingest 대기) |
| `yumyunggeun` | `counterclaim` | civil(반소 손해배상) | active | (ingest 대기) |
| `yumyunggeun` | `trademark-semmaeul` | trademark(상표권) | active | (ingest 대기) |
| `leekwongu` | `loan-hankyungsuk` | civil(대여금 반환) | active | (ingest 대기) |
| `leehyunmi` | `payment-order-kimjungchun` | civil(지급명령) | active | (ingest 대기) |

## DB 구조

### master.sqlite (메타데이터 중앙 DB)

| 테이블 | 용도 |
|--------|------|
| `clients` | 의뢰인 정보 (client_id PK) |
| `cases` | 사건 정보 (client_id + case_slug UNIQUE) |
| `evidence` | 증거 목록 (사건별 갑/을 호증 관리) |
| `documents` | 코워크 산출물 (소장, 고소장, 준비서면 등) |
| `transactions_meta` | 거래내역 테이블 메타 (어떤 DB에 어떤 테이블이 있는지) |
| `pages` | PDF/docx 페이지별 텍스트 (전문 검색용) |
| `image_ocr` | 이미지 OCR 결과 |

### jokim/to-prison (legacy DB: `db/legacy/jokim-to-prison.sqlite`)

> ⚠️ 기존 분석 진행중 — 마이그레이션 전까지 legacy DB 사용

| 테이블명 | 내용 | 원본 |
|---------|------|------|
| `acct_22991001751404` | 조대제 계좌 입출금 | 22991001751404_조대제_입출금내역_404.xlsx |
| `acct_22991001907204` | 메인계좌 입출금 | 22991001907204_메인계좌_입출금_204.xlsx |
| `acct_22991001951104` | 김상균 계좌 입출금 | 22991001951104_김상균_입출금내역_104.xlsx |
| `acct_22991002022504` | 송명욱 계좌 입출금 | 22991002022504_송명욱_입출금내역_504.xlsx |
| `fee_statement_조대제_김상균` | 수임금액명세서 (조대제+김상균) | 수임금액명세서_조대제+김상균.xlsx |
| `fee_statement_송명욱` | 수임금액명세서 (송명욱) | 수임금액명세서_송명욱.xlsx |
| `cash_sales_statement` | 현금매출명세서 9기간 | 현금매출명세서_태율법인전체.xlsx |

### 거래내역 DB 규칙 (새 사건)

새 사건의 엑셀 데이터는 `db/{client_id}_{case_slug}.sqlite`에 저장된다.
테이블 메타정보는 `master.sqlite`의 `transactions_meta`에서 조회.

## 디렉토리 구조
```
claude_hub/
├── CLAUDE.md           ← 이 파일 (세션 부팅 디스크)
├── .gitignore
│
├── db/
│   ├── master.sqlite              ← 의뢰인·사건·증거 메타데이터 + pages + OCR
│   ├── {client}_{case}.sqlite     ← 사건별 거래내역 (엑셀 기반)
│   └── legacy/
│       └── jokim-to-prison.sqlite ← 기존 DB (마이그레이션 전까지 유지)
│
├── memory/
│   ├── progress.md
│   ├── decisions.md
│   └── questions.md
│
├── projects/
│   ├── {client_id}/
│   │   ├── README.md              ← 의뢰인 정보
│   │   └── {case_slug}/
│   │       ├── README.md          ← 사건 개요, 상태, 관할
│   │       ├── summaries/         ← PDF·docx 요약
│   │       ├── index/             ← 페이지 인덱스, 증거 목록, 영상메모
│   │       └── outputs/           ← 코워크 산출물 (소장, 고소장 등)
│
├── raw/                           ← 원본 파일 (.gitignore 대상)
│   └── {client_id}/{case_slug}/   ← projects/와 동일 계층
│
├── scripts/
│   ├── ingest.py                  ← python ingest.py {client_id}/{case_slug}
│   ├── excel_to_sqlite.py
│   ├── pdf_to_chunks.py
│   ├── docx_to_summary.py
│   ├── image_catalog.py           ← OCR 기능 포함
│   └── register_evidence.py       ← 증거 수동 등록
│
└── sessions/                      ← 세션 보고서
```

## Git 커밋 규칙
```bash
git pull origin main     # 세션 시작 전
git commit -m "[claude] 작업 내용 요약"
git push origin main     # 세션 종료 시
```

## 주의사항
- memory/ 파일은 간결하게 유지 (각 100줄 이내)
- summaries/ 요약은 소스 1건당 1페이지 이내
- 전처리 스크립트는 멱등성 보장 (여러 번 실행해도 같은 결과)
- 영상 파일은 전처리하지 않는다 (영상메모 템플릿만 생성)
- 의뢰인 ID, 사건 ID에 공백 사용 금지 (하이픈으로 연결)
- OneDrive 동기화 범위 밖에서 사용 권장 (SQLite 잠금 방지)
