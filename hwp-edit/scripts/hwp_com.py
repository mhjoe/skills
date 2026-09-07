"""
hwp_com.py — hwp-edit 스킬의 COM 폴백 헬퍼.

기본 경로는 hwp_handler.py(XML 직접 처리)다. 이 모듈은 XML로 처리할 수 없는
경우에만 쓴다 — 주로 **바이너리 .hwp v5를 .hwpx로 변환**하기 위해서다.

실행 (pip 아님):
    uv run --python 3.12 --link-mode=copy --with pywin32 python 스크립트.py

자세한 배경과 함정은 references/com-automation.md 참조.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

__all__ = [
    "detect_format", "needs_conversion", "ensure_security_module",
    "security_module_status", "HwpSecurityModuleError",
    "HwpApp", "shared_app", "to_hwpx", "to_hwp", "to_pdf", "get_text",
]

ZIP_SIG = b"PK\x03\x04"
OLE_SIG = b"\xd0\xcf\x11\xe0"

_REG_PATHS = (
    r"Software\HNC\HwpAutomation\Modules",
    r"Software\Hnc\HwpUserAction\Modules",
)


# --------------------------------------------------------------------------
# 포맷 판별
# --------------------------------------------------------------------------

def detect_format(path: str | os.PathLike) -> str:
    """파일 시그니처로 실제 포맷을 판별한다.

    Returns: 'zip'(hwpx 또는 HWPML .hwp) | 'ole'(바이너리 .hwp v5) | 'unknown'

    확장자는 신뢰할 수 없다. .hwp가 ZIP일 수도, OLE일 수도 있다.
    """
    with open(path, "rb") as f:
        sig = f.read(4)
    if sig == ZIP_SIG:
        return "zip"
    if sig == OLE_SIG:
        return "ole"
    return "unknown"


def needs_conversion(path: str | os.PathLike) -> bool:
    """hwp_handler.py로 열 수 없어 COM 변환이 필요한 파일인가."""
    return detect_format(path) == "ole"


# --------------------------------------------------------------------------
# 보안 모듈 — 등록되지 않으면 Open/SaveAs 때마다 보안 승인 대화상자가 뜬다
# --------------------------------------------------------------------------
#
# 대화상자 문구:
#   "한글을 이용하여 위 파일에 접근하려는 시도(파일의 손상 또는 유출의 위험 등)가
#    있습니다. 정상적인 작업 과정에만 접근을 허용하십시오."
#   [접근 허용] [모두 허용] [허용 안 함] [모두 안 함]
#
# 이 창은 파일 하나를 열 때마다, 저장할 때마다 다시 뜬다. 한글 창이 숨겨진
# 상태(Visible=False)면 화면에 안 보이는 채로 떠서 스크립트가 영구 정지한다.
#
# 없애는 방법은 하나뿐이다: FilePathCheckerModule.dll을 레지스트리에 등록하고
# COM 인스턴스마다 RegisterModule()을 Open/SaveAs 이전에 호출한다.


class HwpSecurityModuleError(RuntimeError):
    """보안 모듈이 등록되지 않아 대화상자가 뜰 상태. Open 전에 미리 던진다."""


_STABLE_DLL = Path(os.environ.get("LOCALAPPDATA", "")) / "HwpAutomation" / "FilePathCheckerModule.dll"


def _dll_candidates():
    """FilePathCheckerModule.dll이 있을 만한 곳을 우선순위대로."""
    yield _STABLE_DLL
    try:
        import pyhwpx  # noqa: F401  (설치되어 있을 때만)

        yield Path(pyhwpx.__file__).parent / "FilePathCheckerModule.dll"
    except ImportError:
        pass
    for root in (
        os.environ.get("ProgramFiles(x86)"),
        os.environ.get("ProgramFiles"),
    ):
        if not root:
            continue
        base = Path(root) / "Hnc"
        if base.is_dir():
            # 설치 버전에 따라 하위 경로가 달라 glob으로 찾는다.
            for hit in base.glob("**/FilePathCheckerModule.dll"):
                yield hit


def _find_dll() -> Path | None:
    """DLL을 찾아 고정 경로(LOCALAPPDATA)에 복사하고 그 경로를 반환한다.

    고정 경로에 두는 이유: uv의 임시 가상환경에 있는 pyhwpx 경로는 실행마다
    바뀌어서, 레지스트리에 그 경로를 넣으면 다음 실행에 무효가 된다.
    """
    for cand in _dll_candidates():
        if not cand.exists():
            continue
        if cand == _STABLE_DLL:
            return cand
        try:
            _STABLE_DLL.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(cand, _STABLE_DLL)
            return _STABLE_DLL
        except OSError:
            return cand  # 복사 실패 시 원본 경로라도 쓴다
    return None


def security_module_status() -> dict:
    """등록 상태를 진단한다. {'dll': 경로|None, 'registered': [키...], 'missing': [키...]}"""
    import winreg

    dll = None
    for cand in _dll_candidates():
        if cand.exists():
            dll = cand
            break

    registered, missing = [], []
    for path in _REG_PATHS:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_READ) as key:
                value, _ = winreg.QueryValueEx(key, "FilePathCheckerModule")
            if value and Path(value).exists():
                registered.append(path)
            else:
                missing.append(path)
        except OSError:
            missing.append(path)
    return {"dll": dll, "registered": registered, "missing": missing}


def ensure_security_module() -> bool:
    """DLL을 고정 경로에 배치하고 레지스트리에 등록한다. 성공 여부를 반환.

    - 키가 없으면 **만든다.** HKCU 아래의 평범한 키이고, 값이 없으면 대화상자가
      뜨는 것 말고는 얻을 게 없다. (한글을 한 번 실행하면 한글이 직접 만들지만,
      그걸 사용자에게 시키는 대신 우리가 만든다.)
    - regsvr32는 쓰지 않는다 — 이 DLL에는 DllRegisterServer 진입점이 없어
      exit code 4로 실패한다. 레지스트리 REG_SZ 값 등록이 유일한 방법이다.
    - 값은 써넣은 뒤 되읽어 검증한다.
    """
    import winreg

    dll = _find_dll()
    if dll is None:
        return False

    ok = False
    for path in _REG_PATHS:
        try:
            with winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_READ | winreg.KEY_WRITE
            ) as key:
                winreg.SetValueEx(key, "FilePathCheckerModule", 0, winreg.REG_SZ, str(dll))
                back, _ = winreg.QueryValueEx(key, "FilePathCheckerModule")
            if back == str(dll):
                ok = True
        except OSError:
            continue
    return ok


_DLL_HELP = r"""보안 모듈(FilePathCheckerModule.dll)을 등록할 수 없습니다.
등록되지 않으면 파일을 열고 저장할 때마다 한글 보안 승인 대화상자가 뜨고,
한글 창이 숨겨져 있으면 보이지 않는 채로 떠서 스크립트가 멈춥니다.

