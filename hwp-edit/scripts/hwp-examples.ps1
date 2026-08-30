# HWP 파일 처리 사용 예제

# 스크립트 디렉토리에서 헬퍼 함수 로드
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDir "hwp-helper.ps1")

# ============================================
# 예제 1: HWP 문서에서 텍스트 추출
# ============================================
Write-Host "=== 예제 1: 텍스트 추출 ===" -ForegroundColor Green
$hwpPath = "C:\path\to\your\document.hwp"  # 실제 경로로 변경하세요

if (Test-Path $hwpPath) {
    $text = Get-HwpText -Path $hwpPath
    Write-Host "추출된 텍스트 길이: $($text.Length) 자"
    Write-Host "처음 200자:" -ForegroundColor Yellow
    Write-Host $text.Substring(0, [Math]::Min(200, $text.Length))
}
else {
    Write-Host "문서를 찾을 수 없습니다. 경로를 확인하세요." -ForegroundColor Red
}

# ============================================
# 예제 2: 특정 텍스트 찾기
# ============================================
Write-Host "`n=== 예제 2: 텍스트 검색 ===" -ForegroundColor Green
if (Test-Path $hwpPath) {
    $searchResult = Find-HwpText -Path $hwpPath -SearchText "회의"
    Write-Host "검색 결과: '$($searchResult.SearchTerm)'이(가) $($searchResult.Found)번 발견되었습니다."
}

# ============================================
# 예제 3: 일괄 텍스트 변경 (주석 처리됨 - 안전상 이유)
# ============================================
Write-Host "`n=== 예제 3: 일괄 텍스트 변경 ===" -ForegroundColor Green
Write-Host "주의: 이 기능은 문서를 직접 수정하므로 신중하게 사용하세요."
Write-Host "백업이 자동으로 생성됩니다."

# 아래 줄을 사용하려면 주석을 제거하세요:
# $replaceResult = Replace-HwpText -Path $hwpPath -SearchText "회의" -ReplaceText "미팅"
# Write-Host "변경 완료: '$($replaceResult.SearchTerm)' → '$($replaceResult.ReplaceTerm)' ($($replaceResult.ReplacedCount)번)"

# ============================================
# 예제 4: 문서 텍스트 길이 확인
# ============================================
Write-Host "`n=== 예제 4: 문서 정보 ===" -ForegroundColor Green
if (Test-Path $hwpPath) {
    $length = Get-HwpTextLength -Path $hwpPath
    Write-Host "총 텍스트 길이: $length 자"
}

# ============================================
# 예제 5: 특정 범위의 텍스트 추출
# ============================================
Write-Host "`n=== 예제 5: 범위 텍스트 추출 ===" -ForegroundColor Green
if (Test-Path $hwpPath) {
    $rangeText = Get-HwpTextRange -Path $hwpPath -Start 0 -Length 100
    Write-Host "처음 100자:"
    Write-Host $rangeText
}

Write-Host "`n=== 예제 완료 ===" -ForegroundColor Green
