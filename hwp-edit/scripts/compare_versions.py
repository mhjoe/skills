# -*- coding: utf-8 -*-
"""같은 문서의 두 버전(.hwpx)을 비교해 의도하지 않은 변경(회귀)을 찾는다.

새 버전을 저장한 직후, 직전 버전과 비교해서 '의도한 수정 외에는 바뀐 것이 없는지'
확인하는 용도다. 옛 버전 파일을 원본으로 잘못 잡아 그 사이 수정(그림 교체, 수치 정정,
조판)이 사라지는 사고를 저장 단계에서 잡아낸다.

사용법:
    python compare_versions.py 직전버전.hwpx 새버전.hwpx [--expect "옛문구=>새문구" ...]

비교 항목:
    1. 본문 텍스트 (문단 단위 diff)
    2. 삽입 이미지 (BinData 바이너리 해시)
    3. 표 개수, 그림 개체 개수
--expect로 의도한 치환을 주면, 그 치환 외의 텍스트 차이만 '의도하지 않은 차이'로 보고한다.
종료 코드: 0 = 의도 외 차이 없음, 1 = 의도 외 차이 있음, 2 = 입력 오류

.hwp(바이너리)는 먼저 hwpx로 변환한 뒤 비교한다(hwp_com 참조).
"""
import argparse
import difflib
import hashlib
import re
import sys
import zipfile


def load(path):
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        sys.exit(f"[오류] HWPX(ZIP)가 아닙니다: {path}  (.hwp는 먼저 .hwpx로 변환)")
    sections = sorted(
        (n for n in z.namelist() if re.match(r"Contents/section\d+\.xml$", n)),
        key=lambda n: int(re.search(r"(\d+)", n.split("/")[-1]).group(1)),
    )
    xml = "".join(z.read(n).decode("utf-8") for n in sections)
    paras = []
    for p in re.findall(r"<hp:p[ >].*?</hp:p>", xml, re.S):
        t = re.sub(r"<[^>]+>", "", "".join(re.findall(r"<hp:t(?: [^>]*)?>(.*?)</hp:t>", p, re.S))).strip()
        if t:
            paras.append(t)
    bins = {
        n.split("/")[-1]: hashlib.md5(z.read(n)).hexdigest()
        for n in z.namelist() if n.startswith("BinData/")
    }
    return {
        "paras": paras,
        "bins": bins,
        "tables": len(re.findall(r"<hp:tbl[ >]", xml)),
        "pics": len(re.findall(r"<hp:pic[ >]", xml)),
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--expect", action="append", default=[], help='의도한 치환 "옛=>새"')
    a = ap.parse_args()

    old, new = load(a.old), load(a.new)
    expects = []
    for e in a.expect:
        if "=>" not in e:
            sys.exit(2)
        expects.append(tuple(e.split("=>", 1)))

    def apply_expected(s):
        for o, n in expects:
            s = s.replace(o, n)
        return s

    problems = 0
    # 1. 텍스트
    base = [apply_expected(p) for p in old["paras"]]
    diff = list(difflib.unified_diff(base, new["paras"], "직전(의도 치환 적용)", "새 버전", n=0, lineterm=""))
    print(f"[텍스트] 문단 {len(old['paras'])} → {len(new['paras'])}")
    if diff:
        problems += 1
        print("  ✖ 의도하지 않은 텍스트 차이:")
        for line in diff[2:]:
            print("   ", line[:300])
    else:
        print("  ✔ 의도한 치환 외 차이 없음")
    for o, n in expects:
        before = sum(p.count(o) for p in old["paras"])
        after = sum(p.count(n) for p in new["paras"])
        print(f"  · '{o}' → '{n}': 직전본 {before}곳" + ("  (직전본에 없음 — 이미 반영됐을 수 있음)" if before == 0 else ""))

    # 2. 이미지
    changed = sorted(k for k in set(old["bins"]) | set(new["bins"]) if old["bins"].get(k) != new["bins"].get(k))
    print(f"[이미지] {len(old['bins'])} → {len(new['bins'])}개")
    if changed:
        problems += 1
        print("  ✖ 바뀐/추가/삭제된 이미지:", ", ".join(changed))
    else:
        print("  ✔ 모두 동일")

    # 3. 개체 수
    for key, label in (("tables", "표"), ("pics", "그림 개체")):
        if old[key] != new[key]:
            problems += 1
            print(f"[{label}] ✖ {old[key]} → {new[key]}")
        else:
            print(f"[{label}] ✔ {old[key]}개 동일")

    print("\n결과:", "의도 외 차이 있음 — 편집 원본(기준본)이 직전 버전이 맞는지 확인할 것" if problems else "의도 외 차이 없음")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
