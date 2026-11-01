using Il2CppInterop.Runtime;
using Il2CppInterop.Runtime.InteropTypes.Arrays;
using UnityEngine;
using UnityEngine.UI;
using TMPro;

namespace MonmusuMod;

internal sealed class KoreanFont
{
    readonly string family;
    readonly bool enabled;
    readonly Action<string> info, warning;
    readonly HashSet<char> reportedMissing = new();
    Font? font;
    TMP_FontAsset? tmpFont;
    bool tmpAttempted;
    readonly HashSet<char> tmpCharacters = new();
    readonly Dictionary<int, Font> originalFonts = new();
    bool attempted;
    public KoreanFont(string family, bool enabled, Action<string> info, Action<string> warning)
        => (this.family, this.enabled, this.info, this.warning) = (family, enabled, info, warning);
    static bool ContainsHangul(string value) => value.Any(ch => ch is >= '\uAC00' and <= '\uD7A3' or >= '\u1100' and <= '\u11FF' or >= '\u3130' and <= '\u318F');
    Font? EnsureFont()
    {
        if (!attempted)
        {
            attempted = true;
            try
            {
                // This game's string overload is an unstripping-failure stub, and the
                // array overload references a stripped constructor. Allocate the IL2CPP
                // wrapper and call the retained native font initializer directly.
                var candidate = new Font(IL2CPP.il2cpp_object_new(Il2CppClassPointerStore<Font>.NativeClassPtr));
                Font.Internal_CreateDynamicFont(candidate, new Il2CppStringArray(new[] { family }), 32);
                if (candidate == null || !candidate.dynamic || !candidate.HasCharacter('\uAC00'))
                {
                    if (candidate != null) UnityEngine.Object.Destroy(candidate);
                    warning("MM_FONT_MISSING family=" + family + "; keeping the game's font");
                    return null;
                }
                UnityEngine.Object.DontDestroyOnLoad(candidate);
                font = candidate;
                info("MM_FONT_READY family=" + family + " route=Internal_CreateDynamicFont");
            }
            catch (Exception ex)
            {
                warning("MM_FONT_FAILED family=" + family + "; keeping the game's font: " + ex.Message);
                return null;
            }
        }
        return font;
    }
    public void Apply(Text? text)
    {
        if (!enabled || text == null) return;
        int id = text.GetInstanceID();
        if (!ContainsHangul(text.text))
        {
            if (font != null && text.font == font && originalFonts.Remove(id, out var original) && original != null)
                text.font = original;
            return;
        }
        if (EnsureFont() == null) return;
        foreach (char ch in text.text.Where(ch => !char.IsWhiteSpace(ch)))
            if (!font!.HasCharacter(ch) && reportedMissing.Add(ch)) warning($"MM_FONT_GLYPH_MISSING U+{(int)ch:X4}");
        if (text.font != font)
        {
            originalFonts[id] = text.font;
            text.font = font;
        }
    }
    public void Apply(TMP_Text? text)
    {
        if (!enabled || text == null || !ContainsHangul(text.text) || EnsureFont() == null) return;
        if (!tmpAttempted)
        {
            tmpAttempted = true;
            tmpFont = TMP_FontAsset.CreateFontAsset(font!);
            if (tmpFont == null) { warning("MM_TMP_FONT_MISSING family=" + family); return; }
            UnityEngine.Object.DontDestroyOnLoad(tmpFont);
            info("MM_TMP_FONT_READY family=" + family);
        }
        if (tmpFont == null) return;
        string missing = new(text.text.Where(ch => ContainsHangul(ch.ToString()) && tmpCharacters.Add(ch)).Distinct().ToArray());
        if (missing.Length > 0 && !tmpFont.TryAddCharacters(missing, out string failed, false))
            warning("MM_TMP_GLYPH_MISSING " + string.Join(" ", failed.Select(ch => $"U+{(int)ch:X4}")));
        var primary = text.font;
        if (primary == null) { text.font = tmpFont; return; }
        // Retain each UI's primary font/material and use Korean only as a fallback.
        // Japanese/numeric labels therefore keep their original appearance.
        primary.fallbackFontAssetTable ??= new Il2CppSystem.Collections.Generic.List<TMP_FontAsset>();
        if (!primary.fallbackFontAssetTable.Contains(tmpFont)) primary.fallbackFontAssetTable.Add(tmpFont);
    }
}
