---
name: hwp-edit
description: >-
  이미 존재하는 한글 문서(.hwp/.hwpx)를 열어 텍스트를 읽고 수정하며, 특히 표로 된
  양식의 빈 칸을 좌표로 정확히 채운다. 사용 시점: 사용자가 "한글 파일 읽어줘",
  "이 hwpx에서 텍스트 뽑아줘", "이 문서에서 A를 B로 바꿔줘", "심사서/평가표/신청서
  양식에 내용을 작성해줘", "표의 해당 칸에 체크해줘" 같은 요청을 할 때. 파이썬으로
  내부 XML을 직접 파싱하므로 한글 프로그램이나 COM 없이 동작하고, 원본의 서식은
  그대로 유지된다. 빈 문서에서 새 보고서를 생성하는 작업이 아니라 기존 문서를
  편집하는 작업에 쓴다(새 보고서 생성은 hwpx-report-brief 스킬). 한글의 기본
  저장 형식인 바이너리 .hwp는 COM으로 .hwpx 변환 후 동일하게 처리한다.
---

# 한글 문서 읽기 및 수정 (HWP/HWPX)

기존 `.hwp`/`.hwpx` 문서를 열어 텍스트를 추출·검색·치환하고, **표 양식의 빈 셀을
좌표로 지정해 채운다.** 파일 내부 XML을 직접 다루므로 한글 프로그램이 설치되어
있지 않아도 되고, 글꼴·크기·색상 등 원본 서식은 보존된다.

**이 스킬의 범위는 "기존 문서 편집"이다.** 템플릿 스타일을 물려받아 새 보고서를
조판하는 작업은 `hwpx-report-brief` 스킬을 쓴다.

## 언제 쓰나

- 한글 문서의 내용을 읽어야 할 때 (Read 도구는 hwpx 바이너리를 파싱하지 못한다)
- 문서 전체에서 특정 단어를 일괄 치환할 때
- **심사서·평가표·신청서·점검표 같은 표 양식의 빈 칸을 채울 때** ← 이 스킬의 핵심

## 전제 조건

```bash
uv run --python 3.12 --link-mode=copy --with lxml python 작업스크립트.py
```

`scripts/hwp_handler.py`를 import 경로에 두고 사용한다.

**`pip install lxml`을 쓰지 말 것.** Python이 uv로 관리되는 환경에서는
`This Python installation is managed by uv`로 실패하며, `pip` 명령 자체가 없을
수도 있다. `--link-mode=copy`는 uv 캐시의 `액세스가 거부되었습니다 (os error 5)`를
예방한다(백신·동기화 폴더 간섭).

## 0단계 — 이 파일이 XML로 열리는가 (생략 금지)

`.hwp` 확장자는 **서로 다른 두 포맷**을 가리킨다. 확장자로는 구분할 수 없으므로
파일 시그니처를 먼저 본다.

```python
from hwp_com import detect_format, to_hwpx

fmt = detect_format("문서.hwp")     # 'zip' | 'ole' | 'unknown'
path = to_hwpx("문서.hwp")          # 'ole'이면 변환, 'zip'이면 원본 경로 그대로
```

| 시그니처 | 포맷 | 처리 |
|---|---|---|
| `PK\x03\x04` | ZIP (.hwpx, HWPML로 저장된 .hwp) | 그대로 `HwpDocument`로 |
| `\xd0\xcf\x11\xe0` | OLE — **바이너리 .hwp v5 (한글 기본 저장 형식)** | `to_hwpx()`로 변환 후 진행 |

바이너리 `.hwp`를 그대로 `HwpDocument()`에 넘기면 이렇게 실패한다:

```
ValueError: 잘못된 HWP 파일 형식입니다: ...\문서.hwp
```

**이건 파일이 손상됐다는 뜻이 아니다.** ZIP으로 열려다 실패한 것뿐이므로
사용자에게 "손상된 문서"라고 보고하지 말고 `to_hwpx()`로 변환한다.
변환에는 한글 프로그램이 필요하다(COM). 자세한 내용과 함정은
[`references/com-automation.md`](./references/com-automation.md).

```bash
uv run --python 3.12 --link-mode=copy --with pywin32 --with lxml python 작업스크립트.py
```

변환 후에는 **평소대로 XML 경로로 작업한다.** COM으로 직접 편집하지 말 것 —
느리고 함정이 많다. COM은 변환·PDF 내보내기 등 XML로 불가능한 작업에만 쓴다.

