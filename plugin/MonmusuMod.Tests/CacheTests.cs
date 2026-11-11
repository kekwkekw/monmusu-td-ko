using System.Net;
using System.Text.Json.Nodes;
using MonmusuMod.Core;

static class CacheTests
{
    public static int Run(string fixture)
    {
        int passed = 0;
        void Check(bool ok, string why) { if (!ok) throw new Exception(why); }
        void Test(string name, Action action) { action(); passed++; Console.WriteLine("PASS " + name); }
        var uri = new Uri("https://unit.invalid/");
        string cache = Path.Combine(fixture, "lazy-cache");
        var originalManifest = File.ReadAllBytes(Path.Combine(fixture, "manifest.json"));
        var originalNovel = File.ReadAllBytes(Path.Combine(fixture, "novels/test.json"));
        var payload = new Dictionary<string, byte[]>(StringComparer.Ordinal)
        {
            ["manifest.json"] = originalManifest, ["names.json"] = File.ReadAllBytes(Path.Combine(fixture, "names.json")),
            ["novels/test.json"] = originalNovel
        };
        using var handler = new CountingHandler(payload);
        using var client = new HttpClient(handler);
        TranslationPackage Refresh(CancellationToken token = default) => PackageCache.RefreshAsync(client, uri, cache, token).GetAwaiter().GetResult();
        NovelSession Session(TranslationPackage p, TimeSpan? timeout = null) => new(p,
            (e,t) => PackageCache.ReadFileAsync(e,p.RootDirectory,cache,client,uri,t), _ => {}, timeout);
        var common = Refresh();
        string scene = common.Manifest.Scenarios.Single().ScenarioName!;
        string grid = "exact-grid ";
        string pointer = File.ReadAllText(Path.Combine(cache,"active.txt"));
        Test("Cold startup requests common files only; 0 Novel rows loaded", () =>
            Check(handler.Requests.SequenceEqual(new[]{"manifest.json","names.json"}) && common.RowCount == 0, "startup eagerly loaded novels"));
        var session = Session(common);
        Test("Concurrent scene loads share one request; repeated entry uses memory", () =>
        {
            var tasks = Enumerable.Range(0,16).Select(_ => session.PrepareAsync(scene)).ToArray();
            Task.WhenAll(tasks).GetAwaiter().GetResult();
            Check(tasks.All(t => t.Result?.RowCount == 3) && handler.Requests.Count(p=>p=="novels/test.json")==1, "not single flight");
            session.PrepareAsync(scene).GetAwaiter().GetResult();
            Check(handler.Requests.Count(p=>p=="novels/test.json")==1 && session.ForGrid(grid)?.RowCount == 3, "repeat downloaded");
        });
        Test("Same manifest restart only fetches manifest, reuses directory and disk Novel", () =>
        {
            handler.Requests.Clear();
            var next = Refresh();
            Check(next.Identity == common.Identity && handler.Requests.SequenceEqual(new[]{"manifest.json"}), "unchanged data downloaded");
            Check(Directory.GetDirectories(Path.Combine(cache,"versions")).Length == 1 &&
                File.ReadAllText(Path.Combine(cache,"active.txt")) == pointer, "duplicate generation directory");
            Check(Session(next).PrepareAsync(scene).GetAwaiter().GetResult()?.RowCount == 3 && handler.Requests.Count==1, "disk novel not reused");
        });
        var novel = JsonNode.Parse(originalNovel)!;
        novel["rows"]![0]!["ko"] = "<b>변경</b>\n$NAME";
        var changedNovel = System.Text.Encoding.UTF8.GetBytes(novel.ToJsonString());
        var manifest = JsonNode.Parse(originalManifest)!;
        manifest["scenarios"]![0]!["sha256"] = TranslationPackage.Hash(changedNovel);
        manifest["scenarios"]![0]!["grid_names"] = new JsonArray(grid);
        payload["manifest.json"] = System.Text.Encoding.UTF8.GetBytes(manifest.ToJsonString());
        payload["novels/test.json"] = changedNovel;
        TranslationPackage nextGeneration = null!;
        Test("Changed Novel stays lazy, common hashes reused, old session remains pinned", () =>
        {
            handler.Requests.Clear(); nextGeneration = Refresh();
            Check(handler.Requests.SequenceEqual(new[]{"manifest.json"}) && nextGeneration.Identity != common.Identity, "changed novel fetched at startup");
            var next = Session(nextGeneration);
            Check(next.ScenarioForGrid(grid)==scene && next.ScenarioForGrid(grid.Trim())==null, "non-exact routing");
            Check(next.PrepareAsync(scene).GetAwaiter().GetResult()?.RowCount==3 && handler.Requests.Count==2, "new novel not fetched once");
            Check(session.Common.Identity == common.Identity && session.ForGrid(grid)!.Identity == common.Identity, "active generation changed");
        });
        Test("Broken local and object cache repaired by verified download", () =>
        {
            var entry = nextGeneration.Manifest.Scenarios.Single();
            File.WriteAllText(TranslationPackage.ResolvePath(nextGeneration.RootDirectory,entry.Path),"broken");
            File.WriteAllText(Path.Combine(cache,"objects",entry.Sha256),"broken");
            handler.Requests.Clear();
            Check(Session(nextGeneration).PrepareAsync(scene).GetAwaiter().GetResult()?.RowCount==3 &&
                handler.Requests.SequenceEqual(new[]{entry.Path}), "repair failed");
        });
        Test("Late transport cancellation preserves pointer and leaves no temporary files", () =>
        {
            string prior = File.ReadAllText(Path.Combine(cache,"active.txt"));
            handler.DelayMs=250;
            handler.Requests.Clear();
            using var cts = new CancellationTokenSource(30);
            var timer=System.Diagnostics.Stopwatch.StartNew();
            bool canceled=false;
            try { Refresh(cts.Token); } catch(OperationCanceledException) {canceled=true;}
            Check(canceled && timer.ElapsedMilliseconds<200, "startup cancellation not bounded");
            Thread.Sleep(280);
            handler.DelayMs=0;
            Check(File.ReadAllText(Path.Combine(cache,"active.txt"))==prior &&
                !Directory.EnumerateFiles(cache,"*.tmp",SearchOption.AllDirectories).Any(), "late publication / temporary leak");
        });
        Test("Changed Names with invalid hash cannot publish a mixed generation", () =>
        {
            string prior=File.ReadAllText(Path.Combine(cache,"active.txt"));
            var broken=JsonNode.Parse(payload["manifest.json"])!;
            broken["names"]!["sha256"]=new string('b',64);
            payload["manifest.json"]=System.Text.Encoding.UTF8.GetBytes(broken.ToJsonString());
            bool rejected=false;
            try {Refresh();} catch(InvalidDataException){rejected=true;}
            Check(rejected && File.ReadAllText(Path.Combine(cache,"active.txt"))==prior, "invalid names published");
            payload["manifest.json"]=System.Text.Encoding.UTF8.GetBytes(manifest.ToJsonString());
        });
        Test("New policy with previous row policy fails closed without old-scene fallback", () =>
        {
            var other=JsonNode.Parse(payload["manifest.json"])!;
            other["policy_sha256"]=new string('c',64);
            payload["manifest.json"]=System.Text.Encoding.UTF8.GetBytes(other.ToJsonString());
            var generation=Refresh();
            var rejected=Session(generation);
            Check(rejected.PrepareAsync(scene).GetAwaiter().GetResult()==null && rejected.ForGrid(grid)==null &&
                rejected.LoadedCount==0, "row policy mixed with generation");
            payload["manifest.json"]=System.Text.Encoding.UTF8.GetBytes(manifest.ToJsonString());
        });
        Test("Scene failure suppression and hard timeout discard late result", () =>
        {
            int requests=0;
            var slow=new NovelSession(common,async (_,_)=>{Interlocked.Increment(ref requests);await Task.Delay(150);return originalNovel;},_=>{},TimeSpan.FromMilliseconds(20));
            Check(slow.PrepareAsync(scene).GetAwaiter().GetResult()==null,"late scene accepted");
            Check(slow.PrepareAsync(scene).GetAwaiter().GetResult()==null && requests==1,"failed request storm");
            Thread.Sleep(170);
            Check(slow.LoadedCount==0 && slow.ForGrid(grid)==null,"late scene published");
        });
        Test("Ambiguous aliases rejected, partial-review unused header not routable", () =>
        {
            var broken=JsonNode.Parse(originalManifest)!;
            var second=JsonNode.Parse(broken["scenarios"]![0]!.ToJsonString())!;
            broken["scenarios"]![0]!["grid_names"]=new JsonArray(grid);
            second["grid_names"]=new JsonArray(grid);second["scenario_name"]="other";second["path"]="novels/other.json";
            broken["scenarios"]!.AsArray().Add(second);
            bool rejected=false;
            try{TranslationPackage.ReadManifest(System.Text.Encoding.UTF8.GetBytes(broken.ToJsonString()));}catch(InvalidDataException){rejected=true;}
            Check(rejected,"ambiguous alias accepted");
            var doc=JsonNode.Parse(originalNovel)!;
            var extra=JsonNode.Parse(doc["headers"]![0]!.ToJsonString())!;extra["grid_index"]=1;extra["grid_name"]="unused";
            doc["headers"]!.AsArray().Add(extra);
            var data=System.Text.Encoding.UTF8.GetBytes(doc.ToJsonString());
            var entry=common.Manifest.Scenarios.Single();
            string old=entry.Sha256;
            entry.Sha256=TranslationPackage.Hash(data);entry.GridNames=new(){grid};
            var partial=common.WithNovel(entry,data);
            Check(!partial.HasGrid("unused") && partial.HasGrid(grid),"unused header exposed");
            entry.Sha256=old;entry.GridNames=null;
        });
        Test("Offline old manifest reads no Novel until requested, invalid pointer falls back", () =>
        {
            File.WriteAllText(Path.Combine(cache,"active.txt"),"../invalid");
            var offline=PackageCache.LoadPreferred(fixture,cache,_=>{},false);
            Check(offline.RowCount==0,"offline eager parsing");
            var s=new NovelSession(offline,(e,t)=>PackageCache.ReadFileAsync(e,fixture,cache,null,null,t),_=>{});
            Check(s.PrepareAsync(scene).GetAwaiter().GetResult()?.RowCount==3,"legacy manifest unsupported");
        });
        return passed;
    }
    sealed class CountingHandler : HttpMessageHandler
    {
        readonly Dictionary<string,byte[]> files;
        public CountingHandler(Dictionary<string,byte[]> files) => this.files=files;
        public List<string> Requests {get;}=new();
        public int DelayMs;
        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request,CancellationToken token)
        {
            string path=Uri.UnescapeDataString(request.RequestUri!.AbsolutePath.TrimStart('/'));
            lock(Requests) Requests.Add(path);
            if(DelayMs>0) await Task.Delay(DelayMs); // intentionally ignores cancellation
            return new HttpResponseMessage(HttpStatusCode.OK){Content=new ByteArrayContent(files[path])};
        }
    }
}
