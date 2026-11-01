param(
    [Parameter(Mandatory=$true)][string]$GameDir,
    [string]$PackageDir = "$PSScriptRoot/../dist/MonmusuMod",
    [string]$CdnBaseUrl
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$game = (Resolve-Path -LiteralPath $GameDir).Path.TrimEnd('\')
$package = (Resolve-Path -LiteralPath $PackageDir).Path
if (-not (Test-Path -LiteralPath (Join-Path $game 'monster_musume_tdx.exe'))) { throw 'Not the Monmusu IL2CPP game directory' }
if (Get-Process -Name monster_musume_tdx -ErrorAction SilentlyContinue) { throw 'Close the game before installing plugin files' }
$build = Get-Content -LiteralPath (Join-Path $package 'BUILD.json') -Raw | ConvertFrom-Json
foreach ($entry in $build.sha256.PSObject.Properties) {
    $path = [IO.Path]::GetFullPath((Join-Path $package $entry.Name))
    if (-not $path.StartsWith($package.TrimEnd('\')+'\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Package path escapes package root' }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value) { throw "Package checksum mismatch: $($entry.Name)" }
}
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path $root "work/runtime-install/$stamp"
New-Item -ItemType Directory -Path $backup -Force | Out-Null
$bep = Join-Path $game 'BepInEx'
$disabled = Join-Path $bep 'disabled-plugins'
New-Item -ItemType Directory -Path $disabled -Force | Out-Null
$moved = @()
foreach ($name in @('XUnity.AutoTranslator','XUnity.ResourceRedirector')) {
    $source = [IO.Path]::GetFullPath((Join-Path $bep "plugins/$name"))
    $destination = [IO.Path]::GetFullPath((Join-Path $disabled $name))
    if (-not $source.StartsWith($bep+'\plugins\',[StringComparison]::OrdinalIgnoreCase) -or
        -not $destination.StartsWith($bep+'\disabled-plugins\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Unexpected XUnity move target' }
    if (Test-Path -LiteralPath $source) {
        if (Test-Path -LiteralPath $destination) { throw "Both active and disabled XUnity copies exist: $name" }
        $originalHashes = @{}
        Get-ChildItem -LiteralPath $source -Recurse -File | ForEach-Object {
            $originalHashes[[IO.Path]::GetRelativePath($source,$_.FullName)] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
        }
        Move-Item -LiteralPath $source -Destination $destination
        foreach ($relative in $originalHashes.Keys) {
            if ((Get-FileHash -LiteralPath (Join-Path $destination $relative) -Algorithm SHA256).Hash -ne $originalHashes[$relative]) { throw 'XUnity preservation check failed' }
        }
        $moved += @{name=$name;from=$source;to=$destination;preserved_files=$originalHashes.Count}
    }
}
foreach ($relative in @('config/AutoTranslatorConfig.ini','config/gravydevsupreme.xunity.resourceredirector.cfg','config/kekwkekw.monmusu.ko.cfg','config/BepInEx.cfg','LogOutput.log')) {
    $source = Join-Path $bep $relative
    if (Test-Path -LiteralPath $source) { Copy-Item -LiteralPath $source -Destination (Join-Path $backup ([IO.Path]::GetFileName($source))) }
}
$pluginSource = Join-Path $package 'BepInEx/plugins/MonmusuMod'
$pluginTarget = Join-Path $bep 'plugins/MonmusuMod'
if (Test-Path -LiteralPath $pluginTarget) { Copy-Item -LiteralPath $pluginTarget -Destination (Join-Path $backup 'previous-MonmusuMod') -Recurse }
New-Item -ItemType Directory -Path $pluginTarget -Force | Out-Null
$installed = @{}
Get-ChildItem -LiteralPath $pluginSource -Recurse -File | ForEach-Object {
    $relative = [IO.Path]::GetRelativePath($pluginSource, $_.FullName)
    $target = [IO.Path]::GetFullPath((Join-Path $pluginTarget $relative))
    if (-not $target.StartsWith($pluginTarget+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Install path escapes plugin directory' }
    New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($target)) -Force | Out-Null
    Copy-Item -LiteralPath $_.FullName -Destination $target -Force
    $sha = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($sha -ne (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()) { throw 'Installed checksum mismatch' }
    $installed[$relative] = $sha
}
$note = 'XUnity AutoTranslator and ResourceRedirector are disabled by explicit user instruction on 2026-11-01. Do not re-enable until the user explicitly requests it. Preserved outside BepInEx/plugins to avoid recursive plugin discovery.'
$note | Set-Content -LiteralPath (Join-Path $disabled 'KEEP_DISABLED.txt') -Encoding utf8
if ($PSBoundParameters.ContainsKey('CdnBaseUrl')) {
    if ($CdnBaseUrl -and (-not [Uri]::IsWellFormedUriString($CdnBaseUrl,[UriKind]::Absolute) -or ([Uri]$CdnBaseUrl).Scheme -ne 'https')) { throw 'CDN must be an absolute HTTPS URL or empty' }
    $configPath = Join-Path $bep 'config/kekwkekw.monmusu.ko.cfg'
    if (-not (Test-Path -LiteralPath $configPath)) { throw 'Generate the plugin config before overriding its CDN setting' }
    $configText = [IO.File]::ReadAllText($configPath)
    if ([regex]::Matches($configText,'(?m)^CdnBaseUrl\s*=.*$').Count -ne 1) { throw 'Expected one CdnBaseUrl config entry' }
    $configText = [regex]::Replace($configText,'(?m)^CdnBaseUrl\s*=.*$', [Text.RegularExpressions.MatchEvaluator]{ param($match) 'CdnBaseUrl = ' + $CdnBaseUrl })
    [IO.File]::WriteAllText($configPath,$configText,[Text.UTF8Encoding]::new($false))
}
$report = [ordered]@{status='INSTALLED';game_root=$game;plugin_directory=$pluginTarget;backup=$backup;
    xunity_state='DISABLED_UNTIL_EXPLICIT_USER_REQUEST';moved=$moved;installed_sha256=$installed;game_launch='NOT_RUN'}
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $backup 'install.json') -Encoding utf8
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $root 'handover/RUNTIME_INSTALL_20261101.json') -Encoding utf8
$report | ConvertTo-Json -Depth 8
