# -*- coding: utf-8 -*-
"""
build_hwpx.py — 한컴 HWPX 템플릿의 '스타일'을 그대로 물려받아 보고서(.hwpx)를 생성한다.

핵심:
  * 템플릿 header.xml에서 스타일 ID를 '이름'으로 자동 탐지 (템플릿을 다시 저장해 ID가
    바뀌어도 안전). 마커(□ ◯ ― ※)는 각 스타일의 '자동 글머리표(bullet)' 문자로 매칭.
  * 자동 글머리표가 좌여백=0 등으로 렌더링되지 않는 스타일은 자동 감지하여
    (a) 해당 스타일의 문단모양에서 글머리표를 끄고 (b) 행잉 인덴트를 부여하고
    (c) 마커 문자를 본문에 직접 삽입한다. 그래도 문단 '스타일'은 그대로 적용된다.
  * 그림/표를 본문에 삽입하고, mimetype을 무압축·선두로 재패키징한다.

입력(content)은 .docx(권장) 또는 .txt/.md. 문단 규칙:
  Ⅰ. / 1.            → 장/절 제목
  □ ◯ ― ※ 로 시작    → 해당 개요 스타일(※는 -의 바로 하위 단계)
  * 로 시작           → 직전 문단의 위첨자 * 용어·문장에 대한 선택적 부연설명
  [그림 N] ...        → 그림 캡션 + 그림N_*.png 삽입
  [표 N] ...          → 표 캡션 (뒤따르는 docx 표가 한글 표로 변환)
  출처:/자료:         → 캡션(작은 글씨)
  그 외               → 본문
  graph/sequenceDiagram(Mermaid) 블록은 건너뜀(그림 이미지로 대체)

사용:
  python build_hwpx.py --template TPL.hwpx --content 보고서.docx \
      --figures ./그림 --out 결과.hwpx [--title "제목"] [--date "2026. 7."]
"""
import re, io, os, sys, glob, zipfile, shutil, argparse, tempfile

# 결과 요약에 □◯※ 같은 기호를 찍으므로, cp949 콘솔에서 죽지 않게 대체 문자로 흘린다.
try:
    sys.stdout.reconfigure(errors='replace')
except Exception:
    pass

# ---------------------------------------------------------------- args
# 기본 템플릿은 스킬에 번들된 assets/template.hwpx.
# 이 템플릿의 스타일(글꼴/크기/색/문단모양/글머리표)을 한글에서 바꿔 저장하면,
# 이 스크립트는 스타일을 '이름'으로 다시 읽으므로 바뀐 서식이 그대로 결과물에 반영된다.
DEFAULT_TPL = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "assets", "template.hwpx"))

ap = argparse.ArgumentParser()
ap.add_argument("--template", default=DEFAULT_TPL,
                help="스타일 템플릿 hwpx (기본: 번들된 assets/template.hwpx)")
ap.add_argument("--content", required=True, help=".docx / .txt / .md")
ap.add_argument("--figures", default=None, help="그림 폴더(그림N_*.png)")
ap.add_argument("--out", required=True)
ap.add_argument("--title", default=None, help="표지 제목(없으면 본문 첫 줄)")
ap.add_argument("--date", default=None, help='표지 날짜 예: "2026. 7."')
args = ap.parse_args()

CONTENT_W = 46000            # 본문 폭(HWPUNIT) 근사값
WORK = tempfile.mkdtemp(prefix="hwpx_")

# ---------------------------------------------------------------- unpack
with zipfile.ZipFile(args.template) as z:
    z.extractall(WORK)
HP = os.path.join(WORK, "Contents")
sec = io.open(os.path.join(HP, "section0.xml"), encoding="utf-8").read()
hdr = io.open(os.path.join(HP, "header.xml"), encoding="utf-8").read()


def split_paras(s):
    out, stack, start = [], 0, None
    for m in re.finditer(r'<hp:p\b|</hp:p>', s):
        if m.group().startswith('<hp:p'):
            if stack == 0: start = m.start()
            stack += 1
        else:
            stack -= 1
            if stack == 0: out.append(s[start:m.end()])
    return out


first_p = sec.index('<hp:p')
WRAP_OPEN, WRAP_CLOSE = sec[:first_p], '</hs:sec>'
tpl = split_paras(sec)

# ---------------------------------------------------------------- ids
_UID = [3000000000]; _ZO = [50]
def uid():
    _UID[0] += 1; return str(_UID[0])
def zo():
    _ZO[0] += 1; return str(_ZO[0])
def esc(t):
    return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
def lineseg(vs):
    return (f'<hp:linesegarray><hp:lineseg textpos="0" vertpos="0" vertsize="{vs}" '
            f'textheight="{vs}" baseline="{int(vs*0.85)}" spacing="{int(vs*0.6)}" '
            f'horzpos="0" horzsize="48188" flags="393216"/></hp:linesegarray>')
def P(text, styleID, paraID, charID, vs=1400, pageBreak=0):
    return (f'<hp:p id="{uid()}" paraPrIDRef="{paraID}" styleIDRef="{styleID}" '
            f'pageBreak="{pageBreak}" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="{charID}"><hp:t>{esc(text)}</hp:t></hp:run>{lineseg(vs)}</hp:p>')

