# -*- coding: utf-8 -*-
"""HWPX 구조 검증 (한글 없이 무결성 점검). 사용: python verify.py 파일.hwpx"""
import sys, re, zipfile, io
from lxml import etree

def main(path):
    z = zipfile.ZipFile(path)
    ok = True
    # 1) well-formed
    for f in ['Contents/section0.xml', 'Contents/header.xml', 'Contents/content.hpf']:
        try:
            etree.fromstring(z.read(f)); print("WF ok:", f)
        except Exception as e:
            ok = False; print("WF FAIL:", f, e)
    h = z.read('Contents/header.xml').decode('utf-8')
    sec = z.read('Contents/section0.xml').decode('utf-8')
    hpf = z.read('Contents/content.hpf').decode('utf-8')

    def ids(s, t): return set(re.findall(r'<hh:%s id="(\d+)"' % t, s))
    have = {'charPrIDRef': ids(h, 'charPr'), 'paraPrIDRef': ids(h, 'paraPr'),
            'styleIDRef': ids(h, 'style'), 'borderFillIDRef': ids(h, 'borderFill')}
    for attr, pool in have.items():
        miss = set(re.findall(r'%s="(\d+)"' % attr, sec)) - pool
        if miss:
            ok = False; print("MISSING", attr, sorted(miss, key=int))
        else:
            print("refs ok:", attr)

    # 2) image manifest
    refs = set(re.findall(r'binaryItemIDRef="([^"]+)"', sec))
    decl = set(re.findall(r'<opf:item id="(image\d+)"', hpf))
    if refs - decl:
        ok = False; print("image not declared:", refs - decl)
    names = z.namelist()
    for iid in refs:
        if not any(n.lower().startswith('bindata/' + iid.lower()) for n in names):
            ok = False; print("BinData missing for", iid)
    print("images ok:", sorted(refs))

    # 3) mimetype
    zi = z.getinfo('mimetype')
    mt_ok = names[0] == 'mimetype' and zi.compress_type == 0
    if not mt_ok:
        ok = False
    print("mimetype first & STORED:", mt_ok, "| content:", z.read('mimetype').decode())

    print("\n=== RESULT:", "PASS" if ok else "FAIL", "===")
    return 0 if ok else 1

if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
