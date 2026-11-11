using System.Collections.Concurrent;
using System.Net.Http;

namespace MonmusuMod.Core;

public static class PackageCache
{
    static readonly ConcurrentDictionary<string, SemaphoreSlim> locks = new(StringComparer.Ordinal);
    public static TranslationPackage LoadPreferred(string bundledRoot, string cacheRoot, Action<string> warning, bool includeNovels = true)
    {
        var pointer = Path.Combine(cacheRoot, "active.txt");
        if (File.Exists(pointer))
        {
            try
            {
                var name = File.ReadAllText(pointer).Trim();
                return TranslationPackage.Load(TranslationPackage.ResolvePath(cacheRoot, "versions/" + name), includeNovels);
            }
            catch (Exception ex) { warning("Cached package rejected: " + ex.Message); }
        }
        return TranslationPackage.Load(bundledRoot, includeNovels);
    }
    public static Uri ValidateBase(Uri uri)
    {
        if (!uri.IsAbsoluteUri || uri.Scheme != "https" && !(uri.Scheme == "http" && uri.IsLoopback))
            throw new ArgumentException("CDN base must be HTTPS (HTTP only for local tests)");
        if (!string.IsNullOrEmpty(uri.Query) || !string.IsNullOrEmpty(uri.Fragment)) throw new ArgumentException("CDN base must be a directory URL");
        return new Uri(uri.AbsoluteUri.TrimEnd('/') + "/");
    }
    static Uri Remote(Uri baseUri, string path) => new(baseUri, string.Join("/", path.Split('/').Select(Uri.EscapeDataString)));

    static async Task AtomicWrite(string path, byte[] bytes, CancellationToken token)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        string temporary = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
        try
        {
            await File.WriteAllBytesAsync(temporary, bytes, token).ConfigureAwait(false);
            token.ThrowIfCancellationRequested();
            File.Move(temporary, path, true);
        }
        finally { if (File.Exists(temporary)) File.Delete(temporary); }
    }
    static async Task<byte[]?> ValidLocal(string path, string hash, CancellationToken token)
    {
        try
        {
            if (!File.Exists(path)) return null;
            byte[] bytes = await File.ReadAllBytesAsync(path, token).ConfigureAwait(false);
            return TranslationPackage.Hash(bytes) == hash ? bytes : null;
        }
        catch (IOException) { return null; }
    }
    public static async Task<byte[]> ReadFileAsync(FileEntry entry, string selectedRoot, string cacheRoot,
        HttpClient? client, Uri? baseUri, CancellationToken token, Action<string>? log = null, string? bundledRoot = null)
    {
        string local = TranslationPackage.ResolvePath(selectedRoot, entry.Path);
        var bytes = await ValidLocal(local, entry.Sha256, token).ConfigureAwait(false);
        if (bytes != null) { log?.Invoke("MM_CACHE_HIT path=" + entry.Path); return bytes; }
        if (client == null || baseUri == null) throw new InvalidDataException("Missing/corrupt local payload: " + entry.Path);
        string blob = Path.Combine(cacheRoot, "objects", entry.Sha256);
        var gate = locks.GetOrAdd(Path.GetFullPath(blob), _ => new SemaphoreSlim(1, 1));
        await gate.WaitAsync(token).ConfigureAwait(false);
        try
        {
            bytes = await ValidLocal(blob, entry.Sha256, token).ConfigureAwait(false);
            if (bytes == null)
            {
                // Import old GUID-version caches on demand, without reading Novel bodies at boot.
                var roots = new List<string>();
                if (bundledRoot != null) roots.Add(bundledRoot);
                string versions = Path.Combine(cacheRoot, "versions");
                if (Directory.Exists(versions)) roots.AddRange(Directory.EnumerateDirectories(versions));
                foreach (string root in roots)
                {
                    token.ThrowIfCancellationRequested();
                    bytes = await ValidLocal(TranslationPackage.ResolvePath(root, entry.Path), entry.Sha256, token).ConfigureAwait(false);
                    if (bytes != null) break;
                }
            }
            if (bytes == null)
            {
                log?.Invoke("MM_CDN_REQUEST path=" + entry.Path);
                bytes = await client.GetByteArrayAsync(Remote(ValidateBase(baseUri), entry.Path), token).WaitAsync(token).ConfigureAwait(false);
                if (TranslationPackage.Hash(bytes) != entry.Sha256) throw new InvalidDataException("CDN checksum mismatch: " + entry.Path);
            }
            else log?.Invoke("MM_CACHE_REUSE path=" + entry.Path);
            token.ThrowIfCancellationRequested();
            await AtomicWrite(blob, bytes, token).ConfigureAwait(false);
            await AtomicWrite(local, bytes, token).ConfigureAwait(false);
            return bytes;
        }
        finally { gate.Release(); }
    }
    // Common files commit a generation. Each scene is independently validated on entry.
    public static async Task<TranslationPackage> RefreshAsync(HttpClient client, Uri baseUri, string cacheRoot,
        CancellationToken token, Action<string>? log = null, string? bundledRoot = null)
    {
        baseUri = ValidateBase(baseUri);
        log?.Invoke("MM_CDN_REQUEST path=manifest.json");
        byte[] bytes = await client.GetByteArrayAsync(new Uri(baseUri, "manifest.json"), token).WaitAsync(token).ConfigureAwait(false);
        var manifest = TranslationPackage.ReadManifest(bytes);
        string version = TranslationPackage.Hash(bytes);
        string folder = Path.Combine(cacheRoot, "versions", version);
        await Task.WhenAll(manifest.StartupFiles.Select(entry => ReadFileAsync(entry, folder, cacheRoot, client, baseUri, token, log, bundledRoot))).ConfigureAwait(false);
        await AtomicWrite(Path.Combine(folder, "manifest.json"), bytes, token).ConfigureAwait(false);
        var package = TranslationPackage.Load(folder, includeNovels: false);
        token.ThrowIfCancellationRequested();
        await AtomicWrite(Path.Combine(cacheRoot, "active.txt"), System.Text.Encoding.UTF8.GetBytes(version), token).ConfigureAwait(false);
        return package;
    }
}