# ---------------------------------------------------------------- style detection
def parse_styles(h):
    d = {}
    for m in re.finditer(r'<hh:style id="(\d+)" type="PARA" name="([^"]*)"[^>]*'
                         r'paraPrIDRef="(\d+)" charPrIDRef="(\d+)"', h):
        d[m.group(2)] = dict(sid=m.group(1), para=m.group(3), char=m.group(4))
    return d

def parapr_xml(h, pid):
    return re.search(r'<hh:paraPr id="%s"[ >].*?</hh:paraPr>' % pid, h, re.S).group(0)

def default_left(h, pid):
    x = parapr_xml(h, pid)
    d = re.search(r'<hp:default>.*?</hp:default>', x, re.S)
    blk = d.group(0) if d else x
    m = re.search(r'<hc:left value="(-?\d+)"', blk)
    return int(m.group(1)) if m else 0

def bullet_of(h, pid):
    x = parapr_xml(h, pid)
    hd = re.search(r'<hh:heading type="(\w+)" idRef="(\d+)"', x)
    if not hd or hd.group(1) != 'BULLET':
        return None
    b = re.search(r'<hh:bullet id="%s" char="([^"]*)"' % hd.group(2), h)
    return b.group(1) if b else None

def char_height(h, cid):
    m = re.search(r'<hh:charPr id="%s"[^>]*height="(\d+)"' % cid, h)
    return int(m.group(1)) if m else 0

def line_spacing_pct(h, pid):
    """문단모양의 줄간격(PERCENT). PERCENT가 아니면 100으로 본다."""
    try:
        x = parapr_xml(h, pid)
    except AttributeError:
        return 100
    m = re.search(r'<hh:lineSpacing type="PERCENT" value="(\d+)"', x)
    return int(m.group(1)) if m else 100

def para_gap(h, pid):
    """문단 위/아래 간격(prev, next) HWPUNIT."""
    try:
        x = parapr_xml(h, pid)
    except AttributeError:
        return 0, 0
    mg = re.search(r'<hh:margin>.*?</hh:margin>', x, re.S)
    blk = mg.group(0) if mg else x
    def g(k):
        m = re.search(r'<hc:%s value="(-?\d+)"' % k, blk)
        return int(m.group(1)) if m else 0
    return g('prev'), g('next')

def split_cells(x):
    """표 XML에서 최상위 <hp:tc> 구간 [(start, end), ...]를 돌려준다."""
    out, st, start = [], 0, None
    for m in re.finditer(r'<hp:tc\b|</hp:tc>', x):
        if m.group().startswith('<hp:tc'):
            if st == 0:
                start = m.start()
            st += 1
        else:
            st -= 1
            if st == 0:
                out.append((start, m.end()))
    return out

def para_texts(p):
    return [t for t in re.findall(r'<hp:t>([^<]*)</hp:t>', p)]

STY = parse_styles(hdr)
BODY = STY.get('본문') or STY.get('바탕글')
NORMAL = STY.get('바탕글')
CAPTION = STY.get('표/그림 제목') or BODY

# 원고 마커 → 스타일 매칭.
#   1순위: 각 개요 스타일의 '자동 글머리표(bullet) 문자'로 매칭 → 스타일 이름이 무엇이든 동작
#          (템플릿에서 스타일 이름을 'ㅁ'→'□'로 바꿔도, 새 스타일을 추가해도 그대로 붙는다).
#   2순위: 글머리표가 없는 스타일은 '스타일 이름' 자체를 마커로 해석.
# 어느 쪽이든 문단모양/글자모양 ID를 매번 새로 읽으므로, 템플릿에서 글꼴·크기·색·간격을
# 바꿔 저장하면 결과물에 그대로 반영된다.
CANON = {                                    # 원고/템플릿의 이형(異形) 기호 → 대표 마커
    '□': '□', '■': '□', '◻': '□', 'ㅁ': '□',
    '◯': '◯', '○': '◯', '●': '◯', '◦': '◯', 'ㅇ': '◯',
    '―': '-', '—': '-', '–': '-', '‐': '-', '-': '-',
    '※': '※',
    '*': '*', '•': '*', '∙': '*',
}
MARKERS = {}            # 대표 마커 -> dict(sid,para,char,vs,literal)
FIX_PARAS = set()       # 글머리표가 안 나와서 고칠 paraPr id 목록

def reg_marker(marker, st):
    if not st or marker in MARKERS:          # 먼저 잡힌 스타일(=id가 작은 쪽) 우선
        return
    left = default_left(hdr, st['para'])
    has_bullet = bullet_of(hdr, st['para']) is not None
    # 좌여백 0 + 글머리표 스타일 = 글머리표가 그려질 공간이 없어 렌더 실패 → 직접 삽입 + 문단모양 고침.
    literal = has_bullet and (left == 0)
    if literal:
        FIX_PARAS.add(st['para'])
    vs = max(1300, min(1600, char_height(hdr, st['char']) or 1500))
    MARKERS[marker] = dict(sid=st['sid'], para=st['para'], char=st['char'],
                           vs=vs, literal=literal)

