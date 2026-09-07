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

### 2. 보안 모듈 등록 — 생략하면 대화상자가 뜨거나 멈춘다

`RegisterModule` 없이 `Open()`이나 `SaveAs()`를 호출하면 한글이 **파일마다,
저장마다** 보안 승인 대화상자를 띄운다:

> 한글을 이용하여 위 파일에 접근하려는 시도(파일의 손상 또는 유출의 위험 등)가
> 있습니다. 정상적인 작업 과정에만 접근을 허용하십시오.
> `[접근 허용]` `[모두 허용]` `[허용 안 함]` `[모두 안 함]`

한글 창이 보이는 상태면 사용자가 매번 클릭해야 하고, 숨겨진 상태(`Visible=False`,
자동화의 기본값)면 **화면에 아무것도 안 보이는 채로** 떠서 스크립트가 **영구 정지**한다.
원인을 찾기 어려운 쪽은 후자지만 둘은 같은 문제다.

**대화상자에서 "모두 허용"을 눌러도 다음 실행에 또 뜬다.** 그 선택은 저장되지 않는다.
없애는 방법은 등록뿐이다.

```python
h = win32com.client.Dispatch('HWPFrame.HwpObject')
if not h.RegisterModule('FilePathCheckDLL', 'FilePathCheckerModule'):
    raise RuntimeError('보안 모듈 등록 실패 — 이대로 진행하면 대화상자가 뜬다')
```

두 가지를 모두 지켜야 한다:

1. **인스턴스마다** `RegisterModule`을 `Open`/`SaveAs` **이전에** 호출한다.
   객체 단위 설정이므로 `Dispatch`를 새로 할 때마다 다시 해야 한다.
   **반환값을 확인한다.** `False`면 DLL을 못 불러온 것이고, 그대로 진행하면
   대화상자가 뜬다.
2. **DLL을 레지스트리에 등록한다** (머신당 한 번, 영구히 유지된다).

`scripts/hwp_com.py`가 둘 다 처리한다. `HwpApp` 생성 시 등록을 확인하고,
안 되어 있으면 `Open` 이전에 `HwpSecurityModuleError`를 던진다 — 보이지 않는
대화상자 앞에서 멈추는 것보다 낫다.

```bash
# 확보 + 등록 (DLL이 없으면 자동으로 내려받는다)
uv run --python 3.12 --link-mode=copy --with pywin32 python hwp_com.py --setup

# 상태 확인 (내려받지 않는다 - 읽기 전용)
uv run --python 3.12 --link-mode=copy --with pywin32 python hwp_com.py --check
```

#### 새 환경에서는 DLL도 자동으로 확보한다

`fetch_dll()`이 `uv`로 **일회성 환경**에 `pyhwpx`를 받아 DLL만 고정 경로로 복사한다.
`pyhwpx`를 호출자 환경에 설치하지 않는다 — 필요한 건 DLL 하나뿐이고, 확보 후에는
`pyhwpx`도 네트워크도 필요 없다.

`ensure_security_module()`이 DLL을 어디에서도 못 찾으면 이 경로를 자동으로 탄다.
**새 PC에서 사용자에게 설치 명령을 안내할 필요가 없다.** PowerShell의
`Register-HwpSecurityModule`도 같은 일을 한다(`hwp_com.py --setup`을 호출).

- 최초 1회만 네트워크가 필요하다(1~2분).
- 자식 프로세스에는 `HWP_COM_DLL_BOOTSTRAP=1`을 넘겨 재귀를 막는다.
- 한 프로세스에서 두 번 시도하지 않는다(`_FETCH_TRIED`). 실패마다 수백 초를 쓰면
  안 된다.
- `--check`는 내려받지 않는다. 진단은 읽기 전용이어야 한다.
- `uv`는 PATH에 없으면 `%USERPROFILE%\.local\bin\uv.exe`와
  `%LOCALAPPDATA%\uv\bin\uv.exe`도 본다.

실패는 두 경우뿐이고 예외 메시지가 어느 쪽인지 알려준다: `uv`가 없거나
(`winget install astral-sh.uv`), 오프라인이거나. 오프라인이면 DLL을 고정 경로에
직접 두면 된다.

#### 등록의 내용 (`ensure_security_module()`이 하는 일)

