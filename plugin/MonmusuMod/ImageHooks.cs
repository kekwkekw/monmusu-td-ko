using MonmusuMod.Core;
using UnityEngine;
using UnityEngine.UI;
using Object = UnityEngine.Object;

namespace MonmusuMod;

// GCMod's UI-reference replacement approach, adapted to observed Monmusu contexts.
// Never changes shared source textures, source bundles, button events or transforms.
internal static class ImageHooks
{
    static readonly Dictionary<string, Texture2D> textures = new(StringComparer.Ordinal);
    static readonly Dictionary<(string, int), Sprite> sprites = new();
    static readonly HashSet<string> logged = new(StringComparer.Ordinal);
    [ThreadStatic] static bool applying;
    static ImagePackage? Package => Plugin.Instance.Images;
    static bool Own(Object obj) => obj != null && obj.name.StartsWith("MonmusuMod:Image:", StringComparison.Ordinal);
    static string Context(Component component)
    {
        var names = new List<string>();
        for (var t = component.transform; t != null; t = t.parent) names.Add(t.name.Replace("(Clone)", ""));
        names.Reverse(); return string.Join("/", names);
    }
    static void Warn(Exception ex)
    {
        if (logged.Add("error:" + ex.Message)) Plugin.Instance.Log.LogWarning("MM_IMAGE_FAILED: " + ex);
    }
    static Texture2D? Load(ImageEntry entry)
    {
        if (textures.TryGetValue(entry.Sha256, out var cached) && cached != null) return cached;
        var package = Package;
        if (package == null) return null;
        var texture = new Texture2D(2, 2, TextureFormat.RGBA32, false);
        try
        {
            if (!ImageConversion.LoadImage(texture, package.Read(entry), true)) throw new InvalidDataException("PNG decode failed: " + entry.Id);
            texture.name = "MonmusuMod:Image:" + entry.Sha256;
            texture.filterMode = FilterMode.Bilinear; texture.wrapMode = TextureWrapMode.Clamp;
            Object.DontDestroyOnLoad(texture); textures[entry.Sha256] = texture;
            return texture;
        }
        catch { Object.Destroy(texture); throw; }
    }
    static Sprite? Translate(Image component, Sprite? original)
    {
        if (original == null || Own(original) || Package == null) return original;
        var rect = original.rect;
        var source = original.texture;
        if (source == null) return original;
        string context = Context(component);
        var entry = Package.Catalog.Match("sprite", original.name, (int)rect.width, (int)rect.height, context, source.name, source.width, source.height);
        if (entry == null)
        {
            if (Package.Catalog.Entries.Any(e => e.Name == original.name) && logged.Add("unmatched:" + original.name + ":" + context))
                Plugin.Instance.Log.LogInfo($"MM_IMAGE_UNMATCHED name={original.name} size={rect.width}x{rect.height} texture={source.name} texture_size={source.width}x{source.height} context={context}");
            return original;
        }
        var key = (entry.Id, original.GetInstanceID());
        if (sprites.TryGetValue(key, out var cached) && cached != null) return cached;
        var texture = Load(entry);
        if (texture == null) return original;
        var pivot = original.pivot;
        var sprite = Sprite.Create(texture, new Rect(0, 0, texture.width, texture.height),
            new Vector2(pivot.x / rect.width, pivot.y / rect.height), original.pixelsPerUnit,
            0, SpriteMeshType.FullRect, original.border);
        sprite.name = "MonmusuMod:Image:" + entry.Id;
        Object.DontDestroyOnLoad(sprite); sprites[key] = sprite;
        if (logged.Add(entry.Id + ":" + context)) Plugin.Instance.Log.LogInfo($"MM_IMAGE_APPLIED id={entry.Id} context={context}");
        return sprite;
    }
    public static void SetSprite(Image __instance, ref Sprite value)
    {
        if (applying || Package == null) return;
        try { value = Translate(__instance, value)!; } catch (Exception ex) { Warn(ex); }
    }
    public static void EnableImage(Image __instance)
    {
        if (applying || Package == null || __instance == null) return;
        try
        {
            applying = true;
            var original = __instance.sprite;
            var translated = Translate(__instance, original);
            if (translated != original) __instance.sprite = translated;
            // The public getter falls back to the base sprite; inspect the actual
            // override field so recycled/transitioning buttons are not pinned.
            original = __instance.m_OverrideSprite;
            translated = Translate(__instance, original);
            if (translated != original) __instance.overrideSprite = translated;
        }
        catch (Exception ex) { Warn(ex); }
        finally { applying = false; }
    }
    public static void SetTexture(RawImage __instance, ref Texture value)
    {
        if (applying || Package == null || value == null || Own(value) || __instance.uvRect != new Rect(0, 0, 1, 1)) return;
        try
        {
            var entry = Package.Catalog.Match("texture", value.name, value.width, value.height, Context(__instance), value.name, value.width, value.height);
            if (entry != null && Load(entry) is { } texture) value = texture;
        }
        catch (Exception ex) { Warn(ex); }
    }
    public static void EnableGraphic(MaskableGraphic __instance)
    {
        var raw = __instance?.TryCast<RawImage>();
        if (raw == null) return;
        Texture original = raw.texture, translated = original;
        SetTexture(raw, ref translated);
        if (translated != original) raw.texture = translated;
    }
}