_by_id = sorted(STY.items(), key=lambda kv: int(kv[1]['sid']))
for _name, _st in _by_id:                    # (1) 글머리표 문자로
    b = (bullet_of(hdr, _st['para']) or '').strip()
    if b and CANON.get(b[0]):
        reg_marker(CANON[b[0]], _st)
for _name, _st in _by_id:                    # (2) 폴백: 스타일 이름이 곧 마커인 경우
    n = _name.strip()
    if len(n) == 1 and CANON.get(n):
        reg_marker(CANON[n], _st)

def item_para(marker, text):
    m = MARKERS[marker]
    if m['literal']:
        text = f'{marker}  ' + text
    return P(text, m['sid'], m['para'], m['char'], vs=m['vs'])

def body_para(text):
    return P(text, BODY['sid'], BODY['para'], BODY['char'], vs=1300)
def caption_para(text):
    return P(text, CAPTION['sid'], CAPTION['para'], CAPTION['char'], vs=1400)
def source_para(text):
    return P(text, NORMAL['sid'], NORMAL['para'], BODY['char'], vs=1100)

# 절 제목용 char: 큰 헤드라인 계열(1600~1900) 우선, 없으면 ㅁ의 char
def pick_section_char(h):
    best = None
    for m in re.finditer(r'<hh:charPr id="(\d+)"[^>]*height="(\d+)"[^>]*textColor="(#0{6}|#000000)"', h):
        hh = int(m.group(2))
        if 1600 <= hh <= 1900:
            if best is None or hh > best[1]:
                best = (m.group(1), hh)
    if best:
        return best[0]
    return (STY.get('ㅁ') or BODY)['char']
SEC_CHAR = pick_section_char(hdr)
def section_head(text):
    return P(text, NORMAL['sid'], BODY['para'], SEC_CHAR, vs=1800)

# ---------------------------------------------------------------- template structure
def find_idx(pred, lo=0):
    for i in range(lo, len(tpl)):
        if pred(tpl[i]):
            return i
    return None

TOC_TITLE_RE = re.compile(r'목\s*차')
def is_toc_title_para(p):
    return any(TOC_TITLE_RE.fullmatch(t.strip()) for t in para_texts(p))

toc_title_i = find_idx(is_toc_title_para) or 1
# 목차 '제목'과 목차 '항목 표'는 별개의 문단이다. 제목이 장식 표(얇은 칸으로 좌우를 감싼
# 표) 안에 들어 있는 템플릿이 흔한데, 그 표를 항목 표로 오인하면 폭이 몇 mm뿐인 장식 칸에
# 항목 텍스트가 들어가 한 글자씩 줄바꿈되며 목차 표가 세로로 폭발한다.
# → 제목 문단 '다음'부터 찾고, 제목 텍스트를 품은 표는 후보에서 제외한다.
toc_table_i = find_idx(lambda p: 'numberingType="TABLE"' in p and not is_toc_title_para(p),
                       toc_title_i + 1)
divider_i = find_idx(lambda p: '<hp:t>제 목</hp:t>' in p or '<hp:t>제목</hp:t>' in p,
                     (toc_table_i or toc_title_i) + 1)
chap_i = find_idx(lambda p: '<hp:t>Ⅰ</hp:t>' in p and 'numberingType="TABLE"' in p,
                  (divider_i or toc_table_i or 0))
CHAP_TPL = tpl[chap_i] if chap_i is not None else None

def chapter_box(numeral, title, first=False):
    if CHAP_TPL is None:                    # 폴백: 큰 제목 문단
        return P(f'{numeral}. {title}'.strip('. '), NORMAL['sid'], BODY['para'],
                 SEC_CHAR, vs=2000, pageBreak=1)
    x = CHAP_TPL
    if not first:
        x = re.sub(r'<hp:ctrl><hp:newNum[^>]*/></hp:ctrl>', '', x)
    x = re.sub(r'(<hp:tbl id=")\d+(")', lambda m: m.group(1)+uid()+m.group(2), x, count=1)
    x = re.sub(r'(zOrder=")\d+(")', lambda m: m.group(1)+zo()+m.group(2), x, count=1)
    x = x.replace('<hp:t>Ⅰ</hp:t>', f'<hp:t>{esc(numeral)}</hp:t>', 1)
    x = x.replace('<hp:t> 제목</hp:t>', f'<hp:t> {esc(title)}</hp:t>', 1)
    x = x.replace('pageBreak="0"', 'pageBreak="1"', 1)
    return x

# ---------------------------------------------------------------- images
IMG_ITEMS = []; _imgn = [0]
# 기존 image 번호 최대값
for m in re.finditer(r'href="BinData/image(\d+)\.', io.open(os.path.join(HP, "content.hpf"), encoding="utf-8").read()):
    _imgn[0] = max(_imgn[0], int(m.group(1)))

