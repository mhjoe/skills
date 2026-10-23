"""hwp_layout.py — 조판(레이아웃) 작업 계층

XML 직접 편집(hwp_handler)은 서식을 보존하지만 **조판 결과를 알 수 없다**.
줄 수·쪽수는 한글이 다시 조판해야 정해지므로, 다음 작업은 이 모듈을 쓴다.

  - 문단별 줄 수 / 마지막 줄 길이 계측
  - 끝줄에 1~3자만 남은 문단의 자간을 줄여 한 줄 흡수
  - 그림 삽입과 정확한 크기 지정
  - 쪽수 확인, PDF 출력

전제: 한글(Hancom Office) 설치 + pywin32. 보안 모듈 등록은 hwp_com이 처리한다.

    uv run --python 3.12 --link-mode=copy --with pywin32 python scripts/hwp_layout.py --check

주의 (실패 사례에서 얻은 규칙):
  1. HWPML을 XML 파서로 재직렬화하면 문서가 깨질 수 있다(28쪽 -> 1453쪽 사례).
     구조를 바꿀 때는 문자열 치환으로 최소 범위만 고치고, 반드시 pages()로 검증한다.
  2. 열려 있는 문서와 같은 경로로 SaveAs 하면 조용히 실패한다. save()가 이를 처리한다.
  3. Quit 전에 모든 문서의 수정 표시를 지우지 않으면 저장 확인 대화상자가 떠
     프로세스가 남는다. close()가 처리한다.
  4. InsertPicture의 width/height 인자는 무시되는 판본이 있다. insert_picture()는
     삽입 후 HWPML에서 크기를 보정한다(IMAGECLIP은 건드리지 않는다 — 건드리면 잘린다).
"""
from __future__ import annotations

import os
import re
import sys
import time

try:
    import win32com.client as win32
except ImportError:  # pragma: no cover
    win32 = None

try:
    from . import hwp_com  # type: ignore
except (ImportError, ValueError):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import hwp_com  # type: ignore

HWPUNIT_PER_MM = 7200.0 / 25.4          # 1mm = 283.46 HWPUNIT
DEFAULT_STEPS = (-3, -5, -7, -10)       # 자간 단계(%)
SCRIPTS = ("Hangul", "Hanja", "Japanese", "Latin", "Other", "Symbol", "User")


def mm(value: float) -> int:
    """밀리미터를 HWPUNIT으로."""
    return int(round(value * HWPUNIT_PER_MM))