### COM을 쓸 때의 절대 규칙 — `RegisterModule` 먼저

`RegisterModule` 없이 `Open()`이나 `SaveAs()`를 호출하면 한글이 **파일마다,
저장마다** 이 대화상자를 띄운다:

> 한글을 이용하여 위 파일에 접근하려는 시도(파일의 손상 또는 유출의 위험 등)가
> 있습니다. 정상적인 작업 과정에만 접근을 허용하십시오.
> `[접근 허용]` `[모두 허용]` `[허용 안 함]` `[모두 안 함]`

사용자가 매번 클릭해야 하고, 한글 창이 숨겨져 있으면 **화면에 보이지도 않는 채로**
떠서 스크립트가 영구 정지한다. 대화상자에서 "모두 허용"을 눌러도 다음 실행에 또 뜬다 —
근본 해결은 등록뿐이다.

**`scripts/hwp_com.py`가 있으면 그것만 쓴다.** `HwpApp`이 등록·검증을 모두 처리하고,
등록이 안 된 상태면 `Open` 이전에 예외를 던져 대화상자 앞에서 멈추는 일을 막는다.

```python
from hwp_com import to_hwpx, to_pdf, shared_app, close_shared
```

**`scripts/`가 없어서 COM 코드를 직접 써야 한다면, 아래 두 부분을 반드시 포함한다.**
한 줄이라도 빠지면 대화상자가 뜬다.

```python
import os, shutil, winreg
from pathlib import Path
import win32com.client as w

# (1) 보안 모듈 DLL 등록 — 한 번만 하면 영구히 유지된다
dll = Path(os.environ["LOCALAPPDATA"]) / "HwpAutomation" / "FilePathCheckerModule.dll"
if not dll.exists():                      # DLL은 pyhwpx 패키지에 동봉되어 있다
    import pyhwpx                         #   → 실행에 --with pyhwpx 를 추가할 것
    dll.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(pyhwpx.__file__).parent / "FilePathCheckerModule.dll", dll)
for key in (r"Software\HNC\HwpAutomation\Modules",
            r"Software\Hnc\HwpUserAction\Modules"):
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_WRITE) as k:
        winreg.SetValueEx(k, "FilePathCheckerModule", 0, winreg.REG_SZ, str(dll))

# (2) 인스턴스마다, Open/SaveAs 이전에 호출 — 반환값이 False면 진행하지 말 것
hwp = w.Dispatch("HWPFrame.HwpObject")
if not hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule"):
    raise RuntimeError(f"보안 모듈 등록 실패: {dll} — 이대로 진행하면 대화상자가 뜬다")
```

#### 새 환경에서의 준비 — 자동이다

`hwp_com.py`는 DLL이 어디에도 없으면 **스스로 확보한다.** `uv`로 일회성 환경에
`pyhwpx`를 받아 DLL만 `%LOCALAPPDATA%\HwpAutomation\`에 복사하고 등록한다.
`pyhwpx`를 현재 환경에 설치하지는 않는다.

**따라서 새 PC에서도 사용자에게 설치 명령을 안내할 필요가 없다.** 첫 COM 호출에서
자동으로 처리된다. 최초 1회만 네트워크가 필요하고(1~2분), 그 뒤로는 `pyhwpx`도
네트워크도 필요 없다. PowerShell의 `New-HwpObject`도 같은 경로를 탄다.

미리 준비하거나 상태를 확인하려면:

```bash
# 확보 + 등록 (DLL이 없으면 자동으로 내려받는다)
uv run --python 3.12 --link-mode=copy --with pywin32 python scripts/hwp_com.py --setup

# 등록 상태만 확인 (내려받지 않는다)
uv run --python 3.12 --link-mode=copy --with pywin32 python scripts/hwp_com.py --check
```

자동 확보가 실패하는 경우는 둘뿐이고, 예외 메시지가 어느 쪽인지 알려준다:
`uv`가 PATH에 없거나(`winget install astral-sh.uv`), 오프라인이거나. 오프라인이면
DLL을 위 경로에 직접 두면 된다(한글과 **비트수가 같아야** 한다).

PowerShell에서는 `New-Object -ComObject`를 직접 쓰지 말고
`scripts/hwp-helper.ps1`의 `New-HwpObject`를 쓴다(등록을 대신 처리한다).
`Hancom.HwpObject`는 **존재하지 않는 ProgID다** — `HWPFrame.HwpObject`를 쓴다.

인스턴스를 여러 번 만들지 않는다. `Quit()` 직후 새 `Dispatch()`는 영구 정지하고,
새 인스턴스마다 `RegisterModule`을 다시 해야 한다. 여러 파일을 처리할 때는
`shared_app()`을 쓰거나 `Clear(1)` 후 같은 인스턴스를 재사용한다.

## 기본 사용

### 텍스트 추출

```python
from hwp_handler import HwpDocument