DLL은 pyhwpx 패키지에 동봉되어 있습니다. 아래처럼 pyhwpx를 포함해 한 번만
실행하면 DLL이 %LOCALAPPDATA%\HwpAutomation\ 에 복사되고 등록됩니다:

    uv run --python 3.12 --link-mode=copy --with pyhwpx --with pywin32         python hwp_com.py --setup

이후 실행에는 pyhwpx가 필요 없습니다."""


# --------------------------------------------------------------------------
# COM 세션
# --------------------------------------------------------------------------

class HwpApp:
    """한글 COM 인스턴스. context manager로 쓴다.

        with HwpApp() as app:
            app.open("문서.hwp")
            app.save_as("문서.hwpx", "HWPX")

    생성 시 보안 모듈을 등록하고 RegisterModule()을 호출한다. 등록에 실패하면
    Open/SaveAs로 넘어가지 않고 즉시 HwpSecurityModuleError를 던진다 — 보이지
    않는 보안 대화상자 앞에서 영구 정지하는 것보다 낫다.

    Quit() 직후 새 Dispatch()는 영구 정지한다. 여러 파일을 처리할 때는
    인스턴스를 새로 만들지 말고 shared_app()을 쓰거나 clear() 후 재사용한다.
    """

    def __init__(self, register_module: bool = True, visible: bool = False):
        import win32com.client as w

        if register_module and not ensure_security_module():
            raise HwpSecurityModuleError(_DLL_HELP)

        self.hwp = w.Dispatch("HWPFrame.HwpObject")

        if register_module:
            # 이 호출을 빠뜨리면 파일을 열고 저장할 때마다 보안 승인
            # 대화상자가 뜬다. 한글 창이 숨겨져 있으면 화면에 보이지도 않는
            # 채로 떠서 스크립트가 영구 정지한다. Open/SaveAs 이전에 필수.
            if not self.hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule"):
                st = security_module_status()
                raise HwpSecurityModuleError(
                    "RegisterModule이 실패했습니다 (DLL 로드 불가)." "\n"
                    f"  DLL       : {st['dll']}" "\n"
                    f"  등록된 키 : {st['registered'] or '없음'}" "\n"
                    f"  누락된 키 : {st['missing'] or '없음'}" "\n"
                    "DLL과 한글의 비트수가 맞는지 확인하세요 "
                    "(한글이 32비트면 DLL도 32비트여야 합니다)." "\n\n" + _DLL_HELP
                )

        self._set_visible(visible)

    def _set_visible(self, visible: bool) -> None:
        """한글 창 표시 여부. 실패해도 작업에는 영향이 없으므로 조용히 넘긴다."""
        try:
            self.hwp.XHwpWindows.Item(0).Visible = visible
        except Exception:
            pass

    def __enter__(self) -> "HwpApp":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def open(self, path: str | os.PathLike, fmt: str = "HWP") -> None:
        self.hwp.Open(str(Path(path).resolve()), fmt, "forceopen:true")

    def save_as(self, path: str | os.PathLike, fmt: str = "HWPX") -> str:
        out = str(Path(path).resolve())
        self.hwp.SaveAs(out, fmt, "")
        return out

    def text(self) -> str:
        """문서 전체 텍스트. InitScan/GetText 루프는 무한 루프에 빠지므로 쓰지 않는다.

        GetTextFile은 빈 문서에서 None을 반환한다 - 호출자가 len()을 쓸 수 있게 ""로 바꾼다.
        """
        return self.hwp.GetTextFile("TEXT", "") or ""

    def clear(self) -> None:
        """다음 문서를 열기 전에 현재 문서를 비운다(저장 여부 묻지 않음)."""
        self.hwp.Clear(1)

    def close(self) -> None:
        try:
            self.hwp.Clear(1)
            self.hwp.Quit()
        except Exception:
            pass


_SHARED: "HwpApp | None" = None


def shared_app() -> HwpApp:
    """프로세스당 하나의 HwpApp을 재사용한다.

    변환을 여러 번 하면서 매번 Dispatch/Quit을 반복하면 (1) 인스턴스마다
    RegisterModule을 다시 해야 하고 (2) Quit 직후 Dispatch가 영구 정지하는
    문제를 만난다. 여러 파일을 처리하는 스크립트는 이 함수를 쓴다.
    """
    global _SHARED
    if _SHARED is None:
        _SHARED = HwpApp()
    else:
        _SHARED.clear()
    return _SHARED


def close_shared() -> None:
    """shared_app()이 만든 인스턴스를 정상 종료한다(스크립트 끝에서 한 번)."""
    global _SHARED
    if _SHARED is not None:
        _SHARED.close()
        _SHARED = None


# --------------------------------------------------------------------------
# 편의 함수
# --------------------------------------------------------------------------

def _convert(src, dst, src_fmt, dst_fmt) -> str:
    # 인스턴스를 매번 새로 만들지 않는다 — Quit 직후 Dispatch가 영구 정지하고,
    # 인스턴스마다 RegisterModule을 다시 해야 한다. shared_app()이 둘 다 처리한다.
    app = shared_app()
    app.open(src, src_fmt)
    return app.save_as(dst, dst_fmt)


def to_hwpx(src: str | os.PathLike, dst: str | os.PathLike | None = None) -> str:
    """바이너리 .hwp를 .hwpx로 변환한다. 이미 ZIP 기반이면 원본 경로를 그대로 반환.

    변환 후에는 hwp_handler.HwpDocument로 넘겨서 작업한다.
    """
    src = Path(src)
    if detect_format(src) == "zip":
        return str(src)
    dst = Path(dst) if dst else src.with_suffix(".hwpx")
    return _convert(src, dst, "HWP", "HWPX")


def to_hwp(src: str | os.PathLike, dst: str | os.PathLike | None = None) -> str:
    """.hwpx를 바이너리 .hwp로 되돌린다. 왕복 변환은 서식 손실 위험이 있으므로
    꼭 필요할 때만 쓰고, 사용자에게 알린다."""
    src = Path(src)
    dst = Path(dst) if dst else src.with_suffix(".hwp")
    return _convert(src, dst, "HWP", "HWP")


def to_pdf(src: str | os.PathLike, dst: str | os.PathLike | None = None) -> str:
    """PDF로 내보낸다. XML 경로로는 불가능한 작업이다."""
    src = Path(src)
    dst = Path(dst) if dst else src.with_suffix(".pdf")
    return _convert(src, dst, "HWP", "PDF")


def get_text(src: str | os.PathLike) -> str:
    """포맷과 무관하게 텍스트를 추출한다(바이너리 .hwp 포함)."""
    app = shared_app()
    app.open(src)
    return app.text()


def _print_status() -> bool:
    st = security_module_status()
    print(f"DLL       : {st['dll'] or '찾을 수 없음'}")
    print(f"등록된 키 : {st['registered'] or '없음'}")
    print(f"누락된 키 : {st['missing'] or '없음'}")
    ok = bool(st["dll"]) and not st["missing"]
    if ok:
        print("결과      : 등록 완료. 보안 대화상자가 뜨지 않습니다.")
    else:
        print("결과      : 미등록. 파일을 열거나 저장할 때마다 보안 대화상자가 뜹니다.")
    return ok


if __name__ == "__main__":
    import sys

    # 콘솔 코드페이지가 cp949면 일부 문자에서 UnicodeEncodeError가 난다.
    # 출력이 깨지는 건 데이터 문제가 아니므로 죽이지 말고 대체 문자로 넘긴다.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass

    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        print("사용법:")
        print("  python hwp_com.py --setup          보안 모듈 등록 (한 번만, 영구)")
        print("  python hwp_com.py --check          등록 상태만 확인")
        print("  python hwp_com.py <파일>            파일 포맷 + 등록 상태 확인")
        sys.exit(0)

    if args[0] == "--check":
        sys.exit(0 if _print_status() else 1)

    if args[0] == "--setup":
        registered = ensure_security_module()
        ok = _print_status()
        if not registered or not ok:
            print()
            print(_DLL_HELP)
            sys.exit(1)
        sys.exit(0)

    target = args[0]
    print(f"format   : {detect_format(target)}")
    print(f"needs COM: {needs_conversion(target)}")
    ensure_security_module()
    _print_status()
