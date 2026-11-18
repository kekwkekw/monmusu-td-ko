using System;
using System.IO;
using UnityEngine;
using UnityEditor;
using UnityEngine.TextCore.LowLevel;
using TMPro;
public static class UiFontBuilder {
 public static void Build() {
  var root=Directory.GetParent(Application.dataPath).FullName;
  var corpus=File.ReadAllText(Path.Combine(root,"corpus.txt"));
  var builds=new System.Collections.Generic.List<AssetBundleBuild>();
  foreach(var id in new[]{"RHR","Maple"}) {
   var src=AssetDatabase.LoadAssetAtPath<Font>("Assets/Fonts/"+id+".ttf");
   var a=TMP_FontAsset.CreateFontAsset(src,60,8,GlyphRenderMode.SDFAA,4096,4096,AtlasPopulationMode.Dynamic,false);
   a.name=id=="RHR"?"Monmusu_RHR_Bold_UI":"Monmusu_Maple_Bold_UI";
   string missing;
   if(!a.TryAddCharacters(corpus,out missing,false)) throw new Exception(id+" missing "+missing);
   if(a.atlasTextures.Length!=1)throw new Exception("Expected one atlas");
   a.atlasPopulationMode=AtlasPopulationMode.Static;
   a.normalStyle=0;a.boldStyle=0;
   string path="Assets/Baked/"+id+".asset";
   AssetDatabase.DeleteAsset(path);AssetDatabase.CreateAsset(a,path);
   AssetDatabase.AddObjectToAsset(a.material,a);
   foreach(var t in a.atlasTextures)AssetDatabase.AddObjectToAsset(t,a);
   var so=new SerializedObject(a);
   foreach(var prop in new[]{"m_SourceFontFile_EditorRef","m_SourceFontFile"}) {var p=so.FindProperty(prop);if(p!=null)p.objectReferenceValue=null;}
   so.ApplyModifiedPropertiesWithoutUndo();EditorUtility.SetDirty(a);AssetDatabase.SaveAssets();
   builds.Add(new AssetBundleBuild{assetBundleName=id.ToLowerInvariant()+"-bold-ui.bundle",assetNames=new[]{path}});
   Debug.Log("UI_FONT_BAKED "+a.name+" chars="+a.characterTable.Count+" point="+a.faceInfo.pointSize+" family="+a.faceInfo.familyName+" style="+a.faceInfo.styleName);
  }
  var output=Path.Combine(root,"../bundles");Directory.CreateDirectory(output);
  if(BuildPipeline.BuildAssetBundles(output,builds.ToArray(),BuildAssetBundleOptions.ChunkBasedCompression|BuildAssetBundleOptions.StrictMode,BuildTarget.StandaloneWindows64)==null)throw new Exception("BUILD_FAILED");
 }
}