def add_image(path):
    _imgn[0] += 1
    iid = f"image{_imgn[0]}"
    ext = os.path.splitext(path)[1].lstrip('.').upper()
    shutil.copy(path, os.path.join(WORK, "BinData", f"{iid}.{ext}"))
    IMG_ITEMS.append((iid, f"BinData/{iid}.{ext}"))
    return iid

def image_para(path):
    from PIL import Image
    iid = add_image(path)
    iw, ih = Image.open(path).size
    W = CONTENT_W; H = int(W * ih / iw)
    pic = (f'<hp:pic reverse="0" id="{uid()}" zOrder="{zo()}" numberingType="PICTURE" '
           f'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" '
           f'href="" groupLevel="0" instid="{uid()}"><hp:offset x="0" y="0"/>'
           f'<hp:orgSz width="{W}" height="{H}"/><hp:curSz width="{W}" height="{H}"/>'
           f'<hp:flip horizontal="0" vertical="0"/>'
           f'<hp:rotationInfo angle="0" centerX="{W//2}" centerY="{H//2}" rotateimage="1"/>'
           f'<hp:renderingInfo><hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
           f'<hc:scaMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
           f'<hc:rotMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/></hp:renderingInfo>'
           f'<hc:img binaryItemIDRef="{iid}" bright="0" contrast="0" effect="REAL_PIC" alpha="0"/>'
           f'<hp:imgRect><hc:pt0 x="0" y="0"/><hc:pt1 x="{W}" y="0"/><hc:pt2 x="{W}" y="{H}"/>'
           f'<hc:pt3 x="0" y="{H}"/></hp:imgRect><hp:imgClip left="0" right="{W}" top="0" bottom="{H}"/>'
           f'<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
           f'<hp:sz width="{W}" widthRelTo="ABSOLUTE" height="{H}" heightRelTo="ABSOLUTE" protect="0"/>'
           f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" '
           f'holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" '
           f'horzAlign="CENTER" vertOffset="0" horzOffset="0"/>'
           f'<hp:outMargin left="0" right="0" top="0" bottom="0"/></hp:pic>')
    return (f'<hp:p id="{uid()}" paraPrIDRef="{CAPTION["para"]}" styleIDRef="0" pageBreak="0" '
            f'columnBreak="0" merged="0"><hp:run charPrIDRef="{BODY["char"]}">{pic}<hp:t/></hp:run>'
            f'{lineseg(H)}</hp:p>')

def fig_by_num(n):
    if not args.figures: return None
    g = glob.glob(os.path.join(args.figures, f"그림{n}_*.png")) or \
        glob.glob(os.path.join(args.figures, f"*{n}*.png"))
    return g[0] if g else None

# ---------------------------------------------------------------- tables
# 표 테두리용 borderFill id는 기존 최대값+1부터(다른 요소의 id="30" 등과 혼동 방지)
_bfids = [int(x) for x in re.findall(r'<hh:borderFill id="(\d+)"', hdr)]
HBF, BBF = max(_bfids) + 1, max(_bfids) + 2      # header-cell / body-cell

TCELL = STY.get('표 내용')      # 템플릿에 표 셀 전용 스타일이 있으면 그 서식을 물려받는다
def cell_paras(text, header):
    parts = text.split('\n') or ['']
    if TCELL:
        pid, cid, vs = TCELL['para'], TCELL['char'], 1100
    else:
        pid, cid, vs = (27, 12, 1100) if header else (0, BODY['char'], 1100)
    out = ''
    for pt in parts:
        out += (f'<hp:p id="{uid()}" paraPrIDRef="{pid}" styleIDRef="0" pageBreak="0" '
                f'columnBreak="0" merged="0"><hp:run charPrIDRef="{cid}"><hp:t>{esc(pt)}</hp:t></hp:run>'
                f'{lineseg(vs)}</hp:p>')
    return out

def build_table(rows):
    nr = len(rows); nc = max(len(r) for r in rows)
    rows = [r + [''] * (nc - len(r)) for r in rows]
    has_header = nr > 1 and nc > 1 and rows[0][0].strip() in ('구분', '단계', '권역', '단 계')
    has_label = (not has_header) and nc == 2 and nr >= 3
    cw = CONTENT_W // nc; widths = [cw]*(nc-1) + [CONTENT_W - cw*(nc-1)]; ch = 2400
    trs = ''
    for r in range(nr):
        tcs = ''
        for c in range(nc):
            hdr_cell = (has_header and r == 0) or (has_label and c == 0)
            bf = HBF if hdr_cell else BBF
            tcs += (f'<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" dirty="0" '
                    f'borderFillIDRef="{bf}"><hp:subList id="" textDirection="HORIZONTAL" '
                    f'lineWrap="BREAK" vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" '
                    f'textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
                    f'{cell_paras(rows[r][c], hdr_cell)}</hp:subList>'
                    f'<hp:cellAddr colAddr="{c}" rowAddr="{r}"/><hp:cellSpan colSpan="1" rowSpan="1"/>'
                    f'<hp:cellSz width="{widths[c]}" height="{ch}"/>'
                    f'<hp:cellMargin left="141" right="141" top="141" bottom="141"/></hp:tc>')
        trs += f'<hp:tr>{tcs}</hp:tr>'
    TH = ch * nr
    tbl = (f'<hp:tbl id="{uid()}" zOrder="{zo()}" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" '
           f'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="1" '
           f'rowCnt="{nr}" colCnt="{nc}" cellSpacing="0" borderFillIDRef="{BBF}" noAdjust="0">'
           f'<hp:sz width="{CONTENT_W}" widthRelTo="ABSOLUTE" height="{TH}" heightRelTo="ABSOLUTE" protect="0"/>'
           f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" '
           f'holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="PARA" vertAlign="TOP" horzAlign="CENTER" '
           f'vertOffset="0" horzOffset="0"/><hp:outMargin left="283" right="283" top="283" bottom="283"/>'
           f'<hp:inMargin left="141" right="141" top="141" bottom="141"/>{trs}</hp:tbl>')
    return (f'<hp:p id="{uid()}" paraPrIDRef="{CAPTION["para"]}" styleIDRef="0" pageBreak="0" '
            f'columnBreak="0" merged="0"><hp:run charPrIDRef="{BODY["char"]}">{tbl}<hp:t/></hp:run>'
            f'{lineseg(TH)}</hp:p>')

