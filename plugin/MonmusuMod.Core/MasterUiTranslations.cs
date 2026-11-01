using System.Text.Json.Serialization;
using System.Text.RegularExpressions;

namespace MonmusuMod.Core;

public interface IMasterNode
{
    IMasterNode? Field(string name);
    IEnumerable<IMasterNode>? Elements();
    string? Text { get; set; }
}

public sealed class MasterBinding
{
    [JsonPropertyName("class")] public string Class { get; set; } = "";
    [JsonPropertyName("source_id")] public string SourceId { get; set; } = "";
}
public sealed class MasterBindings
{
    [JsonPropertyName("schema_version")] public int SchemaVersion { get; set; }
    [JsonPropertyName("tables")] public Dictionary<string, MasterBinding> Tables { get; set; } = new();
}

public sealed class MasterUiTranslations
{
    readonly Dictionary<string, string> ui;
    readonly Dictionary<string, Dictionary<string, Dictionary<string, string>>> master;
    readonly MasterBindings bindings;
    static readonly Regex Segment = new(@"^[A-Za-z_][A-Za-z_0-9]*(?:\[\])*$");
    static readonly Regex Numeric = new(@"\d+(?:[.,]\d+)*");
    public int UiCount => ui.Count;
    public int MasterCount => master.Values.Sum(t => t.Values.Sum(f => f.Count));
    public IEnumerable<string> KoreanTexts => ui.Values.Concat(master.Values.SelectMany(t => t.Values).SelectMany(f => f.Values));
    public MasterUiTranslations(Dictionary<string, string> ui,
        Dictionary<string, Dictionary<string, Dictionary<string, string>>> master, MasterBindings bindings)
    {
        this.ui = ui; this.master = master; this.bindings = bindings;
        if (bindings.SchemaVersion != 1) throw new InvalidDataException("Invalid master binding schema");
        foreach (var pair in ui) ValidatePair(pair.Key, pair.Value);
        foreach (var table in master)
        {
            if (!bindings.Tables.TryGetValue(table.Key, out var binding) || string.IsNullOrWhiteSpace(binding.Class))
                throw new InvalidDataException("Missing master class binding: " + table.Key);
            foreach (var field in table.Value)
            {
                if (!field.Key.Split('.').All(p => Segment.IsMatch(p)) || Structural(field.Key))
                    throw new InvalidDataException("Invalid/display-ineligible master field: " + field.Key);
                foreach (var pair in field.Value) ValidatePair(pair.Key, pair.Value);
            }
        }
    }
    public static bool Structural(string path)
    {
        string leaf = path.Split('.').Last().Replace("[]", "").ToLowerInvariant();
        return new[] { "id", "key", "code", "kana", "scenario_name", "m_name", "m_script" }.Contains(leaf) ||
            leaf.EndsWith("_id") || leaf.EndsWith("_ids") || leaf.EndsWith("_rid");
    }
    public static void ValidatePair(string jp, string ko)
    {
        static IEnumerable<string> Numbers(string text) => Numeric.Matches(text.Normalize(System.Text.NormalizationForm.FormKC)).Select(m => m.Value);
        if (string.IsNullOrEmpty(jp) || string.IsNullOrWhiteSpace(ko) || jp == ko || ko.Contains('\0') ||
            !ControlTokens.Read(jp).SequenceEqual(ControlTokens.Read(ko)) || !Numbers(jp).SequenceEqual(Numbers(ko)))
            throw new InvalidDataException("Invalid Master/UI pair or changed controls/numbers");
    }
    public string? TranslateUi(string exact) => ui.TryGetValue(exact, out var result) ? result : null;
    public bool HasMaster(string name, string className) => master.ContainsKey(name) && bindings.Tables[name].Class == className;
    public int ApplyMaster(string name, string className, IMasterNode root, Action<string>? missingField = null)
    {
        if (!HasMaster(name, className)) return 0;
        int count = 0;
        foreach (var field in master[name])
        {
            var nodes = new List<IMasterNode> { root };
            foreach (string segment in field.Key.Split('.'))
            {
                string fieldName = segment.Replace("[]", "");
                int arrays = (segment.Length - fieldName.Length) / 2;
                var children = new List<IMasterNode>();
                foreach (var parent in nodes)
                {
                    var child = parent.Field(fieldName);
                    if (child == null) { missingField?.Invoke(field.Key); continue; }
                    children.Add(child);
                }
                for (int i = 0; i < arrays; i++)
                    children = children.SelectMany(n => n.Elements() ?? Array.Empty<IMasterNode>()).ToList();
                nodes = children;
            }
            foreach (var node in nodes)
                if (node.Text is { } text && field.Value.TryGetValue(text, out var translated))
                { node.Text = translated; count++; }
        }
        return count;
    }
    public static MasterUiTranslations Empty { get; } = new(new(), new(), new() { SchemaVersion = 1 });
}
