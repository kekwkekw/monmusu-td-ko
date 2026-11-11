using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace MonmusuMod.Core;

public sealed class TranslationPackage
{
    readonly Dictionary<(string Grid, int Row), (string Scenario, NovelHeader Header, NovelRow Row)> rows = new();
    readonly Dictionary<string, string> names;
    readonly HashSet<string> grids = new(StringComparer.Ordinal);
    readonly Dictionary<string, Dictionary<int, string[]>> headers = new(StringComparer.Ordinal);
    public RuntimeManifest Manifest { get; }
    public string Identity { get; }
    public string RootDirectory { get; private set; } = "";
    public int RowCount => rows.Count;
    public int NameCount => names.Count;
    public MasterUiTranslations MasterUi { get; private set; } = MasterUiTranslations.Empty;
    public ImagePackage? Images { get; private set; }
    public bool HasGrid(string grid) => grids.Contains(grid);
    public IEnumerable<string> GridNames => grids;
    public bool HeadersMatch(string grid, Func<int, IReadOnlyList<string>?> read)
        => headers.TryGetValue(grid, out var expected) && expected.All(item =>
            read(item.Key) is { } actual && actual.SequenceEqual(item.Value));
    public string? TranslateName(string exact) => names.TryGetValue(exact, out var value) ? value : null;
    public IEnumerable<string> KoreanTexts => rows.Values.Where(x => x.Row.Hold == false).Select(x => x.Row.Ko!).Concat(names.Values).Concat(MasterUi.KoreanTexts);

    TranslationPackage(RuntimeManifest manifest, string identity, Dictionary<string, string> names)
        => (Manifest, Identity, this.names) = (manifest, identity, names);

    public static string Hash(byte[] data) => Convert.ToHexString(SHA256.HashData(data)).ToLowerInvariant();
    public static T Parse<T>(byte[] data) => JsonSerializer.Deserialize<T>(data) ?? throw new InvalidDataException("Empty JSON document");
    static void Require(bool value, string message) { if (!value) throw new InvalidDataException(message); }
    public static string ResolvePath(string root, string relative)
    {
        Require(!string.IsNullOrEmpty(relative) && !Path.IsPathRooted(relative) && !relative.Contains('\\') &&
                !relative.Contains(':') && relative.Split('/').All(x => x != ".." && x != "." && x.Length > 0), "Invalid package path");
        return Path.Combine(root, relative.Replace('/', Path.DirectorySeparatorChar));
    }
    public static RuntimeManifest ReadManifest(byte[] data)
    {
        var value = Parse<RuntimeManifest>(data);
        Require(value.Schema == "monmusu-runtime-manifest-v1", "Unknown runtime schema");
        Require(IsHash(value.PolicySha256), "Invalid policy hash");
        var paths = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        Require(value.Names.Path == "names.json", "Invalid Names path");
        Require(value.Images == null ? value.ImageFiles.Count == 0 : value.Images.Path == "images.json", "Invalid image descriptor");
        if (value.Master != null || value.Ui != null || value.MasterBindings != null)
            Require(value.Master?.Path == "master.json" && value.Ui?.Path == "ui.json" &&
                value.MasterBindings?.Path == "master-bindings.json", "Incomplete Master/UI payloads");
        foreach (var entry in value.Files)
        {
            ResolvePath(".", entry.Path);
            Require(paths.Add(entry.Path) && IsHash(entry.Sha256), "Duplicate path / invalid checksum");
        }
        Require(value.Scenarios.Select(x => x.ScenarioName).Distinct(StringComparer.Ordinal).Count() == value.Scenarios.Count &&
                value.Scenarios.All(x => !string.IsNullOrEmpty(x.ScenarioName) && x.Path.StartsWith("novels/", StringComparison.Ordinal)), "Invalid scenario identities");
        var aliases = new HashSet<string>(StringComparer.Ordinal);
        foreach (var entry in value.Scenarios)
            if (entry.GridNames != null)
                foreach (string grid in entry.GridNames)
                    Require(!string.IsNullOrEmpty(grid) && aliases.Add(grid), "Ambiguous/empty grid alias");
        return value;
    }
    static bool IsHash(string text) => text.Length == 64 && text.All(ch => ch is >= '0' and <= '9' or >= 'a' and <= 'f');
    public static TranslationPackage Load(string root, bool includeNovels = true)
    {
        byte[] manifestBytes = File.ReadAllBytes(Path.Combine(root, "manifest.json"));
        var manifest = ReadManifest(manifestBytes);
        byte[] Read(FileEntry entry)
        {
            var bytes = File.ReadAllBytes(ResolvePath(root, entry.Path));
            Require(Hash(bytes) == entry.Sha256, "Checksum mismatch: " + entry.Path); return bytes;
        }
        var names = Parse<Dictionary<string, string>>(Read(manifest.Names));
        Require(names.All(x => !string.IsNullOrEmpty(x.Key) && !string.IsNullOrWhiteSpace(x.Value) && !x.Value.Contains('\0')), "Invalid Names");
        var package = new TranslationPackage(manifest, Hash(manifestBytes), names) { RootDirectory = root };
        if (manifest.Images != null)
            package.Images = new ImagePackage(root, ImageCatalog.Parse(Read(manifest.Images)), manifest.ImageFiles);
        if (manifest.Master != null)
            package.MasterUi = new MasterUiTranslations(Parse<Dictionary<string, string>>(Read(manifest.Ui!)),
                Parse<Dictionary<string, Dictionary<string, Dictionary<string, string>>>>(Read(manifest.Master)),
                Parse<MasterBindings>(Read(manifest.MasterBindings!)));
        var rowIds = new HashSet<string>(StringComparer.Ordinal);
        foreach (var entry in includeNovels ? manifest.Scenarios : Enumerable.Empty<FileEntry>())
        {
            package.AddNovel(entry, Read(entry), rowIds);
        }
        return package;
    }

