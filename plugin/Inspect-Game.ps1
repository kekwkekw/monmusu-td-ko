param(
    [Parameter(Mandatory=$true)][string]$GameDir,
    [string]$Out = "$PSScriptRoot/../work/plugin-analysis/game-profile.json"
)
$ErrorActionPreference = 'Stop'
$game = (Resolve-Path -LiteralPath $GameDir).Path
Add-Type -Path (Join-Path $game 'BepInEx/core/Mono.Cecil.dll')
$assembly = [Mono.Cecil.ModuleDefinition]::ReadModule((Join-Path $game 'BepInEx/interop/Assembly-CSharp.dll'))
$textModule = [Mono.Cecil.ModuleDefinition]::ReadModule((Join-Path $game 'BepInEx/interop/UnityEngine.TextRenderingModule.dll'))
$modules = @{}
foreach ($name in @('UnityEngine.CoreModule.dll','UnityEngine.AssetBundleModule.dll','UnityEngine.UI.dll','Unity.TextMeshPro.dll','UnityEngine.ImageConversionModule.dll')) {
    $modules[$name] = [Mono.Cecil.ModuleDefinition]::ReadModule((Join-Path $game "BepInEx/interop/$name"))
}
try {
    $expected = @(
        @{ Type='StoryDataBase'; Method='PlayStoryAdv'; Parameters=@('StoryData','Il2CppSystem.Collections.Generic.Dictionary`2<StoryData,Il2CppSystem.Collections.Generic.Dictionary`2<StoryData,StoryData>>','Il2CppSystem.Action`1<StoryData>') },
        @{ Type='Utage.AdvChapterData'; Method='BootInit'; Parameters=@('Utage.AdvSettingDataManager') },
        @{ Type='AdvScene'; Method='ActBootAction'; Parameters=@('System.String') },
        @{ Type='Utage.AdvScenarioData'; Method='Init'; Parameters=@('Utage.AdvSettingDataManager') },
        @{ Type='Utage.AdvImportScenarioSheet'; Method='CreateCommandList'; Parameters=@('Utage.AdvSettingDataManager') },
        @{ Type='Utage.AdvUguiMessageWindow'; Method='OnTextChanged'; Parameters=@('Utage.AdvMessageWindow') },
        @{ Type='Utage.AdvUguiBacklog'; Method='Init'; Parameters=@('Utage.AdvBacklog') },
        @{ Type='Utage.AdvUguiSelection'; Method='Init'; Parameters=@('Utage.AdvSelection','Il2CppSystem.Action`1<Utage.AdvUguiSelection>') },
        @{ Type='ntd.database.DataBaseManager/_Preload_d__184'; Method='MoveNext'; Parameters=@() },
        @{ Type='ntd.database.DataBaseManager/_PreloadBeforeTitle_d__183'; Method='MoveNext'; Parameters=@() },
        @{ Module='UnityEngine.UI.dll'; Type='UnityEngine.UI.Text'; Method='set_text'; Parameters=@('System.String') },
        @{ Module='UnityEngine.UI.dll'; Type='UnityEngine.UI.Text'; Method='OnEnable'; Parameters=@() },
        @{ Module='UnityEngine.UI.dll'; Type='UnityEngine.UI.Text'; Method='OnPopulateMesh'; Parameters=@('UnityEngine.UI.VertexHelper') },
        @{ Module='Unity.TextMeshPro.dll'; Type='TMPro.TMP_Text'; Method='set_text'; Parameters=@('System.String') },
        @{ Module='Unity.TextMeshPro.dll'; Type='TMPro.TextMeshProUGUI'; Method='OnEnable'; Parameters=@() },
        @{ Module='Unity.TextMeshPro.dll'; Type='TMPro.TextMeshProUGUI'; Method='OnPreRenderCanvas'; Parameters=@() },
        @{ Module='UnityEngine.UI.dll'; Type='UnityEngine.UI.Image'; Method='set_sprite'; Parameters=@('UnityEngine.Sprite') },
        @{ Module='UnityEngine.UI.dll'; Type='UnityEngine.UI.Image'; Method='set_overrideSprite'; Parameters=@('UnityEngine.Sprite') },
        @{ Module='UnityEngine.UI.dll'; Type='UnityEngine.UI.Image'; Method='OnEnable'; Parameters=@() },
        @{ Module='UnityEngine.UI.dll'; Type='UnityEngine.UI.RawImage'; Method='set_texture'; Parameters=@('UnityEngine.Texture') },
        @{ Module='UnityEngine.UI.dll'; Type='UnityEngine.UI.MaskableGraphic'; Method='OnEnable'; Parameters=@() }
    )
    $hooks = foreach ($spec in $expected) {
        $source = if ($spec.Module) { $modules[$spec.Module] } else { $assembly }
        $type = $source.GetType($spec.Type)
        $methods = @($type.Methods | Where-Object { $_.Name -eq $spec.Method -and
            ($_.Parameters.ParameterType.FullName -join '|') -eq ($spec.Parameters -join '|') })
        if ($methods.Count -ne 1) { throw "Missing/ambiguous hook: $($spec.Type).$($spec.Method)" }
        $method = $methods[0]
        $native = @($method.Body.Instructions | Where-Object { $_.Operand -and $_.Operand.ToString() -match '::il2cpp_runtime_invoke' }).Count -gt 0
        if (-not $native) { throw "Hook is not an IL2CPP native method wrapper: $($method.FullName)" }
        @{ signature=$method.FullName; native_wrapper=$native; metadata_token=$method.MetadataToken.ToInt32() }
    }
    $imageApis = foreach ($spec in @(
        @{ Module='UnityEngine.CoreModule.dll'; Type='UnityEngine.Texture2D'; Method='.ctor'; Parameters=@('System.Int32','System.Int32','UnityEngine.TextureFormat','System.Boolean') },
        @{ Module='UnityEngine.CoreModule.dll'; Type='UnityEngine.Sprite'; Method='Create'; Parameters=@('UnityEngine.Texture2D','UnityEngine.Rect','UnityEngine.Vector2','System.Single','System.UInt32','UnityEngine.SpriteMeshType','UnityEngine.Vector4') },
        @{ Module='UnityEngine.ImageConversionModule.dll'; Type='UnityEngine.ImageConversion'; Method='LoadImage'; Parameters=@('UnityEngine.Texture2D','Il2CppInterop.Runtime.InteropTypes.Arrays.Il2CppStructArray`1<System.Byte>','System.Boolean') }
    )) {
        $type = $modules[$spec.Module].GetType($spec.Type)
        $methods = @($type.Methods | Where-Object { $_.Name -eq $spec.Method -and
            ($_.Parameters.ParameterType.FullName -join '|') -eq ($spec.Parameters -join '|') })
        if ($methods.Count -ne 1) { throw "Missing/ambiguous image API: $($spec.Type).$($spec.Method)" }
        $native = @($methods[0].Body.Instructions | Where-Object { $_.Operand -and $_.Operand.ToString() -match '::il2cpp_runtime_invoke' }).Count -gt 0
        if (-not $native) { throw "Image API is not a retained native wrapper: $($methods[0].FullName)" }
        @{ signature=$methods[0].FullName; native_wrapper=$native }
    }
    $files = @('GameAssembly.dll','UnityPlayer.dll','monster_musume_tdx_Data/il2cpp_data/Metadata/global-metadata.dat',
        'BepInEx/interop/Assembly-CSharp.dll','BepInEx/interop/UnityEngine.UI.dll','BepInEx/interop/UnityEngine.CoreModule.dll',
        'BepInEx/interop/UnityEngine.TextRenderingModule.dll','BepInEx/interop/Il2Cppmscorlib.dll','BepInEx/interop/UnityEngine.ImageConversionModule.dll',
        'BepInEx/interop/Unity.TextMeshPro.dll','BepInEx/interop/UnityEngine.AssetBundleModule.dll','BepInEx/interop/UnityEngine.TextCoreFontEngineModule.dll',
        'BepInEx/core/BepInEx.Core.dll','BepInEx/core/BepInEx.Unity.IL2CPP.dll',
        'BepInEx/core/0Harmony.dll','BepInEx/core/Il2CppInterop.Runtime.dll')
    $hashes = @{}
    foreach ($relative in $files) { $hashes[$relative] = (Get-FileHash -LiteralPath (Join-Path $game $relative) -Algorithm SHA256).Hash.ToLowerInvariant() }
    $novelText = $assembly.Types | Where-Object FullName -EQ 'Utage.UguiNovelText'
    if ($novelText.BaseType.FullName -ne 'UnityEngine.UI.Text') { throw 'Story font adapter no longer matches the game' }
    $fontType = $textModule.Types | Where-Object FullName -EQ 'UnityEngine.Font'
    $fontInitializer = @($fontType.Methods | Where-Object {
        $_.Name -eq 'Internal_CreateDynamicFont' -and $_.IsPublic -and $_.IsStatic -and
        ($_.Parameters.ParameterType.FullName -join '|') -eq 'UnityEngine.Font|Il2CppInterop.Runtime.InteropTypes.Arrays.Il2CppStringArray|System.Int32'
    })
    if ($fontInitializer.Count -ne 1 -or -not ($fontInitializer[0].Body.Instructions | Where-Object {
        $_.Operand -and $_.Operand.ToString() -match 'Internal_CreateDynamicFontDelegate::Invoke'
    })) { throw 'Retained native font initializer is missing or changed' }
    $fontWrapper = @($fontType.Methods | Where-Object { $_.Name -eq '.ctor' -and $_.IsPublic -and
        ($_.Parameters.ParameterType.FullName -join '|') -eq 'System.IntPtr' })
    if ($fontWrapper.Count -ne 1) { throw 'IL2CPP font wrapper constructor missing' }
    $report = [ordered]@{ schema='monmusu-static-game-profile-v1'; status='STATIC_API_VERIFIED';
        game_root=$game; unity_file_version=(Get-Item -LiteralPath (Join-Path $game 'UnityPlayer.dll')).VersionInfo.FileVersion;
        story_text_base=$novelText.BaseType.FullName; hooks=@($hooks); image_apis=@($imageApis); font_initializer=$fontInitializer[0].FullName; sha256=$hashes;
        runtime_execution='NOT_RUN'; native_hook_execution='NOT_RUN'; game_files_modified=$false }
    $fullOut = [IO.Path]::GetFullPath($Out)
    New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($fullOut)) -Force | Out-Null
    $report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $fullOut -Encoding utf8
    Write-Output "STATIC_API_VERIFIED: $($hooks.Count) native hook wrappers; UguiNovelText : UnityEngine.UI.Text. Report: $fullOut"
} finally { $assembly.Dispose(); $textModule.Dispose(); foreach($module in $modules.Values) { $module.Dispose() } }
