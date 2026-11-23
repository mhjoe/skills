# -*- coding: utf-8 -*-
"""차례 점선 탭 줄의 줄 배치 캐시 제거 회귀 테스트 (COM 불필요).

    python test_toc_layout.py
"""
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

NS = ('xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" '
      'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"')
LSA = ('<hp:linesegarray><hp:lineseg textpos="0" vertpos="0" vertsize="1200" textheight="1200" '
       'baseline="1020" spacing="1200" horzpos="5300" horzsize="40056" flags="393216"/></hp:linesegarray>')


def para(text, tab_leader=None, page=""):
    tab = f'<hp:tab width="14854" leader="{tab_leader}" type="2"/>{page}' if tab_leader is not None else ""
    return f'<hp:p><hp:run charPrIDRef="1"><hp:t>{text}{tab}</hp:t></hp:run>{LSA}</hp:p>'


def build(path):
    body = "".join([
        para("본문 문단"),                                  # 탭 없음 — 캐시를 건드리면 안 된다
        para("1절 | 제목 하나", 3, "24"),                    # 점선 탭 + 쪽번호
        para("2절 | 전각 쪽번호", 3, "５"),                  # 전각 숫자
        para("탭만 있고 점선 없음", 0, "7"),                 # leader=0 — 대상 아님
    ])
    xml = f'<?xml version="1.0" encoding="UTF-8"?><hs:sec {NS}>{body}</hs:sec>'
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/hwp+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("Contents/section0.xml", xml)
        z.writestr("Contents/header.xml", f'<hh:head xmlns:hh="x" {NS}/>')


def count_lsa(path):
    z = zipfile.ZipFile(path)
    x = z.read("Contents/section0.xml").decode("utf-8")
    parts = x.split("</hp:p>")[:-1]
    return [("<hp:linesegarray" in p) for p in parts]


def run(*args):
    return subprocess.run([sys.executable, str(HERE / "check_toc.py"), *args],
                          capture_output=True, text=True, encoding="utf-8")


def main():
    with tempfile.TemporaryDirectory() as d:
        src, dst = Path(d, "in.hwpx"), Path(d, "out.hwpx")
        build(src)
        assert count_lsa(src) == [True, True, True, True]

        r = run("scan", str(src))
        assert r.returncode == 1 and "점선 탭 줄 2개 중 줄 배치 캐시가 남은 줄 2개" in r.stdout, r.stdout
        assert "→ 5" in r.stdout and "→ 24" in r.stdout, r.stdout     # 전각 ５ → 5
        print("[1] scan: 점선 탭 줄 2개만 잡고 전각 숫자를 정규화 ✓")

        r = run("fix", str(src), str(dst))
        assert r.returncode == 0 and "2개" in r.stdout, r.stdout
        assert count_lsa(dst) == [True, False, False, True], count_lsa(dst)
        assert run("scan", str(dst)).returncode == 0
        print("[2] fix: 점선 탭 줄의 캐시만 제거, 본문·비점선 탭 줄은 보존 ✓")

        from hwp_handler import HwpDocument
        import shutil
        copy = Path(d, "h.hwpx"); shutil.copy(src, copy)
        with HwpDocument(str(copy), create_backup=False) as doc:
            n = doc.reset_tab_layout()
            assert n == 2, n
            doc.save(str(Path(d, "h2.hwpx")))
        assert count_lsa(Path(d, "h2.hwpx")) == [True, False, False, True]
        print("[3] HwpDocument.reset_tab_layout(): 같은 결과 ✓")

        assert run("scan", str(Path(d, "nope.hwpx"))).returncode == 2
        print("[4] 없는 파일은 종료 코드 2 ✓")
    print("ALL TOC TESTS PASSED")


if __name__ == "__main__":
    main()
