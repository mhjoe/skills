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

### 2. HWPX Report Brief (`hwpx-report-brief`)
- **설명**: 한컴 HWPX 템플릿의 '스타일'(□·ㅇ·-·※·* 개요, 본문, 표/그림 제목 등)을 그대로 물려받아 한글(.hwpx) 공공기관 보고서를 생성하는 스킬. 파이썬으로 XML을 직접 생성하므로 한글 프로그램 없이 동작한다.
- **위치**: [`hwpx-report-brief`](./hwpx-report-brief) 또는 [`hwpx-report-brief/SKILL.md`](./hwpx-report-brief/SKILL.md)
- **주요 기능**:
  - 번들 템플릿(`assets/template.hwpx`, 지방공기업평가원 기본 보고서 양식) 스타일 상속 — 한글에서 스타일만 고쳐 저장하면 다음 생성부터 반영
  - 개요 스타일을 **자동 글머리표 문자**로 매칭(스타일 이름·ID가 바뀌어도 안전)
  - `.docx`/`.txt`/`.md` 원고 → 표지·목차·장 번호박스·표·그림까지 조판
  - 생성물 구조 검증기 동봉 (`references/verify.py`)

### 3. HWP Edit (`hwp-edit`)
- **설명**: 이미 존재하는 한글 문서(.hwp/.hwpx)를 열어 텍스트를 읽고 수정하는 스킬. 특히 **표로 된 양식의 빈 칸을 좌표로 정확히 채운다**(심사서·평가표·신청서·점검표). 내부 XML을 직접 파싱하므로 한글 프로그램이나 COM 없이 동작하고 원본 서식은 보존된다.
- **위치**: [`hwp-edit`](./hwp-edit) 또는 [`hwp-edit/SKILL.md`](./hwp-edit/SKILL.md)
- **주요 기능**:
  - 텍스트 추출·검색·치환, 문서 구조 분석
  - `dump_tables()`로 표의 행/셀 좌표를 먼저 확인한 뒤 `set_cell_text()`로 기입
  - `expect_label`로 기입 직전 같은 행의 라벨을 대조해 **좌표 착오를 차단**
  - 문단 리스트로 줄바꿈 처리 + 레이아웃 캐시 제거로 **셀 밖 넘침 방지**
  - 수정 전 자동 백업
- **`hwpx-report-brief`와의 구분**: 이 스킬은 **기존 문서 편집**, `hwpx-report-brief`는 **새 보고서 생성**이다.

---

## 🛠️ 스킬 사용 방법

이 리포지토리의 스킬 폴더를 에이전트 커스텀 스킬 디렉토리(`.agents/skills/` 또는 사용자 지정 스킬 루트)에 배치하여 즉시 사용할 수 있습니다.
