# Claude & Agent Skills Collection

이 리포지토리는 AI 에이전트 및 LLM을 위한 커스텀 스킬(Skills) 모음입니다.

## 📄 등록된 스킬 목록 (Skills)

### 1. Docu-Git (`docu-git`)
- **설명**: Git이 소스코드를 관리하듯, 사용자의 문서 작업 요청(Input)과 산출물(Output)을 요약·기록하고 저장 시 파일명에 버전을 반영하는 문서 이력관리 에이전트 스킬
- **위치**: [`skills/docu-git`](./docu-git) 또는 [`docu-git/SKILL.md`](./docu-git/SKILL.md)
- **주요 기능**:
  - 사용자 Input/Output 연속 이력 축적 (`DOCU_HISTORY.md`)
  - 로컬 저장 파일명 버전 포함 규칙 적용 (`{문서명}_v{버전}_{주요변경사항}.{ext}`)
  - 핵심요지 손실 없는 고밀도 요약
  - Status / Log / Diff / Branch / Tag 문서 이력 관리 지원

---

## 🛠️ 스킬 사용 방법

이 리포지토리의 스킬 폴더를 에이전트 커스텀 스킬 디렉토리(`.agents/skills/` 또는 사용자 지정 스킬 루트)에 배치하여 즉시 사용할 수 있습니다.
