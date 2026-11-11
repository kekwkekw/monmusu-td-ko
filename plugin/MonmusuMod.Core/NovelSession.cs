namespace MonmusuMod.Core;

// Common data stays on one generation for the lifetime of the game.
public sealed class NovelSession
{
    readonly object gate = new();
    readonly Dictionary<string, FileEntry> entries;
    readonly Dictionary<string, string> gridOwners = new(StringComparer.Ordinal);
    readonly HashSet<string> ambiguous = new(StringComparer.Ordinal);
    readonly Dictionary<string, Task<TranslationPackage?>> pending = new(StringComparer.Ordinal);
    readonly Dictionary<string, DateTimeOffset> retryAfter = new(StringComparer.Ordinal);
    readonly Dictionary<string, TranslationPackage> loaded = new(StringComparer.Ordinal);
    readonly Func<FileEntry, CancellationToken, Task<byte[]>> read;
    readonly Action<string> log;
    readonly TimeSpan timeout;
    public TranslationPackage Common { get; }
    public int LoadedCount { get { lock (gate) return loaded.Count; } }
    public NovelSession(TranslationPackage common, Func<FileEntry, CancellationToken, Task<byte[]>> read,
        Action<string> log, TimeSpan? timeout = null)
    {
        Common = common; this.read = read; this.log = log;
        this.timeout = timeout ?? TimeSpan.FromSeconds(10);
        entries = common.Manifest.Scenarios.ToDictionary(e => e.ScenarioName!, StringComparer.Ordinal);
        foreach (var e in entries.Values)
            foreach (string grid in e.GridNames ?? new List<string>()) gridOwners.Add(grid, e.ScenarioName!);
    }
    public string? ScenarioForGrid(string grid)
    {
        lock (gate) return !ambiguous.Contains(grid) && gridOwners.TryGetValue(grid, out var name) ? name : null;
    }
    public TranslationPackage? ForGrid(string grid)
    {
        lock (gate) return !ambiguous.Contains(grid) && gridOwners.TryGetValue(grid, out var name) &&
            loaded.TryGetValue(name, out var package) && package.HasGrid(grid) ? package : null;
    }
    public Task<TranslationPackage?> PrepareAsync(string scenario)
    {
        lock (gate)
        {
            if (loaded.TryGetValue(scenario, out var package)) return Task.FromResult<TranslationPackage?>(package);
            if (!entries.TryGetValue(scenario, out var entry)) return Task.FromResult<TranslationPackage?>(null);
            if (pending.TryGetValue(scenario, out var task) && !task.IsCompleted) return task;
            if (retryAfter.TryGetValue(scenario, out var until) && DateTimeOffset.UtcNow < until) return Task.FromResult<TranslationPackage?>(null);
            return pending[scenario] = Task.Run(() => LoadAsync(entry));
        }
    }
    async Task<TranslationPackage?> LoadAsync(FileEntry entry)
    {
        string name = entry.ScenarioName!;
        using var cts = new CancellationTokenSource(timeout);
        try
        {
            var bytes = await read(entry, cts.Token).WaitAsync(cts.Token).ConfigureAwait(false);
            var package = Common.WithNovel(entry, bytes);
            cts.Token.ThrowIfCancellationRequested();
            lock (gate)
            {
                foreach (string grid in package.GridNames)
                    if (ambiguous.Contains(grid) || gridOwners.TryGetValue(grid, out var owner) && owner != name)
                    {
                        ambiguous.Add(grid);
                        throw new InvalidDataException("Conflicting grid owner: " + grid);
                    }
                foreach (string grid in package.GridNames) gridOwners[grid] = name;
                loaded[name] = package;
            }
            log($"MM_NOVEL_READY scenario={name} rows={package.RowCount} generation={Common.Identity}");
            return package;
        }
        catch (Exception ex)
        {
            lock (gate) retryAfter[name] = DateTimeOffset.UtcNow.AddSeconds(30);
            log($"MM_NOVEL_FAILED scenario={name} generation={Common.Identity} reason={ex.Message}");
            return null;
        }
    }
}
