# -*- coding: utf-8 -*-
"""
① PDF → 페이지별 텍스트 덤프 + 내장 TOC/메타데이터 출력

usage:
    uv run --python 3.12 --with pymupdf python scratch/pdf_extract.py "Fear*.pdf" scratch/fear

- 첫 인자는 프로젝트 루트 기준 **glob 패턴**. 파일명에 타이포그래픽 아포스트로피(’)가 들어가도
  셸 인용부호 문제 없이 매칭하기 위해서다. 패턴을 인자로 넘기기가 곤란하면 아래 PATTERN 상수를 고친다.
- 출력: <outdir>/pages.json, <outdir>/toc_raw.json, 그리고 화면에 페이지별 첫 줄 목록
"""
import glob
import json
import os
import re
import sys

import pymupdf

sys.stdout.reconfigure(encoding="utf-8")

PATTERN = sys.argv[1] if len(sys.argv) > 1 else "*.pdf"
OUTDIR = sys.argv[2] if len(sys.argv) > 2 else "scratch/out"

matches = sorted(glob.glob(PATTERN))
if not matches:
    sys.exit(f"no PDF matched: {PATTERN!r} (cwd={os.getcwd()})")
if len(matches) > 1:
    print("여러 개 매칭됨 — 첫 번째를 사용한다:")
    for m in matches:
        print("   ", m)
path = matches[0]

os.makedirs(OUTDIR, exist_ok=True)
doc = pymupdf.open(path)

print(f"file  : {path}")
print(f"pages : {doc.page_count}")
print(f"meta  : {doc.metadata}")

toc = doc.get_toc()
with open(os.path.join(OUTDIR, "toc_raw.json"), "w", encoding="utf-8") as f:
    json.dump(toc, f, ensure_ascii=False, indent=1)

print(f"\n=== 내장 TOC ({len(toc)} entries) — 정확하면 그대로 toc.json 으로 옮겨 쓴다 ===")
for lvl, title, page in toc:
    print(f"  {'  ' * (lvl - 1)}{title}  →  p.{page}")

pages = [p.get_text("text") for p in doc]
with open(os.path.join(OUTDIR, "pages.json"), "w", encoding="utf-8") as f:
    json.dump(pages, f, ensure_ascii=False)
print(f"\nwrote {OUTDIR}/pages.json — {sum(len(p) for p in pages):,} chars")

print("\n=== 각 페이지 첫 비어있지 않은 줄 (TOC가 없거나 틀렸을 때 챕터 시작점을 눈으로 찾는 용도) ===")
for i, p in enumerate(pages, start=1):
    first = next((l.strip() for l in p.split("\n") if l.strip()), "")
    squeezed = re.sub(r"\s+", " ", first)
    print(f"  p.{i:>4}  {squeezed[:70]}")

print(f"""
다음 단계: {OUTDIR}/toc.json 을 아래 형식으로 만든다.
마지막 항목은 본문이 끝나는 지점(감사의 말/판권 등)을 가리키는 **경계 표시**여야 한다.

[
  ["Introduction", 7],
  ["W. S.", 15],
  ...
  ["Acknowledgements", 209]
]
""")
