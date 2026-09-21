# HWPX 내부 구조 노트

`hwp-edit` 스킬이 다루는 파일 형식의 세부 사항. 스킬 본문(`SKILL.md`)의 규칙이
왜 그런지 확인해야 할 때 참조한다.

## 패키지 구성

`.hwpx`는 ZIP 아카이브다. 전형적인 구성:

```
mimetype
version.xml
settings.xml
META-INF/container.xml
META-INF/container.rdf
META-INF/manifest.xml
Contents/content.hpf
Contents/header.xml        # 글꼴·문단모양·글자모양·스타일 정의
Contents/section0.xml      # 본문 (구역마다 section1, section2 …)
Preview/PrvText.txt        # 평문 미리보기 (빠른 텍스트 확인용)
Preview/PrvImage.png
```

구형 `.hwp`(HWPML로 저장된 경우)는 최상위에 `content.xml`을 둔다. 핸들러는
`content.xml`을 먼저 찾고, 없으면 `Contents/section0.xml`로 넘어간다.

`Preview/PrvText.txt`는 문서의 평문 사본이라 **구조 없이 내용만 빠르게 확인할 때**
유용하다. 다만 최신 편집분이 반영되지 않을 수 있으므로 신뢰할 소스로 쓰지 않는다.

## 네임스페이스

```
hp   http://www.hancom.co.kr/hwpml/2011/paragraph   # 문단·표·런·텍스트
hs   http://www.hancom.co.kr/hwpml/2011/section     # 구역
hh   http://www.hancom.co.kr/hwpml/2011/head        # 헤더(스타일 정의)
hc   http://www.hancom.co.kr/hwpml/2011/core
```

거의 모든 본문 조작은 `hp` 네임스페이스에서 이뤄진다. `lxml`로 다룰 때는 정규화된
이름을 쓴다: `{http://www.hancom.co.kr/hwpml/2011/paragraph}tbl`

## 섹션

`.hwpx`의 본문은 `Contents/section0.xml` 하나가 아니다. 한글은 장/절 구분이나 단
구성이 바뀌는 지점마다 새 섹션을 만들어 `section0.xml`, `section1.xml`,
`section2.xml` … 로 번호를 붙인다.

```
Contents/section0.xml   표지·국문초록
Contents/section1.xml   영문초록
Contents/section2.xml   본문 전체
```

**`section0`만 읽으면 본문을 놓치고도 오류가 나지 않는다.** 텍스트 추출·치환·표 탐색은
모든 `section*.xml`을 번호 순으로 순회해야 하고, 저장할 때도 수정한 섹션을 각각
되써야 한다. 섹션 사이에 문단·표 번호가 이어지는 것이 아니므로, 문서 전체 기준의
순번이 필요하면 순회하면서 직접 매겨야 한다.

## 문단

```xml
<hp:p id="0" paraPrIDRef="30" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
  <hp:run charPrIDRef="14">
    <hp:t>연구주제의 창의성</hp:t>
  </hp:run>
  <hp:linesegarray>
    <hp:lineseg textpos="0" vertpos="0" vertsize="1100" textheight="1100"
                baseline="935" spacing="440" horzpos="0" horzsize="7448" flags="393216"/>
  </hp:linesegarray>
</hp:p>
```

- `paraPrIDRef` / `charPrIDRef` — `header.xml`의 문단모양·글자모양 참조.
  텍스트만 갈아끼우고 이 값을 유지하면 **서식이 보존된다.**
- `<hp:t>` — 실제 텍스트. **빈 문단에는 이 요소가 없고 `<hp:run>`이 self-closing이다.**
- `<hp:linesegarray>` — 레이아웃 캐시. `<hp:lineseg>` 하나가 화면의 한 줄에 대응한다.

### 줄바꿈

**줄바꿈은 문자가 아니라 `<hp:p>` 경계다.** `<hp:t>` 안에 `\n`을 넣어도 화면에는
아무 변화가 없다. n줄을 만들려면 `<hp:p>` n개를 만든다.

### `<hp:t>` 안의 개행은 한글이 저장할 때 데이터를 버린다

표시만의 문제가 아니다. 개행이 든 `<hp:t>`가 있는 문서를 **한글에서 한 번 열어
저장하면 개행 뒤의 텍스트가 통째로 사라진다.**

```
<hp:t>0.1649*** (0.0087)</hp:t>   <- (0.0087) 앞에 개행이 있으면
<hp:t>0.1649***</hp:t>            <- 한글 저장 후 이렇게 남는다
```

편집 직후에는 정상이고 파일도 문제없이 열리므로, **사용자가 한글에서 저장하기
전까지 드러나지 않는다.** 실제로 회귀표의 표준오차 44칸이 이렇게 사라졌다.

`HwpDocument.find_text_newlines()`로 저장 직전에 점검하고, 여러 줄이 필요하면
문단을 나누거나 한 줄로 합친다.

### linesegarray를 반드시 제거해야 하는 이유

`linesegarray`는 한글이 마지막으로 조판한 결과의 캐시이고, **`lineseg`의 `textpos`는
그 문단 텍스트에 대한 문자 인덱스**다. 캐시를 남긴 채 문단의 텍스트 길이를 바꾸면
두 가지가 일어난다. 두 번째가 훨씬 치명적이다.

**① 텍스트가 길어진 경우 — 잘못 그려진다**

`lineseg`가 1개인 문단의 텍스트를 300자로 늘리면 한글이 캐시를 신뢰해 **한 줄로
그리고 글자가 셀 밖으로 흘러넘친다.** 파일은 열리지만 조판이 깨진다.

