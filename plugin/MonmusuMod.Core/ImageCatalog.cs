using System.Buffers.Binary;
using System.Text.Json.Serialization;

namespace MonmusuMod.Core;

// Adapted from the user's GCMod ImageCatalog/ImageCache design. See plugin/THIRD_PARTY.
// Authoring provenance identifies original records; runtime selectors use observed
// component context and source texture identity as well as the sprite name/size.
public sealed class ImageCatalog
{
    [JsonPropertyName("schema")] public string Schema { get; set; } = "";
    [JsonPropertyName("entries")] public List<ImageEntry> Entries { get; set; } = new();
    public static ImageCatalog Parse(byte[] json)
    {
        var catalog = TranslationPackage.Parse<ImageCatalog>(json);
        if (catalog.Schema != "monmusu-images-v1") throw new InvalidDataException("Unknown image catalog");
        var ids = new HashSet<string>(StringComparer.Ordinal);
        foreach (var entry in catalog.Entries)
        {
            if (!ids.Add(entry.Id) || string.IsNullOrWhiteSpace(entry.Id) || entry.Kind != "sprite" && entry.Kind != "texture" ||
                string.IsNullOrWhiteSpace(entry.Name) || entry.Width <= 0 || entry.Height <= 0 || entry.Bytes < 33 ||
                !IsHash(entry.Sha256) || entry.File != "images/" + entry.Sha256 + ".png" ||
                entry.ReviewStatus != "reviewed" || string.IsNullOrWhiteSpace(entry.ReviewId) ||
                string.IsNullOrWhiteSpace(entry.Jp) || string.IsNullOrWhiteSpace(entry.Ko) ||
                entry.SourceIds.Length == 0 || entry.ContextSuffixes.Length == 0 ||
                entry.ContextSuffixes.Any(s => string.IsNullOrWhiteSpace(s) || s.StartsWith('/') || s.Contains('\\')) ||
                entry.SourceTextures.Length == 0 || entry.SourceTextures.Any(s => string.IsNullOrEmpty(s.Name) || s.Width <= 0 || s.Height <= 0))
                throw new InvalidDataException("Invalid/unreviewed image: " + entry.Id);
        }
        return catalog;
    }
    static bool IsHash(string value) => value.Length == 64 && value.All(c => c is >= '0' and <= '9' or >= 'a' and <= 'f');

    public ImageEntry? Match(string kind, string name, int width, int height, string context, string textureName, int textureWidth, int textureHeight)
    {
        ImageEntry? match = null;
        foreach (var entry in Entries)
        {
            if (entry.Kind != kind || entry.Name != name || entry.Width != width || entry.Height != height ||
                !entry.ContextSuffixes.Any(s => context == s || context.EndsWith("/" + s, StringComparison.Ordinal)) ||
                !entry.SourceTextures.Any(s => s.Name == textureName && s.Width == textureWidth && s.Height == textureHeight)) continue;
            if (match != null) return null; // Ambiguous contexts must not select arbitrarily.
            match = entry;
        }
        return match;
    }
}

public sealed class ImageEntry
{
    [JsonPropertyName("id")] public string Id { get; set; } = "";
    [JsonPropertyName("kind")] public string Kind { get; set; } = "";
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("width")] public int Width { get; set; }
    [JsonPropertyName("height")] public int Height { get; set; }
    [JsonPropertyName("file")] public string File { get; set; } = "";
    [JsonPropertyName("sha256")] public string Sha256 { get; set; } = "";
    [JsonPropertyName("bytes")] public long Bytes { get; set; }
    [JsonPropertyName("source_ids")] public string[] SourceIds { get; set; } = Array.Empty<string>();
    [JsonPropertyName("context_suffixes")] public string[] ContextSuffixes { get; set; } = Array.Empty<string>();
    [JsonPropertyName("source_textures")] public ImageTextureIdentity[] SourceTextures { get; set; } = Array.Empty<ImageTextureIdentity>();
    [JsonPropertyName("jp")] public string Jp { get; set; } = "";
    [JsonPropertyName("ko")] public string Ko { get; set; } = "";
    [JsonPropertyName("review_status")] public string ReviewStatus { get; set; } = "";
    [JsonPropertyName("review_id")] public string ReviewId { get; set; } = "";
    public bool Matches(byte[] bytes) => bytes.LongLength == Bytes && bytes.Length >= 33 &&
        bytes.AsSpan(0, 8).SequenceEqual(new byte[] { 137, 80, 78, 71, 13, 10, 26, 10 }) &&
        bytes.AsSpan(12, 4).SequenceEqual(new byte[] { 73, 72, 68, 82 }) &&
        BinaryPrimitives.ReadInt32BigEndian(bytes.AsSpan(16, 4)) == Width &&
        BinaryPrimitives.ReadInt32BigEndian(bytes.AsSpan(20, 4)) == Height && TranslationPackage.Hash(bytes) == Sha256;
}

public sealed class ImageTextureIdentity
{
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("width")] public int Width { get; set; }
    [JsonPropertyName("height")] public int Height { get; set; }
}

public sealed class ImagePackage
{
    public ImageCatalog Catalog { get; }
    readonly string root;
    public ImagePackage(string root, ImageCatalog catalog, IReadOnlyList<FileEntry> files)
    {
        this.root = root; Catalog = catalog;
        var expected = catalog.Entries.GroupBy(e => e.File).ToDictionary(g => g.Key, g => g.First().Sha256, StringComparer.Ordinal);
        if (files.Count != expected.Count || files.Any(f => !expected.TryGetValue(f.Path, out var hash) || hash != f.Sha256))
            throw new InvalidDataException("Image payload manifest mismatch");
        foreach (var entry in catalog.Entries) Read(entry);
    }
    public byte[] Read(ImageEntry entry)
    {
        byte[] bytes = File.ReadAllBytes(TranslationPackage.ResolvePath(root, entry.File));
        if (!entry.Matches(bytes)) throw new InvalidDataException("Image content mismatch: " + entry.Id);
        return bytes;
    }
}
