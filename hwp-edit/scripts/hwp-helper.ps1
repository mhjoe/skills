# hwp-helper.ps1 — 한글 COM을 PowerShell에서 쓸 때의 최소 헬퍼
#
# 이 스킬의 기본 경로는 Python + XML 직접 처리(hwp_handler.py)다. 한글이 필요
# 없고 서식도 보존된다. **먼저 그 방법을 쓴다.**
#
# 여기 있는 함수는 XML로 불가능한 작업(바이너리 .hwp 변환, PDF 내보내기, 텍스트
# 추출)에만 쓴다. 문서 편집을 COM으로 하지 말 것 — 느리고 함정이 많다.
#
# ── 보안 승인 대화상자에 관하여 ────────────────────────────────────────────
# COM 객체를 만든 뒤 RegisterModule을 호출하지 않으면, 파일을 열 때와 저장할 때
# 마다 한글이 이 대화상자를 띄운다:
#
#   "한글을 이용하여 위 파일에 접근하려는 시도(파일의 손상 또는 유출의 위험 등)가
#    있습니다. 정상적인 작업 과정에만 접근을 허용하십시오."
#   [접근 허용] [모두 허용] [허용 안 함] [모두 안 함]
#
# 한글 창이 숨겨져 있으면 화면에 보이지도 않는 채로 떠서 스크립트가 영구 정지한다.
# 이 파일의 New-HwpObject가 매번 등록을 처리하므로, **COM 객체는 반드시
# New-HwpObject로 만든다.** New-Object -ComObject 를 직접 쓰지 말 것.

# Set-StrictMode는 여기서 켜지 않는다 - 이 파일은 dot-source(. .\hwp-helper.ps1)로
# 쓰이므로 호출자 세션의 설정까지 바꿔버린다.

$script:HwpProgId = 'HWPFrame.HwpObject'   # 'Hancom.HwpObject'는 존재하지 않는다
$script:HwpModuleRegPaths = @(
    'HKCU:\Software\HNC\HwpAutomation\Modules',
    'HKCU:\Software\Hnc\HwpUserAction\Modules'
)
$script:HwpDllPath = Join-Path $env:LOCALAPPDATA 'HwpAutomation\FilePathCheckerModule.dll'


