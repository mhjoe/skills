# COM 폴백 — 한글 프로그램을 직접 제어해야 할 때

`hwp-edit`의 기본 경로는 **XML 직접 처리**다(`hwp_handler.py`). 한글 프로그램이
필요 없고, 빠르고, 서식이 보존된다. **먼저 그 방법을 쓴다.**

이 문서는 XML 경로가 **구조적으로 불가능한 경우**에만 쓰는 폴백을 다룬다.
아래 내용은 Windows 11 + 한컴오피스 2024 한글(13.0) 환경에서 전 과정을 실제로
실행해 검증했다.

## 언제 COM이 필요한가

| 상황 | XML 경로 | COM 필요 |
|---|---|---|
| `.hwpx` 읽기/수정/표 기입 | ✅ 가능 | 불필요 |
| HWPML로 저장된 `.hwp` (내부가 ZIP) | ✅ 가능 | 불필요 |
| **바이너리 `.hwp` v5 (한글 기본 저장 형식)** | ❌ **불가능** | ✅ 변환에 필요 |
| PDF 변환, 인쇄, 페이지 수 계산 | ❌ 불가능 | ✅ |
| 맞춤법 검사, 차례 갱신 등 한글 기능 | ❌ 불가능 | ✅ |

### 바이너리 `.hwp`를 구분하는 법

`.hwp` 확장자는 두 가지 서로 다른 포맷을 가리킨다. **파일 시그니처로 판별한다.**

```python
sig = open(path, 'rb').read(4)
# b'PK\x03\x04'      → ZIP  → hwp_handler.py로 처리 가능
# b'\xd0\xcf\x11\xe0' → OLE 복합파일 → 바이너리 v5, COM 변환 필요
```

바이너리 `.hwp`를 `HwpDocument()`에 넘기면 이렇게 실패한다:

```
ValueError: 잘못된 HWP 파일 형식입니다: ...\문서.hwp
```

이는 손상된 파일이라는 뜻이 **아니다.** `hwp_handler._extract_hwp()`가
`zipfile.ZipFile`로 여는데 OLE 파일이라 `BadZipFile`이 난 것뿐이다.
**"손상됐다"고 사용자에게 보고하지 말 것.** 아래 변환을 거치면 된다.

## 권장 패턴 — 변환 후 XML 경로로 복귀

COM으로 편집까지 하지 말고, **형식 변환에만 쓰고 곧바로 `hwp_handler`로 넘긴다.**
COM 편집은 느리고 함정이 많다.

```
바이너리 .hwp  ──COM 변환──▶  .hwpx  ──hwp_handler──▶  읽기·표 기입·저장
```

```python
# scripts/hwp_com.py 사용
from hwp_com import to_hwpx
hwpx = to_hwpx("원본.hwp")        # → "원본.hwpx" 경로 반환 (이미 hwpx면 그대로 반환)

from hwp_handler import HwpDocument
doc = HwpDocument(hwpx)
print(doc.dump_tables())
...
```

사용자에게 결과물을 원래의 `.hwp`로 돌려줘야 한다면 마지막에 다시 변환한다
(`to_hwp()`). **다만 변환은 왕복할 때마다 미세한 서식 손실 위험이 있으므로,
가능하면 `.hwpx`로 전달하고 그 사실을 알린다.**

## 환경 준비

### 1. 실행 방법 — `pip` 대신 `uv`

Python이 uv로 관리되는 환경에서는 `pip install`이 다음 오류로 실패한다:

```
This Python installation is managed by uv and should not be modified.
```

`pip` 명령 자체가 없을 수도 있다. **항상 `uv run --with`로 실행한다.**

```bash
uv run --python 3.12 --link-mode=copy --with pywin32 python 스크립트.py
uv run --python 3.12 --link-mode=copy --with lxml   python 스크립트.py   # XML 경로도 동일
```

`--link-mode=copy`가 없으면 uv 캐시에서 `액세스가 거부되었습니다 (os error 5)`가
날 수 있다(백신·동기화 폴더 간섭). 붙여두는 편이 안전하다.

### 2. 보안 모듈 등록 — 생략하면 반드시 멈춘다

`RegisterModule` 없이 `Open()`이나 `SaveAs()`를 호출하면 한글이 **보이지 않는**
보안 승인 대화상자를 띄우고 스크립트가 **영구 정지**한다. 화면에 아무것도 안 보여서
원인을 찾기 어렵다.

```python
h = win32com.client.Dispatch('HWPFrame.HwpObject')
h.RegisterModule('FilePathCheckDLL', 'FilePathCheckerModule')   # 반드시 Open/SaveAs 이전
```

