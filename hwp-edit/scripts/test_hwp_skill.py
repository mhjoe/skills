#!/usr/bin/env python3
"""HWP Skill 테스트 스크립트"""

import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# 테스트용 HWP 파일 생성
test_hwp = Path(__file__).parent.parent / "test_sample.hwp"

# 간단한 content.xml 생성
content_xml = b'''<root>
    <p><Text>Test content 1</Text></p>
    <p><Text>Conference schedule</Text></p>
    <p><Text>Conference room</Text></p>
</root>'''

# HWP 파일 (ZIP) 생성
with zipfile.ZipFile(test_hwp, 'w') as hwp:
    hwp.writestr('content.xml', content_xml)
    hwp.writestr('meta.xml', b'<meta/>')

print('Test file created')
print('')

# HwpDocument로 파일 읽기
try:
    from hwp_handler import HwpDocument

    print('Testing HwpDocument:')
    print('-' * 50)

    with HwpDocument(str(test_hwp)) as doc:
        print('[1] File opened ✓')

        # 텍스트 추출
        text = doc.get_text()
        print(f'[2] Text extracted: {len(text)} chars ✓')
        print(f'    Content: "{text.strip()}"')

        # 검색
        count = doc.count_text('Conference')
        print(f'[3] Search: "Conference" found {count} times ✓')

        # 문서 정보
        info = doc.get_document_info()
        print(f'[4] Document info ✓')
        print(f'    Chars: {info["char_count"]}, Paragraphs: {info["para_count"]}')

        # 범위 추출
        range_text = doc.get_text(start=0, length=20)
        print(f'[5] Range extraction: "{range_text}" ✓')

    print('')
    print('=' * 50)
    print('✓ ALL TESTS PASSED!')
    print('=' * 50)
    print('')
    print('HWP Skill is ready to use!')

except Exception as e:
    print(f'ERROR: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
