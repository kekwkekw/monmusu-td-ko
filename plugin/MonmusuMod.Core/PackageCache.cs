using System.Net.Http;

namespace MonmusuMod.Core;

public static class PackageCache
{
    public static TranslationPackage LoadPreferred(string bundledRoot, string cacheRoot, Action<string> warning)
    {
        var pointer = Path.Combine(cacheRoot, "active.txt");
        if (File.Exists(pointer))
        {
            try
            {
                var name = File.ReadAllText(pointer).Trim();
                return TranslationPackage.Load(TranslationPackage.ResolvePath(cacheRoot, "versions/" + name));
            }
            catch (Exception ex) { warning("Cached package rejected: " + ex.Message); }
        }
        return TranslationPackage.Load(bundledRoot);
    }

    // A complete, validated version is published by a single pointer replacement.
    // Interrupted downloads never replace the current package; no Unity objects are used here.
    public static async Task<TranslationPackage> RefreshAsync(HttpClient client, Uri baseUri, string cacheRoot, CancellationToken token)
    {
        if (!baseUri.IsAbsoluteUri || baseUri.Scheme != "https" && !(baseUri.Scheme == "http" && baseUri.IsLoopback))
            throw new ArgumentException("CDN base must be HTTPS (HTTP is allowed only for a local test server)");
        if (!string.IsNullOrEmpty(baseUri.Query) || !string.IsNullOrEmpty(baseUri.Fragment)) throw new ArgumentException("CDN base must be a directory URL");
        baseUri = new Uri(baseUri.AbsoluteUri.TrimEnd('/') + "/");
        byte[] manifestBytes = await client.GetByteArrayAsync(new Uri(baseUri, "manifest.json"), token).ConfigureAwait(false);
        var manifest = TranslationPackage.ReadManifest(manifestBytes);
        string version = TranslationPackage.Hash(manifestBytes) + "-" + Guid.NewGuid().ToString("N");
        string folder = Path.Combine(cacheRoot, "versions", version);
        Directory.CreateDirectory(folder);
        foreach (var file in manifest.Files)
        {
            byte[] data = await client.GetByteArrayAsync(new Uri(baseUri, file.Path), token).ConfigureAwait(false);
            if (TranslationPackage.Hash(data) != file.Sha256) throw new InvalidDataException("CDN checksum mismatch: " + file.Path);
            string path = TranslationPackage.ResolvePath(folder, file.Path);
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            await File.WriteAllBytesAsync(path, data, token).ConfigureAwait(false);
        }
        await File.WriteAllBytesAsync(Path.Combine(folder, "manifest.json"), manifestBytes, token).ConfigureAwait(false);
        var package = TranslationPackage.Load(folder);
        string temporary = Path.Combine(cacheRoot, "active-" + Guid.NewGuid().ToString("N") + ".tmp");
        await File.WriteAllTextAsync(temporary, version, token).ConfigureAwait(false);
        token.ThrowIfCancellationRequested();
        File.Move(temporary, Path.Combine(cacheRoot, "active.txt"), true);
        return package;
    }
}