이 호출이 동작하려면 사전 등록이 1회 필요하다(`scripts/hwp_com.py`의
`ensure_security_module()`이 자동 수행):

1. `FilePathCheckerModule.dll`을 고정 경로에 배치
   (`pyhwpx` 패키지에 동봉되어 있다: `uv run --with pyhwpx python -c "import pyhwpx,os;print(os.path.dirname(pyhwpx.__file__))"`)
2. 레지스트리 값 등록 — **`REG_SZ` 값이며, 키가 아니다**
   - `HKCU\Software\HNC\HwpAutomation\Modules` → `FilePathCheckerModule` = DLL 전체 경로
   - `HKCU\Software\Hnc\HwpUserAction\Modules` → 동일 (양쪽 모두 넣어두면 안전)

**`regsvr32`는 쓰지 말 것.** 이 DLL에는 `DllRegisterServer` 진입점이 없어서
`exit code 4`로 실패한다. 관리자 권한으로도 안 된다. 등록은 위의 레지스트리
방식이 유일하다.

두 레지스트리 키는 **한글이 직접 만드는 키다.** 없다면 새로 만들지 말고
사용자에게 한글을 한 번 실행해달라고 요청한 뒤 다시 확인한다.

## 함정 (모두 실제로 겪은 것)

### `Quit()` 직후 새 `Dispatch()`는 멈춘다

COM 서버가 종료되는 중이라 새 연결이 무한 대기한다.

```python
# ❌ 멈춘다
h.Quit()
h2 = Dispatch('HWPFrame.HwpObject')   # 여기서 영구 정지

# ✅ 한 인스턴스를 재사용
h.Clear(1)
h.Open(다음파일, 'HWP', 'forceopen:true')
```

### 텍스트 추출에 `InitScan`/`GetText` 루프를 쓰지 말 것

`GetText()`가 종료 상태를 반환하지 않아 **무한 루프**에 빠진다.

```python
# ❌ 무한 루프
h.InitScan(option=0x07)
while True:
    st, t = h.GetText()
    if st == 0: break

# ✅
text = h.GetTextFile('TEXT', '')
```

### Hwp 프로세스를 강제 종료하지 말 것

반복 강제 종료하면 COM이 통째로 응답 불능이 되어 `Dispatch()`부터 멈춘다.
**복구 방법: 사용자에게 한글을 직접 한 번 실행했다 닫아달라고 요청한다.**
재부팅까지는 필요 없다.

작업이 끝나면 `h.Clear(1)` 후 `h.Quit()`으로 정상 종료한다. 그래도 남는
인스턴스는 **창 제목이 비어 있는 것만** 정리한다 — 제목이 있으면 사용자가
열어둔 문서이고, 죽이면 미저장 작업이 사라진다.

```powershell
Get-Process Hwp | Select-Object Id, MainWindowTitle
```

### 콘솔의 한글 깨짐은 데이터 문제가 아니다

터미널 코드페이지 때문에 출력만 깨져 보인다. 확인이 필요하면 UTF-8 파일로
써서 읽는다.

```python
open(out, 'w', encoding='utf-8').write(text)
```

## 한컴 Assistant MCP 서버는 쓸 수 없다

`C:\Program Files (x86)\HncTools\McpServers\`에 설치되어 있더라도 **Claude Code나
일반 에이전트에서는 동작하지 않는다.** 호출한 앱을 검사해 허용 목록에 없으면
스스로 종료한다:

```
ERROR - MCP Server is being terminated because it is being run by an unauthorized app.
```

설치 문제가 아니라 한컴의 정책이다. **등록·재시도에 시간을 쓰지 말 것.**
MCP 서버로 등록해두면 세션마다 `CONNECTION_CLOSED` 오류만 반복된다.

## 검증된 최소 예제

```python
import os, win32com.client as w

h = w.Dispatch('HWPFrame.HwpObject')
h.RegisterModule('FilePathCheckDLL', 'FilePathCheckerModule')

h.Open(src, 'HWP', 'forceopen:true')
text = h.GetTextFile('TEXT', '')
h.SaveAs(dst, 'HWPX', '')       # 포맷: 'HWP' | 'HWPX' | 'PDF' | 'TEXT'

h.Clear(1)
h.Quit()
```

경로에 한글이 포함된 환경(`C:\Users\홍길동`)에서는 셸에 경로를 리터럴로 쓰면
인코딩이 깨진다. `os.environ['TEMP']` 등 **환경변수를 통해 얻는다.**