function Register-HwpSecurityModule {
    <#
    .SYNOPSIS
        FilePathCheckerModule.dll을 레지스트리에 등록한다 (한 번만 하면 영구).
    .DESCRIPTION
        등록하지 않으면 Open/SaveAs마다 보안 승인 대화상자가 뜬다.

        regsvr32는 통하지 않는다 - 이 DLL에는 DllRegisterServer 진입점이 없어
        exit code 4로 실패한다. 레지스트리 REG_SZ 값 등록이 유일한 방법이다.

        DLL이 없으면 pyhwpx 패키지에서 가져와야 한다:
          uv run --python 3.12 --link-mode=copy --with pyhwpx --with pywin32 `
              python hwp_com.py --setup
    .OUTPUTS
        [bool] 등록 성공 여부
    #>
    [CmdletBinding()]
    param()

    if (-not (Test-Path $script:HwpDllPath)) {
        # 새 환경 첫 실행. 사용자에게 설치 명령을 시키지 않고 직접 확보한다.
        # DLL은 pyhwpx 패키지에 동봉되어 있다. 최초 1회만 네트워크가 필요하다.
        Write-Host "보안 모듈 DLL이 없습니다. pyhwpx에서 자동으로 확보합니다 (최초 1회)..." -ForegroundColor Yellow

        $uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
        if (-not $uv) {
            foreach ($c in @("$env:USERPROFILE\.local\bin\uv.exe", "$env:LOCALAPPDATA\uv\bin\uv.exe")) {
                if (Test-Path $c) { $uv = $c; break }
            }
        }
        if (-not $uv) {
            Write-Warning "uv를 찾을 수 없어 DLL을 확보할 수 없습니다. 설치: winget install astral-sh.uv"
            return $false
        }

        $comPy = Join-Path $PSScriptRoot 'hwp_com.py'
        & $uv run --python 3.12 --link-mode=copy --with pyhwpx --with pywin32 python $comPy --setup | Out-Null

        if (-not (Test-Path $script:HwpDllPath)) {
            Write-Warning "DLL 자동 확보에 실패했습니다. 네트워크를 확인하거나, 오프라인 환경이라면"
            Write-Warning "DLL을 직접 이 경로에 두세요: $script:HwpDllPath"
            Write-Warning "(한글과 비트수가 같아야 합니다 - 한글이 32비트면 DLL도 32비트)"
            return $false
        }
        Write-Host "  OK  DLL 확보 완료 - 이후 실행에는 pyhwpx도, 네트워크도 필요 없습니다" -ForegroundColor Green
    }

    $ok = $false
    foreach ($key in $script:HwpModuleRegPaths) {
        try {
            # 키가 없으면 만든다. HKCU 아래의 평범한 키이고, 값이 없으면
            # 대화상자가 뜨는 것 말고는 얻을 게 없다.
            if (-not (Test-Path $key)) { New-Item -Path $key -Force | Out-Null }
            New-ItemProperty -Path $key -Name 'FilePathCheckerModule' `
                -Value $script:HwpDllPath -PropertyType String -Force | Out-Null
            if ((Get-ItemProperty $key).FilePathCheckerModule -eq $script:HwpDllPath) { $ok = $true }
        }
        catch {
            Write-Verbose "등록 실패 ($key): $_"
        }
    }
    return $ok
}


function New-HwpObject {
    <#
    .SYNOPSIS
        보안 모듈이 등록된 한글 COM 객체를 만든다. COM 객체는 항상 이 함수로 만든다.
    .PARAMETER Visible
        한글 창을 보이게 할지 여부 (기본값: 숨김)
    .EXAMPLE
        $hwp = New-HwpObject
        try { $hwp.Open($path, 'HWP', 'forceopen:true') } finally { Close-HwpObject $hwp }
    #>
    [CmdletBinding()]
    param([switch]$Visible)

    if (-not (Register-HwpSecurityModule)) {
        throw "보안 모듈을 등록할 수 없어 중단합니다. 계속하면 파일을 열고 저장할 때마다 보안 승인 대화상자가 뜨고, 창이 숨겨져 있으면 보이지 않는 채로 떠서 스크립트가 멈춥니다."
    }

    $hwp = New-Object -ComObject $script:HwpProgId

    # Open/SaveAs 이전에 호출해야 한다. 빠뜨리면 파일 접근마다 대화상자가 뜬다.
    if (-not $hwp.RegisterModule('FilePathCheckDLL', 'FilePathCheckerModule')) {
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($hwp)
        throw "RegisterModule이 실패했습니다 (DLL 로드 불가). DLL과 한글의 비트수가 맞는지 확인하세요 - 한글이 32비트면 DLL도 32비트여야 합니다: $script:HwpDllPath"
    }

    try { $hwp.XHwpWindows.Item(0).Visible = [bool]$Visible } catch { }
    return $hwp
}


function Close-HwpObject {
    <#
    .SYNOPSIS
        한글 COM 객체를 정상 종료한다.
    .DESCRIPTION
        Hwp 프로세스를 강제 종료하지 말 것 - 반복하면 COM이 통째로 응답 불능이
        되어 다음 객체 생성부터 멈춘다. 복구하려면 사용자가 한글을 직접 한 번
        실행했다 닫아야 한다.
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)]$Hwp)

    try { $Hwp.Clear(1) } catch { }
    try { $Hwp.Quit() } catch { }
    try { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($Hwp) } catch { }
}


