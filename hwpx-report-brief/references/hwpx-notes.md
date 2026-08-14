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

## 7. 검증 체크리스트(한글 없이 할 수 있는 것)
- 모든 XML well-formed (lxml).
- `section0.xml`이 참조하는 `paraPrIDRef/charPrIDRef/styleIDRef/borderFillIDRef`가 header에 존재.
- `binaryItemIDRef`가 `content.hpf`에 등록.
- `BinData` 실제 파일 존재.
- mimetype이 zip 첫 엔트리 & STORED.
- 남은 템플릿 샘플 텍스트("헤드라인M 폰트 …" 등)가 제거됐는지.

## 8. 문단모양/글자모양 조회 회고
`header.xml`은 UTF-8. 콘솔(CP949)로 print 시 한글이 깨질 수 있으니, 조사 결과는 파일로 써서 읽어라.
