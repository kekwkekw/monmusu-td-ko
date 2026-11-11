using BepInEx;
using BepInEx.Unity.IL2CPP;
using HarmonyLib;
using MonmusuMod.Core;
using System.Net.Http;
using System.Reflection;
using Utage;
using UnityEngine;
using UnityEngine.UI;
using TMPro;

namespace MonmusuMod;

[BepInPlugin(Guid, "Monmusu Korean Translation", "0.4.0")]
[BepInProcess("monster_musume_tdx.exe")]
public sealed class Plugin : BasePlugin
{
    public const string Guid = "kekwkekw.monmusu.ko";
    internal static Plugin Instance { get; private set; } = null!;
    TranslationPackage? package;
    internal TranslationPackage? Package => Volatile.Read(ref package);
    internal NovelSession Novels { get; private set; } = null!;
    HttpClient? cdnClient;
    internal ImagePackage? Images { get; private set; }
    internal KoreanFont Fonts { get; private set; } = null!;
    internal bool LogUnmatched { get; private set; }
    Harmony? harmony;

    public override void Load()
    {
        Instance = this;
        if (!Config.Bind("General", "Enabled", true, "Enable reviewed scenario translations at game startup.").Value) return;
        string pluginRoot = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location)!;
        string data = Config.Bind("Translation", "DataDirectory", "data", "Reviewed runtime package directory, relative to this plugin folder.").Value;
        string cache = Path.Combine(Paths.CachePath, "MonmusuMod");
        string cdn = Config.Bind("Translation", "CdnBaseUrl", "https://raw.githubusercontent.com/kekwkekw/monmusu-td-ko/main/translations/ko/", "Public HTTPS directory containing manifest.json; empty uses bundled/local data.").Value;
        string fontName = Config.Bind("Font", "Family", "Malgun Gothic", "Installed Unity dynamic font family used for Korean scenario text.").Value;
        string fontBundle = Config.Bind("Font", "TmpBundle", "fonts/RHR_Medium_GFSAFE_ADH.bundle", "Separately supplied TMP font bundle, relative to this plugin folder.").Value;
        bool useFont = Config.Bind("Font", "Enabled", true, "Apply Korean fonts to translated Text/TMP labels containing Hangul.").Value;
        string localImages = Config.Bind("Images", "LocalDirectory", "", "Optional explicitly installed local image preview catalog; empty uses the verified CDN package images.").Value;
        LogUnmatched = Config.Bind("Diagnostics", "LogUnmatchedGrids", false, "Log encountered grid names without translations for runtime diagnosis.").Value;
        try
        {
            string bundled = Path.IsPathRooted(data) ? data : Path.Combine(pluginRoot, data);
            Uri? cdnUri = string.IsNullOrWhiteSpace(cdn) ? null : PackageCache.ValidateBase(new Uri(cdn));
            package = cdnUri == null ? TranslationPackage.Load(bundled, false) :
                PackageCache.LoadPreferred(bundled, cache, msg => Log.LogWarning(msg), false);
            if (!string.IsNullOrWhiteSpace(cdn))
            {
                try
                {
                    cdnClient = new HttpClient { Timeout = TimeSpan.FromSeconds(10) };
                    using var startup = new CancellationTokenSource(TimeSpan.FromSeconds(15));
                    var timer = System.Diagnostics.Stopwatch.StartNew();
                    // Includes manifest and all common payloads, independently of per-request timeout.
                    var refresh = Task.Run(() => PackageCache.RefreshAsync(cdnClient, cdnUri!, cache, startup.Token,
                        msg => Log.LogInfo(msg), bundled));
                    package = refresh.WaitAsync(startup.Token).GetAwaiter().GetResult();
                    Log.LogInfo($"MM_CDN_STARTUP elapsed_ms={timer.ElapsedMilliseconds} bound_ms=15000 novel_reads=0 novel_requests=0");
                    Log.LogInfo($"MM_CDN_READY package={package.Identity}; selected before installing hooks");
                }
                catch (Exception ex) { Log.LogWarning("MM_CDN_FAILED; keeping validated local package: " + ex.Message); }
            }
            var selected = package;
            string sceneRoot = cdnUri == null ? selected.RootDirectory : Path.Combine(cache, "versions", selected.Identity);
            Novels = new NovelSession(selected, (entry, token) => PackageCache.ReadFileAsync(entry, sceneRoot, cache,
                cdnClient, cdnUri, token, msg => Log.LogInfo(msg), bundled), msg => Log.LogInfo(msg));
            Fonts = new KoreanFont(fontName, Path.IsPathRooted(fontBundle) ? fontBundle : Path.Combine(pluginRoot, fontBundle), useFont, msg => Log.LogInfo(msg), msg => Log.LogWarning(msg));
            Images = package.Images;
            if (!string.IsNullOrWhiteSpace(localImages))
            {
                try
                {
                    string imageRoot = Path.IsPathRooted(localImages) ? localImages : Path.Combine(pluginRoot, localImages);
                    var catalog = ImageCatalog.Parse(File.ReadAllBytes(Path.Combine(imageRoot, "images.json")));
                    Images = new ImagePackage(imageRoot, catalog, catalog.Entries.GroupBy(e => e.File)
                        .Select(g => new FileEntry { Path = g.Key, Sha256 = g.First().Sha256 }).ToArray());
                    Log.LogInfo("MM_IMAGES_LOCAL_PREVIEW: explicit local image catalog selected");
                }
                catch (Exception ex) { Log.LogWarning("MM_IMAGES_LOCAL_FAILED; keeping package images: " + ex.Message); }
            }
            harmony = new Harmony(Guid);
            // Explicit signatures checked against the installed game's interop assemblies.
            var groups = typeof(Il2CppSystem.Collections.Generic.Dictionary<StoryData, Il2CppSystem.Collections.Generic.Dictionary<StoryData, StoryData>>);
            var callback = typeof(Il2CppSystem.Action<StoryData>);
            Patch(typeof(StoryDataBase), "PlayStoryAdv", nameof(Hooks.StoryStarting), null, typeof(StoryData), groups, callback);
            Patch(typeof(AdvScene), "ActBootAction", nameof(Hooks.SceneBooting), null, typeof(string));
            Patch(typeof(AdvChapterData), "BootInit", nameof(Hooks.ChapterStarting), null, typeof(AdvSettingDataManager));
            Patch(typeof(AdvScenarioData), "Init", nameof(Hooks.ScenarioStarting), null, typeof(AdvSettingDataManager));
            Patch(typeof(AdvImportScenarioSheet), "CreateCommandList", nameof(Hooks.BeforeCommands), null, typeof(AdvSettingDataManager));
            Patch(typeof(AdvUguiMessageWindow), "OnTextChanged", null, nameof(Hooks.MessageChanged), typeof(AdvMessageWindow));
            Patch(typeof(AdvUguiBacklog), "Init", null, nameof(Hooks.BacklogReady), typeof(AdvBacklog));
            Patch(typeof(AdvUguiSelection), "Init", null, nameof(Hooks.SelectionReady), typeof(AdvSelection), typeof(Il2CppSystem.Action<AdvUguiSelection>));
            PatchTo(typeof(ntd.database.DataBaseManager._Preload_d__184), "MoveNext", typeof(MasterHooks), null, nameof(MasterHooks.PreloadReady));
            PatchTo(typeof(ntd.database.DataBaseManager._PreloadBeforeTitle_d__183), "MoveNext", typeof(MasterHooks), null, nameof(MasterHooks.BeforeTitleReady));
            PatchTo(typeof(Text), "set_text", typeof(UiHooks), nameof(UiHooks.LegacySet), nameof(UiHooks.LegacyReady), typeof(string));
            PatchTo(typeof(Text), "OnEnable", typeof(UiHooks), null, nameof(UiHooks.LegacyReady));
            PatchTo(typeof(Text), "OnPopulateMesh", typeof(UiHooks), nameof(UiHooks.LegacyReady), null, typeof(VertexHelper));
            PatchTo(typeof(TMP_Text), "set_text", typeof(UiHooks), nameof(UiHooks.TmpSet), nameof(UiHooks.TmpReady), typeof(string));
            PatchTo(typeof(TextMeshProUGUI), "OnEnable", typeof(UiHooks), null, nameof(UiHooks.TmpReady));
            PatchTo(typeof(TextMeshProUGUI), "OnPreRenderCanvas", typeof(UiHooks), nameof(UiHooks.TmpReady), null);
            PatchTo(typeof(Image), "set_sprite", typeof(ImageHooks), nameof(ImageHooks.SetSprite), null, typeof(Sprite));
            PatchTo(typeof(Image), "set_overrideSprite", typeof(ImageHooks), nameof(ImageHooks.SetSprite), null, typeof(Sprite));
            PatchTo(typeof(Image), "OnEnable", typeof(ImageHooks), null, nameof(ImageHooks.EnableImage));
            PatchTo(typeof(RawImage), "set_texture", typeof(ImageHooks), nameof(ImageHooks.SetTexture), null, typeof(Texture));
            PatchTo(typeof(MaskableGraphic), "OnEnable", typeof(ImageHooks), null, nameof(ImageHooks.EnableGraphic));
            Log.LogInfo($"MM_IMAGES_READY targets={Images?.Catalog.Entries.Count ?? 0} image_hooks=5");
            Log.LogInfo($"MM_READY version=0.4.0 package={package.Identity} scenarios={package.Manifest.Scenarios.Count} loaded_scenarios={Novels.LoadedCount} rows={package.RowCount} names={package.NameCount} ui={package.MasterUi.UiCount} master={package.MasterUi.MasterCount} hooks=21");
            Log.LogInfo("MM_DIAGNOSTICS: MM_GRID records source matching; MM_FONT_READY records Korean font initialization. Visual/voice checks are recorded separately.");
            if (Directory.EnumerateFiles(Paths.PluginPath, "XUnity.AutoTranslator*.dll", SearchOption.AllDirectories).Any())
                Log.LogWarning("MM_OTHER_TRANSLATOR: XUnity AutoTranslator is installed. Its text/font hooks can affect the later visual test; its configuration was not modified.");
        }
        catch (Exception ex)
        {
            harmony?.UnpatchSelf();
            Log.LogError("MM_STARTUP_FAILED: " + ex);
        }
    }

    void Patch(Type type, string method, string? prefix, string? postfix, params Type[] arguments)
        => PatchTo(type, method, typeof(Hooks), prefix, postfix, arguments);

    void PatchTo(Type type, string method, Type handlers, string? prefix, string? postfix, params Type[] arguments)
    {
        var target = AccessTools.DeclaredMethod(type, method, arguments) ?? throw new MissingMethodException(type.FullName, method);
        HarmonyMethod? Handler(string? name) => name == null ? null : new HarmonyMethod(handlers, name);
        harmony!.Patch(target, prefix: Handler(prefix), postfix: Handler(postfix));
        Log.LogInfo($"MM_HOOK {type.FullName}.{method}");
    }

    // In-memory imported scripts must not be partially unpatched while the game is using them.
    public override bool Unload() => false;
}
