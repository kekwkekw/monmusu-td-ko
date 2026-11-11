using System.Net;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using MonmusuMod.Core;

int passed = 0;
void Check(bool ok, string message) { if (!ok) throw new Exception(message); }
void Throws(Action act) { try { act(); } catch (InvalidDataException) { return; } throw new Exception("Expected rejection"); }
void Test(string name, Action action) { action(); passed++; Console.WriteLine("PASS " + name); }
string testRoot = Environment.GetEnvironmentVariable("MONMUSU_TEST_TEMP_ROOT") ?? Path.GetTempPath();
string root = Path.Combine(testRoot, "monmusu-mod-tests-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(root);
var jsonOptions = new JsonSerializerOptions { WriteIndented = true };
string policy = new('a', 64);
NovelRow Row(int position, string ko, bool hold = false) => new()
{
    RowId = "row:" + position, GridIndex = 0, HeaderRow = 0, RowIndex = position, SerializedRowIndex = position,
    SourceCells = new[] { "", "人物", "<b>同じ</b>\n$NAME", "voice" }, Jp = "<b>同じ</b>\n$NAME",
    JpSha256 = TranslationPackage.Hash(Encoding.UTF8.GetBytes("<b>同じ</b>\n$NAME")), Ko = hold ? null : ko,
    Hold = hold, Reason = hold ? "Reviewed hold" : "", ReviewStatus = "reviewed", ReviewId = "test-review",
    TranslationStatus = hold ? "hold" : "translated", PolicySha256 = policy
};
var document = new ReviewedNovel
{
    Schema = "monmusu-reviewed-novel-v1", ScenarioName = "exact-scene ", TotalRows = 4, ReviewedRows = 3, PendingRows = 1,
    Headers = new() { new() { GridIndex = 0, GridName = "exact-grid ", HeaderRow = 0, Columns = new[] { "Command", "Arg1", "Text", "Voice" }, TextColumn = 2 } },
    Rows = new() { Row(1, "<b>첫째</b>\n$NAME"), Row(2, "<b>둘째</b>\n$NAME"), Row(3, "", true) }
};
void WritePackage(string folder)
{
    Directory.CreateDirectory(Path.Combine(folder, "novels"));
    byte[] names = JsonSerializer.SerializeToUtf8Bytes(new Dictionary<string, string> { ["人物"] = "인물" });
    byte[] novel = JsonSerializer.SerializeToUtf8Bytes(document, jsonOptions);
    File.WriteAllBytes(Path.Combine(folder, "names.json"), names);
    File.WriteAllBytes(Path.Combine(folder, "novels/test.json"), novel);
    var manifest = new RuntimeManifest { Schema = "monmusu-runtime-manifest-v1", PolicySha256 = policy,
        Names = new() { Path = "names.json", Sha256 = TranslationPackage.Hash(names) },
        Scenarios = new() { new() { Path = "novels/test.json", Sha256 = TranslationPackage.Hash(novel), ScenarioName = document.ScenarioName } } };
    File.WriteAllBytes(Path.Combine(folder, "manifest.json"), JsonSerializer.SerializeToUtf8Bytes(manifest, jsonOptions));
}
try
{
    WritePackage(root);
    {
        byte[] png = Convert.FromBase64String("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jY9sAAAAASUVORK5CYII=");
        string digest = TranslationPackage.Hash(png);
        var image = new ImageEntry { Id = "sample", Kind = "sprite", Name = "repeated-name", Width = 1, Height = 1,
            File = "images/" + digest + ".png", Sha256 = digest, Bytes = png.Length,
            SourceIds = new[] { "source:1" }, ContextSuffixes = new[] { "Gallery/Label" },
            SourceTextures = new[] { new ImageTextureIdentity { Name = "original-atlas", Width = 2048, Height = 2048 } },
            Jp = "原文", Ko = "번역", ReviewStatus = "reviewed", ReviewId = "test-review" };
        var images = new ImageCatalog { Schema = "monmusu-images-v1", Entries = new() { image } };
        byte[] CatalogBytes() => JsonSerializer.SerializeToUtf8Bytes(images, jsonOptions);
        Test("Image selectors distinguish repeated names by component and original texture", () =>
        {
            var c = ImageCatalog.Parse(CatalogBytes());
            Check(c.Match("sprite", image.Name, 1, 1, "Canvas/Gallery/Label", "original-atlas", 2048, 2048) != null, "valid target missed");
            Check(c.Match("sprite", image.Name, 1, 1, "Canvas/Shop/Label", "original-atlas", 2048, 2048) == null, "wrong screen matched");
            Check(c.Match("sprite", image.Name, 1, 1, "Canvas/Gallery/Label", "new-atlas", 2048, 2048) == null, "new source revision matched");
            c.Entries.Add(new ImageEntry { Id = "conflict", Kind = image.Kind, Name = image.Name, Width = 1, Height = 1,
                ContextSuffixes = image.ContextSuffixes, SourceTextures = image.SourceTextures });
            Check(c.Match("sprite", image.Name, 1, 1, "Canvas/Gallery/Label", "original-atlas", 2048, 2048) == null, "ambiguous target selected");
        });
        Test("Image content drift, wrong dimensions and unreviewed catalogs are rejected", () =>
        {
            Check(image.Matches(png), "valid PNG rejected");
            byte[] changed = (byte[])png.Clone(); changed[^1] ^= 1;
            Check(!image.Matches(changed), "modified PNG accepted");
            image.Width = 2; Check(!image.Matches(png), "wrong canvas accepted"); image.Width = 1;
            image.ReviewStatus = "pending"; Throws(() => ImageCatalog.Parse(CatalogBytes())); image.ReviewStatus = "reviewed";
            string file = image.File; image.File = "../escape.png"; Throws(() => ImageCatalog.Parse(CatalogBytes())); image.File = file;
        });
        Directory.CreateDirectory(Path.Combine(root, "images"));
        File.WriteAllBytes(Path.Combine(root, image.File), png);
        File.WriteAllBytes(Path.Combine(root, "images.json"), CatalogBytes());
        var manifest = TranslationPackage.ReadManifest(File.ReadAllBytes(Path.Combine(root, "manifest.json")));
        manifest.Images = new() { Path = "images.json", Sha256 = TranslationPackage.Hash(CatalogBytes()) };
        manifest.ImageFiles.Add(new() { Path = image.File, Sha256 = digest });
        File.WriteAllBytes(Path.Combine(root, "manifest.json"), JsonSerializer.SerializeToUtf8Bytes(manifest, jsonOptions));
        Test("Image publication joins the verified package and interrupted download keeps active version", () =>
        {
            Check(TranslationPackage.Load(root).Images!.Catalog.Entries.Count == 1, "images not loaded");
            string cache = Path.Combine(root, "image-cache");
            using (var client = new HttpClient(new LocalHandler(root)))
                PackageCache.RefreshAsync(client, new Uri("https://example.invalid/"), cache, CancellationToken.None).GetAwaiter().GetResult();
            string active = File.ReadAllText(Path.Combine(cache, "active.txt"));
            // A changed image is required: unchanged validated bytes must not be requested again.
            image.File = "images/changed.png";
            image.Sha256 = new string('b', 64);
            var changedCatalog = CatalogBytes();
            File.WriteAllBytes(Path.Combine(root, "images.json"), changedCatalog);
            manifest.Images!.Sha256 = TranslationPackage.Hash(changedCatalog);
            manifest.ImageFiles = new() { new() { Path = image.File, Sha256 = image.Sha256 } };
            File.WriteAllBytes(Path.Combine(root, "manifest.json"), JsonSerializer.SerializeToUtf8Bytes(manifest, jsonOptions));
            using (var client = new HttpClient(new LocalHandler(root, image.File)))
            {
                bool failed = false;
                try { PackageCache.RefreshAsync(client, new Uri("https://example.invalid/"), cache, CancellationToken.None).GetAwaiter().GetResult(); }
                catch (HttpRequestException) { failed = true; }
                Check(failed && File.ReadAllText(Path.Combine(cache, "active.txt")) == active, "interrupted image set became active");
            }
            Check(PackageCache.LoadPreferred(root, cache, _ => { }, false).Images!.Catalog.Entries.Count == 1, "complete image cache unavailable");
        });
        WritePackage(root);
    }
    var package = TranslationPackage.Load(root);
    Test("Duplicate JP remains row-specific", () => Check(package.Match("exact-grid ", 1, 1, document.Rows[0].SourceCells).Translation != package.Match("exact-grid ", 2, 2, document.Rows[1].SourceCells).Translation, "collapsed duplicate JP"));
    Test("HOLD remains original and pending row has no lookup", () =>
    {
        Check(package.Match("exact-grid ", 3, 3, document.Rows[2].SourceCells).Kind == MatchKind.Hold, "HOLD not retained");
        Check(package.Match("exact-grid ", 4, 4, document.Rows[0].SourceCells).Kind == MatchKind.Missing, "pending row translated");
    });
    Test("Exact grid name including trailing space", () => Check(package.Match("exact-grid", 1, 1, document.Rows[0].SourceCells).Kind == MatchKind.Missing, "normalized scene"));
    Test("Header reorder or missing header cannot target a wrong cell", () =>
    {
        Check(package.HeadersMatch("exact-grid ", _ => document.Headers[0].Columns), "original header rejected");
        Check(!package.HeadersMatch("exact-grid ", _ => new[] { "Command", "Text", "Arg1", "Voice" }), "reordered header accepted");
        Check(!package.HeadersMatch("exact-grid ", _ => null), "missing header accepted");
    });
    Test("Changed command/speaker/voice and shifted row are rejected", () =>
    {
        foreach (int cell in new[] { 0, 1, 3 })
        {
            var source = (string[])document.Rows[0].SourceCells.Clone(); source[cell] = "changed";
            Check(package.Match("exact-grid ", 1, 1, source).Kind == MatchKind.SourceMismatch, "changed control accepted");
        }
        Check(package.Match("exact-grid ", 1, 2, document.Rows[0].SourceCells).Kind == MatchKind.SourceMismatch, "shifted row accepted");
    });
    Test("Repeated initialization is idempotent", () =>
    {
        var source = (string[])document.Rows[0].SourceCells.Clone(); source[2] = document.Rows[0].Ko!;
        Check(package.Match("exact-grid ", 1, 1, source).Kind == MatchKind.AlreadyApplied, "double apply");
    });
    Test("Markup quotes and variable/newline order", () =>
    {
        Check(ControlTokens.Read("<x value='a>b'>JP</x>\n$NAME\\n{0}%s■").SequenceEqual(ControlTokens.Read("<x value='a>b'>KO</x>\n$NAME\\n{0}%s■")), "token parsing");
        Throws(() => ControlTokens.Read("<b"));
        document.Rows[0].Ko = "<b>잘못</b>$NAME\n"; WritePackage(root); Throws(() => TranslationPackage.Load(root));
        document.Rows[0].Ko = "<b>첫째</b>\n$NAME"; WritePackage(root);
    });
    Test("Unreviewed/invalid HOLD data cannot load", () =>
    {
        document.Rows[0].ReviewStatus = "pending"; WritePackage(root); Throws(() => TranslationPackage.Load(root));
        document.Rows[0].ReviewStatus = "reviewed"; document.Rows[2].Ko = "가짜"; WritePackage(root); Throws(() => TranslationPackage.Load(root));
        document.Rows[2].Ko = null; WritePackage(root);
    });
    Test("Checksums and package path traversal", () =>
    {
        File.AppendAllText(Path.Combine(root, "names.json"), " "); Throws(() => TranslationPackage.Load(root)); WritePackage(root);
        foreach (string path in new[] { "../outside", "C:/outside", "novels/../../outside", "novels\\outside", "/absolute" }) Throws(() => TranslationPackage.ResolvePath(root, path));
    });
    Test("Exact name mappings", () => Check(package.TranslateName("人物") == "인물" && package.TranslateName("人物 ") == null, "names normalized"));
    var masterUi = new MasterUiTranslations(new() { ["確認"] = "확인" },
        new() { ["sample"] = new() { ["table[].name"] = new() { ["名前1"] = "이름1" },
                                       ["groups[].labels[]"] = new() { ["確認"] = "확인" } } },
        new() { SchemaVersion = 1, Tables = new() { ["sample"] = new() { Class = "Game.Table" } } });
    Test("UI exact never uses substring or trims source", () =>
    {
        Check(masterUi.TranslateUi("確認") == "확인", "UI exact missing");
        Check(masterUi.TranslateUi("確認 ") == null && masterUi.TranslateUi("確認する") == null, "UI used partial lookup");
    });
    Test("Master exact class and field scope preserves IDs and unrelated text", () =>
    {
        var data = JsonNode.Parse("{\"table\":[{\"id\":7,\"name\":\"名前1\",\"other\":\"名前1\"},{\"id\":8,\"name\":\"changed\"}],\"groups\":[{\"labels\":[\"確認\",\"other\"]}]}")!;
        Check(masterUi.ApplyMaster("sample", "Wrong.Class", new JsonMasterNode(data)) == 0, "wrong master class translated");
        Check(masterUi.ApplyMaster("sample", "Game.Table", new JsonMasterNode(data)) == 2, "nested array fields not applied");
        Check(data["table"]![0]!["id"]!.GetValue<int>() == 7 && data["table"]![0]!["other"]!.GetValue<string>() == "名前1" &&
            data["table"]![1]!["name"]!.GetValue<string>() == "changed", "master unrelated data changed");
        Check(masterUi.ApplyMaster("sample", "Game.Table", new JsonMasterNode(data)) == 0, "master reentry applied twice");
    });
    Test("Master identifiers and UI control/number changes are rejected", () =>
    {
        Check(MasterUiTranslations.Structural("table[].id") && MasterUiTranslations.Structural("table[].scenario_name"), "identifier accepted");
        Throws(() => MasterUiTranslations.ValidatePair("<b>残り2</b>\n{0}", "<b>남음3</b>\n{0}"));
        Throws(() => MasterUiTranslations.ValidatePair("<b>残り2</b>\n{0}", "남음2\n{0}"));
        MasterUiTranslations.ValidatePair("<b>残り2</b>\n{0}", "<b>남음2</b>\n{0}");
    });
    passed += CacheTests.Run(root);

    if (args.Length >= 1)
    {
        var actual = TranslationPackage.Load(Path.GetFullPath(args[0]));
        Test("Exported approved package loads", () => Check(actual.RowCount > 0, "empty actual package"));
        Test("All exported scenes load lazily with exact source and per-row HOLD", () =>
        {
            var common = TranslationPackage.Load(Path.GetFullPath(args[0]), false);
            Check(common.RowCount == 0, "common startup parsed Novel rows");
            int translated = 0, held = 0;
            foreach (var entry in common.Manifest.Scenarios)
            {
                var bytes = File.ReadAllBytes(TranslationPackage.ResolvePath(args[0], entry.Path));
                var document = TranslationPackage.Parse<ReviewedNovel>(bytes);
                var scene = common.WithNovel(entry, bytes);
                foreach (var row in document.Rows)
                {
                    var header = document.Headers.Single(h => h.GridIndex == row.GridIndex && h.HeaderRow == row.HeaderRow);
                    var match = scene.Match(header.GridName, row.RowIndex, row.SerializedRowIndex ?? 0, row.SourceCells);
                    Check(match.Kind == (row.Hold == true ? MatchKind.Hold : MatchKind.Apply), "actual lazy row mismatch: " + row.RowId);
                    if (row.Hold == true) { Check(match.Translation == null, "actual HOLD changed text"); held++; }
                    else translated++;
                }
            }
            Check(translated + held == actual.RowCount, "lazy/eager row coverage differs");
            Console.WriteLine($"ACTUAL scenes={common.Manifest.Scenarios.Count} translated={translated} hold={held} names={common.NameCount}");
        });
        if (args.Length >= 2)
        {
            var book = JsonNode.Parse(File.ReadAllBytes(args[1]))!.AsObject();
            var before = JsonNode.Parse(book.ToJsonString())!;
            int applied = 0, already = 0, changedCells = 0;
            foreach (var grid in book["importGridList"]!.AsArray())
            {
                string gridName = grid!["name"]!.GetValue<string>();
                var rows = grid["rows"]!.AsArray();
                if (actual.HasGrid(gridName)) Check(actual.HeadersMatch(gridName,
                    i => rows[i]!["strings"]!.AsArray().Select(x => x!.GetValue<string>()).ToArray()), "actual book header mismatch");
                for (int index = 0; index < rows.Count; index++)
                {
                    var row = rows[index]!; var array = row["strings"]!.AsArray();
                    string[] values = array.Select(x => x!.GetValue<string>()).ToArray();
                    var match = actual.Match(gridName, index, row["rowIndex"]!.GetValue<int>(), values);
                    if (match.Kind != MatchKind.Apply) continue;
                    array[match.TextColumn] = match.Translation;
                    applied++;
                    var twice = actual.Match(gridName, index, row["rowIndex"]!.GetValue<int>(), array.Select(x => x!.GetValue<string>()).ToArray());
                    if (twice.Kind == MatchKind.AlreadyApplied) already++;
                }
            }
            var originalGrids = before["importGridList"]!.AsArray();
            var modifiedGrids = book["importGridList"]!.AsArray();
            for (int g = 0; g < originalGrids.Count; g++)
            {
                var originalRows = originalGrids[g]!["rows"]!.AsArray(); var modifiedRows = modifiedGrids[g]!["rows"]!.AsArray();
                for (int r = 0; r < originalRows.Count; r++)
                {
                    var a = originalRows[r]!["strings"]!.AsArray(); var b = modifiedRows[r]!["strings"]!.AsArray();
                    for (int c = 0; c < a.Count; c++)
                        if (a[c]?.ToJsonString() != b[c]?.ToJsonString()) { changedCells++; b[c] = a[c] == null ? null : JsonNode.Parse(a[c]!.ToJsonString()); }
                }
            }
            Test("Actual extracted book: exactly 26 Text cells; all remaining content preserved", () =>
                Check(applied == 26 && already == 26 && changedCells == 26 && book.ToJsonString() == before.ToJsonString(), $"actual fixture mismatch: applied={applied} already={already} cells={changedCells}"));
        }
    }
    Console.WriteLine($"PASSED {passed} checks; Unity/game execution NOT_RUN");
}
finally
{
    string temporaryRoot = Path.GetFullPath(testRoot).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
    if (!Path.GetFullPath(root).StartsWith(temporaryRoot, StringComparison.OrdinalIgnoreCase) || !Path.GetFileName(root).StartsWith("monmusu-mod-tests-", StringComparison.Ordinal))
        throw new InvalidOperationException("Unexpected temporary test directory");
    Directory.Delete(root, true);
}

sealed class LocalHandler : HttpMessageHandler
{
    readonly string root;
    readonly string? failPath;
    public LocalHandler(string root, string? failPath = null) => (this.root, this.failPath) = (root, failPath);
    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken token)
    {
        token.ThrowIfCancellationRequested();
        if (request.RequestUri!.AbsolutePath.TrimStart('/') == failPath) throw new HttpRequestException("Simulated network interruption");
        string path = TranslationPackage.ResolvePath(root, request.RequestUri!.AbsolutePath.TrimStart('/'));
        return Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK) { Content = new ByteArrayContent(File.ReadAllBytes(path)) });
    }
}

sealed class JsonMasterNode : IMasterNode
{
    readonly JsonNode node;
    readonly Action<JsonNode>? replace;
    public JsonMasterNode(JsonNode node, Action<JsonNode>? replace = null) => (this.node, this.replace) = (node, replace);
    public IMasterNode? Field(string name) => node is JsonObject obj && obj[name] is { } child ? new JsonMasterNode(child, next => obj[name] = next) : null;
    public IEnumerable<IMasterNode>? Elements() => node is JsonArray array ? array.Select((child, index) =>
        (IMasterNode)new JsonMasterNode(child!, next => array[index] = next)).ToArray() : null;
    public string? Text
    {
        get => node is JsonValue value && value.TryGetValue<string>(out var text) ? text : null;
        set => replace!(JsonValue.Create(value)!);
    }
}
