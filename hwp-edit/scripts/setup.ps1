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

# [4/4] 보안 모듈 - 등록하지 않으면 파일 접근마다 보안 승인 대화상자가 뜬다
Write-Host "[4/4] 보안 모듈 확인 / 등록..." -ForegroundColor Yellow
. (Join-Path $PSScriptRoot 'hwp-helper.ps1')

if (-not $clsid) {
    Write-Host "  -   한글 미설치로 불필요" -ForegroundColor DarkGray
}
else {
    $st = Test-HwpEnvironment
    if (-not $st.DialogFree) {
        # 그냥 알려주고 끝내지 않는다. 등록은 이 스크립트가 직접 한다.
        Write-Host "  ..  미등록 상태 - 지금 등록합니다" -ForegroundColor Yellow
        [void](Register-HwpSecurityModule)
        $st = Test-HwpEnvironment
    }

    if ($st.DialogFree) {
        Write-Host "  OK  보안 모듈 등록됨 - 보안 승인 대화상자가 뜨지 않습니다" -ForegroundColor Green
    }
    elseif (-not $st.DllPresent) {
        Write-Host "  X   보안 모듈 DLL이 없습니다" -ForegroundColor Red
        Write-Host "      DLL 자동 확보에 실패했습니다. 확인할 것:" -ForegroundColor Yellow
        Write-Host "      - 네트워크 (최초 1회만 필요, pyhwpx 다운로드)" -ForegroundColor Yellow
        Write-Host "      - uv 설치: winget install astral-sh.uv" -ForegroundColor Yellow
        Write-Host "      오프라인이면 DLL을 직접 이 경로에 두면 됩니다:" -ForegroundColor Yellow
        Write-Host "      %LOCALAPPDATA%\HwpAutomation\FilePathCheckerModule.dll" -ForegroundColor White
        Write-Host "      (한글과 비트수가 같아야 합니다 - 한글이 32비트면 DLL도 32비트)" -ForegroundColor DarkGray
        Write-Host "      regsvr32는 이 DLL에 통하지 않습니다 - DllRegisterServer 진입점이 없습니다." -ForegroundColor DarkGray
        $fail = $true
    }
    else {
        Write-Host "  X   레지스트리 등록에 실패했습니다" -ForegroundColor Red
        Write-Host "      DLL: $($st.DllPath)" -ForegroundColor DarkGray
        Write-Host "      등록된 키: $($st.RegisteredKeys -join ', ')" -ForegroundColor DarkGray
        $fail = $true
    }
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
