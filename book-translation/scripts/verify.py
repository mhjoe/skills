# -*- coding: utf-8 -*-
"""
③ 완역 검증 — 원문 챕터 vs 번역 .md 대조

usage:
    uv run --python 3.12 python scratch/verify.py scratch/fear translations_Fear

주 지표
  ratio = 한글 본문 글자수(공백 제외) / 원문 단어수
    ≥ 2.00        ✅ 완역   (실측: 완역으로 확인된 편들이 전부 1.99 ~ 2.50 구간)
    1.85 ~ 2.00   문장 수·인용부호가 정상이면 통과, 아니면 ⚠️ 경계
    < 1.85        ❌ 축약 — 다시 번역한다 (실패 사례: 1.23, 0.78)
    > 2.70        ⚠️ 해설/역주가 본문 영역에 섞여 들어갔는지 확인

보조 지표
  sent%  = 번역 문장 종결부호 수 / 원문 문장 종결부호 수.
           한국어가 문장을 더 잘게 끊으므로 **110~140%가 정상**. 85% 미만이면 문단 통째 누락 의심.
  quote% = 여는 인용부호 수 대조(원문 ‘ “ / 번역 " ' 「).
           95~105%가 정상. 70% 미만이면 대화가 빠졌거나 지문으로 녹여버린 것.

본문 영역은 `## 📖` 와 `## 🔍` 사이. 역주(*[역주] …*)와 소제목 줄은 글자수에서 제외한다.
원문은 챕터 첫 두 줄(제목·작가명)을 제외하고 센다.
"""
import glob
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

D = sys.argv[1] if len(sys.argv) > 1 else "scratch/out"
T = sys.argv[2] if len(sys.argv) > 2 else "translations"

chapters = json.load(open(os.path.join(D, "chapters.json"), encoding="utf-8"))
mds = sorted(glob.glob(os.path.join(T, "[0-9][0-9]_*.md")))
if not mds:
    sys.exit(f"번역 파일 없음: {T}/NN_*.md")

SENT = re.compile(r"[.!?。]")
LDQ, RDQ, LSQ = chr(0x201C), chr(0x201D), chr(0x2018)


def body_of(md_text):
    """## 📖 ~ ## 🔍 사이를 본문으로 잘라낸다. 해설이 아직 없으면 파일 끝까지."""
    m = re.search(r"##\s*\U0001F4D6.*?\n(.*?)(?:\n---\s*\n\s*##\s*\U0001F50D|\Z)", md_text, re.S)
    return m.group(1) if m else ""


def clean(t):
    t = re.sub(r"\*\[역주\].*?\*", "", t, flags=re.S)   # 역주 제외
    t = re.sub(r"^#+ .*$", "", t, flags=re.M)           # 소제목 줄 제외
    return t


hdr = f"{'#':<3} {'file':<42} {'words':>7} {'kchars':>7} {'ratio':>6} {'quote':>6} {'sent':>6}  판정"
print(hdr)
print("-" * len(hdr))

bad = []
tot_w = tot_k = 0
for md in mds:
    n = int(os.path.basename(md)[:2])
    ch = next((c for c in chapters if c["n"] == n), None)
    if ch is None:
        print(f"{n:<3} {os.path.basename(md)[:42]:<42}  ← 대응하는 원문 챕터 없음")
        continue

    body = clean(body_of(open(md, encoding="utf-8").read()))
    ob = "\n".join(ch["text"].split("\n")[2:])          # 제목·작가명 두 줄 제외

    sw = len(ob.split())
    kc = len(re.sub(r"\s", "", body))
    ratio = kc / sw if sw else 0
    tot_w += sw
    tot_k += kc

    # 여는 인용부호: 원문은 ‘ “ , 번역은 " ' 「 (쌍이므로 반으로 나눈다)
    oq = ob.count(LSQ) + ob.count(LDQ) + ob.count('"') // 2
    tq = body.count(LDQ) + body.count(LSQ) + body.count("「") + body.count('"') // 2 + body.count("'") // 2
    qp = tq / oq * 100 if oq else 100

    osn = len(SENT.findall(ob))
    tsn = len(SENT.findall(body))
    sp = tsn / osn * 100 if osn else 100

    if not body:
        verdict = "❌ 본문 섹션 파싱 실패 (📖/🔍 헤더 확인)"
    elif ratio < 1.85:
        verdict = "❌ 축약 — 재번역"
    elif ratio < 2.00 and not (sp >= 100 and qp >= 70):
        verdict = "⚠️ 경계 — 누락 대조 필요"
    elif ratio > 2.70:
        verdict = "⚠️ 과다 — 해설 혼입 확인"
    elif sp < 85:
        verdict = "⚠️ 문단 누락 의심"
    elif qp < 70:
        verdict = "⚠️ 대화 대조 필요"
    else:
        verdict = "✅ 완역"
    if not verdict.startswith("✅"):
        bad.append((os.path.basename(md), verdict))

    print(f"{n:<3} {os.path.basename(md)[:42]:<42} {sw:>7} {kc:>7} {ratio:>6.2f} "
          f"{qp:>5.0f}% {sp:>5.0f}%  {verdict}")

print("-" * len(hdr))
print(f"{'':<3} {'TOTAL':<42} {tot_w:>7} {tot_k:>7} {tot_k / tot_w if tot_w else 0:>6.2f}")

if bad:
    print(f"\n손봐야 할 파일 {len(bad)}개:")
    for f, v in bad:
        print(f"  {v}  {f}")
else:
    print("\n전편 완역 판정 ✅ — README 색인을 쓸 차례다.")

print("\n[README 목차표용] 원문 단어 수")
for c in chapters:
    print(f"  {c['n']:02d} {c['title'][:30]:<30} pp.{c['pdf_start']}–{c['pdf_end']}  {c['words']:,} words")
