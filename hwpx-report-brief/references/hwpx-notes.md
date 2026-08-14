# HWPX 내부 구조 & 실전 노트

한컴 HWPX(=OWPML) 문서를 코드로 생성할 때 필요한 지식과, 이 스킬을 만들며 겪은 함정 정리.

## 1. 패키지 구조
HWPX는 ZIP 컨테이너. 주요 파일:
```
mimetype                 → "application/hwp+zip" (무압축·zip 선두 필수)
version.xml, settings.xml
META-INF/container.xml, container.rdf, manifest.xml
Contents/content.hpf     → OPF 매니페스트(이미지/섹션/헤더 목록 + spine)
Contents/header.xml       → 폰트/테두리/글자모양/문단모양/스타일/글머리표 정의
Contents/section0.xml     → 본문(문단 <hp:p> 나열)
BinData/imageN.PNG        → 삽입 이미지
Preview/PrvText.txt, PrvImage.png
```
- **mimetype 및 무압축 규칙**: `mimetype`은 zip의 첫 엔트리이면서 STORED(무압축)여야 함. 또한 `version.xml` 및 `Preview/PrvImage.png`도 STORED(무압축) 상태여야 한글 2024에서 "손상/변조 경고창"이 발생하지 않음.

## 2. 스타일 = styleIDRef
한글 UI에서 "스타일 적용"은 결국 문단의 `styleIDRef`를 지정하는 것. 코드로 같은 값을 쓰면 동일 결과.
```
<hp:p paraPrIDRef="38" styleIDRef="4" …><hp:run charPrIDRef="5"><hp:t>텍스트</hp:t></hp:run>…</hp:p>
```
- `header.xml`의 `<hh:style id="4" name="□" paraPrIDRef="37" charPrIDRef="5">`가 스타일 정의.
- 깨끗한 스타일 적용 = 문단의 `paraPrIDRef`/`charPrIDRef`를 **그 스타일이 지정한 값과 동일하게** 둔다.
  다르면 "스타일 + 로컬 덧칠" 상태가 된다(드롭다운엔 스타일명 표시됨).
- 스타일 ID는 하드코딩하지 마라. 템플릿을 한글에서 다시 저장하면 ID가 재배열될 수 있다.
  이름도 안전하지 않다 — 실제로 이 양식은 개요 스타일 이름이 `ㅁ`(U+3141)에서 `□`(U+25A1)로 바뀐 적이 있다.
  개요 스타일은 **자동 글머리표 문자로 조회**하고, 이름 조회는 폴백으로만 쓰는 편이 견고하다.

## 3. 개요 스타일의 자동 글머리표(bullet) — 핵심 함정
`<hh:paraPr>`에 `<hh:heading type="BULLET" idRef="3" level="2"/>`가 있으면 해당 문단 앞에
글머리표가 **자동으로** 그려진다. 글머리표 문자는 `<hh:bullets>`의 `<hh:bullet id="3" char="□">`.
→ 따라서 원고 텍스트에 □를 넣으면 **안 된다**(자동 글머리표와 중복). 마커를 떼고 스타일만 지정.

### `※`와 `*`의 의미는 계층이 다르다

- `※`는 `ㅁ → ㅇ → - → ※` 개요 체계에서 `-`의 바로 하위 단계다. 활성 `-` 상위 문단이
  없는 고립된 `※`에는 해당 스타일을 적용하지 않고 경고한다. 같은 `-` 아래의 연속 `※`는 허용한다.
- `*`는 개요 단계가 아니라, 직전 문단에서 위첨자 `*`를 붙인 용어·문장을 풀이하는 부연설명이다.
- 따라서 두 스타일을 들여쓰기 깊이만으로 교환하지 않는다. `*`는 직전 문단에 위첨자 표시가
  있을 때만 적용하고, 표시가 없으면 일반 본문으로 남겨 잘못된 의미 부여를 막는다.
- DOCX는 run의 superscript 속성으로 근거 표시를 확인한다. TXT/MD는 `용어*`처럼 앞말에 붙은
  별표를 위첨자 표시 의도로 해석한다.

