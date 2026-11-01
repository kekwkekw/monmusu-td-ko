param(
    [Parameter(Mandatory=$true)][string]$GameDir,
    [string]$Python = "$PSScriptRoot/../extractor/.venv/Scripts/python.exe",
    [string]$Dotnet = '',
    [string]$Book = '',
    [string]$NugetPackages = '',
    [switch]$Offline
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$game = (Resolve-Path -LiteralPath $GameDir).Path
if (-not $Dotnet) {
    $command = Get-Command dotnet -ErrorAction SilentlyContinue
    $Dotnet = if ($command) { $command.Source } else { Join-Path $env:ProgramFiles 'dotnet/dotnet.exe' }
}
if (-not (Test-Path -LiteralPath $Python)) { throw 'Supply -Python with Python 3.14 or later.' }
$env:DOTNET_CLI_HOME = Join-Path $root 'work/dotnet-home'
$env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE = '1'
$env:DOTNET_CLI_TELEMETRY_OPTOUT = '1'
$env:DOTNET_GENERATE_ASPNET_CERTIFICATE = 'false'
$env:DOTNET_ADD_GLOBAL_TOOLS_TO_PATH = 'false'
$env:MONMUSU_TEST_TEMP_ROOT = Join-Path $root 'work/plugin-tests'
New-Item -ItemType Directory -Path $env:MONMUSU_TEST_TEMP_ROOT -Force | Out-Null
if ($NugetPackages) { $env:NUGET_PACKAGES = (Resolve-Path -LiteralPath $NugetPackages).Path }
$restoreArguments = @('--ignore-failed-sources', '-p:NuGetAudit=false')
if ($Offline) {
    $feed = Join-Path $root 'work/nuget-empty-feed'
    New-Item -ItemType Directory -Path $feed -Force | Out-Null
    $restoreArguments += @('--source', $feed)
}
function Check-Exit([string]$Step) { if ($LASTEXITCODE -ne 0) { throw "$Step failed (exit $LASTEXITCODE)" } }
Push-Location $root
try {
    & (Join-Path $PSScriptRoot 'Inspect-Game.ps1') -GameDir $game
    $package = Join-Path $root 'dist/MonmusuMod/BepInEx/plugins/MonmusuMod'
    & $Python -X utf8 tools/update/cli.py mod-package --out "$package/data" --report work/plugin-analysis/package-export.json
    Check-Exit 'Runtime package export'
    $testProject = Join-Path $PSScriptRoot 'MonmusuMod.Tests/MonmusuMod.Tests.csproj'
    $pluginProject = Join-Path $PSScriptRoot 'MonmusuMod/MonmusuMod.csproj'
    & $Dotnet restore $testProject @restoreArguments
    Check-Exit 'Core test restore'
    & $Dotnet build $testProject -c Release --no-restore
    Check-Exit 'Core test build'
    $testArguments = @("$package/data")
    if ($Book) { $testArguments += (Resolve-Path -LiteralPath $Book).Path }
    & $Dotnet (Join-Path $PSScriptRoot 'MonmusuMod.Tests/bin/Release/net6.0/MonmusuMod.Tests.dll') @testArguments
    Check-Exit 'Core tests'
    & $Dotnet restore $pluginProject "-p:GameDir=$game" @restoreArguments
    Check-Exit 'Plugin restore'
    & $Dotnet build $pluginProject -c Release --no-restore "-p:GameDir=$game"
    Check-Exit 'Plugin build'
    foreach ($name in @('MonmusuMod.dll', 'MonmusuMod.Core.dll')) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot "MonmusuMod/bin/Release/net6.0/$name") -Destination (Join-Path $package $name) -Force
    }
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'README_KO.md') -Destination (Join-Path $root 'dist/MonmusuMod/README_KO.md') -Force
    # A new binary must not carry a previous run's runtime attestation.
    $oldAttestation = Join-Path $root 'dist/MonmusuMod/RUNTIME_TEST.json'
    if (Test-Path -LiteralPath $oldAttestation) { Remove-Item -LiteralPath $oldAttestation }
    $files = @{}
    Get-ChildItem -LiteralPath (Join-Path $root 'dist/MonmusuMod') -Recurse -File | Where-Object Name -NE 'BUILD.json' | ForEach-Object {
        $relative = [IO.Path]::GetRelativePath((Join-Path $root 'dist/MonmusuMod'), $_.FullName).Replace('\','/')
        $files[$relative] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    $report = [ordered]@{ status='BUILT_STATIC_ONLY'; version='0.2.0'; core_tests='PASSED';
        extracted_book_test=([bool]$Book); game_execution='NOT_RUN'; game_installation='NOT_RUN';
        sha256=$files }
    $report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $root 'dist/MonmusuMod/BUILD.json') -Encoding utf8
    Write-Output "BUILT_STATIC_ONLY: $root/dist/MonmusuMod (no game writes or launch)"
} finally { Pop-Location }
