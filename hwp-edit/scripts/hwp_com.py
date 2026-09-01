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
    "HwpApp", "to_hwpx", "to_hwp", "to_pdf", "get_text",
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
# 보안 모듈 (없으면 Open/SaveAs가 보이지 않는 대화상자에서 영구 정지한다)
# --------------------------------------------------------------------------

def _find_dll() -> Path | None:
    """FilePathCheckerModule.dll을 찾는다. pyhwpx 패키지에 동봉되어 있다."""
    stable = Path(os.environ["LOCALAPPDATA"]) / "HwpAutomation" / "FilePathCheckerModule.dll"
    if stable.exists():
        return stable
    try:
        import pyhwpx  # noqa: F401  (설치되어 있을 때만)
        cand = Path(pyhwpx.__file__).parent / "FilePathCheckerModule.dll"
        if cand.exists():
            stable.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(cand, stable)
            return stable
    except ImportError:
        pass
    return None


def ensure_security_module() -> bool:
    """보안 모듈 DLL을 배치하고 레지스트리에 등록한다. 성공 여부를 반환.

    regsvr32는 쓰지 않는다 — 이 DLL에는 DllRegisterServer 진입점이 없어
    exit code 4로 실패한다. 레지스트리 REG_SZ 값 등록이 유일한 방법이다.
    """
    import winreg

    dll = _find_dll()
    if dll is None:
        return False

    ok = False
    for path in _REG_PATHS:
        try:
            # 키를 새로 만들지 않는다. 한글이 만드는 키이며, 없다면
            # 사용자에게 한글을 한 번 실행해달라고 요청해야 한다.
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_WRITE)
        except FileNotFoundError:
            continue
        try:
            winreg.SetValueEx(key, "FilePathCheckerModule", 0, winreg.REG_SZ, str(dll))
            ok = True
        finally:
            winreg.CloseKey(key)
    return ok


# --------------------------------------------------------------------------
# COM 세션
# --------------------------------------------------------------------------

class HwpApp:
    """한글 COM 인스턴스. 반드시 context manager로 쓴다.

        with HwpApp() as app:
            app.open("문서.hwp")
            app.save_as("문서.hwpx", "HWPX")

    한 인스턴스를 재사용할 것. Quit() 직후 새 Dispatch()는 영구 정지한다.
    """

    def __init__(self, register_module: bool = True):
        import win32com.client as w

        ensure_security_module()
        self.hwp = w.Dispatch("HWPFrame.HwpObject")
        if register_module:
            # 이 호출을 빠뜨리면 Open/SaveAs에서 보이지 않는 보안
            # 대화상자에 걸려 스크립트가 영구 정지한다.
            self.hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")

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
        """문서 전체 텍스트. InitScan/GetText 루프는 무한 루프에 빠지므로 쓰지 않는다."""
        return self.hwp.GetTextFile("TEXT", "")

    def clear(self) -> None:
        """다음 문서를 열기 전에 현재 문서를 비운다(저장 여부 묻지 않음)."""
        self.hwp.Clear(1)

    def close(self) -> None:
        try:
            self.hwp.Clear(1)
            self.hwp.Quit()
        except Exception:
            pass


# --------------------------------------------------------------------------
# 편의 함수
# --------------------------------------------------------------------------

def _convert(src, dst, src_fmt, dst_fmt) -> str:
    with HwpApp() as app:
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
    with HwpApp() as app:
        app.open(src)
        return app.text()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    target = sys.argv[1]
    print(f"format   : {detect_format(target)}")
    print(f"needs COM: {needs_conversion(target)}")
    print(f"security : {'registered' if ensure_security_module() else 'NOT registered'}")
