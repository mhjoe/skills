# -*- coding: utf-8 -*-
"""차례(목차)·점선 탭 줄의 쪽번호가 깨지는 문제를 찾고 고친다.

증상
    차례 줄의 쪽번호가 자릿수가 뒤집히거나 떨어져 보인다.
        "24"  ->  "4 ······ 2"      "125" -> "521"      "60" -> "0 ··· 6"
    XML을 열어 보면 값은 정상이다(`<hp:tab .../>24`). 파일이 아니라 **화면**이 깨진 것이다.

원인
    '제목 → 점선 오른쪽 탭 → 쪽번호' 줄은 한글이 저장해 둔 줄 배치 캐시
    (`<hp:linesegarray>`)와 탭의 계산 폭(`<hp:tab width=...>`)을 함께 믿고 그린다.
    HWP↔HWPX 왕복을 거치면서 이 캐시가 실제 글자 폭과 어긋난 줄은, 오른쪽 탭의 끝
    위치를 못 찾고 쪽번호 글자를 하나씩 따로 배치한다. 같은 모양의 줄 중 **일부만**
    깨지므로(제목이 길거나 두 줄 가까운 줄) 값이 틀렸다고 오해하기 쉽다.
    쪽번호를 갱신하려고 몇 줄만 고친 사람이 "내가 망가뜨렸다"고 착각하기도 하는데,
    고치지 않은 줄도 같은 원인으로 이미 깨져 있을 수 있다.

해결
    그 문단들의 `<hp:linesegarray>`를 지운다. 한글이 열 때 다시 배치하므로 지워서 잃는
    것이 없다. 탭 폭(`width`)과 문단 모양의 탭 정의는 건드릴 필요가 없다
    (실험: width=0 으로 비워도, 그대로 둬도 결과가 같았다).

사용법
    # 1) 점검: 점선 탭 줄 목록과 캐시 보유 여부 (COM 불필요)
    python check_toc.py scan 문서.hwpx

    # 2) 수리: 점선 탭 줄의 줄 배치 캐시를 지운 새 파일을 만든다
    python check_toc.py fix 문서.hwpx 고친문서.hwpx

    # 3) 검증: PDF로 내보낸 결과에서 쪽번호가 XML의 값과 같은 줄에 정렬됐는지 대조
    #    (hwp_com 으로 PDF를 만든 뒤)
    python check_toc.py verify 고친문서.hwpx 고친문서.pdf [--pages 1-8]

종료 코드: 0 = 이상 없음, 1 = 깨진 줄이 있다/의심된다, 2 = 입력 오류
"""
from __future__ import annotations

import argparse
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

HP = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"
SECTION = re.compile(r"Contents/section\d+\.xml$")


def _fw_to_ascii(s: str) -> str:
    """전각 숫자(９ ２ ５)를 반각으로. 이 보고서류 차례는 한 자리 쪽번호를 전각으로 적는다."""
    return "".join(chr(ord(c) - 0xFEE0) if 0xFF10 <= ord(c) <= 0xFF19 else c for c in s)


def tab_leader_paragraphs(root):
    """점선(채움) 탭 뒤에 쪽번호가 오는 최상위 문단을 (문단, 제목, 쪽번호)로 낸다."""
    for p in root:
        if p.tag != HP + "p":
            continue
        for t in p.iter(HP + "t"):
            tab = t.find(HP + "tab")
            if tab is None or tab.get("leader", "0") == "0":
                continue
            tail = (tab.tail or "").strip()
            if tail:
                yield p, (t.text or "").strip(), re.sub(r"\D", "", _fw_to_ascii(tail))
            break


def reset_tab_layout(root) -> int:
    """점선 탭 줄의 `linesegarray`를 제거한다. 지운 문단 수를 돌려준다."""
    n = 0
    for p, _title, _num in list(tab_leader_paragraphs(root)):
        lsas = p.findall(HP + "linesegarray")
        for lsa in lsas:
            p.remove(lsa)
        n += bool(lsas)
    return n


def _sections(z):
    return sorted(
        (n for n in z.namelist() if SECTION.match(n)),
        key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[1]).group(1)),
    )