# ---------------------------------------------------------------- read content
def read_items(path):
    """(종류, 내용, 직전 * 부연설명의 근거가 되는 위첨자 표시 여부) 목록을 읽는다."""
    ext = os.path.splitext(path)[1].lower()
    if ext == '.docx':
        import docx
        from docx.oxml.text.paragraph import CT_P
        from docx.oxml.table import CT_Tbl
        from docx.table import Table
        from docx.text.paragraph import Paragraph
        d = docx.Document(path)
        out = []
        for ch in d.element.body.iterchildren():
            if isinstance(ch, CT_P):
                p = Paragraph(ch, d)
                # '*' 부연설명 스타일은 직전 문단에 실제 위첨자 *가 있을 때만 허용한다.
                has_sup_star = any('*' in run.text and run.font.superscript is True
                                   for run in p.runs)
                out.append(('p', p.text, has_sup_star))
            elif isinstance(ch, CT_Tbl):
                out.append(('t', [[c.text.strip() for c in row.cells]
                                  for row in Table(ch, d).rows], False))
        return out
    else:
        out = []
        for ln in io.open(path, encoding='utf-8-sig').read().splitlines():
            # 평문은 서식 정보를 담지 못하므로 '용어*'처럼 앞말에 붙은 별표를 위첨자 의도로 본다.
            # 줄 첫머리 '* '는 부연설명 문단의 마커이므로 근거 표시로 세지 않는다.
            has_sup_star = not ln.lstrip().startswith('*') and re.search(r'(?<=\S)\*', ln) is not None
            out.append(('p', ln, has_sup_star))
        return out

items = read_items(args.content)

CH_RE = re.compile(r'^([ⅠⅡⅢⅣⅤ])\.\s*(.+)')
SEC_RE = re.compile(r'^(\d+)\.\s*(.+)')
FIG_RE = re.compile(r'^\[그림\s*(\d+)\]')
TAB_RE = re.compile(r'^\[표\s*\d+\]')

# 표지 제목/부제 = 첫 두 문단(--title 우선)
doc_title = args.title
subtitle = None
lead = [v for k, v, _ in items if k == 'p' and v.strip()][:2]
if doc_title is None and lead:
    doc_title = lead[0]
if len(lead) > 1:
    subtitle = lead[1]

body = []
style_warnings = []
dash_context_active = False
for item_i, (kind, val, has_sup_star) in enumerate(items[2:], start=2):
    if kind == 't':
        body.append(build_table(val)); continue
    t = val.strip()
    if not t:
        continue
    if t.startswith('graph ') or t.startswith('sequenceDiagram') or t.startswith('autonumber'):
        continue
    if t == '참고자료':
        dash_context_active = False
        body.append(chapter_box('', '참고자료')); continue
    mfig = FIG_RE.match(t)
    if mfig:
        body.append(caption_para(t))
        fp = fig_by_num(mfig.group(1))
        if fp:
            body.append(image_para(fp))
        continue
    if TAB_RE.match(t):
        body.append(caption_para(t)); continue
    if t.startswith('출처:') or t.startswith('자료:'):
        body.append(source_para(t)); continue
    mch = CH_RE.match(t)
    if mch:
        dash_context_active = False
        body.append(chapter_box(mch.group(1), mch.group(2), first=(mch.group(1) == 'Ⅰ'))); continue
    msec = SEC_RE.match(t)
    if msec:
        dash_context_active = False
        body.append(section_head(t)); continue
    mk = CANON.get(t[0])
    if mk in MARKERS:
        if mk in ('□', '◯'):
            dash_context_active = False
        elif mk == '-':
            dash_context_active = True
        elif mk == '※' and not dash_context_active:
            style_warnings.append(
                f"원고 항목 {item_i + 1}: 상위 '-' 문단이 없어 "
                "'※' 하위 계층 스타일을 적용하지 않음")
            body.append(body_para(t))
            continue
        if mk == '*':
            prev_is_anchor = (item_i > 0 and items[item_i - 1][0] == 'p'
                              and items[item_i - 1][2])
            if not prev_is_anchor:
                style_warnings.append(
                    f"원고 항목 {item_i + 1}: 직전 문단에 위첨자 * 표시가 없어 "
                    "'*' 부연설명 스타일을 적용하지 않음")
                body.append(body_para(t))
                continue
        body.append(item_para(mk, t[1:].strip())); continue
    body.append(body_para(t))

