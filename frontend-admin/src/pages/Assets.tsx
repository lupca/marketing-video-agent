import { useState, useRef } from "react";
import { Database, UploadCloud, RefreshCw, Search, FolderPlus } from "lucide-react";
import { useAssets } from "../hooks/useAssets";
import { AssetTable } from "../components/features/assets/AssetTable";
import { Button } from "../components/ui/Button";

export default function Assets() {
  const [filterType, setFilterType] = useState<string>("all");
  const { assets, loading, refreshing, fetchAssets, deleteAsset, uploadAsset } = useAssets(filterType);
  const [currentPath, setCurrentPath] = useState<string>("");
  
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  const handleRefresh = () => fetchAssets(true);

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to permanently delete this asset?")) return;
    setDeletingId(id);
    try {
      await deleteAsset(id);
    } catch (err) {
      console.error(err);
      alert("Failed to delete asset");
    } finally {
      setDeletingId(null);
    }
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFolderUploadClick = () => {
    folderInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    let assetType = "doc";
    if (file.type.startsWith("video/")) assetType = "video";
    else if (file.type.startsWith("audio/")) assetType = "audio";
    else if (file.type.startsWith("text/")) assetType = "script";
    else if (file.name.endsWith(".srt") || file.name.endsWith(".vtt")) assetType = "script";
    else if (file.type.startsWith("image/")) assetType = "image";

    try {
      await uploadAsset(file, assetType, undefined, currentPath);
    } catch (err) {
      console.error(err);
      alert("Failed to upload asset");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleFolderChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setUploading(true);
    try {
      // Upload sequentially to avoid overloading MinIO and DB with too many simultaneous requests
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        let assetType = "doc";
        if (file.type.startsWith("video/")) assetType = "video";
        else if (file.type.startsWith("audio/")) assetType = "audio";
        else if (file.type.startsWith("text/")) assetType = "script";
        else if (file.name.endsWith(".srt") || file.name.endsWith(".vtt")) assetType = "script";
        else if (file.type.startsWith("image/")) assetType = "image";

        const pathParts = file.webkitRelativePath.split("/");
        pathParts.pop(); // remove file name
        let folderPath = pathParts.join("/");
        if (currentPath) {
          folderPath = currentPath + (currentPath.endsWith("/") ? "" : "/") + folderPath;
        }

        await uploadAsset(file, assetType, undefined, folderPath);
      }
    } catch (err) {
      console.error(err);
      alert("Failed to upload folder");
    } finally {
      setUploading(false);
      if (folderInputRef.current) folderInputRef.current.value = "";
    }
  };

  return (
    <div className="max-w-7xl mx-auto p-8 lg:p-12 space-y-10">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="space-y-2">
          <h2 className="text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60 flex items-center gap-3">
            <Database className="w-8 h-8 text-primary" /> Asset Library
          </h2>
          <p className="text-muted-foreground text-lg">
            Manage your raw S3 media files, scripts, and video renders.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="relative mr-2">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <select
              title="Filter Assets"
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="pl-9 pr-8 py-2 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all appearance-none cursor-pointer"
            >
              <option value="all" className="bg-[#1A1A24]">All Media</option>
              <option value="video" className="bg-[#1A1A24]">Videos</option>
              <option value="clip" className="bg-[#1A1A24]">Segment Clips</option>
              <option value="voiceover" className="bg-[#1A1A24]">Voiceovers</option>
              <option value="bgm" className="bg-[#1A1A24]">Music & SFX</option>
              <option value="script" className="bg-[#1A1A24]">Scripts</option>
            </select>
          </div>

          <Button onClick={handleRefresh} variant="secondary" isLoading={refreshing} size="icon">
            {!refreshing && <RefreshCw className="w-4 h-4" />}
          </Button>
          
          <Button
            onClick={handleFolderUploadClick}
            disabled={uploading}
            isLoading={uploading}
            variant="secondary"
            className="pr-6 pl-4"
          >
            {!uploading && <FolderPlus className="w-4 h-4 mr-2" />}
            Folder
          </Button>

          <Button
            onClick={handleUploadClick}
            disabled={uploading}
            isLoading={uploading}
            className="glowing-button pr-6 pl-4"
          >
            {!uploading && <UploadCloud className="w-4 h-4 mr-2" />}
            File
          </Button>
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            className="hidden"
            title="Upload Media"
          />
          <input
            type="file"
            ref={folderInputRef}
            onChange={handleFolderChange}
            className="hidden"
            title="Upload Folder"
            // @ts-ignore
            webkitdirectory="true"
            directory="true"
          />
        </div>
      </div>

      <AssetTable
        assets={assets}
        loading={loading}
        deletingId={deletingId}
        onDelete={handleDelete}
        onUploadClick={handleUploadClick}
        currentPath={currentPath}
        setCurrentPath={setCurrentPath}
      />
    </div>
  );
}
