using MonmusuMod.Core;
using Utage;

namespace MonmusuMod;

internal static class Hooks
{
    static readonly HashSet<string> reported = new(StringComparer.Ordinal);
    static Plugin P => Plugin.Instance;
    static void Guard(Action action)
    {
        try { action(); }
        catch (Exception ex) { P.Log.LogWarning("MM_HOOK_FAILED: " + ex); }
    }
    public static void BookReady(AdvImportBook __instance) => Guard(() =>
    {
        var grids = __instance.ImportGridList;
        if (grids == null) return;
        for (int i = 0; i < grids.Count; i++) Apply(grids[i]);
    });
    public static void BeforeCommands(AdvImportScenarioSheet __instance) => Guard(() => Apply(__instance));

    static void Apply(AdvImportScenarioSheet grid)
    {
        var package = P.Package;
        if (package == null || grid == null) return;
        string name = grid.Name;
        if (!package.HasGrid(name))
        {
            if (P.LogUnmatched && reported.Add("missing:" + name)) P.Log.LogInfo("MM_GRID_UNTRANSLATED " + name);
            return;
        }
        int applied = 0, already = 0, held = 0, mismatch = 0;
        var rows = grid.Rows;
        if (!package.HeadersMatch(name, index => index < 0 || index >= rows.Count || rows[index]?.Strings == null ? null : Copy(rows[index].Strings)))
        {
            if (reported.Add("header:" + name)) P.Log.LogWarning("MM_HEADER_MISMATCH grid=" + name + "; retained original grid");
            return;
        }
        for (int i = 0; i < rows.Count; i++)
        {
            var row = rows[i];
            if (row == null || row.Strings == null) continue;
            var cells = row.Strings;
            string[] source = Copy(cells);
            var match = package.Match(name, i, row.RowIndex, source);
            switch (match.Kind)
            {
                case MatchKind.Apply:
                    // Only the Text array element changes, before Utage constructs commands/TextData.
                    // Arg1 character IDs, jumps, Voice, PageCtrl and the on-disk book remain original.
                    cells[match.TextColumn] = match.Translation!;
                    applied++;
                    break;
                case MatchKind.AlreadyApplied: already++; break;
                case MatchKind.Hold: held++; break;
                case MatchKind.SourceMismatch:
                    mismatch++;
                    if (reported.Add("mismatch:" + match.RowId)) P.Log.LogWarning($"MM_SOURCE_MISMATCH grid={name} row={i} id={match.RowId}; retained current game text");
                    break;
            }
        }
        string report = $"MM_GRID grid={name} applied={applied} already={already} hold={held} mismatch={mismatch}";
        if (applied > 0 || reported.Add(report)) P.Log.LogInfo(report);
    }

    static string[] Copy(Il2CppInterop.Runtime.InteropTypes.Arrays.Il2CppStringArray cells)
    {
        string[] result = new string[cells.Length];
        for (int j = 0; j < result.Length; j++) result[j] = cells[j];
        return result;
    }

    public static void MessageChanged(AdvUguiMessageWindow __instance) => Guard(() =>
    {
        TranslateLabel(__instance.nameText);
        P.Fonts.Apply(__instance.Text);
    });
    public static void BacklogReady(AdvUguiBacklog __instance) => Guard(() =>
    {
        TranslateLabel(__instance.characterName);
        P.Fonts.Apply(__instance.text);
    });
    public static void SelectionReady(AdvUguiSelection __instance) => Guard(() => P.Fonts.Apply(__instance.text));
    static void TranslateLabel(UnityEngine.UI.Text? text)
    {
        if (text == null) return;
        string? translated = P.Package?.TranslateName(text.text);
        if (translated != null) text.text = translated;
        P.Fonts.Apply(text);
    }
}
