using System.Text;
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
    static bool Protected(Component text) => text == null || text.GetComponentInParent<InputField>(true) != null ||
        text.GetComponentInParent<TMP_InputField>(true) != null || text.GetComponentInParent<AdvUguiMessageWindow>(true) != null ||
        text.GetComponentInParent<AdvUguiBacklog>(true) != null || text.GetComponentInParent<AdvUguiSelection>(true) != null ||
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
        try { if (!Protected(__instance)) value = Translate(value, "TMP") ?? value; }
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
        if (!string.IsNullOrEmpty(current) && Translate(current, "TMP") is { } translated) __instance.text = translated;
        Plugin.Instance.Fonts.Apply(__instance);
    });
}
