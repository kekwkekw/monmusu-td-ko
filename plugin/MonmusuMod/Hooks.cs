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
    static readonly HashSet<string> unavailableThisEntry = new(StringComparer.Ordinal);
    static long entryStart;
    static TimeSpan Remaining => TimeSpan.FromMilliseconds(Math.Max(0, 10000 -
        (System.Diagnostics.Stopwatch.GetTimestamp() - entryStart) * 1000.0 / System.Diagnostics.Stopwatch.Frequency));
    public static void StoryStarting(StoryData __0) => Guard(() =>
    {
        entryStart = System.Diagnostics.Stopwatch.GetTimestamp();
        unavailableThisEntry.Clear();
        _ = P.Novels.PrepareAsync(__0.scenario_name);
        P.Log.LogInfo("MM_NOVEL_ENTRY scenario=" + __0.scenario_name + " generation=" + P.Package!.Identity);
    });
    // Also covers scene entry paths that do not use the gallery's PlayStoryAdv.
    // No blocking occurs before this boot boundary; all subsequent grids share this deadline.
    public static void SceneBooting() => Guard(() =>
    {
        entryStart = System.Diagnostics.Stopwatch.GetTimestamp();
        unavailableThisEntry.Clear();
    });
    public static void ChapterStarting(AdvChapterData __instance) => Guard(() =>
    {
        var books = __instance.dataList;
        if (books == null) return;
        for (int b = 0; b < books.Count; b++)
        {
            var grids = books[b]?.importGridList;
            if (grids == null) continue;
            for (int g = 0; g < grids.Count; g++)
                if (grids[g] is { } grid && P.Novels.ScenarioForGrid(grid.Name) is { } scene)
                    _ = P.Novels.PrepareAsync(scene);
        }
    });
    public static void ScenarioStarting(AdvScenarioData __instance) => Guard(() =>
    {
        if (__instance.DataGrid is { } grid) Ensure(P.Novels.ScenarioForGrid(grid.Name) ?? __instance.name, grid.Name);
    });
    static void Ensure(string scenario, string grid)
    {
        if (unavailableThisEntry.Contains(grid) || P.Novels.ForGrid(grid) != null) return;
        if (entryStart == 0) entryStart = System.Diagnostics.Stopwatch.GetTimestamp();
        var task = P.Novels.PrepareAsync(scenario);
        try
        {
            var ready = task.WaitAsync(Remaining).GetAwaiter().GetResult();
            if (ready == null || !ready.HasGrid(grid)) unavailableThisEntry.Add(grid);
        }
        catch (TimeoutException)
        {
            unavailableThisEntry.Add(grid);
            P.Log.LogWarning($"MM_NOVEL_DEADLINE scenario={scenario} grid={grid}; original commands for this entry");
        }
    }
    public static void BeforeCommands(AdvImportScenarioSheet __instance) => Guard(() => Apply(__instance));

    static void Apply(AdvImportScenarioSheet grid)
    {
        if (grid == null) return;
        string name = grid.Name;
        if (unavailableThisEntry.Contains(name)) return;
        if (P.Novels.ScenarioForGrid(name) is { } scene) Ensure(scene, name);
        if (unavailableThisEntry.Contains(name)) return;
        var package = P.Novels.ForGrid(name);
        if (package == null)
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
                    // Il2CppStringArray.set_Item in the installed interop writes a raw pointer
                    // without a GC write barrier. Use the native Array setter, as Master does.
                    var replacement = new Il2CppSystem.String(Il2CppInterop.Runtime.IL2CPP.ManagedStringToIl2Cpp(match.Translation!));
                    new Il2CppSystem.Array(cells.Pointer).SetValue(replacement, match.TextColumn);
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
