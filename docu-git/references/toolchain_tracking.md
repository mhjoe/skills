# Docu-Git 작업 환경 기록 지침 (Toolchain Tracking Protocol)

이 지침서는 **Docu-Git** 스킬이 각 커밋에 "무엇으로 작업했는가"를 기록하고, 다른 PC·다른 세션에서 동일한 방식으로 작업을 이어가도록 보장하는 규칙을 정의합니다.

---

## 1. 왜 기록하는가

문서는 편집 수단에 따라 결과가 달라집니다.

- HWP 문서를 XML 파싱으로 편집하면 서식이 보존되지만, 조판(자간·줄바꿈·쪽수)은 계산되지 않습니다.
- 반대로 한글 프로그램을 통한 편집은 조판이 반영되지만 해당 프로그램이 설치된 PC에서만 가능합니다.
- 같은 문서를 번갈아 다른 방식으로 편집하면 서식 충돌·재조판 사고가 생길 수 있습니다.

따라서 이력에는 변경 내용과 함께 **사용한 스킬·도구와 그 설치 출처**를 남깁니다.

---

## 2. 기록 대상 판단 기준

### 2.1 기록한다
1. 문서의 생성·편집·변환·검증에 **실제로 사용한** 스킬 (예: `hwp-edit`, `hwpx-report-brief`, `docx`, `pdf`)
2. 스킬 없이 수행한 경우의 **도구 조합** (예: `python+hwp-com`, `python-docx`, `pandoc`)
3. 외부 프로그램 의존 (예: 한글, MS Word, LibreOffice)
4. 산출물 검증에 사용한 수단 (예: `can_open`/`roundtrip` 검증, PDF 렌더링 대조)

### 2.2 기록하지 않는다
- 설치되어 있으나 이번 작업에 쓰지 않은 스킬
- 파일 복사·백업처럼 어떤 환경에서나 동일한 일반 작업
- 일회성 조회(웹 검색 등)로 문서 내용에 직접 반영되지 않은 수단

### 2.3 표기 형식
```text
{name}@{version}          # 스킬: hwp-edit@1.0.0
{name}                    # 버전 정보가 없는 도구: python+hwp-com
```

---

## 3. 기록 위치와 서식

### 3.1 `DOCU_HISTORY.md` 헤더 — 프로젝트 누적 환경

```markdown
## 🧰 작업 환경 (Toolchain)

| 스킬 / 도구 | 버전 | 담당 범위 | 출처 / 요건 |
| :--- | :---: | :--- | :--- |
| hwp-edit | 1.0.0 | 본문·표 텍스트 편집, 서식 보존 | https://github.com/{owner}/skills/tree/main/hwp-edit |
| python+hwp-com | - | 자간·그림·쪽수 등 조판 작업, PDF 출력 | 한글(Hancom Office) 설치 필요 |
| docu-git | 1.1.0 | 버전 부여 및 이력 기록 | https://github.com/{owner}/skills/tree/main/docu-git |
```

### 3.2 커밋 블록 — 해당 커밋에서 쓴 것

```markdown
- **사용 스킬 / 도구**: `hwp-edit@1.0.0` (표 셀 입력), `docu-git@1.1.0` (이력 기록)
```

### 3.3 `DOCU_HISTORY.json` — 기계 판독용

```json
{
  "toolchain": [
    {
      "name": "hwp-edit",
      "version": "1.0.0",
      "source": "https://github.com/{owner}/skills/tree/main/hwp-edit",
      "scope": "본문·표 텍스트 편집, 서식 보존",
      "requires": null
    },
    {
      "name": "python+hwp-com",
      "version": null,
      "source": "pywin32 + HWPFrame.HwpObject",
      "scope": "조판(자간·그림·쪽수), PDF 출력",
      "requires": "한글(Hancom Office) 설치"
    }
  ],
  "documents": [
    {
      "history": [
        {
          "commit_id": "doc-commit-20261024-013814",
          "skills_used": ["python+hwp-com", "docu-git@1.1.0"]
        }
      ]
    }
  ]
}
```

- `toolchain`: 프로젝트 전체에서 한 번이라도 사용된 항목을 누적 (중복 없이)
- `skills_used`: 해당 커밋에서 사용한 항목만. `toolchain[].name`과 일치시킬 것

---

## 4. 다른 PC에서 이어받는 절차

1. **환경 확인** — 이력을 연 직후 `toolchain`을 읽고, 현재 PC에 설치된 스킬 목록과 대조합니다.
2. **부족분 설치** — 없는 스킬은 `source` 경로에서 내려받아 스킬 디렉터리에 배치합니다.
3. **설치 불가 항목 처리** — `requires`를 충족할 수 없으면(예: 한글 미설치) 해당 `scope`의 작업은 **보류**하고 사용자에게 보고합니다. 다른 수단으로 대체하면 서식·조판이 어긋날 수 있습니다.
4. **방식 변경 시 기록** — 직전 커밋과 다른 수단으로 작업했다면, 새 커밋의 `Diff Snapshot`에 변경 사유와 영향 범위를 남깁니다.

### 4.1 `docu-git env` 출력 예시

```text
📦 작업 환경 (3개)
  ✔ docu-git@1.1.0        이력 기록                         (설치됨)
  ✔ hwp-edit@1.0.0        본문·표 텍스트 편집                (설치됨)
  ✘ python+hwp-com        조판·PDF 출력                     (한글 미설치 — 해당 작업 보류)

마지막 커밋(v2.0)에서 사용: python+hwp-com, docu-git@1.1.0
```

---

## 5. 기존 이력에 소급 적용

`toolchain` 항목이 없는 기존 `DOCU_HISTORY`를 만났을 때:

1. 커밋 블록의 `검증` 또는 `변경 내역` 서술에서 사용 수단의 단서를 찾습니다.
   - 예: `can_open 통과`, `<hp:t> 내 개행 0건`, `header.xml 문단모양 신설` → XML 직접 편집 계열(`hwp-edit`)
   - 예: `PDF 29쪽`, `자간 조정`, `쪽수 변화` → 조판 엔진 사용(`python+hwp-com` 등)
2. 확실한 커밋에만 `skills_used`를 소급 기록하고, 추정인 경우 `"(추정)"`을 덧붙입니다.
3. 소급이 불가능한 커밋은 비워 두고, 이후 커밋부터 정식 기록을 시작합니다.
