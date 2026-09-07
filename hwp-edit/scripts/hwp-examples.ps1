# hwp-helper.ps1 사용 예제
#
# 주의: 문서를 읽고 고치는 기본 경로는 Python + XML(hwp_handler.py)이다.
# 여기 있는 COM 경로는 XML로 불가능한 작업 - 바이너리 .hwp 변환, PDF 내보내기,
# 텍스트 추출 - 에만 쓴다.

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDir "hwp-helper.ps1")

# ============================================
# 예제 0: 환경 점검 (제일 먼저 이걸 실행한다)
# ============================================
Write-Host "=== 예제 0: 환경 점검 ===" -ForegroundColor Green
$env0 = Test-HwpEnvironment
$env0 | Format-List

if (-not $env0.DialogFree) {
    Write-Host "보안 모듈이 등록되지 않았습니다. 등록하지 않으면 파일을 열고" -ForegroundColor Yellow
    Write-Host "저장할 때마다 한글 보안 승인 대화상자가 뜹니다. 지금 등록합니다..." -ForegroundColor Yellow
    if (Register-HwpSecurityModule) {
        Write-Host "  OK  등록 완료" -ForegroundColor Green
    } else {
        Write-Host "  X   DLL이 없습니다. 아래를 한 번 실행하세요:" -ForegroundColor Red
        Write-Host "      uv run --python 3.12 --link-mode=copy --with pyhwpx --with pywin32 python hwp_com.py --setup" -ForegroundColor White
        return
    }
}

$hwpPath = "C:\path\to\your\document.hwp"   # 실제 경로로 변경하세요
if (-not (Test-Path $hwpPath)) {
    Write-Host "`n문서를 찾을 수 없습니다. `$hwpPath를 실제 경로로 바꾸세요." -ForegroundColor Red
    return
}

# ============================================
# 예제 1: 텍스트 추출
# ============================================
Write-Host "`n=== 예제 1: 텍스트 추출 ===" -ForegroundColor Green
$text = Get-HwpText -Path $hwpPath
Write-Host "추출된 텍스트 길이: $($text.Length) 자"
Write-Host $text.Substring(0, [Math]::Min(200, $text.Length))

# ============================================
# 예제 2: 바이너리 .hwp -> .hwpx 변환 후 XML 경로로 넘기기
# ============================================
Write-Host "`n=== 예제 2: .hwpx로 변환 ===" -ForegroundColor Green
$hwpx = Convert-HwpFile -Path $hwpPath -Format HWPX
Write-Host "변환 완료: $hwpx"
Write-Host "이제부터는 COM이 아니라 Python XML 경로로 작업합니다:" -ForegroundColor Cyan
Write-Host "  uv run --python 3.12 --link-mode=copy --with lxml python work.py" -ForegroundColor White

# ============================================
# 예제 3: PDF 내보내기 (XML 경로로는 불가능한 작업)
# ============================================
Write-Host "`n=== 예제 3: PDF 내보내기 ===" -ForegroundColor Green
$pdf = Convert-HwpFile -Path $hwpPath -Format PDF
Write-Host "PDF 생성: $pdf"

# ============================================
# 텍스트 검색/치환은 COM으로 하지 않는다
# ============================================
Write-Host "`n=== 검색 / 치환 ===" -ForegroundColor Green
Write-Host "COM으로 하지 말고 hwp_handler.py를 쓰세요. 표 양식의 빈 칸은" -ForegroundColor Yellow
Write-Host "replace_text가 아니라 set_cell_text(좌표)로 채워야 합니다." -ForegroundColor Yellow
Write-Host "자세한 내용은 SKILL.md의 '표 작업 규칙'을 보세요." -ForegroundColor Yellow

Write-Host "`n=== 예제 완료 ===" -ForegroundColor Green
