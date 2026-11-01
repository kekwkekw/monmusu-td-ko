using Il2CppInterop.Runtime;
using Il2CppInterop.Runtime.InteropTypes.Arrays;
using Il2CppSystem.Reflection;
using MonmusuMod.Core;
using UnityEngine;

namespace MonmusuMod;

internal static class MasterHooks
{
    [ThreadStatic] static bool applying;
    static readonly HashSet<string> warned = new(StringComparer.Ordinal);
    public static void AssetReady(UnityEngine.Object? __result)
    {
        if (applying || __result == null || Plugin.Instance.Package == null) return;
        try
        {
            applying = true;
            var value = new Il2CppSystem.Object(__result.Pointer);
            string name = __result.name;
            string className = value.GetIl2CppType().FullName;
            var translations = Plugin.Instance.Package.MasterUi;
            if (!translations.HasMaster(name, className)) return;
            int count = translations.ApplyMaster(name, className, new NativeNode(value), field =>
            {
                if (warned.Add(name + ":" + field)) Plugin.Instance.Log.LogWarning($"MM_MASTER_FIELD_MISSING table={name} field={field}");
            });
            if (count > 0) Plugin.Instance.Log.LogInfo($"MM_MASTER_APPLIED table={name} class={className} fields={count}");
        }
        catch (Exception ex) { Plugin.Instance.Log.LogWarning("MM_MASTER_FAILED: " + ex); }
        finally { applying = false; }
    }
    public static void AssetsReady(Il2CppReferenceArray<UnityEngine.Object>? __result)
    {
        if (__result == null) return;
        foreach (var asset in __result) AssetReady(asset);
    }

    // Reflection runs only over manifest-selected fields on exact typed master
    // assets. Strings are assigned through IL2CPP FieldInfo (GC write barrier).
    sealed class NativeNode : IMasterNode
    {
        readonly Il2CppSystem.Object value;
        readonly Action<Il2CppSystem.Object>? replace;
        public NativeNode(Il2CppSystem.Object value, Action<Il2CppSystem.Object>? replace = null)
            => (this.value, this.replace) = (value, replace);
        public IMasterNode? Field(string name)
        {
            var type = value.GetIl2CppType();
            var field = type.GetField(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            if (field == null) return null;
            var child = field.GetValue(value);
            if (child == null) return null;
            return new NativeNode(child, next =>
            {
                field.SetValue(value, next);
                if (type.IsValueType) replace?.Invoke(value);
            });
        }
        public IEnumerable<IMasterNode>? Elements()
        {
            if (!value.GetIl2CppType().IsArray) return null;
            var array = new Il2CppSystem.Array(value.Pointer);
            var nodes = new List<IMasterNode>();
            for (int index = 0; index < array.Length; index++)
            {
                int at = index;
                var child = array.GetValue(index);
                if (child != null) nodes.Add(new NativeNode(child, next => array.SetValue(next, at)));
            }
            return nodes;
        }
        public string? Text
        {
            get => value.GetIl2CppType().FullName == "System.String" ? value.ToString() : null;
            set
            {
                if (value == null || replace == null) throw new InvalidOperationException("Master string is not assignable");
                replace(new Il2CppSystem.String(IL2CPP.ManagedStringToIl2Cpp(value)));
            }
        }
    }
}
