# HWP 문서 처리 헬퍼 함수들

function Get-HwpText {
    <#
    .SYNOPSIS
        HWP 문서에서 모든 텍스트 추출
    .PARAMETER Path
        HWP 파일 경로
    .EXAMPLE
        Get-HwpText -Path "C:\document.hwp"
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$Path
    )

    if (-not (Test-Path $Path)) {
        throw "파일을 찾을 수 없습니다: $Path"
    }

    try {
        $hwp = New-Object -ComObject Hancom.HwpObject
        $hwp.Open($Path, , , 1)  # 읽기 전용 모드
        $text = $hwp.Api.GetText()
        $hwp.Quit()
        return $text
    }
    catch {
        Write-Error "HWP 파일 읽기 실패: $_"
        if ($hwp) { $hwp.Quit() }
    }
}

function Find-HwpText {
    <#
    .SYNOPSIS
        HWP 문서에서 특정 텍스트 찾기
    .PARAMETER Path
        HWP 파일 경로
    .PARAMETER SearchText
        찾을 텍스트
    .EXAMPLE
        Find-HwpText -Path "C:\document.hwp" -SearchText "회의"
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$Path,
        [Parameter(Mandatory=$true)]
        [string]$SearchText
    )

    try {
        $hwp = New-Object -ComObject Hancom.HwpObject
        $hwp.Open($Path, , , 1)  # 읽기 전용 모드

        $text = $hwp.Api.GetText()
        $count = ([regex]::Matches($text, [regex]::Escape($SearchText))).Count

        $hwp.Quit()
        return @{
            Found = $count
            Path = $Path
            SearchTerm = $SearchText
        }
    }
    catch {
        Write-Error "HWP 파일 검색 실패: $_"
        if ($hwp) { $hwp.Quit() }
    }
}

function Replace-HwpText {
    <#
    .SYNOPSIS
        HWP 문서의 텍스트 일괄 변경
    .PARAMETER Path
        HWP 파일 경로
    .PARAMETER SearchText
        찾을 텍스트
    .PARAMETER ReplaceText
        바꿀 텍스트
    .PARAMETER Backup
        변경 전 백업 파일 생성 여부 (기본값: $true)
    .EXAMPLE
        Replace-HwpText -Path "C:\document.hwp" -SearchText "회의" -ReplaceText "미팅"
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$Path,
        [Parameter(Mandatory=$true)]
        [string]$SearchText,
        [Parameter(Mandatory=$true)]
        [string]$ReplaceText,
        [bool]$Backup = $true
    )

    if (-not (Test-Path $Path)) {
        throw "파일을 찾을 수 없습니다: $Path"
    }

    # 백업 생성
    if ($Backup) {
        $backupPath = "$Path.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
        Copy-Item -Path $Path -Destination $backupPath
        Write-Host "백업 파일 생성: $backupPath"
    }

    try {
        $hwp = New-Object -ComObject Hancom.HwpObject
        $hwp.Open($Path, , , 0)  # 편집 모드

        # 찾기/바꾸기 실행
        $findReplace = $hwp.CreateReplace()
        $findReplace.SetFindString($SearchText)
        $findReplace.SetReplaceString($ReplaceText)
        $replaceCount = $findReplace.ReplaceAll()

        $hwp.Save()
        $hwp.Quit()

        return @{
            Path = $Path
            SearchTerm = $SearchText
            ReplaceTerm = $ReplaceText
            ReplacedCount = $replaceCount
        }
    }
    catch {
        Write-Error "HWP 파일 수정 실패: $_"
        if ($hwp) { $hwp.Quit() }

        # 백업에서 복구
        if ($Backup -and (Test-Path $backupPath)) {
            Write-Host "변경사항이 취소되었습니다."
        }
    }
}

function Get-HwpTextLength {
    <#
    .SYNOPSIS
        HWP 문서의 텍스트 길이 확인
    .PARAMETER Path
        HWP 파일 경로
    .EXAMPLE
        Get-HwpTextLength -Path "C:\document.hwp"
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$Path
    )

    try {
        $hwp = New-Object -ComObject Hancom.HwpObject
        $hwp.Open($Path, , , 1)  # 읽기 전용 모드
        $length = $hwp.Api.GetTextLength()
        $hwp.Quit()
        return $length
    }
    catch {
        Write-Error "HWP 파일 길이 확인 실패: $_"
        if ($hwp) { $hwp.Quit() }
    }
}

function Get-HwpTextRange {
    <#
    .SYNOPSIS
        HWP 문서의 특정 범위 텍스트 추출
    .PARAMETER Path
        HWP 파일 경로
    .PARAMETER Start
        시작 위치 (기본값: 0)
    .PARAMETER Length
        추출할 텍스트 길이
    .EXAMPLE
        Get-HwpTextRange -Path "C:\document.hwp" -Start 0 -Length 100
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$Path,
        [int]$Start = 0,
        [Parameter(Mandatory=$true)]
        [int]$Length
    )

    try {
        $hwp = New-Object -ComObject Hancom.HwpObject
        $hwp.Open($Path, , , 1)  # 읽기 전용 모드

        $hwp.Api.SetCursorPos($Start)
        $text = $hwp.Api.GetText($Length)
        $hwp.Quit()
        return $text
    }
    catch {
        Write-Error "HWP 텍스트 범위 추출 실패: $_"
        if ($hwp) { $hwp.Quit() }
    }
}

# Export
Export-ModuleMember -Function @(
    'Get-HwpText',
    'Find-HwpText',
    'Replace-HwpText',
    'Get-HwpTextLength',
    'Get-HwpTextRange'
)
