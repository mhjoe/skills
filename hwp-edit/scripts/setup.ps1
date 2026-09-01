# HWP 처리 환경 설정 / 점검 스크립트
#
# 기본 경로(XML 처리)는 lxml만 있으면 된다.
# 바이너리 .hwp 변환·PDF 내보내기가 필요하면 한글 + pywin32 + 보안모듈이 추가로 필요하다.
#
# 이 스크립트는 아무것도 전역 설치하지 않는다. uv가 실행 시점에 의존성을 준비한다.

$ErrorActionPreference = 'Continue'

Write-Host "========================================" -ForegroundColor Green
Write-Host "hwp-edit 환경 점검"
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

$fail = $false

# [1/4] uv
Write-Host "[1/4] uv 확인..." -ForegroundColor Yellow
$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv) {
    Write-Host "  OK  uv: $(uv --version)" -ForegroundColor Green
} else {
    Write-Host "  X   uv가 없습니다." -ForegroundColor Red
    Write-Host "      설치: winget install astral-sh.uv" -ForegroundColor Yellow
    Write-Host "      pip install 은 uv 관리 환경에서 실패하므로 uv를 쓴다." -ForegroundColor Yellow
    $fail = $true
}

# [2/4] lxml (기본 경로)
Write-Host "[2/4] lxml 확인 (XML 경로 - 필수)..." -ForegroundColor Yellow
if ($uv) {
    uv run --python 3.12 --link-mode=copy --with lxml python -c "import lxml.etree" 2>&1 | Out-Null
    if ($?) { Write-Host "  OK  lxml 사용 가능" -ForegroundColor Green }
    else { Write-Host "  X   lxml 준비 실패" -ForegroundColor Red; $fail = $true }
} else {
    Write-Host "  -   uv가 없어 건너뜀" -ForegroundColor DarkGray
}

# [3/4] 한글 COM (폴백 경로)
Write-Host "[3/4] 한글 COM 확인 (바이너리 .hwp 변환 - 선택)..." -ForegroundColor Yellow
$clsid = (Get-ItemProperty 'HKLM:\SOFTWARE\Classes\HWPFrame.HwpObject\CLSID' -ErrorAction SilentlyContinue).'(default)'
if ($clsid) {
    Write-Host "  OK  HWPFrame.HwpObject 등록됨" -ForegroundColor Green
} else {
    Write-Host "  -   한글이 설치되지 않았습니다 (.hwpx 작업만 가능)" -ForegroundColor DarkGray
}

# [4/4] 보안 모듈
Write-Host "[4/4] 보안 모듈 확인..." -ForegroundColor Yellow
$dll = "$env:LOCALAPPDATA\HwpAutomation\FilePathCheckerModule.dll"
$reg = $false
foreach ($k in @('HKCU:\Software\HNC\HwpAutomation\Modules','HKCU:\Software\Hnc\HwpUserAction\Modules')) {
    if (Test-Path $k) {
        $v = (Get-ItemProperty $k -ErrorAction SilentlyContinue).FilePathCheckerModule
        if ($v) { $reg = $true }
    }
}
if ($reg -and (Test-Path $dll)) {
    Write-Host "  OK  보안 모듈 등록됨" -ForegroundColor Green
} elseif ($clsid) {
    Write-Host "  !   미등록 - Open/SaveAs가 보이지 않는 대화상자에서 멈춥니다." -ForegroundColor Yellow
    Write-Host "      자동 등록: scripts 폴더에서 아래 실행" -ForegroundColor Cyan
    Write-Host "      uv run --python 3.12 --link-mode=copy --with pyhwpx --with pywin32 python hwp_com.py" -ForegroundColor White
    Write-Host "      레지스트리 키가 없다면 한글을 한 번 실행한 뒤 재시도하세요." -ForegroundColor Yellow
    Write-Host "      regsvr32는 이 DLL에 통하지 않습니다 (DllRegisterServer 없음)." -ForegroundColor DarkGray
} else {
    Write-Host "  -   한글 미설치로 불필요" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
if ($fail) {
    Write-Host "점검 실패 - 위 항목을 조치하세요" -ForegroundColor Red
} else {
    Write-Host "점검 완료" -ForegroundColor Green
}
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "실행 예:" -ForegroundColor Cyan
Write-Host "  uv run --python 3.12 --link-mode=copy --with lxml --with pywin32 python work.py" -ForegroundColor White
Write-Host ""
