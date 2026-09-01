# -*- coding: utf-8 -*-
"""
② pages.json + toc.json → chapters.json + 챕터별 원문 .txt

usage:
    uv run --python 3.12 python scratch/split_chapters.py scratch/fear

입력  : <dir>/pages.json, <dir>/toc.json   (toc.json = [["Title", 시작PDF페이지], ...])
출력  : <dir>/chapters.json, <dir>/txt/NN_Title.txt

toc.json 의 **마지막 항목은 본문 끝 경계**(감사의 말·판권 등)이며 챕터로 만들어지지 않는다.
출력된 각 챕터 앞머리 160자를 눈으로 확인해 제목이 제자리에서 잘렸는지 반드시 검사할 것.
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

D = sys.argv[1] if len(sys.argv) > 1 else "scratch/out"

pages = json.load(open(os.path.join(D, "pages.json"), encoding="utf-8"))
toc = json.load(open(os.path.join(D, "toc.json"), encoding="utf-8"))
# 내장 TOC를 그대로 복사해 [level, title, page] 3요소로 남아 있어도 받아준다
toc = [(e[-2], e[-1]) if len(e) == 3 else (e[0], e[1]) for e in toc]

OUT = os.path.join(D, "txt")
os.makedirs(OUT, exist_ok=True)

chapters = []
for i, (title, start) in enumerate(toc[:-1]):
    end = toc[i + 1][1]
    text = "\n".join(pages[start - 1:end - 1])
    chapters.append({
        "n": i,
        "title": title,
        "pdf_start": start,
        "pdf_end": end - 1,
        "words": len(text.split()),
        "chars": len(text),
        "text": text,
    })

with open(os.path.join(D, "chapters.json"), "w", encoding="utf-8") as f:
    json.dump(chapters, f, ensure_ascii=False)

for c in chapters:
    safe = "".join(ch if ch.isalnum() or ch == " " else "_" for ch in c["title"]).strip().replace(" ", "_")
    p = os.path.join(OUT, f"{c['n']:02d}_{safe}.txt")
    with open(p, "w", encoding="utf-8") as f:
        f.write(c["text"])
    head = re.sub(r"\s+", " ", c["text"][:160])
    print(f"{c['n']:02d} | {c['title'][:26]:<26} | pp.{c['pdf_start']}-{c['pdf_end']} | {c['words']:>6} words | {head}")

print(f"\nTOTAL {len(chapters)} chapters, {sum(c['words'] for c in chapters):,} words")
print(f"wrote {D}/chapters.json and {OUT}/*.txt")