doc = HwpDocument("문서.hwpx")
text = doc.get_text()
doc.close()
```

### 검색 / 치환

```python
doc = HwpDocument("문서.hwpx")
n = doc.count_text("위원회")
doc.replace_text("회의", "미팅")
doc.save()
doc.close()
```

### 표(양식)에 기입 — 반드시 이 방법으로

**표의 빈 칸을 채우는 데 `replace_text()`를 쓰면 안 된다.** 아래 "표 작업 규칙"을
먼저 읽을 것.

```python
doc = HwpDocument("심사서식.hwpx")

# 1단계: 좌표 확인 (생략 금지)
print(doc.dump_tables())
# ===== TABLE 4  rowCnt=15 colCnt=2 =====
#   r3   [c0 1x1]'연구주제의 창의성' [c1 1x1]''   ← c1이 빈 답란

# 2단계: 좌표로 기입. 리스트의 각 원소가 한글에서 한 문단(줄)이 된다.
doc.set_cell_text(
    4, 3, 1,                                 # 표4 / 행3 / colAddr=1
    ["첫째 문단입니다.", "둘째 문단입니다."],
    expect_label=(0, "연구주제의 창의성"),     # 같은 행 c0 라벨 검증
)
doc.set_cell_text(1, 2, 5, "○", expect_label=(1, "연구주제의 창의성"))

doc.save()
doc.close()
```

---

## 표 작업 규칙 (중요)

표 양식을 채우는 작업에서 반복적으로 발생하는 실패가 있다. 아래 세 가지를 지키지
않으면 **내용이 엉뚱한 셀에 들어가거나, 한 줄로 뭉쳐 셀 밖으로 넘친다.**

### 규칙 1 — 빈 셀은 텍스트 검색으로 찾을 수 없다

빈 셀에는 `<hp:t>` 요소가 **아예 존재하지 않는다**:

```xml
<hp:tc>                          <!-- c0: 라벨 셀 -->
  <hp:p><hp:run charPrIDRef="14"><hp:t>연구주제의 창의성</hp:t></hp:run></hp:p>
<hp:tc>                          <!-- c1: 채워야 할 답란 -->
  <hp:p><hp:run charPrIDRef="15"/></hp:p>     <!-- run이 self-closing -->
