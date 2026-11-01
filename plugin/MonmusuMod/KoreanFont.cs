using Il2CppInterop.Runtime;
using Il2CppInterop.Runtime.InteropTypes.Arrays;
using UnityEngine;
using UnityEngine.UI;
using TMPro;
using System.Text.Json;
using System.Security.Cryptography;

namespace MonmusuMod;

internal sealed class KoreanFont
{
    readonly string family;
    readonly string bundlePath;
    readonly bool enabled;
    readonly Action<string> info, warning;
    readonly HashSet<char> reportedMissing = new();
    Font? font;
    TMP_FontAsset? tmpFont;
    AssetBundle? fontBundle;
    bool tmpAttempted;
    readonly HashSet<char> tmpCharacters = new();
    readonly Dictionary<int, Font> originalFonts = new();
    bool attempted;
    public KoreanFont(string family, string bundlePath, bool enabled, Action<string> info, Action<string> warning)
        => (this.family, this.bundlePath, this.enabled, this.info, this.warning) = (family, bundlePath, enabled, info, warning);
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
            // OS dynamic Font data is not readable by TMP's FontEngine in this
            // player. Prefer an independently supplied, prebuilt TMP bundle.
            if (File.Exists(bundlePath))
            {
                fontBundle = AssetBundle.LoadFromFile(bundlePath);
                if (fontBundle != null)
                    foreach (string asset in fontBundle.GetAllAssetNames())
                    {
                        tmpFont = fontBundle.LoadAsset_Internal(asset, Il2CppType.Of<TMP_FontAsset>())?.TryCast<TMP_FontAsset>();
                        if (tmpFont != null) break;
                    }
            }
            tmpFont ??= TMP_FontAsset.CreateFontAsset(font!);
            if (tmpFont == null) { warning("MM_TMP_FONT_MISSING family=" + family); return; }
            if (tmpFont.material == null && fontBundle != null)
            {
                // TMP serialization versions differ between the two games;
                // the bundled material still exists even when the inherited
                // material reference is not deserialized by this player.
                var materials = fontBundle.LoadAssetWithSubAssets_Internal("", Il2CppType.Of<Material>());
                if (materials.Length == 1) tmpFont.material = materials[0].TryCast<Material>();
            }
            if (tmpFont.material == null) { warning("MM_TMP_MATERIAL_MISSING"); tmpFont = null; return; }
            // Newer bundles serialize pointSize as float, but this player uses
            // int and silently leaves it zero. Restore the source metric bound
            // to the exact bundle bytes, rather than guessing a layout scale.
            if (tmpFont.faceInfo.pointSize <= 0 && fontBundle != null)
            {
                using var metrics = JsonDocument.Parse(File.ReadAllBytes(bundlePath + ".metrics.json"));
                var meta = metrics.RootElement;
                string hash = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(bundlePath))).ToLowerInvariant();
                int point = meta.GetProperty("point_size").GetInt32();
                if (meta.GetProperty("bundle_sha256").GetString() != hash || meta.GetProperty("asset").GetString() != tmpFont.name || point <= 0 || point > 4096)
                    throw new InvalidDataException("TMP source metrics do not match bundle");
                var face = tmpFont.faceInfo;
                face.pointSize = point;
                tmpFont.faceInfo = face;
            }
            var gameMaterial = text.fontSharedMaterial;
            if (gameMaterial != null && gameMaterial.shader != null) tmpFont.material.shader = gameMaterial.shader;
            if (tmpFont.atlasTexture != null) tmpFont.material.mainTexture = tmpFont.atlasTexture;
            UnityEngine.Object.DontDestroyOnLoad(tmpFont);
            if (!TMP_Settings.fallbackFontAssets.Contains(tmpFont)) TMP_Settings.fallbackFontAssets.Add(tmpFont);
            info("MM_TMP_FONT_READY asset=" + tmpFont.name + " route=" + (fontBundle != null ? "bundle" : "dynamic"));
            info($"MM_TMP_FONT_INFO glyphs={tmpFont.characterTable.Count} atlas={tmpFont.atlasWidth}x{tmpFont.atlasHeight} point={tmpFont.faceInfo.pointSize} scale={tmpFont.faceInfo.scale} texture={tmpFont.material.mainTexture?.name} shader={tmpFont.material.shader?.name}");
        }
        if (tmpFont == null) return;
        string missing = new(text.text.Where(ch => ContainsHangul(ch.ToString()) && tmpCharacters.Add(ch)).Distinct().ToArray());
        if (missing.Length > 0)
        {
            if (tmpFont.atlasPopulationMode != AtlasPopulationMode.Static) tmpFont.TryAddCharacters(missing, out _, false);
            foreach (char ch in missing)
                if (!tmpFont.HasCharacter(ch)) warning($"MM_TMP_GLYPH_MISSING U+{(int)ch:X4}");
        }
        var primary = text.font;
        if (primary == null) { text.font = tmpFont; return; }
        // Retain each UI's primary font/material and use Korean only as a fallback.
        // Japanese/numeric labels therefore keep their original appearance.
        primary.fallbackFontAssetTable ??= new Il2CppSystem.Collections.Generic.List<TMP_FontAsset>();
        if (!primary.fallbackFontAssetTable.Contains(tmpFont))
        {
            primary.fallbackFontAssetTable.Add(tmpFont);
            text.havePropertiesChanged = true;
            text.SetVerticesDirty();
        }
    }
}