    public TranslationPackage WithNovel(FileEntry entry, byte[] bytes)
    {
        Require(Manifest.Scenarios.Contains(entry), "Scene outside selected generation");
        var package = new TranslationPackage(Manifest, Identity, names) { MasterUi = MasterUi, Images = Images, RootDirectory = RootDirectory };
        package.AddNovel(entry, bytes, new HashSet<string>(StringComparer.Ordinal));
        return package;
    }

    void AddNovel(FileEntry entry, byte[] bytes, HashSet<string> rowIds)
    {
            Require(Hash(bytes) == entry.Sha256, "Scenario checksum mismatch");
            var package = this;
            var manifest = Manifest;
            var doc = Parse<ReviewedNovel>(bytes);
            Require(doc.Schema == "monmusu-reviewed-novel-v1" && doc.ScenarioName == entry.ScenarioName, "Scenario identity mismatch");
            Require(doc.Rows.Count == doc.ReviewedRows && doc.PendingRows >= 0 && doc.TotalRows == doc.ReviewedRows + doc.PendingRows, "Invalid row counts");
            var usedGrids = doc.Rows.Select(row => doc.Headers.Single(h => h.GridIndex == row.GridIndex && h.HeaderRow == row.HeaderRow).GridName).ToHashSet(StringComparer.Ordinal);
            Require(entry.GridNames == null || usedGrids.SetEquals(entry.GridNames), "Grid index differs from approved rows");
            foreach (var row in doc.Rows)
            {
                var header = doc.Headers.Single(h => h.GridIndex == row.GridIndex && h.HeaderRow == row.HeaderRow);
                Require(!string.IsNullOrEmpty(header.GridName) && header.TextColumn >= 0 && header.TextColumn < header.Columns.Length &&
                        header.Columns[header.TextColumn].Trim() == "Text", "Invalid grid header");
                Require(row.RowIndex > row.HeaderRow && row.SourceCells.Length > header.TextColumn && row.SourceCells[header.TextColumn] == row.Jp, "Invalid source cells");
                Require(rowIds.Add(row.RowId) && !string.IsNullOrWhiteSpace(row.RowId) && Hash(Encoding.UTF8.GetBytes(row.Jp)) == row.JpSha256, "Invalid original row hash / duplicate ID");
                Require(row.ReviewStatus == "reviewed" && !string.IsNullOrWhiteSpace(row.ReviewId) && row.PolicySha256 == manifest.PolicySha256 && row.Hold.HasValue, "Row not explicitly reviewed");
                if (row.Hold == true)
                    Require(row.Ko == null && !string.IsNullOrWhiteSpace(row.Reason) && row.TranslationStatus == "hold", "Invalid HOLD row");
                else
                    Require(row.TranslationStatus == "translated" && !string.IsNullOrWhiteSpace(row.Ko) && !row.Ko.Contains('\0') &&
                            ControlTokens.Read(row.Jp).SequenceEqual(ControlTokens.Read(row.Ko)), "Invalid translated row / controls");
                Require(package.rows.TryAdd((header.GridName, row.RowIndex), (doc.ScenarioName, header, row)), "Ambiguous grid position");
                package.grids.Add(header.GridName);
                if (!package.headers.TryGetValue(header.GridName, out var table))
                    package.headers.Add(header.GridName, table = new());
                if (table.TryGetValue(header.HeaderRow, out var existing))
                    Require(existing.SequenceEqual(header.Columns), "Conflicting grid headers");
                else table.Add(header.HeaderRow, header.Columns);
            }
    }

    // No JP-only fallback: repeated JP at different rows retains distinct translations/HOLD.
    public RowMatch Match(string gridName, int rowIndex, int serializedRowIndex, IReadOnlyList<string> cells)
    {
        if (!rows.TryGetValue((gridName, rowIndex), out var found)) return new(MatchKind.Missing, "", "", -1, null);
        var (scenario, header, row) = found;
        RowMatch Result(MatchKind kind) => new(kind, scenario, row.RowId, header.TextColumn, row.Ko);
        if (row.SerializedRowIndex.HasValue && row.SerializedRowIndex.Value != serializedRowIndex || cells.Count != row.SourceCells.Length)
            return Result(MatchKind.SourceMismatch);
        bool original = true, already = row.Hold == false;
        for (int i = 0; i < cells.Count; i++)
        {
            original &= cells[i] == row.SourceCells[i];
            already &= cells[i] == (i == header.TextColumn ? row.Ko : row.SourceCells[i]);
        }
        if (original) return Result(row.Hold == true ? MatchKind.Hold : MatchKind.Apply);
        return Result(already ? MatchKind.AlreadyApplied : MatchKind.SourceMismatch);
    }
}
