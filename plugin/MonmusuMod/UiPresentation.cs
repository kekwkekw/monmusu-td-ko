using TMPro;
using UnityEngine;
using MonmusuMod.Core;

namespace MonmusuMod;

internal static class UiPresentation
{
    // Keep the original white lettering and dark SDF border, tuned for RHR.
    // Per-renderer instances leave shared game and font-atlas materials intact.
    static readonly Dictionary<int, (TMP_Text Text, Material Original, Material Styled)> materials = new();
    static readonly Dictionary<int, (TMP_Text Text, Vector4 Margin, float LineSpacing, bool Wrap, float MinSize)> layouts = new();
    static bool SubskillName(string path) => path.EndsWith("/Name", StringComparison.Ordinal) &&
        (path.Contains("/AttachAbilityRarityParent(Clone)/", StringComparison.Ordinal)
        || path.Contains("/Subskill(Clone)/", StringComparison.Ordinal));
    static void Layout(TMP_Text text, string path, bool korean)
    {
        bool header = path.EndsWith("/HeaderTitleCommon(Clone)/Text", StringComparison.Ordinal);
        bool slot = path.Contains("/DeckUnitSlot.", StringComparison.Ordinal) && path.EndsWith("/AbilityRoot/Image", StringComparison.Ordinal);
        bool card = SubskillName(path);
        bool ex = path.EndsWith("/ExSkillTextArea/TextArea/Text", StringComparison.Ordinal);
        int id = text.GetInstanceID();
        if (!korean || !(header || slot || card || ex))
        {
            if (layouts.Remove(id, out var old) && old.Text == text)
            { text.margin = old.Margin; text.lineSpacing = old.LineSpacing; text.enableWordWrapping = old.Wrap; text.fontSizeMin = old.MinSize; }
            return;
        }
        if (!layouts.TryGetValue(id, out var original) || original.Text != text)
            layouts[id] = original = (text, text.margin, text.lineSpacing, text.enableWordWrapping, text.fontSizeMin);
        var margin = original.Margin;
        // Expand only the measured vertical padding of known one-line labels.
        // Do not change the font glyphs, other panels, or general overflow mode.
        if (header)
        {
            margin.y = -4; margin.w = -4;
            // Keep long titles clear of the back/help buttons on both sides.
            margin.x = Math.Max(margin.x, 6); margin.z = Math.Max(margin.z, 6);
            text.fontSizeMin = Math.Min(original.MinSize, 16);
        }
        if (slot || card) { margin.y = 0; margin.w = 0; }
        if (ex) { margin.w = 0; text.lineSpacing = original.LineSpacing - 20; }
        if (text.margin != margin) text.margin = margin;
        if (header || slot || card) text.enableWordWrapping = false;
    }
    public static string PathOf(Transform t)
    {
        string path = t.name;
        for (int i = 0; t.parent != null && i < 48; i++) { t = t.parent; path = t.name + "/" + path; }
        return path;
    }
    public static void Apply(TMP_Text text, string path)
    {
        bool korean = UiDisplayText.ContainsHangul(text.text);
        Layout(text, path, korean);
        bool skill = path.EndsWith("/ExSkillTextArea/Title/TitleText", StringComparison.Ordinal)
            || path.EndsWith("/ExSkillTextArea/TextArea/Text", StringComparison.Ordinal)
            || SubskillName(path)
            || (path.Contains("/DeckUnitSlot.", StringComparison.Ordinal) && path.EndsWith("/AbilityRoot/Image", StringComparison.Ordinal))
            || (path.Contains("/Bom_Detail_StatusView/", StringComparison.Ordinal) &&
                (path.EndsWith("/TextArea/Text", StringComparison.Ordinal) || path.EndsWith("/Title/TitleText", StringComparison.Ordinal)))
            || (path.Contains("/Voice/ScrollView_Home/", StringComparison.Ordinal) && path.EndsWith("/Off/Text", StringComparison.Ordinal));
        int id = text.GetInstanceID();
        if (!skill || !korean)
        {
            if (materials.Remove(id, out var previous))
            {
                if (previous.Text == text && text.fontSharedMaterial == previous.Styled) text.fontSharedMaterial = previous.Original;
                UnityEngine.Object.Destroy(previous.Styled);
            }
            return;
        }
        if (materials.TryGetValue(id, out var old) && old.Text == text && text.fontSharedMaterial == old.Styled) return;
        foreach (int key in materials.Where(p => p.Value.Text == null).Select(p => p.Key).ToArray())
        {
            UnityEngine.Object.Destroy(materials[key].Styled);
            materials.Remove(key);
        }
        foreach (int key in layouts.Where(p => p.Value.Text == null).Select(p => p.Key).ToArray()) layouts.Remove(key);
        var original = text.fontSharedMaterial;
        if (original == null) return;
        if (materials.Remove(id, out old)) UnityEngine.Object.Destroy(old.Styled);
        var material = new Material(original) { name = "Monmusu_UiOutline_" + id };
        material.SetColor("_FaceColor", Color.white);
        material.SetColor("_OutlineColor", new Color(80f / 255, 70f / 255, 70f / 255, 1));
        // SDF outline expands inward too. Match dilate to width to retain the
        // white stroke while extending the dark border around it.
        material.SetFloat("_FaceDilate", 0.36f);
        material.SetFloat("_OutlineWidth", 0.36f);
        material.SetFloat("_OutlineSoftness", 0.02f);
        text.fontSharedMaterial = material;
        text.havePropertiesChanged = true;
        text.UpdateMeshPadding();
        text.SetVerticesDirty();
        materials[id] = (text, original, material);
        Plugin.Instance.Log.LogInfo($"MM_UI_OUTLINE_STYLE renderer={path} size={text.fontSize} auto={text.enableAutoSizing} font={text.font?.name} outline=0.36 dilate=0.36");
    }
}