```

따라서 `if elem.text == "연구주제의 창의성"` 같은 검색은 **답란을 절대 찾지 못하고**,
그 문자열이 실재하는 유일한 곳인 라벨 셀에 착지해 라벨을 덮어쓴다.

- ❌ `doc.replace_text("주제", "주제\n" + 의견)`
- ✅ `doc.set_cell_text(4, 3, 1, [의견], expect_label=(0, "연구주제의 창의성"))`

`replace_text()`는 "문서 전체에서 단어 X를 Y로" 같은 용도에만 쓴다. 전역 치환이라
의도치 않은 곳까지 함께 바꾼다(예: `replace_text("수정", "게재불가")`가 판정란 라벨과
안내문의 "수정·보완사항"까지 훼손).

### 규칙 2 — 줄바꿈은 `\n`이 아니라 문단이다

HWPX에서 줄바꿈은 문자가 아니라 `<hp:p>` 경계다. `<hp:t>` 안의 `\n`은 XML 공백으로
취급되어 **화면에 아무 효과가 없다**. 여러 줄은 리스트로 전달한다.

- ❌ `set_cell_text(4, 3, 1, ["1문단\n2문단"])` → `ValueError`로 차단됨
- ✅ `set_cell_text(4, 3, 1, ["1문단", "2문단"])`

또한 `<hp:linesegarray>`는 **렌더링된 줄 수만큼의 레이아웃 캐시**다. 이걸 남긴 채
텍스트만 길게 바꾸면 한글이 옛 줄 수대로 그려서 긴 문장이 한 줄로 셀 밖에 넘친다.
`set_cell_text()`는 이 캐시를 제거해 한글이 재계산하도록 한다.

### 규칙 3 — 좌표는 `dump_tables()`로 확인하고 `expect_label`로 검증한다

`col`은 리스트 인덱스가 아니라 `<hp:cellAddr>`의 **`colAddr` 값**이다. 셀 병합
(`colSpan`/`rowSpan`) 때문에 행마다 셀 개수가 다르고 colAddr도 건너뛴다.

```
r1  [c0]'평가항목' [c1]'세부항목' [c2 2x1]'A 아주 우수' [c4]'B 우수' [c5]'C 보통' ...
r2  [c0 1x2]'주제' [c1]'연구주제의 창의성' [c2 2x1]'' [c4]'' [c5]'' ...
r3            (c0 없음 — 위 행에 병합됨)  [c1]'연구목적의 타당성' ...
```

A열은 `colSpan=2`라 `c2`, B열은 `c4`, C열은 `c5`다. 인덱스로 세면 반드시 어긋난다.
`expect_label=(라벨열, 기대문자열)`을 넘기면 기입 전에 같은 행의 라벨을 대조해
좌표 착오를 즉시 잡아준다. **항상 사용할 것.**

### 작업 순서

1. `dump_tables()`로 표/행/`colAddr`을 확인한다
2. 원본을 백업한다 (이미 편집한 파일 위에 덧쓰면 오류가 누적된다)
3. `set_cell_text(..., expect_label=...)`로 기입한다
4. 저장 후 `get_cell_text()`로 되읽어 검증한다
5. 검증 결과를 사용자에게 보고한다

**한 번 실패했다면 치환 문자열을 바꿔가며 재시도하지 말고 1번으로 돌아간다.**
같은 잘못된 모델 위의 재시도는 파일 오염만 누적시킨다.

---

## API

### 문서

| 메서드 | 설명 |
|---|---|
| `HwpDocument(path, create_backup=True)` | 열기 |
| `save(output_path=None)` | 저장 |
| `close()` | 리소스 해제 (context manager 지원) |
| `get_document_info()` / `get_style_info()` | 메타정보 |

### 텍스트

| 메서드 | 설명 |
|---|---|
| `get_text(start, length)` | 전체 또는 범위 텍스트 |
| `get_char_count()` / `get_paragraph_count()` | 글자 수 / 문단 수 |
| `find_all(text)` / `count_text(text)` | 검색 |
| `replace_text(a, b)` / `replace_first(a, b)` | 치환 (**표 기입에는 사용 금지**) |

### 표 (좌표 기반)

| 메서드 | 설명 |
|---|---|
| `dump_tables()` | 모든 표의 행/`colAddr`/내용 출력 — **표 작업 전 필수** |
| `get_tables()` | `<hp:tbl>` 엘리먼트 목록 |
| `get_cell(t, r, c)` | 셀 엘리먼트 |
| `get_cell_text(t, r, c)` | 셀 텍스트 (빈 셀은 `""`) |
| `set_cell_text(t, r, c, paragraphs, expect_label=None)` | 셀 내용 교체 |

## 파일 구조

HWP/HWPX는 ZIP 아카이브다:

```
document.hwpx
├── Contents/section0.xml   # 본문 (hwpx)
├── Contents/header.xml     # 스타일
└── content.xml             # 구형 hwp의 본문
```

본문의 계층:

```
hp:tbl (표)
└── hp:tr (행)
    └── hp:tc (셀) + hp:cellAddr(colAddr, rowAddr) + hp:cellSpan
        └── hp:subList
            └── hp:p (문단)          ← 줄바꿈 = 문단 하나
                ├── hp:run
                │   └── hp:t (텍스트) ← 빈 셀에는 이 요소가 없음
                └── hp:linesegarray   ← 렌더링된 줄 수 캐시
