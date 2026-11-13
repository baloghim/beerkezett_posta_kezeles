# Windows PowerShell 5.1; a célgépre nem kell Python vagy fejlesztőeszköz.
param(
    [string]$ApplicationDirectory = $PSScriptRoot,
    [string]$ReportPath = (Join-Path ([Environment]::GetFolderPath('Desktop')) 'EDPD-Windows1607-result.json')
)
$ErrorActionPreference = 'Stop'
$os = Get-CimInstance Win32_OperatingSystem
if ($os.BuildNumber -ne '14393' -or $os.ProductType -ne 1 -or -not [Environment]::Is64BitOperatingSystem) {
    throw 'Ez az ellenőrzés valódi Windows 10 1607 x64 (build 14393) munkaállomást igényel.'
}
$exe = Join-Path $ApplicationDirectory 'EDPD-Manager.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw "Hiányzó alkalmazás: $exe" }
# Korábbi eredmény nem használható új futás igazolására.
if (Test-Path -LiteralPath $ReportPath) { throw 'Az eredményfájl már létezik. Válasszon új ReportPath útvonalat.' }
$argsList = @('--self-test', '--require-windows1607', '--report', ('"' + $ReportPath + '"'))
# Ne maradjon külső QT_QPA_PLATFORM=offscreen: a qwindows plugin is töltődjön be.
$oldPlatform = $env:QT_QPA_PLATFORM
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
try {
    $process = Start-Process -FilePath $exe -ArgumentList $argsList -PassThru
    if (-not $process.WaitForExit(90000)) {
        $process.Kill()
        throw 'Az indítási teszt időtúllépéssel leállt (DLL-hibaablakot is ellenőrizzen).'
    }
    $process.Refresh()
    if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $ReportPath)) {
        throw "A csomagolt EXE indítási próbája sikertelen. Kilépési kód: $($process.ExitCode); eredmény: $ReportPath"
    }
    $result = Get-Content -Raw -LiteralPath $ReportPath -Encoding UTF8 | ConvertFrom-Json
    if (-not $result.passed -or -not $result.windows1607_verified -or -not $result.host.frozen) {
        throw "Az eredmény nem igazolja a 1607-es csomagolt futtatást: $ReportPath"
    }
    if (-not $result.application_version -or -not ($result.checks -contains 'crystal_icons_and_application_icon') -or -not ($result.checks -contains 'independent_workspace_table_and_source_day_column')) {
        throw 'A jelentés nem az EDPD aktuális teljes önellenőrzéséből származik.'
    }
    Write-Host "Sikeres Windows 1607 EXE-önellenőrzés: $ReportPath"
    Write-Host 'Fizikai nyomtató és kétgépes SMB átvételi próbája még szükséges.'
} finally {
    if ($null -eq $oldPlatform) { Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue }
    else { $env:QT_QPA_PLATFORM = $oldPlatform }
}