**② 텍스트가 짧아진 경우 — 파일이 아예 열리지 않는다**

런을 지우거나 짧은 문자열로 치환해 문단이 짧아지면, 남아 있는 `lineseg`의 `textpos`가
**실제 텍스트 길이를 넘어선다.** 이 상태의 파일을 열면 한글이 이렇게 거부한다.

> 파일이 손상되었거나 다른 프로그램에 의해 변경되었습니다.

XML은 완벽하게 well-formed이고 ZIP도 멀쩡하므로 `lxml` 파싱이나 `zipfile.testzip()`
으로는 **절대 잡히지 않는다.** 실제 사례: 272자짜리 런 하나를 문단에서 제거했더니
그 문단의 `lineseg` 30여 개가 모두 범위를 벗어나 문서 전체가 열리지 않았다.

**따라서 불변 규칙은 이것이다.**

> **문단의 텍스트 길이를 바꾸는 모든 편집은, 그 문단의 `<hp:linesegarray>`를
> 함께 제거해야 한다.** 런 추가·삭제, `hp:t` 치환, 런 분할 — 예외 없다.

```python
def drop_linesegs(paragraph):
    """문단 텍스트를 건드렸다면 반드시 호출한다."""
    for lsa in paragraph.findall('{http://www.hancom.co.kr/hwpml/2011/paragraph}linesegarray'):
        paragraph.remove(lsa)
```

제거하면 한글이 열 때 다시 계산하므로 손실은 없다. **남기는 쪽이 위험하고,
지우는 쪽은 안전하다.** 판단이 서지 않으면 지운다.

## 표

```xml
<hp:tbl rowCnt="11" colCnt="8" ...>
  <hp:tr>
    <hp:tc borderFillIDRef="9">
      <hp:subList vertAlign="CENTER" ...>
        <hp:p>...</hp:p>        <!-- 셀 내용은 문단의 나열 -->
      </hp:subList>
      <hp:cellAddr colAddr="5" rowAddr="2"/>
      <hp:cellSpan colSpan="1" rowSpan="1"/>
      <hp:cellSz width="4984" height="2618"/>
      <hp:cellMargin left="141" right="141" top="141" bottom="141"/>
    </hp:tc>
    ...
  </hp:tr>
</hp:tbl>
```

### 셀 주소가 인덱스와 다른 이유

`<hp:cellSpan>` 때문에 **행마다 `<hp:tc>` 개수가 다르고, `colAddr`도 건너뛴다.**
병합된 셀은 시작 행에만 존재하고 이어지는 행에는 아예 없다.

실제 심사서식 표의 예:

```
r1  [c0]'평가항목' [c1]'세부항목' [c2 2x1]'A 아주 우수' [c4]'B 우수' [c5]'C 보통' [c6]'D 미흡' [c7]'F 아주 미흡'
r2  [c0 1x2]'주제' [c1]'연구주제의 창의성' [c2 2x1]'' [c4]'' [c5]'' [c6]'' [c7]''
r3                 [c1]'연구목적의 타당성' [c2 2x1]'' [c4]'' [c5]'' [c6]'' [c7]''
```

- A열은 `colSpan=2`라 `colAddr=2`를 차지하고 `c3`은 존재하지 않는다 → B열은 `c4`
- r2의 `'주제'`는 `rowSpan=2`라 r3에는 그 셀이 없다 → r3의 첫 `<hp:tc>`가 `c1`

따라서 **`tr.findall('tc')[n]` 같은 인덱스 접근은 반드시 어긋난다.** `cellAddr`의
`colAddr` 값으로 찾아야 한다.

### 셀 높이

`<hp:cellSz height>`는 조판 결과값이다. 한글이 열 때 대체로 다시 계산하지만,
문단을 여러 개 넣을 때는 넉넉한 값을 미리 넣어두면 초기 렌더링이 안정적이다.

## 저장 시 주의

- `mimetype` 항목은 **압축하지 않고(`ZIP_STORED`) 아카이브 맨 앞에** 두는 것이 안전하다
- XML 선언(`<?xml version='1.0' encoding='UTF-8'?>`)을 유지한다
- 네임스페이스 접두사를 보존한다 (`lxml`은 원본 문서에서 파싱하면 자동 유지,
  표준 `ElementTree`는 `register_namespace()`가 필요하다)

## 확인용 스니펫

표 구조를 눈으로 확인할 때:

```python
import zipfile
from lxml import etree

P = 'http://www.hancom.co.kr/hwpml/2011/paragraph'
q = lambda t: '{%s}%s' % (P, t)

zf = zipfile.ZipFile('문서.hwpx')
root = etree.fromstring(zf.read('Contents/section0.xml'))
zf.close()

for ti, tbl in enumerate(root.iter(q('tbl'))):
    print('TABLE', ti)
    for ri, tr in enumerate(tbl.findall(q('tr'))):
        cells = []
        for tc in tr.findall(q('tc')):
            a = tc.find(q('cellAddr'))
            s = tc.find(q('cellSpan'))
            txt = ' '.join(''.join(t.itertext()) for t in tc.iter(q('t'))).strip()
            cells.append("[c%s %sx%s]%r" % (
                a.get('colAddr'), s.get('colSpan'), s.get('rowSpan'), txt[:30]))
        print('  r%-3d %s' % (ri, ' '.join(cells)))
```

`HwpDocument.dump_tables()`가 이것과 같은 출력을 낸다.