```

자세한 내용은 [`references/hwpx-structure.md`](./references/hwpx-structure.md).

## 문제 해결

### `WinError 32` — 다른 프로세스가 파일을 사용 중

한글에서 해당 문서를 열어둔 상태다. 어느 문서가 잠겨 있는지 먼저 확인한다:

```powershell
Get-Process Hwp | Select-Object Id, MainWindowTitle
```

`MainWindowTitle`에 파일명이 나온다. 사용자에게 그 문서를 닫아달라고 요청한다.
**프로세스를 임의로 종료하면 사용자의 미저장 작업이 사라진다.**

### 내용이 엉뚱한 셀에 들어감 / 한 줄로 뭉쳐 나옴

표 작업에 `replace_text()`를 사용한 경우다. 위의 **표 작업 규칙** 참조.

- 원인 1: 빈 셀에는 `<hp:t>`가 없어 텍스트 검색이 라벨 셀에 착지
- 원인 2: `\n`은 줄바꿈이 아님 + `linesegarray` 캐시가 남아 한 줄로 렌더링
- 복구: 오염된 파일 위에 재편집하지 말고 **백업에서 복원한 뒤** 좌표 기반으로 재작성

### `잘못된 HWP 파일 형식입니다`

**거의 항상 바이너리 `.hwp` v5다. 손상된 파일이 아니다.** 위의 **0단계**를
건너뛴 경우다. `to_hwpx()`로 변환한 뒤 다시 시도한다.

### `content.xml을 찾을 수 없습니다`

구형 `.hwp`와 `.hwpx`의 내부 경로가 다르다. 핸들러는 `content.xml`을 먼저 찾고
없으면 `Contents/section0.xml`을 사용한다. 둘 다 없으면 손상되었거나 암호화된
문서일 수 있다.

### 보안 승인 대화상자가 뜬다 (또는 스크립트가 아무 출력 없이 멈춤)

> 한글을 이용하여 위 파일에 접근하려는 시도(파일의 손상 또는 유출의 위험 등)가
> 있습니다. `[접근 허용]` `[모두 허용]` `[허용 안 함]` `[모두 안 함]`

`RegisterModule('FilePathCheckDLL', 'FilePathCheckerModule')`을 `Open`/`SaveAs`
이전에 호출하지 않았다. 한글 창이 보이면 대화상자가 파일마다 뜨고, 숨겨져 있으면
**보이지 않는 채로** 떠서 스크립트가 영구 대기한다. 같은 원인, 같은 해결이다.

대화상자에서 "모두 허용"을 눌러도 다음 실행에 또 뜬다. 근본 해결은 등록뿐이다.

1. 등록 상태를 먼저 확인한다:

   ```bash
   uv run --python 3.12 --link-mode=copy --with pywin32 python scripts/hwp_com.py --check
   ```

   `등록 완료`가 나오는데도 대화상자가 뜬다면, **`RegisterModule`을 부르지 않는
   코드가 섞여 있다는 뜻이다.** 직접 작성한 COM 스니펫이나
   `New-Object -ComObject`를 찾아 위의 "COM을 쓸 때의 절대 규칙"대로 고친다.

2. `미등록`이면 등록한다(한 번만, 영구히 유지된다). DLL이 없으면 자동으로
   내려받는다:

   ```bash
   uv run --python 3.12 --link-mode=copy --with pywin32 python scripts/hwp_com.py --setup
   ```

3. `RegisterModule` 자체가 `False`를 반환하면 DLL 로드 실패다. 한글과 DLL의
   **비트수가 같아야 한다** — 한글이 32비트(`C:\Program Files (x86)\Hnc\...`)면
   DLL도 32비트여야 한다. `regsvr32`로는 등록되지 않는다(`DllRegisterServer` 없음).

`hwp_com.HwpApp`은 이 전 과정을 자동 처리하고, 등록이 안 된 상태면 `Open` 이전에
`HwpSecurityModuleError`를 던져 대화상자 앞에서 멈추는 일을 막는다.

`Quit()` 직후 새 `Dispatch()`를 호출해도 같은 증상이 난다 — 한 인스턴스를
재사용할 것. **Hwp 프로세스를 반복 강제 종료하면 COM이 통째로 응답 불능이 된다.**
복구하려면 사용자에게 한글을 직접 한 번 실행했다 닫아달라고 요청한다.

### 텍스트가 제대로 추출되지 않음

- 글상자·표 안의 텍스트는 문서 순서대로 이어져 나온다
- 숨겨진 텍스트는 제외된다
- 암호화된 문서는 처리할 수 없다

## 제한사항

- ❌ 암호화된 문서
- ❌ 매크로
- ⚠️ 매우 복잡한 표 구조에서 일부 기능 제한
- ⚠️ 바이너리 `.hwp`는 한글 설치 필요 (변환에만; 변환 후 작업은 한글 없이 가능)
- ⚠️ 한컴 Assistant MCP 서버는 호출 앱을 검사해 에이전트를 거부한다 — 쓰지 말 것
  (자세한 내용은 [`references/com-automation.md`](./references/com-automation.md))
- ✅ 텍스트 읽기/수정, 표 셀 기입, 서식 유지, 자동 백업
- ✅ COM 폴백으로 `.hwp` ↔ `.hwpx` 변환, PDF 내보내기