### 함정: 자동 글머리표가 안 보이는 경우
글머리표는 문단의 **좌여백(행잉 인덴트) 공간**에 그려진다. 어떤 스타일의 문단모양 좌여백이 `0`이면
글머리표가 그려질 자리가 없어 글자에 가려지거나 사라진다.
- 이 템플릿에서 `ㅇ`=좌2000, `-`=좌4000, `*`=좌5760, `※`=좌6000은 정상. `□`만 **좌0**이라 □가 안 보였다.
- 폰트 문제로 오인하기 쉬우나(디스플레이 폰트 글리프 누락 가설), 실제로 HY헤드라인M에는 □가 **있었다**.
  원인은 순전히 여백=0.
- **해결**: 그 문단모양의 heading을 `NONE`으로 끄고, 좌여백/intent를 행잉(예: left=1500, intent=-1500)으로
  주고, 마커 문자를 본문에 직접 삽입한다. 스타일 자체는 그대로 유지.

폰트 글리프 확인 팁(fonttools):
```python
from fontTools.ttLib import TTFont
def has(fp,cp):
    return any(cp in t.cmap for t in TTFont(fp)['cmap'].tables)
# HY헤드라인M=H2HDRM.TTF: □(0x25A1)=True, ◯(0x25EF)=False, ―(0x2015)=True, ※(0x203B)=True
```

## 4. 이미지 삽입
1. PNG를 `BinData/imageN.PNG`에 복사.
2. `content.hpf`의 `<opf:manifest>`에 등록:
   `<opf:item id="imageN" href="BinData/imageN.PNG" media-type="image/png" isEmbeded="1"/>`
   - `hashkey`는 필수가 아니며(값을 못 맞추면 생략), 잘못된 값보다 생략이 안전.
3. 본문에서 `<hp:pic>`로 참조, 내부 `<hc:img binaryItemIDRef="imageN"/>`.
   - `treatAsChar="1"` + 문단 정렬 CENTER로 인라인·가운데 배치.
   - `orgSz`=`curSz`=`sz`로 두고 trans/sca/rot 매트릭스를 단위행렬로 두면 지정 크기대로 렌더.
   - 크기는 HWPUNIT(=1/7200인치). 본문 폭 ≈ pagePr.width − 좌우여백 ≈ 48190. 46000 정도면 안전.

## 5. 표
- `<hp:tbl rowCnt colCnt borderFillIDRef …>` 안에 `<hp:tr><hp:tc borderFillIDRef=… ><hp:subList>…셀 문단…</hp:subList>…</hp:tc></hp:tr>`.
- 셀 문단은 일반 `<hp:p>`. 셀 내 줄바꿈은 여러 `<hp:p>`로.
- 테두리/음영은 `borderFill`로. 새 borderFill을 추가할 땐 **기존 최대 id+1**부터 부여하고
  `<hh:borderFills itemCnt>`를 증가시킨다. (주의: `id="30"` 문자열 검사는 paraPr/charPr의 id와 충돌하니
  반드시 `<hh:borderFill id="30"`로 검사.)
- `noAdjust="0"`이면 한글이 내용에 맞춰 행높이 자동조정.

## 6. lineseg(레이아웃 캐시) — HWP 2024 멈춤 주의
`<hp:linesegarray>`는 픽셀 좌표 조판 캐시다.
**주의**: 스타일, 여백, 들여쓰기, 글머리표 등을 새로 변경하거나 기존 문단을 개조할 때 문단 내 구(舊) `<hp:linesegarray>`를 그대로 남겨두면, 한글 2024에서 변경된 문단 모양과 구 픽셀 좌표 간 충돌로 인해 레이아웃 무한 재계산 루프가 발생하여 "HWP 2024가 응답하지 않습니다" 멈춤(Freeze) 현상이 일어난다.
→ 문단 스타일/여백을 새로 적용할 때는 구 `<hp:linesegarray>`를 완전히 제거하여 한글 2024가 문서를 열 때 새로 레이아웃 좌표를 계산하도록 처리해야 한다.

## 6-1. 목차 표를 갈아끼울 때 — 세로 폭발 함정 (실제 회귀 사례)
증상: 생성 문서 2페이지 목차 표가 세로로 수 페이지 길이로 늘어남.