class LayoutSession:
    """한글을 띄워 조판 결과를 보며 편집하는 세션.

    with LayoutSession(path) as s:
        for p in s.find_short_last_lines():
            ...
    """

    def __init__(self, path: str, visible: bool = True):
        if win32 is None:
            raise RuntimeError("pywin32가 필요하다: --with pywin32")
        self.path = os.path.abspath(path)
        self.hwp = win32.gencache.EnsureDispatch("HWPFrame.HwpObject")
        if not hwp_com.ensure_security_module():
            raise hwp_com.HwpSecurityModuleError(
                "보안 모듈 미등록. scripts/hwp_com.py --setup 을 먼저 실행할 것")
        self.hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
        # 숨긴 창에서는 조판이 계산되지 않아 크기가 0으로 잡히는 경우가 있다.
        self.hwp.XHwpWindows.Item(0).Visible = visible
        self.hwp.Open(self.path)

    # ── 기본 정보 ──────────────────────────────────────────────
    def pages(self) -> int:
        return int(self.hwp.PageCount)

    def text(self) -> str:
        return self.hwp.GetTextFile("TEXT", "")

    def hwpml(self) -> str:
        return self.hwp.GetTextFile("HWPML2X", "")

    def load_hwpml(self, xml: str, expect_pages: int | None = None) -> None:
        """HWPML을 새 문서로 적재한다. 쪽수가 급변하면 예외로 막는다."""
        self.hwp.HAction.Run("FileNew")
        if not self.hwp.SetTextFile(xml, "HWPML2X", ""):
            raise RuntimeError("SetTextFile 실패 — HWPML이 손상되었을 수 있다")
        if expect_pages is not None:
            got = self.pages()
            if abs(got - expect_pages) > max(2, expect_pages * 0.2):
                raise RuntimeError(
                    "조판 결과가 비정상이다(%d쪽 -> %d쪽). 적재를 취소할 것" % (expect_pages, got))

    # ── 문단 계측 ──────────────────────────────────────────────
    def _indicator(self):
        k = self.hwp.KeyIndicator()
        return {"page": k[3], "line": k[5], "col": k[6]}   # col 단위: 반각(한글 1자 = 2)

    def measure(self, index: int) -> dict | None:
        """문단 하나의 줄 수와 마지막 줄 길이(반각 칸)."""
        if not self.hwp.SetPos(0, index, 0):
            return None
        start = self._indicator()
        self.hwp.HAction.Run("MoveParaEnd")
        end = self._indicator()
        same_page = end["page"] == start["page"]
        return {
            "index": index,
            "page": start["page"],
            "lines": (end["line"] - start["line"] + 1) if same_page else None,
            "tail": end["col"] - start["col"],   # 마지막 줄 길이(반각)
            "multiline": (not same_page) or end["line"] > start["line"],
        }

    def measure_all(self, limit: int = 2000) -> list[dict]:
        out = []
        for i in range(limit):
            m = self.measure(i)
            if m:
                out.append(m)
        return out

    def find_short_last_lines(self, max_chars: int = 3, limit: int = 2000) -> list[dict]:
        """끝줄에 max_chars자 이하만 남아 한 줄이 늘어난 문단."""
        cap = max_chars * 2
        return [m for m in self.measure_all(limit)
                if m["multiline"] and 0 < m["tail"] <= cap]

    def paragraph_text(self, index: int) -> str:
        self.hwp.SetPos(0, index, 0)
        self.hwp.HAction.Run("MoveSelParaEnd")
        txt = self.hwp.GetTextFile("TEXT", "saveblock:true") or ""
        self.hwp.HAction.Run("Cancel")
        return re.sub(r"&#\d+;", "", txt).strip()

    # ── 자간 / 장평 ────────────────────────────────────────────
    def set_char_shape(self, index: int, spacing: int | None = None,
                       ratio: int | None = None) -> None:
        """문단 하나에만 자간(spacing %) / 장평(ratio %)을 적용한다.

        문단을 블록 선택해 적용하므로 다른 문단은 영향받지 않는다.
        다만 Execute는 선택 영역의 글자모양 전체를 덮어쓰므로, 문단 안에서
        굵기 등이 섞여 있으면 평탄화된다 — uniform_char_shape()로 먼저 확인할 것.
        """
        self.hwp.SetPos(0, index, 0)
        self.hwp.HAction.Run("MoveSelParaEnd")
        pset = self.hwp.HParameterSet.HCharShape
        self.hwp.HAction.GetDefault("CharShape", pset.HSet)
        for s in SCRIPTS:
            if spacing is not None:
                setattr(pset, "Spacing" + s, spacing)
            if ratio is not None:
                setattr(pset, "Ratio" + s, ratio)
        self.hwp.HAction.Execute("CharShape", pset.HSet)
        self.hwp.HAction.Run("Cancel")

    def uniform_char_shape(self, index: int, xml: str | None = None) -> bool:
        """문단이 단일 글자모양이고 표·그림을 품고 있지 않은지(평탄화 안전 여부)."""
        xml = xml or self.hwpml()
        body = xml[xml.index("<BODY>"):]
        paras = re.findall(r"<P [^>]*>.*?</P>", body, re.S)
        # 표 안의 문단은 중첩되어 잡히므로 섹션 직속 문단만 센다.
        depth, tops = 0, []
        for m in re.finditer(r"<(/?)(P|CELL)\b", body):
            if m.group(2) == "CELL":
                depth += -1 if m.group(1) else 1
            elif not m.group(1) and depth == 0:
                tops.append(m.start())
        if index >= len(tops):
            return False
        seg = body[tops[index]: tops[index + 1] if index + 1 < len(tops) else len(body)]
        shapes = set(re.findall(r'<TEXT CharShape="(\d+)"', seg))
        return len(shapes) == 1 and "<TABLE" not in seg and "<PICTURE" not in seg

    def fit_short_last_lines(self, max_chars: int = 3, steps=DEFAULT_STEPS,
                             check_uniform: bool = True) -> dict:
        """끝줄이 짧은 문단의 자간을 단계적으로 줄여 한 줄을 흡수한다.

        효과가 없으면 자간을 0으로 되돌린다. 반환: {index: 적용 자간}
        """
        xml = self.hwpml() if check_uniform else None
        applied, skipped = {}, []
        for m in self.find_short_last_lines(max_chars):
            i, before = m["index"], m["lines"]
            if before is None:
                skipped.append(i)
                continue
            if check_uniform and not self.uniform_char_shape(i, xml):
                skipped.append(i)
                continue
            for step in steps:
                self.set_char_shape(i, spacing=step)
                after = self.measure(i)["lines"]
                if after is not None and after < before:
                    applied[i] = step
                    break
            else:
                self.set_char_shape(i, spacing=0)
                skipped.append(i)
        return {"applied": applied, "skipped": skipped}

    # ── 그림 ──────────────────────────────────────────────────
    def insert_picture(self, image_path: str, width_mm: float,
                       index: int | None = None, pos: int = 0) -> None:
        """그림을 넣고 지정 폭(mm)으로 맞춘다. 높이는 원본 비율을 따른다.

        InsertPicture의 크기 인자가 무시되는 판본이 있어, 삽입 후 HWPML에서
        SIZE/CurWidth·CurHeight만 고친다. IMAGECLIP은 건드리지 않는다.
        """
        from PIL import Image  # 선택 의존: --with pillow
        with Image.open(image_path) as im:
            ratio = im.height / im.width

        # 삽입 전 그림들의 InstId를 기억해 둔다. 문서 중간에 넣으면 새 그림이
        # XML의 마지막에 오지 않으므로, 위치가 아니라 InstId로 찾아야 한다.
        before_ids = set(re.findall(r'<PICTURE [^>]*>\s*<SHAPEOBJECT [^>]*InstId="(\d+)"',
                                    self.hwpml()))
        pages_before = self.pages()

        if index is not None:
            self.hwp.SetPos(0, index, pos)
        self.hwp.InsertPicture(os.path.abspath(image_path), True, 0, False, False, 0, 0, 0)

        w, h = mm(width_mm), int(round(mm(width_mm) * ratio))
        xml = self.hwpml()
        parts = xml.split("<PICTURE ")
        if len(parts) < 2:
            raise RuntimeError("삽입된 그림을 찾지 못했다")
        target = None
        for k, chunk in enumerate(parts[1:], start=1):
            m = re.match(r'[^>]*>\s*<SHAPEOBJECT [^>]*InstId="(\d+)"', chunk)
            if m and m.group(1) not in before_ids:
                target = k
                break
        if target is None:
            raise RuntimeError("새로 삽입된 그림을 식별하지 못했다")

        c = parts[target]
        c = re.sub(r'<SIZE Height="\d+"', '<SIZE Height="%d"' % h, c, 1)
        c = re.sub(r'(<SIZE [^>]*?)Width="\d+"', r'\g<1>Width="%d"' % w, c, 1)
        c = re.sub(r'CurHeight="\d+"', 'CurHeight="%d"' % h, c, 1)
        c = re.sub(r'CurWidth="\d+"', 'CurWidth="%d"' % w, c, 1)
        parts[target] = c
        self.load_hwpml("<PICTURE ".join(parts), expect_pages=pages_before)

    # ── 저장 ──────────────────────────────────────────────────
    def save(self, path: str | None = None, fmt: str = "HWP") -> str:
        """저장. 같은 경로로 SaveAs 하면 조용히 실패하므로 열린 문서를 먼저 닫는다.

        저장 후 수정시각을 확인해 실제로 기록되었는지 검증한다(파일 잠금 감지).
        """
        target = os.path.abspath(path or self.path)
        before = os.path.getmtime(target) if os.path.exists(target) else 0
        xml = self.hwpml()
        self._clear_documents()
        self.hwp.HAction.Run("FileNew")
        self.hwp.SetTextFile(xml, "HWPML2X", "")
        self.hwp.SaveAs(target, fmt, "")
        time.sleep(0.5)
        if not os.path.exists(target) or os.path.getmtime(target) <= before:
            raise RuntimeError(
                "저장이 반영되지 않았다. 해당 파일이 한글·동기화 프로그램에서 열려 있는지 확인할 것: %s" % target)
        self.path = target
        return target

    def export_pdf(self, path: str | None = None) -> str:
        target = os.path.abspath(path or os.path.splitext(self.path)[0] + ".pdf")
        self.hwp.SaveAs(target, "PDF", "")
        return target

    # ── 종료 ──────────────────────────────────────────────────
    def _clear_documents(self) -> None:
        try:
            docs = self.hwp.XHwpDocuments
            for i in range(docs.Count - 1, -1, -1):
                docs.Item(i).Clear(1)      # 1 = 저장하지 않고 버림
        except Exception:
            pass

    def close(self) -> None:
        """수정 표시를 지우고 종료한다(저장 확인 대화상자·잔존 프로세스 방지)."""
        self._clear_documents()
        try:
            self.hwp.Quit()
        except Exception:
            pass

    def __enter__(self) -> "LayoutSession":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def _check() -> int:
    ok = hwp_com.ensure_security_module(auto_fetch=False)
    print("보안 모듈:", "등록됨" if ok else "미등록 — hwp_com.py --setup 필요")
    print("pywin32:", "있음" if win32 else "없음")
    try:
        from PIL import Image  # noqa: F401
        print("pillow:", "있음 (그림 삽입 가능)")
    except ImportError:
        print("pillow: 없음 — 그림 삽입 시 --with pillow 필요")
    return 0 if ok and win32 else 1


if __name__ == "__main__":
    if "--check" in sys.argv:
        raise SystemExit(_check())
    print(__doc__)
