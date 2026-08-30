"""
HWP 파일 처리 사용 예제
"""

import sys
from pathlib import Path

# 스크립트 디렉토리를 Python 경로에 추가
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from hwp_handler import HwpDocument, extract_text, find_text, replace_all_text


def example_1_extract_text():
    """예제 1: 텍스트 추출"""
    print("=" * 50)
    print("예제 1: 텍스트 추출")
    print("=" * 50)

    hwp_path = "C:\\path\\to\\your\\document.hwp"  # 실제 경로로 변경하세요

    if Path(hwp_path).exists():
        try:
            # 방법 1: 편의 함수 사용
            text = extract_text(hwp_path)
            print(f"추출된 텍스트 길이: {len(text)} 자")
            print(f"처음 200자:\n{text[:200]}\n")

            # 방법 2: 직접 클래스 사용
            with HwpDocument(hwp_path) as doc:
                info = doc.get_document_info()
                print(f"문서 정보: {info}\n")
        except Exception as e:
            print(f"오류: {e}\n")
    else:
        print(f"파일을 찾을 수 없습니다: {hwp_path}\n")


def example_2_search_text():
    """예제 2: 텍스트 검색"""
    print("=" * 50)
    print("예제 2: 텍스트 검색")
    print("=" * 50)

    hwp_path = "C:\\path\\to\\your\\document.hwp"  # 실제 경로로 변경하세요

    if Path(hwp_path).exists():
        try:
            # 방법 1: 편의 함수 사용
            count = find_text(hwp_path, "회의")
            print(f"'회의'가 {count}번 발견되었습니다.\n")

            # 방법 2: 직접 클래스 사용
            with HwpDocument(hwp_path) as doc:
                matches = doc.find_all("회의")
                print(f"발견된 위치들: {matches[:5]}...")  # 처음 5개만 표시
                print(f"총 {len(matches)}개 발견\n")
        except Exception as e:
            print(f"오류: {e}\n")
    else:
        print(f"파일을 찾을 수 없습니다: {hwp_path}\n")


def example_3_replace_text():
    """예제 3: 텍스트 일괄 변경 (주의: 파일이 수정됩니다)"""
    print("=" * 50)
    print("예제 3: 텍스트 일괄 변경")
    print("=" * 50)
    print("⚠️  주의: 이 기능은 파일을 직접 수정합니다.")
    print("백업이 자동으로 생성됩니다.\n")

    hwp_path = "C:\\path\\to\\your\\document.hwp"  # 실제 경로로 변경하세요

    if Path(hwp_path).exists():
        try:
            # 아래 줄의 주석을 해제하여 사용하세요:
            # count = replace_all_text(hwp_path, "회의", "미팅")
            # print(f"'{count}개' 항목이 변경되었습니다.\n")

            print("코드 실행 예제:")
            print("  count = replace_all_text(hwp_path, '회의', '미팅')")
            print("  print(f'{count}개 항목이 변경되었습니다.')\n")

            # 안전한 방식으로 미리보기만 하기
            with HwpDocument(hwp_path) as doc:
                count = doc.count_text("회의")
                print(f"변경하려면 '{count}개' 항목이 영향을 받을 것입니다.\n")
        except Exception as e:
            print(f"오류: {e}\n")
    else:
        print(f"파일을 찾을 수 없습니다: {hwp_path}\n")


def example_4_document_info():
    """예제 4: 문서 정보 조회"""
    print("=" * 50)
    print("예제 4: 문서 정보 조회")
    print("=" * 50)

    hwp_path = "C:\\path\\to\\your\\document.hwp"  # 실제 경로로 변경하세요

    if Path(hwp_path).exists():
        try:
            with HwpDocument(hwp_path) as doc:
                info = doc.get_document_info()
                print("문서 정보:")
                for key, value in info.items():
                    print(f"  {key}: {value}")

                style_info = doc.get_style_info()
                print("\n스타일 정보:")
                for key, value in style_info.items():
                    print(f"  {key}: {value}")
                print()
        except Exception as e:
            print(f"오류: {e}\n")
    else:
        print(f"파일을 찾을 수 없습니다: {hwp_path}\n")


def example_5_range_text():
    """예제 5: 범위 텍스트 추출"""
    print("=" * 50)
    print("예제 5: 범위 텍스트 추출")
    print("=" * 50)

    hwp_path = "C:\\path\\to\\your\\document.hwp"  # 실제 경로로 변경하세요

    if Path(hwp_path).exists():
        try:
            with HwpDocument(hwp_path) as doc:
                # 처음 100자 추출
                text = doc.get_text(start=0, length=100)
                print(f"처음 100자:\n{text}\n")

                # 100자부터 200자까지 추출
                text = doc.get_text(start=100, length=100)
                print(f"100자부터 200자까지:\n{text}\n")
        except Exception as e:
            print(f"오류: {e}\n")
    else:
        print(f"파일을 찾을 수 없습니다: {hwp_path}\n")


def example_6_context_manager():
    """예제 6: Context Manager 사용"""
    print("=" * 50)
    print("예제 6: Context Manager 사용 (권장)")
    print("=" * 50)

    hwp_path = "C:\\path\\to\\your\\document.hwp"  # 실제 경로로 변경하세요

    if Path(hwp_path).exists():
        try:
            # Context manager를 사용하면 자동으로 리소스가 정리됩니다
            with HwpDocument(hwp_path) as doc:
                text = doc.get_text()
                char_count = len(text)
                para_count = doc.get_paragraph_count()

                print(f"글자 수: {char_count}")
                print(f"단락 수: {para_count}")
                print("Context manager 사용으로 자동 정리됨\n")
        except Exception as e:
            print(f"오류: {e}\n")
    else:
        print(f"파일을 찾을 수 없습니다: {hwp_path}\n")


def main():
    """메인 함수"""
    print("\n" + "=" * 50)
    print("HWP 파일 처리 사용 예제")
    print("=" * 50 + "\n")

    # 모든 예제 실행
    example_1_extract_text()
    example_2_search_text()
    example_3_replace_text()
    example_4_document_info()
    example_5_range_text()
    example_6_context_manager()

    print("=" * 50)
    print("예제 완료")
    print("=" * 50)


if __name__ == "__main__":
    main()
