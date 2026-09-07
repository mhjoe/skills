"""
HWP 파일 처리를 위한 핸들러 클래스
HWP 파일의 내부 XML 구조를 파싱하여 텍스트를 읽고 수정합니다.
"""

import zipfile
import tempfile
import shutil
import copy
import os
from pathlib import Path
from typing import List, Optional, Dict, Tuple, Any
import re
from datetime import datetime

try:
    from lxml import etree as ET
except ImportError:
    from xml.etree import ElementTree as ET


class HwpDocument:
    """HWP 문서 처리 클래스"""

    # HWP XML 네임스페이스
    NAMESPACES = {
        'hwp': 'http://www.hancom.co.kr/hwpml/2.1'
    }

    def __init__(self, file_path: str, create_backup: bool = True):
        """
        HWP 파일 열기

        Args:
            file_path: HWP 파일 경로
            create_backup: 수정 전 백업 생성 여부
        """
        self.file_path = Path(file_path)
        self.create_backup = create_backup
        self.backup_path = None
        self.temp_dir = None
        self.content_xml = None
        self.root = None

        if not self.file_path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

        self._extract_hwp()
        self._parse_content()

    def _extract_hwp(self):
        """HWP 파일을 임시 디렉토리에 압축 해제"""
        self.temp_dir = Path(tempfile.mkdtemp())

        try:
            with zipfile.ZipFile(self.file_path, 'r') as zip_ref:
                zip_ref.extractall(self.temp_dir)
        except zipfile.BadZipFile:
            shutil.rmtree(self.temp_dir)
            raise ValueError(f"잘못된 HWP 파일 형식입니다: {self.file_path}")

        self.content_xml = self.temp_dir / 'content.xml'
        # hwpx 형식 지원 (Contents/section0.xml)
        if not self.content_xml.exists():
            self.content_xml = self.temp_dir / 'Contents' / 'section0.xml'

        if not self.content_xml.exists():
            shutil.rmtree(self.temp_dir)
            raise ValueError("content.xml 또는 section0.xml을 찾을 수 없습니다. 손상된 HWP 파일일 수 있습니다.")

    def _parse_content(self):
        """content.xml 파싱"""
        try:
            # lxml 사용 시도 (더 견고한 파싱)
            try:
                parser = ET.XMLParser(recover=True, strip_cdata=False)
                tree = ET.parse(str(self.content_xml), parser)
                self.root = tree.getroot()
            except:
                # lxml 없을 경우 표준 XML 파서 사용
                with open(self.content_xml, 'rb') as f:
                    content = f.read()

                # BOM 제거
                if content.startswith(b'\xef\xbb\xbf'):
                    content = content[3:]

                import xml.etree.ElementTree as StdET
                self.root = StdET.fromstring(content)
        except Exception as e:
            shutil.rmtree(self.temp_dir)
            raise ValueError(f"XML 파싱 실패: {e}")

    def get_text(self, start: int = 0, length: Optional[int] = None) -> str:
        """
        문서의 텍스트 추출

        Args:
            start: 시작 위치 (기본값: 0)
            length: 추출할 길이 (기본값: None = 전체)

        Returns:
            추출된 텍스트
        """
        if self.root is None:
            return ""

        text_list = []

        # 모든 엘리먼트를 순회하며 텍스트 추출
        def extract_text(elem):
            """재귀적으로 모든 텍스트 추출"""
            if elem.text:
                text_list.append(elem.text)
            for child in elem:
                extract_text(child)
                if child.tail:
                    text_list.append(child.tail)

        extract_text(self.root)
        full_text = ''.join(text_list)

        if length is None:
            return full_text[start:]
        else:
            return full_text[start:start + length]

    def get_char_count(self) -> int:
        """문서의 전체 글자 수 반환"""
        return len(self.get_text())

    def get_paragraph_count(self) -> int:
        """문서의 단락 수 반환"""
        # 단락은 <p> 태그로 표현됨
        para_count = 0
        for p in self.root.iter():
            if p.tag.endswith('}p') or p.tag == 'p':
                para_count += 1
        return para_count

    def find_all(self, search_text: str) -> List[Tuple[int, int]]:
        """
        텍스트에서 모든 매치 찾기

        Args:
            search_text: 찾을 텍스트

        Returns:
            (시작 위치, 끝 위치) 튜플의 리스트
        """
        full_text = self.get_text()
        matches = []

        start = 0
        while True:
            pos = full_text.find(search_text, start)
            if pos == -1:
                break
            matches.append((pos, pos + len(search_text)))
            start = pos + 1

        return matches

    def count_text(self, search_text: str) -> int:
        """
        텍스트의 매치 개수 세기

        Args:
            search_text: 찾을 텍스트

        Returns:
            매치 개수
        """
        return len(self.find_all(search_text))

    def replace_text(self, search_text: str, replace_text: str) -> int:
        """
        문서의 모든 텍스트 바꾸기

        Args:
            search_text: 찾을 텍스트
            replace_text: 바꿀 텍스트

        Returns:
            바뀐 개수
        """
        if self.root is None:
            return 0

        replaced_count = 0

        # 모든 텍스트 엘리먼트 순회
        for elem in self.root.iter():
            if elem.text and search_text in elem.text:
                elem.text = elem.text.replace(search_text, replace_text)
                replaced_count += elem.text.count(replace_text)

        return replaced_count

    def replace_first(self, search_text: str, replace_text: str) -> bool:
        """
        첫 번째 텍스트만 바꾸기

        Args:
            search_text: 찾을 텍스트
            replace_text: 바꿀 텍스트

        Returns:
            성공 여부
        """
        if self.root is None:
            return False

        for elem in self.root.iter():
            if elem.text and search_text in elem.text:
                elem.text = elem.text.replace(search_text, replace_text, 1)
                return True

        return False

    def get_document_info(self) -> Dict[str, Any]:
        """문서 정보 조회"""
        return {
            'char_count': self.get_char_count(),
            'para_count': self.get_paragraph_count(),
            'file_size': self.file_path.stat().st_size,
            'file_path': str(self.file_path),
            'modified_time': datetime.fromtimestamp(self.file_path.stat().st_mtime).isoformat()
        }

    def get_style_info(self) -> Dict[str, Any]:
        """스타일 정보 조회"""
        # styles.xml 파일 찾기
        styles_xml = self.temp_dir / 'styles.xml'

        if not styles_xml.exists():
            return {'status': 'styles.xml not found'}

        try:
            tree = ET.parse(styles_xml)
            root = tree.getroot()

            return {
                'has_styles': True,
                'style_count': len(list(root.iter()))
            }
        except:
            return {'status': 'failed to parse styles'}

    # ------------------------------------------------------------------
    # 표(table) 조작
    #
    # 주의: 표 안의 빈 셀에는 <hp:t> 요소가 아예 없다. 따라서 텍스트 검색
    # (find_all/replace_text)으로는 절대 찾을 수 없으며, 검색을 쓰면 그 문자열이
    # 실재하는 유일한 곳인 '라벨 셀'을 덮어쓰게 된다. 표에 기입할 때는 반드시
    # 아래의 좌표 기반 API를 사용할 것.
    # ------------------------------------------------------------------

    _P = 'http://www.hancom.co.kr/hwpml/2011/paragraph'

    @classmethod
    def _q(cls, tag: str) -> str:
        return '{%s}%s' % (cls._P, tag)

    def get_tables(self) -> List[Any]:
        """문서의 모든 <hp:tbl> 엘리먼트를 문서 순서대로 반환"""
        if self.root is None:
            raise ValueError("문서가 로드되지 않았습니다")
        return list(self.root.iter(self._q('tbl')))

    def get_cell(self, table_index: int, row: int, col: int):
        """
        표의 셀을 좌표로 가져온다.

        Args:
            table_index: get_tables() 기준 표 순번
            row: <hp:tr> 순번 (0-based). 병합 때문에 행마다 셀 개수가 다를 수 있다.
            col: <hp:cellAddr>의 colAddr 값. 리스트 인덱스가 아님에 주의.

        Returns:
            <hp:tc> 엘리먼트
        """
        tbl = self.get_tables()[table_index]
        tr = tbl.findall(self._q('tr'))[row]
        for tc in tr.findall(self._q('tc')):
            if tc.find(self._q('cellAddr')).get('colAddr') == str(col):
                return tc
        raise KeyError(
            "표 %d의 행 %d에 colAddr=%s 셀이 없습니다. "
            "dump_tables()로 실제 좌표를 확인하세요." % (table_index, row, col)
        )

    def get_cell_text(self, table_index: int, row: int, col: int) -> str:
        """셀의 텍스트를 반환 (빈 셀이면 빈 문자열)"""
        tc = self.get_cell(table_index, row, col)
        return " ".join(
            "".join(t.itertext()) for t in tc.iter(self._q('t'))
        ).strip()

    def set_cell_text(self, table_index: int, row: int, col: int,
                      paragraphs, expect_label: Optional[Tuple[int, str]] = None) -> None:
        """
        셀 내용을 문단 리스트로 교체한다.

        Args:
            paragraphs: 문자열 또는 문자열 리스트. 리스트의 각 원소가 한 문단이 되며
                        이것이 한글에서 실제 줄바꿈으로 나타난다.
                        문자열 안의 '\\n'은 줄바꿈이 되지 않으므로 쓰지 말 것.
            expect_label: (col, 기대 텍스트). 지정하면 같은 행의 해당 열 텍스트가
                        기대값과 일치하는지 검증한 뒤 기입한다. 좌표 착오를 잡는
                        안전장치이므로 사용을 권장한다.

        예:
            doc.set_cell_text(4, 3, 1, ["첫 문단", "둘째 문단"],
                              expect_label=(0, "연구주제의 창의성"))
        """
        if isinstance(paragraphs, str):
            paragraphs = [paragraphs]
        if any('\n' in p for p in paragraphs):
            raise ValueError(
                "문단 문자열에 개행문자가 있습니다. HWPX에서 줄바꿈은 별도 문단이므로 "
                "리스트의 원소로 나누어 전달하세요."
            )

        if expect_label is not None:
            label_col, expected = expect_label
            actual = self.get_cell_text(table_index, row, label_col)
            if actual != expected:
                raise AssertionError(
                    "좌표 검증 실패: 표 %d 행 %d의 c%s가 '%s'일 것으로 기대했으나 "
                    "'%s'입니다. 대상 셀을 잘못 지정했을 가능성이 높습니다."
                    % (table_index, row, label_col, expected, actual)
                )

        tc = self.get_cell(table_index, row, col)
        sub = tc.find(self._q('subList'))
        existing = sub.findall(self._q('p'))
        if not existing:
            raise ValueError("셀에 문단 템플릿이 없습니다 (비정상 구조)")

        # 첫 문단을 서식 템플릿으로 삼되, 텍스트와 레이아웃 캐시는 비운다.
        template = copy.deepcopy(existing[0])
        for run in template.findall(self._q('run')):
            for t in run.findall(self._q('t')):
                run.remove(t)
        # <hp:linesegarray>는 '렌더링된 줄' 캐시다. 남겨두면 한글이 옛 줄 수대로
        # 그려서 긴 텍스트가 한 줄로 셀 밖에 넘친다. 반드시 제거해 재계산시킨다.
        for lsa in template.findall(self._q('linesegarray')):
            template.remove(lsa)
        if template.find(self._q('run')) is None:
            ET.SubElement(template, self._q('run'), charPrIDRef='0')

        for p in existing:
            sub.remove(p)

        for i, line in enumerate(paragraphs):
            p = copy.deepcopy(template)
            p.set('id', str(i))
            t = ET.SubElement(p.find(self._q('run')), self._q('t'))
            t.text = line
            sub.append(p)

        # 셀 높이 힌트 (한글이 재계산하지만 초기 렌더링 안정성을 높인다)
        sz = tc.find(self._q('cellSz'))
        if sz is not None and len(paragraphs) > 1:
            est = 1200 + sum(1400 * (1 + len(l) // 40) for l in paragraphs)
            if est > int(sz.get('height', 0)):
                sz.set('height', str(est))

    def dump_tables(self, max_text: int = 40) -> str:
        """
        모든 표의 행/셀 좌표와 내용을 사람이 읽을 수 있게 출력한다.
        표에 기입하기 전에 반드시 먼저 호출해 좌표를 확인할 것.
        """
        out = []
        for ti, tbl in enumerate(self.get_tables()):
            rows = tbl.findall(self._q('tr'))
            out.append("===== TABLE %d  rowCnt=%s colCnt=%s ====="
                       % (ti, tbl.get('rowCnt'), tbl.get('colCnt')))
            for ri, tr in enumerate(rows):
                parts = []
                for tc in tr.findall(self._q('tc')):
                    addr = tc.find(self._q('cellAddr'))
                    span = tc.find(self._q('cellSpan'))
                    txt = " ".join("".join(t.itertext())
                                   for t in tc.iter(self._q('t'))).strip()
                    parts.append("[c%s %sx%s]%r" % (
                        addr.get('colAddr'), span.get('colSpan'),
                        span.get('rowSpan'), txt[:max_text]))
                out.append("  r%-3d %s" % (ri, " ".join(parts)))
        return "\n".join(out)

    def save(self, output_path: Optional[str] = None, overwrite: bool = True):
        """
        문서 저장

        Args:
            output_path: 저장할 경로 (None = 원본 덮어쓰기)
            overwrite: 원본 파일을 덮어쓸지 여부
        """
        if self.root is None:
            raise ValueError("문서가 로드되지 않았습니다")

        # 수정된 XML 저장
        tree = ET.ElementTree(self.root)
        tree.write(self.content_xml, encoding='utf-8', xml_declaration=True)

        # 백업 생성 (필요한 경우)
        if self.create_backup and output_path is None and self.backup_path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            # 확장자를 하드코딩하면 .hwpx를 편집할 때 ZIP 파일에 .hwp 이름이 붙는다.
            suffix = self.file_path.suffix or ".hwpx"
            self.backup_path = self.file_path.parent / f"{self.file_path.stem}.backup_{timestamp}{suffix}"
            shutil.copy2(self.file_path, self.backup_path)
            print(f"백업 파일 생성: {self.backup_path}")

        # 새로운 HWP 파일 생성
        save_path = Path(output_path) if output_path else self.file_path

        with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
            for file_path in self.temp_dir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(self.temp_dir)
                    zip_ref.write(file_path, arcname)

        print(f"파일 저장 완료: {save_path}")

    def close(self):
        """리소스 정리"""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
        self.root = None
        self.content_xml = None

    def __enter__(self):
        """Context manager 진입"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager 종료"""
        self.close()


# 편의 함수들

def extract_text(file_path: str) -> str:
    """HWP 파일에서 텍스트 추출"""
    doc = HwpDocument(file_path)
    try:
        return doc.get_text()
    finally:
        doc.close()


def find_text(file_path: str, search_text: str) -> int:
    """HWP 파일에서 텍스트 검색"""
    doc = HwpDocument(file_path)
    try:
        return doc.count_text(search_text)
    finally:
        doc.close()


def replace_all_text(file_path: str, search_text: str, replace_text: str) -> int:
    """HWP 파일의 텍스트 일괄 변경"""
    doc = HwpDocument(file_path, create_backup=True)
    try:
        count = doc.replace_text(search_text, replace_text)
        doc.save()
        return count
    finally:
        doc.close()


if __name__ == "__main__":
    # 테스트 코드
    print("HWP 핸들러 로드됨. import하여 사용하세요.")
