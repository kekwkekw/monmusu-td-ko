# Image replacement references

The MonmusuMod image integration refers to the user's local GCMod Candidate implementation:

- `GCMod.Patches/ImagePatch.cs`: UI component reference replacement, overrideSprite handling, object cache and main-thread PNG loading.
- `GCMod.Services/ImageCatalog.cs`: content-addressed image descriptors and PNG validation.
- `GCMod.Services/ImageCache.cs`: validated cache publication and separation of downloads from Unity object creation.

MonmusuMod adds context and original texture selectors and uses its existing complete-package cache for publication. It does not import GCMod's fixed catalog limits or patch Unity AssetBundle getters. The corresponding upstream and local MIT notices are retained here.
