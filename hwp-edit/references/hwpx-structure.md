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

**줄바꿈은 문자가 아니라 `<hp:p>` 경계다.** `<hp:t>` 안에 `\n`을 넣어도 XML 공백으로
취급되어 화면에 아무 변화가 없다. n줄을 만들려면 `<hp:p>` n개를 만든다.

### linesegarray를 반드시 제거해야 하는 이유

`linesegarray`는 한글이 마지막으로 조판한 결과의 캐시다. `lineseg`가 1개인 문단의
텍스트를 300자로 늘리면서 캐시를 그대로 두면, 한글이 캐시를 신뢰해 **한 줄로 그리고
글자가 셀 밖으로 흘러넘친다.** 문단을 새로 만들 때는 이 요소를 통째로 빼서 한글이
다시 계산하게 한다.

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