원인 세 겹:
1. **제목 표를 항목 표로 오인.** 이 양식의 목차 페이지는 표가 **두 개**다.
   - 「목  차」 **제목 장식 표**: 1행 7열, 칸 폭 `565 / 565 / 1414 / 13191 / 1414 / 565 / 565`
     — 폭 565 HWPUNIT ≈ **2mm**인 장식 칸이 좌우를 감싼다.
   - **항목 표**: 1행 1열, 폭 46492 — 여기에 `Ⅰ…Ⅴ`, `[붙 임]`, `[참 고]` 예시가 들어있다.

   탐지 코드가 `find_idx(…'numberingType="TABLE"'…, toc_title_i)`로 **제목 문단 자신부터**
   찾으면 제목 표를 집어온다(제목이 표 안에 있으므로 `toc_title_i == toc_table_i`).
   → `p_toc.index('<hp:subList')`가 잡는 **첫 칸(폭 2mm)** 에 항목이 들어가고,
   한 글자마다 줄바꿈되어 `Ⅰ. 추진실적(6.29. ~ 7.3.)` 한 줄이 20여 줄로 부풀었다.
   동시에 진짜 항목 표는 조립에서 빠져 사라졌다.
   → **`toc_title_i + 1`부터 찾고, 제목 텍스트를 품은 표는 후보에서 제외**한다.

2. **삽입 칸을 '첫 subList'로 고정.** 폭 기준으로 골라야 한다. 가장 넓은 칸을 쓰고,
   그 폭이 표 전체의 50% 미만이거나 10000 HWPUNIT(≈35mm) 미만이면 **삽입을 포기**한다.
   탐지가 틀려도 얇은 장식 칸에 텍스트가 들어가는 일이 원리적으로 불가능해진다.

3. **높이 미갱신.** 항목 10개용 `<hp:cellSz height="58199">`를 그대로 두고 항목 3개만 넣으면
   그 차이가 빈 공간으로 남는다. 내용 높이로 다시 계산해야 한다:
   ```
   줄높이 = charPr height                       (예: 1800)
   줄간격 초과분 = 줄높이 × (lineSpacing% − 100) / 100   (160% → 1080)
   문단 간격 = paraPr margin의 prev + next      (예: 2500 + 0)
   항목당 = 1800 + 1080 + 2500 = 5380
   표 높이 = 항목당 × 항목수 + cellMargin(top+bottom)
   ```
   `<hp:cellSz height>`(같은 행 **모든** 칸), `<hp:sz height>`, 표를 감싼 문단의
   `<hp:linesegarray>`를 함께 갱신한다(§6 캐시 규칙과 동일한 이유).

부수 원인: 정규식 탐지 실패 시 `paraPr='34'`, `charPr='26'/'34'` 같은 **하드코딩 폴백**이
목차용이 아닌 본문 개요 문단모양(문단 위 간격 2500)을 물려 줄마다 여백을 더했다.
폴백은 상수가 아니라 **대상 칸의 기존 문단**에서 읽어야 한다.

## 7. 검증 체크리스트(한글 없이 할 수 있는 것)
- 모든 XML well-formed (lxml).
- `section0.xml`이 참조하는 `paraPrIDRef/charPrIDRef/styleIDRef/borderFillIDRef`가 header에 존재.
- `binaryItemIDRef`가 `content.hpf`에 등록.
- `BinData` 실제 파일 존재.
- mimetype이 zip 첫 엔트리 & STORED.
- 남은 템플릿 샘플 텍스트("헤드라인M 폰트 …" 등)가 제거됐는지.
- **목차 항목이 폭이 충분한 칸에 들어갔는지** — 표별로 `cellSz width`와 칸 안 문단 수를 덤프해
  보면 §6-1의 세로 폭발을 즉시 잡을 수 있다. `build_hwpx.py`가 찍는 `toc:` 로그(제목문단/항목표
  번호, 셀폭, 항목 수, 표높이)도 같은 목적이다.

## 8. 문단모양/글자모양 조회 회고
`header.xml`은 UTF-8. 콘솔(CP949)로 print 시 한글이 깨질 수 있으니, 조사 결과는 파일로 써서 읽어라.
