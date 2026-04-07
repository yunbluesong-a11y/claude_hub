# 진행 상황 (progress.md)

> 간결하게 유지 — 100줄 이내

## 현재 상태

- 날짜: 2026-04-07
- 상태: 시스템 초기화 완료 (아직 분석 프로젝트 없음)
- 마지막 작업: claude-hub 프로젝트 최초 구축

## 진행 중인 작업

없음 — raw/ 에 파일을 넣고 `python scripts/ingest.py {project-name}` 실행 대기 중

## 완료된 작업

- [x] 디렉토리 구조 생성
- [x] 전처리 스크립트 작성 (ingest, excel_to_sqlite, pdf_to_chunks, image_catalog)
- [x] CLAUDE.md 작성
- [x] .gitignore 작성
- [x] git 초기화

## 다음 단계

1. raw/{project-name}/ 에 원본 파일 배치
2. `python scripts/ingest.py {project-name}` 실행
3. 분석 시작
