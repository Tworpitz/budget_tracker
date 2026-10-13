param(
    [string]$DotNet = '',
    [switch]$Verify,
    [string]$Python = '',
    [switch]$Launch,
    [string]$OutputDirectory = ''
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
if (-not $DotNet) {
    $localSdk = Join-Path $projectRoot 'build/tooling/dotnet/dotnet.exe'
    $DotNet = if (Test-Path $localSdk) { $localSdk } else { (Get-Command dotnet -ErrorAction Stop).Source }
}
if (-not $Python) {
    $localPython = Join-Path $projectRoot '.venv/Scripts/python.exe'
    $Python = if (Test-Path $localPython) { $localPython } else { 'python' }
}
$output = if ($OutputDirectory) { [IO.Path]::GetFullPath([IO.Path]::Combine($projectRoot, $OutputDirectory)) } else { Join-Path $projectRoot 'dist/winui' }
Push-Location $projectRoot
try {
    & $DotNet publish clients/winui/BudgetTracker.Windows/BudgetTracker.Windows.csproj -c Release -p:Platform=x64 -o $output
    if ($LASTEXITCODE -ne 0) { throw 'WinUI publish failed.' }
    if ($Verify) {
        $testDir = Join-Path $projectRoot ('build/winui-verification/' + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Force $testDir | Out-Null
        & $Python clients/winui/tests/python_parity.py $testDir
        if ($LASTEXITCODE -ne 0) { throw 'Python fixture generation failed.' }
        & $DotNet run --project clients/winui/BudgetTracker.Tests/BudgetTracker.Tests.csproj -c Release -- $testDir
        if ($LASTEXITCODE -ne 0) { throw 'C# parity/storage checks failed.' }
        & $Python clients/winui/tests/python_parity.py $testDir --verify
        if ($LASTEXITCODE -ne 0) { throw 'Python interoperability check failed.' }
        $smokeResult = Join-Path $testDir 'ui-smoke.json'
        $app = Start-Process -FilePath (Join-Path $output 'BudgetTracker.WinUI.exe') -ArgumentList @('--smoke-test', ('"' + $smokeResult + '"')) -WindowStyle Hidden -PassThru
        if (-not $app.WaitForExit(90000)) { throw 'WinUI smoke test timed out; inspect its window.' }
        if (-not (Test-Path $smokeResult)) { throw 'WinUI did not produce a smoke-test result.' }
        $result = Get-Content $smokeResult -Raw | ConvertFrom-Json
        if (-not $result.success) { throw "WinUI UI smoke test failed: $($result.error)" }
        Write-Output "All checks passed. Evidence: $testDir"
    }
    Write-Output "WinUI release: $output"
    if ($Launch) { Start-Process -FilePath (Join-Path $output 'BudgetTracker.WinUI.exe') }
}
finally { Pop-Location }
