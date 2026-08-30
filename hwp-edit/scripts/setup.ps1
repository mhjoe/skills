# HWP 처리 환경 설정 스크립트

Write-Host "========================================" -ForegroundColor Green
Write-Host "HWP 처리 환경 설정"
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Python 버전 확인
Write-Host "[1/3] Python 설치 확인..." -ForegroundColor Yellow

try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ Python 설치됨: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Python이 설치되지 않았습니다." -ForegroundColor Red
    Write-Host "Python을 설치한 후 다시 실행하세요: https://www.python.org/" -ForegroundColor Yellow
    exit 1
}

# pip 확인
Write-Host "[2/3] pip 설치 확인..." -ForegroundColor Yellow

try {
    $pipVersion = pip --version 2>&1
    Write-Host "✓ pip 설치됨: $pipVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ pip이 설치되지 않았습니다." -ForegroundColor Red
    exit 1
}

# lxml 라이브러리 설치
Write-Host "[3/3] 필수 라이브러리 설치..." -ForegroundColor Yellow

Write-Host "  - lxml 설치 중..." -ForegroundColor Cyan

pip install lxml --quiet

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ lxml 설치 완료" -ForegroundColor Green
} else {
    Write-Host "✗ lxml 설치 실패" -ForegroundColor Red
    Write-Host "수동 설치: pip install lxml" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "설정 완료!"
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "다음 명령어로 사용 예제를 실행할 수 있습니다:" -ForegroundColor Cyan
Write-Host "  python .\.claude\scripts\hwp-examples.py" -ForegroundColor White
Write-Host ""
Write-Host "Claude Code에서 사용하려면:" -ForegroundColor Cyan
Write-Host "  /hwp-edit" -ForegroundColor White
Write-Host ""