1. `FilePathCheckerModule.dll`을 **고정 경로**에 배치한다:
   `%LOCALAPPDATA%\HwpAutomation\FilePathCheckerModule.dll`

   DLL은 `pyhwpx` 패키지에 동봉되어 있다:

   ```bash
   uv run --with pyhwpx python -c "import pyhwpx,os;print(os.path.dirname(pyhwpx.__file__))"
   ```

   **uv의 임시 가상환경 경로를 레지스트리에 넣지 말 것.** 그 경로는 실행마다
   바뀌므로 다음 실행에 무효가 되고 대화상자가 다시 뜬다. 반드시 복사해서
   고정 경로를 등록한다.

2. 레지스트리 값 등록 — **`REG_SZ` 값이며, 키가 아니다**

   | 키 | 값 이름 | 값 |
   |---|---|---|
   | `HKCU\Software\HNC\HwpAutomation\Modules` | `FilePathCheckerModule` | DLL 전체 경로 |
   | `HKCU\Software\Hnc\HwpUserAction\Modules` | `FilePathCheckerModule` | 동일 |

   양쪽 모두 넣는다. 한글 버전에 따라 참조하는 키가 다르다.

   **키가 없으면 만든다.** HKCU 아래의 평범한 키이고, 값이 없으면 대화상자가
   뜨는 것 말고는 얻을 게 없다. (한글을 한 번 실행하면 한글이 직접 만들지만,
   그걸 사용자에게 시킬 필요는 없다. `winreg.CreateKeyEx` / PowerShell
   `New-Item -Force`로 만들고, 써넣은 값을 되읽어 검증한다.)

**`regsvr32`는 쓰지 말 것.** 이 DLL에는 `DllRegisterServer` 진입점이 없어서
`exit code 4`로 실패한다. 관리자 권한으로도 안 된다. 위의 레지스트리 방식이 유일하다.

#### 등록했는데도 대화상자가 뜬다면

| 확인할 것 | 방법 |
|---|---|
| `RegisterModule`을 안 부르는 코드가 섞여 있다 | 가장 흔한 원인. 직접 쓴 COM 스니펫, `New-Object -ComObject`, 다른 스크립트를 모두 훑는다 |
| 레지스트리에 등록된 DLL 경로가 이미 없다 | `--check`가 경로 존재까지 검사한다 (uv 임시 경로를 등록한 경우) |
| 한글과 DLL의 비트수가 다르다 | 한글이 `C:\Program Files (x86)\Hnc\...`면 32비트. DLL도 32비트여야 `RegisterModule`이 `True`를 반환한다 |
| ProgID가 틀렸다 | `HWPFrame.HwpObject`가 맞다. `Hancom.HwpObject`는 **존재하지 않는다** |

비트수 확인 (PE 헤더의 machine 필드):

```powershell
$clsid = (Get-ItemProperty 'HKLM:\SOFTWARE\Classes\HWPFrame.HwpObject\CLSID').'(default)'
# Wow6432Node 아래에 있으면 한글이 32비트다
Test-Path "HKLM:\SOFTWARE\Classes\Wow6432Node\CLSID\$clsid"
```

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

### `Could not add module ... circular import`은 실패가 아니다

첫 `Dispatch()`에서 pywin32가 타입 라이브러리 캐시를 만들며 stderr에 이런 걸 뱉는다:

```
Rebuilding cache of generated files for COM support...
Could not add module (IID('{...}'), 0, 1, 0) - <class 'ImportError'>:
    cannot import name '_get_good_object_' from partially initialized module 'win32com.client'
Done.
```

`Dispatch`는 늦은 바인딩이라 이 캐시가 없어도 동작한다. **작업은 정상적으로
끝난다.** 새 uv 환경의 첫 실행에서 자주 보인다. 오류로 보고하지 말 것.

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

# Open/SaveAs 이전에. 반환값을 확인하지 않으면 대화상자에 걸린 걸 알 수 없다.
if not h.RegisterModule('FilePathCheckDLL', 'FilePathCheckerModule'):
    raise RuntimeError('보안 모듈 미등록 — hwp_com.py --setup 을 먼저 실행할 것')

h.Open(src, 'HWP', 'forceopen:true')
text = h.GetTextFile('TEXT', '')
h.SaveAs(dst, 'HWPX', '')       # 포맷: 'HWP' | 'HWPX' | 'PDF' | 'TEXT'

h.Clear(1)
h.Quit()
```

경로에 한글이 포함된 환경(`C:\Users\홍길동`)에서는 셸에 경로를 리터럴로 쓰면
인코딩이 깨진다. `os.environ['TEMP']` 등 **환경변수를 통해 얻는다.**
