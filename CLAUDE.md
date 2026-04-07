# claude-hub

## 이 프로젝트는 무엇인가
대용량 소스 파일(엑셀, PDF, 텍스트, 이미지 등)을 컨텍스트에 올리지 않고
효율적으로 분석하기 위한 범용 컨텍스트 관리 시스템.
여러 로컬 시스템의 코워크가 git 동기화로 세션을 이어간다.

## 세션 시작 시 반드시 할 것
1. memory/progress.md → 현재 진행 상황 파악
2. memory/decisions.md → 이전 판단 기준 확인
3. memory/questions.md → 미해결 이슈 확인
4. 작업 대상 프로젝트의 projects/{name}/README.md 확인

## 데이터 접근 규칙 (중요)
- 원본 파일(raw/)을 절대 통째로 읽지 않는다
- 엑셀/CSV → db/ 의 SQLite에 SQL 쿼리로 접근
- PDF → projects/{name}/summaries/ 요약본 먼저 확인,
  상세 필요 시 index/page_index.json으로 해당 페이지만 추출
- 이미지 → index/image_catalog.json으로 목록 확인 후 개별 접근
- 텍스트 → summaries/ 요약본 우선, 필요 시 원본의 특정 부분만 읽기
- 새로운 요약이 생기면 반드시 summaries/에 저장

## 새 분석 프로젝트 추가 방법
1. raw/{project-name}/ 에 원본 파일 배치
2. python scripts/ingest.py {project-name} 실행
3. projects/{project-name}/README.md 작성 (목적, 소스 설명)
4. 분석 시작

## 세션 종료 시 반드시 할 것
1. memory/progress.md 업데이트
2. 새 판단 → memory/decisions.md 추가
3. 미해결 질문 → memory/questions.md 추가
4. 새 요약 → projects/{name}/summaries/ 저장
5. git add, commit, push

## 현재 프로젝트 목록
(ingest 실행 후 여기에 자동 기록)

## DB 스키마
(ingest 실행 후 여기에 자동 기록)