function Get-HwpText {
    <#
    .SYNOPSIS
        한글 문서에서 텍스트 추출 (바이너리 .hwp 포함).
    .DESCRIPTION
        .hwpx라면 COM 없이 Python 경로가 더 빠르다:
          uv run --python 3.12 --link-mode=copy --with lxml python -c "..."
        InitScan/GetText 루프는 종료 상태를 반환하지 않아 무한 루프에 빠지므로
        GetTextFile을 쓴다.
    .EXAMPLE
        Get-HwpText -Path "C:\document.hwp"
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$Path)

    $full = (Resolve-Path -LiteralPath $Path).ProviderPath
    $hwp = New-HwpObject
    try {
        $hwp.Open($full, 'HWP', 'forceopen:true')
        return $hwp.GetTextFile('TEXT', '')
    }
    finally {
        Close-HwpObject $hwp
    }
}


function Convert-HwpFile {
    <#
    .SYNOPSIS
        한글 문서를 다른 포맷으로 변환한다 (.hwp <-> .hwpx, PDF 내보내기).
    .PARAMETER Format
        'HWPX' | 'HWP' | 'PDF' | 'TEXT'
    .DESCRIPTION
        바이너리 .hwp를 XML로 다루려면 먼저 .hwpx로 변환한다. 변환 후에는
        hwp_handler.HwpDocument로 넘겨서 작업한다 - COM으로 편집하지 말 것.
        왕복 변환은 서식 손실 위험이 있으므로 가능하면 .hwpx로 전달한다.
    .EXAMPLE
        Convert-HwpFile -Path "보고서.hwp" -Format HWPX
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][ValidateSet('HWPX', 'HWP', 'PDF', 'TEXT')][string]$Format,
        [string]$Destination
    )

    $full = (Resolve-Path -LiteralPath $Path).ProviderPath
    if (-not $Destination) {
        $ext = @{ HWPX = '.hwpx'; HWP = '.hwp'; PDF = '.pdf'; TEXT = '.txt' }[$Format]
        $Destination = [IO.Path]::ChangeExtension($full, $ext)
    }
    $Destination = [IO.Path]::GetFullPath($Destination)

    $hwp = New-HwpObject
    try {
        $hwp.Open($full, 'HWP', 'forceopen:true')
        $hwp.SaveAs($Destination, $Format, '')
        return $Destination
    }
    finally {
        Close-HwpObject $hwp
    }
}


function Test-HwpEnvironment {
    <#
    .SYNOPSIS
        한글 COM과 보안 모듈 등록 상태를 점검한다.
    #>
    [CmdletBinding()]
    param()

    $clsid = (Get-ItemProperty "HKLM:\SOFTWARE\Classes\$($script:HwpProgId)\CLSID" -ErrorAction SilentlyContinue).'(default)'
    $registered = @()
    foreach ($key in $script:HwpModuleRegPaths) {
        if (Test-Path $key) {
            $v = (Get-ItemProperty $key -ErrorAction SilentlyContinue).FilePathCheckerModule
            if ($v -and (Test-Path $v)) { $registered += $key }
        }
    }
    return [pscustomobject]@{
        HwpInstalled   = [bool]$clsid
        ProgId         = $script:HwpProgId
        DllPresent     = Test-Path $script:HwpDllPath
        DllPath        = $script:HwpDllPath
        RegisteredKeys = $registered
        DialogFree     = ((Test-Path $script:HwpDllPath) -and $registered.Count -eq $script:HwpModuleRegPaths.Count)
    }
}


# dot-source(. .\hwp-helper.ps1)로도, Import-Module로도 쓸 수 있게 한다.
if ($MyInvocation.MyCommand.ModuleName) {
    Export-ModuleMember -Function @(
        'Register-HwpSecurityModule',
        'New-HwpObject',
        'Close-HwpObject',
        'Get-HwpText',
        'Convert-HwpFile',
        'Test-HwpEnvironment'
    )
}
