using System.Text.Json.Serialization;

namespace MonmusuMod.Core;

public sealed class FileEntry
{
    [JsonPropertyName("path")] public string Path { get; set; } = "";
    [JsonPropertyName("sha256")] public string Sha256 { get; set; } = "";
    [JsonPropertyName("scenario_name")] public string? ScenarioName { get; set; }
}

public sealed class RuntimeManifest
{
    [JsonPropertyName("schema")] public string Schema { get; set; } = "";
    [JsonPropertyName("policy_sha256")] public string PolicySha256 { get; set; } = "";
    [JsonPropertyName("names")] public FileEntry Names { get; set; } = new();
    [JsonPropertyName("scenarios")] public List<FileEntry> Scenarios { get; set; } = new();
    [JsonPropertyName("master")] public FileEntry? Master { get; set; }
    [JsonPropertyName("ui")] public FileEntry? Ui { get; set; }
    [JsonPropertyName("master_bindings")] public FileEntry? MasterBindings { get; set; }
    [JsonIgnore] public IEnumerable<FileEntry> Files => new[] { Names }.Concat(Scenarios)
        .Concat(new[] { Master, Ui, MasterBindings }.Where(x => x != null).Cast<FileEntry>());
}

public sealed class NovelHeader
{
    [JsonPropertyName("grid_index")] public int GridIndex { get; set; }
    [JsonPropertyName("grid_name")] public string GridName { get; set; } = "";
    [JsonPropertyName("header_row_index_0based")] public int HeaderRow { get; set; }
    [JsonPropertyName("columns")] public string[] Columns { get; set; } = Array.Empty<string>();
    [JsonPropertyName("text_column_index_0based")] public int TextColumn { get; set; }
}

public sealed class NovelRow
{
    [JsonPropertyName("row_id")] public string RowId { get; set; } = "";
    [JsonPropertyName("grid_index")] public int GridIndex { get; set; }
    [JsonPropertyName("header_row_index_0based")] public int HeaderRow { get; set; }
    [JsonPropertyName("row_index_0based")] public int RowIndex { get; set; }
    [JsonPropertyName("serialized_row_index")] public int? SerializedRowIndex { get; set; }
    [JsonPropertyName("source_cells")] public string[] SourceCells { get; set; } = Array.Empty<string>();
    [JsonPropertyName("jp")] public string Jp { get; set; } = "";
    [JsonPropertyName("jp_sha256")] public string JpSha256 { get; set; } = "";
    [JsonPropertyName("ko")] public string? Ko { get; set; }
    [JsonPropertyName("hold")] public bool? Hold { get; set; }
    [JsonPropertyName("reason")] public string Reason { get; set; } = "";
    [JsonPropertyName("review_status")] public string ReviewStatus { get; set; } = "";
    [JsonPropertyName("translation_status")] public string TranslationStatus { get; set; } = "";
    [JsonPropertyName("review_id")] public string ReviewId { get; set; } = "";
    [JsonPropertyName("policy_sha256")] public string PolicySha256 { get; set; } = "";
}

public sealed class ReviewedNovel
{
    [JsonPropertyName("schema")] public string Schema { get; set; } = "";
    [JsonPropertyName("scenario_name")] public string ScenarioName { get; set; } = "";
    [JsonPropertyName("total_rows")] public int TotalRows { get; set; }
    [JsonPropertyName("reviewed_rows")] public int ReviewedRows { get; set; }
    [JsonPropertyName("pending_rows")] public int PendingRows { get; set; }
    [JsonPropertyName("headers")] public List<NovelHeader> Headers { get; set; } = new();
    [JsonPropertyName("rows")] public List<NovelRow> Rows { get; set; } = new();
}

public enum MatchKind { Missing, Apply, AlreadyApplied, Hold, SourceMismatch }
public sealed record RowMatch(MatchKind Kind, string Scenario, string RowId, int TextColumn, string? Translation);
