using System.Text;
using Il2CppInterop.Runtime;
using MonmusuMod.Core;
using TMPro;
using UnityEngine;
using UnityEngine.UI;
using Utage;

namespace MonmusuMod;

internal static class UiHooks
{
    [ThreadStatic] static bool applying;
    static readonly HashSet<string> logged = new(StringComparer.Ordinal);
    // The generated generic overload has invalid Cast<T> constraints in this
    // game's interop. Use the retained native Type/Boolean overload instead.
    static bool Protected(Component text) => text == null || text.GetComponentInParent(Il2CppType.Of<InputField>(), true) != null ||
        text.GetComponentInParent(Il2CppType.Of<TMP_InputField>(), true) != null || text.GetComponentInParent(Il2CppType.Of<AdvUguiMessageWindow>(), true) != null ||
        text.GetComponentInParent(Il2CppType.Of<AdvUguiBacklog>(), true) != null || text.GetComponentInParent(Il2CppType.Of<AdvUguiSelection>(), true) != null ||
        text.TryCast<UguiNovelText>() != null;
    static string? Translate(string value, string renderer)
    {
        var result = Plugin.Instance.Package?.MasterUi.TranslateUi(value);
        if (result != null)
        {
            string key = TranslationPackage.Hash(Encoding.UTF8.GetBytes(value));
            if (logged.Add(renderer + key)) Plugin.Instance.Log.LogInfo($"MM_UI_APPLIED renderer={renderer} key={key}");
        }
        return result;
    }
    static void Guard(Action action)
    {
        if (applying) return;
        try { applying = true; action(); }
        catch (Exception ex) { Plugin.Instance.Log.LogWarning("MM_UI_FAILED: " + ex); }
        finally { applying = false; }
    }
    public static void LegacySet(Text __instance, ref string value)
    {
        if (applying || string.IsNullOrEmpty(value)) return;
        try { if (!Protected(__instance)) value = Translate(value, "Text") ?? value; }
        catch (Exception ex) { Plugin.Instance.Log.LogWarning("MM_UI_FAILED: " + ex.Message); }
    }
    public static void TmpSet(TMP_Text __instance, ref string value)
    {
        if (applying || string.IsNullOrEmpty(value)) return;
        try { if (!Protected(__instance)) value = UiDisplayText.Render(Translate(value, "TMP") ?? value, UiPresentation.PathOf(__instance.transform), s => Translate(s, "TMP-format")); }
        catch (Exception ex) { Plugin.Instance.Log.LogWarning("MM_UI_FAILED: " + ex.Message); }
    }
    public static void LegacyReady(Text __instance) => Guard(() =>
    {
        if (Protected(__instance)) return;
        string current = __instance.text;
        if (!string.IsNullOrEmpty(current) && Translate(current, "Text") is { } translated) __instance.text = translated;
        Plugin.Instance.Fonts.Apply(__instance);
    });
    public static void TmpReady(TMP_Text __instance) => Guard(() =>
    {
        if (Protected(__instance)) return;
        string current = __instance.text;
        string path = UiPresentation.PathOf(__instance.transform);
        if (!string.IsNullOrEmpty(current))
        {
            string translated = UiDisplayText.Render(Translate(current, "TMP") ?? current, path, s => Translate(s, "TMP-format"));
            if (current != translated) __instance.text = translated;
        }
        var fonts = __instance.font?.name.Contains("Kurokane", StringComparison.OrdinalIgnoreCase) == true
            ? Plugin.Instance.DecorativeFonts : Plugin.Instance.Fonts;
        fonts.Apply(__instance);
        UiPresentation.Apply(__instance, path);
    });
    public static void StatusStarting(cUnitStatusDialog __instance) => Guard(() =>
    {
        string source = __instance.m_tribeTextPrefix;
        if (string.IsNullOrEmpty(source)) return;
        string translated = UiDisplayText.TribePrefix(source, value => Translate(value, "StatusPrefix"));
        if (translated != source) __instance.m_tribeTextPrefix = translated;
    });
}