# ---------------------------------------------------------------- cover / toc / divider
cover = ''.join(tpl[1:toc_title_i])
# 표지 텍스트 치환(템플릿 기본 문구를 제목/날짜로)
def title_lines(s, per=24):
    words = s.split(); lines = []; cur = ''
    for w in words:
        if len(cur) + len(w) + 1 > per and cur:
            lines.append(cur); cur = w
        else:
            cur = (cur + ' ' + w).strip()
    if cur: lines.append(cur)
    return lines[:3]
tl = title_lines(doc_title or '보고서')
# 표지 문구는 하드코딩하지 않는다. 표지 영역에서 '날짜가 아닌' 첫 두 텍스트 조각을
# 제목/부제로 갈아끼운다 → 템플릿의 기관명·양식명이 바뀌어도 그대로 동작한다.
DATE_T_RE = re.compile(r'^\s*\d{4}\s*[.\-]')
def fill_cover_titles(xml, lines):
    n = [0]
    def sub(m):
        inner = m.group(1)
        if not inner.strip() or '<' in inner or DATE_T_RE.match(inner):
            return m.group(0)          # 날짜·탭 등 제어 조각은 건드리지 않음
        if n[0] < len(lines):
            v = lines[n[0]]; n[0] += 1
            return f'<hp:t>{esc(v)}</hp:t>'
        return m.group(0)
    return re.sub(r'<hp:t>(.*?)</hp:t>', sub, xml, flags=re.S)
cover = fill_cover_titles(cover, [tl[0] if tl else '보고서', ' '.join(tl[1:])])
if args.date:
    cover = re.sub(r'\d{4}\.\s*nn\.\s*nn\.', args.date, cover)

# 목차: 제목/표 재구성
chaps = []
for k, v, _ in items:
    if k == 'p':
        m = CH_RE.match(v.strip())
        if m:
            chaps.append((m.group(1), m.group(2)))
# 항목 표를 못 찾아도 목차 '제목' 문단은 살린다(예전엔 통째로 사라졌다).
toc_head = ''.join(tpl[toc_title_i:toc_table_i]) if toc_table_i is not None \
    else ''.join(tpl[toc_title_i:toc_title_i + 1])

# 목차 항목을 넣을 '칸'을 고른다. 첫 <hp:subList>를 그냥 쓰면 장식용 얇은 칸에
# 걸릴 수 있으므로(→ 세로 폭발) 표에서 가장 넓은 칸을 고르고, 그 폭이 아래 기준에
# 미달하면 항목 삽입을 아예 포기한다(템플릿 목차를 그대로 남김).
TOC_MIN_CELL_W = 10000          # 절대 최소 폭(HWPUNIT, ≈35mm)
TOC_MIN_CELL_RATIO = 0.5        # 표 전체 폭 대비 최소 비율

def pick_toc_cell(p):
    """항목을 넣을 셀 구간과 폭을 고른다. 부적합하면 (None, 이유)."""
    tw = re.search(r'<hp:sz width="(\d+)"', p)
    tw = int(tw.group(1)) if tw else 0
    best = None
    for s, e in split_cells(p):
        m = re.search(r'<hp:cellSz width="(\d+)" height="(\d+)"/>', p[s:e])
        if not m or '<hp:subList' not in p[s:e]:
            continue
        w = int(m.group(1))
        if best is None or w > best[2]:
            best = (s, e, w)
    if best is None:
        return None, '삽입 가능한 셀 없음'
    if best[2] < TOC_MIN_CELL_W or (tw and best[2] < tw * TOC_MIN_CELL_RATIO):
        return None, f'가장 넓은 셀 폭 {best[2]}(표 폭 {tw})이 기준 미달'
    return best, None

toc_note = ''
if toc_table_i is None:
    toc = toc_head
    toc_note = '항목 표 미탐지 → 목차 항목 생략'