def _register_namespaces(xml_text: str):
    # ElementTree가 접두어를 잃지 않게 원본 선언을 그대로 등록한다.
    for pfx, uri in re.findall(r'xmlns:(\w+)="([^"]+)"', xml_text[:6000]):
        ET.register_namespace(pfx, uri)


def cmd_scan(path: str) -> int:
    z = zipfile.ZipFile(path)
    total = cached = 0
    for name in _sections(z):
        xml = z.read(name).decode("utf-8")
        _register_namespaces(xml)
        for p, title, num in tab_leader_paragraphs(ET.fromstring(xml)):
            total += 1
            has = p.find(HP + "linesegarray") is not None
            cached += has
            print(f"{'캐시있음' if has else '캐시없음'}  {name.rsplit('/', 1)[1]}  {title[:40]}  → {num}")
    print(f"\n점선 탭 줄 {total}개 중 줄 배치 캐시가 남은 줄 {cached}개")
    if cached:
        print("한글에서 쪽번호가 겹치거나 뒤집혀 보이면 `fix`로 캐시를 지운다.")
    return 1 if cached else 0


def cmd_fix(src: str, dst: str) -> int:
    zin = zipfile.ZipFile(src)
    changed = 0
    with zipfile.ZipFile(dst, "w") as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if SECTION.match(info.filename):
                text = data.decode("utf-8")
                _register_namespaces(text)
                root = ET.fromstring(text)
                n = reset_tab_layout(root)
                if n:
                    changed += n
                    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            comp = zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED
            zout.writestr(info, data, compress_type=comp)
    print(f"줄 배치 캐시를 지운 문단 {changed}개 → {dst}")
    print("다음: 한글로 열어 PDF로 내보낸 뒤 `verify`로 쪽번호 정렬을 대조한다.")
    return 0


def _page_range(spec: str | None, total: int):
    if not spec:
        return range(0, min(total, 12))
    a, _, b = spec.partition("-")
    return range(int(a) - 1, int(b or a))


def cmd_verify(hwpx: str, pdf: str, pages: str | None) -> int:
    try:
        import pymupdf  # type: ignore
    except ImportError:
        print("[오류] pymupdf 가 필요하다: uv run --with pymupdf python check_toc.py verify ...")
        return 2
    z = zipfile.ZipFile(hwpx)
    expected = []
    for name in _sections(z):
        xml = z.read(name).decode("utf-8")
        _register_namespaces(xml)
        expected += [(t, n) for _p, t, n in tab_leader_paragraphs(ET.fromstring(xml)) if t]
    doc = pymupdf.open(pdf)
    lines = []
    for i in _page_range(pages, len(doc)):
        lines += [re.sub(r"\s+", " ", _fw_to_ascii(l)).strip() for l in doc[i].get_text().split("\n")]
    bad = []
    for title, num in expected:
        key = _fw_to_ascii(title)[:14]
        ok = False
        for i, l in enumerate(lines):
            if not l.startswith(key):
                continue
            m = re.search(r"(\d+)\s*$", l)
            if not m and i + 1 < len(lines):  # 쪽번호가 다음 줄로 추출되는 경우
                m = re.fullmatch(r"(\d+)", lines[i + 1])
            if m and m.group(1) == num:
                ok = True
                break
        if not ok:
            bad.append((title, num))
    print(f"점선 탭 줄 {len(expected)}개 중 쪽번호 불일치 {len(bad)}개")
    for t, n in bad[:20]:
        print(f"  {t[:40]}  (기대 {n})")
    if bad:
        print("PDF 쪽을 직접 열어 확인할 것 — 한 자리 쪽번호나 줄바꿈 제목은 오탐일 수 있다.")
    return 1 if bad else 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan"); s.add_argument("hwpx")
    f = sub.add_parser("fix"); f.add_argument("src"); f.add_argument("dst")
    v = sub.add_parser("verify"); v.add_argument("hwpx"); v.add_argument("pdf"); v.add_argument("--pages")
    a = ap.parse_args()
    try:
        if a.cmd == "scan":
            return cmd_scan(a.hwpx)
        if a.cmd == "fix":
            return cmd_fix(a.src, a.dst)
        return cmd_verify(a.hwpx, a.pdf, a.pages)
    except (FileNotFoundError, zipfile.BadZipFile) as e:
        print(f"[오류] {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