else:
    p_toc = tpl[toc_table_i]
    cell, why = pick_toc_cell(p_toc)
    if cell is None:
        toc = toc_head + p_toc                    # 표를 훼손하지 않고 그대로 둔다
        toc_note = f'{why} → 목차 항목 생략'
    else:
        cs, ce, cw = cell
        inner = p_toc[cs:ce]
        oe = inner.index('>', inner.index('<hp:subList')) + 1
        cl = inner.index('</hp:subList>', oe)
        old_paras = split_paras(inner[oe:cl])

        # 항목 문단모양/글자모양은 템플릿의 기존 목차 항목에서 가져온다(하드코딩 없음).
        ep = rc = tc = None
        for q in old_paras:
            runs = re.findall(r'<hp:run charPrIDRef="(\d+)"[^>]*>(.*?)</hp:run>', q, re.S)
            heads = [(c, ''.join(re.findall(r'<hp:t>([^<]*)</hp:t>', b))) for c, b in runs]
            if heads and heads[0][1].strip() in ('Ⅰ', 'Ⅱ', 'Ⅲ', 'Ⅳ', 'Ⅴ'):
                ep = re.search(r'paraPrIDRef="(\d+)"', q).group(1)
                rc = heads[0][0]
                tc = heads[1][0] if len(heads) > 1 else rc
                break
        if ep is None and old_paras:               # 항목 예시가 없는 템플릿
            ep = re.search(r'paraPrIDRef="(\d+)"', old_paras[0]).group(1)
            cm = re.search(r'charPrIDRef="(\d+)"', old_paras[0])
            rc = tc = cm.group(1) if cm else BODY['char']
        if ep is None:
            ep, rc, tc = BODY['para'], BODY['char'], BODY['char']

        # 줄 높이는 글자 크기 × 줄간격에서 산출한다(고정값 2100 금지).
        eh = char_height(hdr, tc) or char_height(hdr, rc) or 1500
        pct = line_spacing_pct(hdr, ep)
        evs = max(900, eh)
        gap_prev, gap_next = para_gap(hdr, ep)
        # 한 항목이 차지하는 실제 높이: 줄높이 + 줄간격 초과분 + 문단 위/아래 간격
        per = evs + max(0, int(evs * (pct - 100) / 100)) + max(0, gap_prev) + max(0, gap_next)

        toc_items = [(rn, f'. {ti}') for rn, ti in chaps]
        # '참고자료'는 원고에 실제로 있을 때만 넣는다(없으면 빈 항목이 남아 목차가 길어짐).
        if any(k == 'p' and v.strip() == '참고자료' for k, v, _ in items):
            toc_items.append(('', ' 참고자료'))

        entries = ''
        for rn, ti in toc_items:
            runs = ''
            if rn:
                runs += f'<hp:run charPrIDRef="{rc}"><hp:t>{esc(rn)}</hp:t></hp:run>'
            runs += f'<hp:run charPrIDRef="{tc}"><hp:t>{esc(ti)}</hp:t></hp:run>'
            entries += (f'<hp:p id="{uid()}" paraPrIDRef="{ep}" styleIDRef="0" pageBreak="0" '
                        f'columnBreak="0" merged="0">{runs}{lineseg(evs)}</hp:p>')

        new_inner = inner[:oe] + entries + inner[cl:]
        # 항목 수가 줄었는데 템플릿의 셀/표 높이를 그대로 두면 빈 공간이 그만큼 남는다.
        # → 내용 높이로 다시 계산해 셀·표 높이와 문단 레이아웃 캐시를 갱신한다.
        cmarg = re.search(r'<hp:cellMargin left="\d+" right="\d+" top="(\d+)" bottom="(\d+)"/>', inner)
        pad = (int(cmarg.group(1)) + int(cmarg.group(2))) if cmarg else 282
        need = max(per, per * len(toc_items)) + pad
        new_inner = re.sub(r'(<hp:cellSz width="\d+" height=")\d+(")',
                           lambda m: m.group(1) + str(need) + m.group(2), new_inner, count=1)
        toc_tbl = p_toc[:cs] + new_inner + p_toc[ce:]
        # 같은 행의 다른 칸(장식 칸)도 행 높이를 맞춰야 표가 어긋나지 않는다.
        toc_tbl = re.sub(r'(<hp:cellSz width="\d+" height=")\d+(")',
                         lambda m: m.group(1) + str(need) + m.group(2), toc_tbl)
        toc_tbl = re.sub(r'(<hp:sz width="\d+" widthRelTo="ABSOLUTE" height=")\d+(")',
                         lambda m: m.group(1) + str(need) + m.group(2), toc_tbl, count=1)
        # 표를 감싼 문단의 구(舊) linesegarray는 제거 후 새 높이로 다시 넣는다.
        # (한글 2024가 낡은 캐시를 신뢰해 재계산을 반복하면 멈춤/과대 높이가 발생한다)
        tbl_end = toc_tbl.rindex('</hp:tbl>') + len('</hp:tbl>')
        toc_tbl = (toc_tbl[:tbl_end]
                   + re.sub(r'<hp:linesegarray>.*?</hp:linesegarray>', lineseg(need),
                            toc_tbl[tbl_end:], flags=re.S))
        toc = toc_head + toc_tbl
        toc_note = (f'셀폭 {cw}, 항목 {len(toc_items)}개, paraPr {ep}/charPr {rc},{tc}, '
                    f'줄높이 {evs}(x{pct}%), 표높이 {need}')

divider = ''
if divider_i is not None:
    divider = tpl[divider_i].replace('<hp:t>제 목</hp:t>',
                                     f'<hp:t>{esc((doc_title or "")[:40])}</hp:t>')

# ---------------------------------------------------------------- assemble section
new_sec = WRAP_OPEN + tpl[0] + cover + toc + divider + ''.join(body) + WRAP_CLOSE
io.open(os.path.join(HP, "section0.xml"), "w", encoding="utf-8").write(new_sec)

# ---------------------------------------------------------------- header patches
# (1) 표 테두리용 borderFill 30/31 추가
bf = ('<hh:borderFill id="30" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">'
      '<hh:slash type="NONE" Crooked="0" isCounter="0"/><hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
      '<hh:leftBorder type="SOLID" width="0.12 mm" color="#808080"/>'
      '<hh:rightBorder type="SOLID" width="0.12 mm" color="#808080"/>'
      '<hh:topBorder type="SOLID" width="0.12 mm" color="#808080"/>'
      '<hh:bottomBorder type="SOLID" width="0.12 mm" color="#808080"/>'
      '<hc:fillBrush><hc:winBrush faceColor="#E7EBEF" hatchColor="#000000" alpha="0"/></hc:fillBrush></hh:borderFill>'
      '<hh:borderFill id="31" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">'
      '<hh:slash type="NONE" Crooked="0" isCounter="0"/><hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
      '<hh:leftBorder type="SOLID" width="0.12 mm" color="#808080"/>'
      '<hh:rightBorder type="SOLID" width="0.12 mm" color="#808080"/>'
      '<hh:topBorder type="SOLID" width="0.12 mm" color="#808080"/>'
      '<hh:bottomBorder type="SOLID" width="0.12 mm" color="#808080"/></hh:borderFill>')
bf = bf.replace('id="30"', f'id="{HBF}"').replace('id="31"', f'id="{BBF}"')
hdr = hdr.replace('</hh:borderFills>', bf + '</hh:borderFills>')
hdr = re.sub(r'(<hh:borderFills itemCnt=")(\d+)(")',
             lambda m: m.group(1) + str(int(m.group(2)) + 2) + m.group(3), hdr, count=1)

# (2) 렌더 안 되는 글머리표 스타일 수정: heading NONE + 행잉 인덴트(좌1500/intent-1500)
for pid in FIX_PARAS:
    x = parapr_xml(hdr, pid)
    nx = re.sub(r'<hh:heading type="BULLET"', '<hh:heading type="NONE"', x)
    nx = nx.replace('<hc:intent value="0" unit="HWPUNIT"/><hc:left value="0" unit="HWPUNIT"/>',
                    '<hc:intent value="-1500" unit="HWPUNIT"/><hc:left value="1500" unit="HWPUNIT"/>')
    hdr = hdr.replace(x, nx)

# (3) 표지 제목 글자 축소(30pt→20pt): 제목이 길어 넘칠 때만. 짧으면 템플릿 크기를 그대로 존중.
if len(tl[0] if tl else '') > 10:
    for m in re.finditer(r'<hh:charPr id="(\d+)"[^>]*height="(\d+)"', hdr):
        if int(m.group(2)) >= 3000:
            hdr = hdr.replace(f'id="{m.group(1)}" height="{m.group(2)}"',
                              f'id="{m.group(1)}" height="2000"', 1)
            break

io.open(os.path.join(HP, "header.xml"), "w", encoding="utf-8").write(hdr)

# ---------------------------------------------------------------- content.hpf: 이미지 등록
hpf = io.open(os.path.join(HP, "content.hpf"), encoding="utf-8").read()
ins = ''.join(f'<opf:item id="{iid}" href="{href}" media-type="image/png" isEmbeded="1"/>'
              for iid, href in IMG_ITEMS)
hpf = hpf.replace('<opf:item id="section0"', ins + '<opf:item id="section0"')
io.open(os.path.join(HP, "content.hpf"), "w", encoding="utf-8").write(hpf)

# ---------------------------------------------------------------- repackage (mimetype 무압축·선두)
if os.path.exists(args.out):
    os.remove(args.out)
names = []
for root, _, files in os.walk(WORK):
    for f in files:
        names.append(os.path.relpath(os.path.join(root, f), WORK).replace('\\', '/'))
names.sort(key=lambda x: (x != 'mimetype', x))
with zipfile.ZipFile(args.out, 'w', zipfile.ZIP_DEFLATED) as z:
    for rel in names:
        if rel == 'mimetype' or rel == 'version.xml' or rel.lower().endswith('.png'):
            zi = zipfile.ZipInfo(rel)
            zi.compress_type = zipfile.ZIP_STORED
            z.writestr(zi, open(os.path.join(WORK, rel), 'rb').read())
        else:
            z.write(os.path.join(WORK, rel), rel)
shutil.rmtree(WORK, ignore_errors=True)
print("OK ->", args.out)
print("markers->style:", {k: v['sid'] for k, v in MARKERS.items()},
      "| body:", BODY['sid'], "| caption:", CAPTION['sid'])
print("bullet-fixed paraPr:", sorted(FIX_PARAS), "| images:", len(IMG_ITEMS), "| chapters:", len(chaps))
print(f"toc: 제목문단 {toc_title_i}, 항목표 {toc_table_i} | {toc_note}")
for warning in style_warnings:
    print("WARNING:", warning)
