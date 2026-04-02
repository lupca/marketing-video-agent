import React from "react";
import { format } from "date-fns";
import { Database, FileAudio, FileVideo, FileText, File, Loader2, Download, ExternalLink, Trash2, Folder, ChevronRight, Play } from "lucide-react";
import { cn } from "../../../lib/utils";
import type { Asset } from "../../../hooks/useAssets";

export function formatBytes(bytes: number, decimals = 2) {
  if (!+bytes) return '0 Bytes';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

export function getMinioDownloadUrl(s3Url: string): string {
  if (!s3Url) return "";
  return s3Url.replace("s3://", "http://localhost:9000/");
}

export function getMinioBrowserUrl(s3Url: string): string {
  if (!s3Url) return "";
  return s3Url.replace("s3://", "http://localhost:9001/browser/");
}

export const getAssetIcon = (type: string, className: string = "w-5 h-5") => {
  switch (type) {
    case "video":
    case "clip":
      return <FileVideo className={className} />;
    case "voiceover":
    case "bgm":
    case "audio":
      return <FileAudio className={className} />;
    case "script":
      return <FileText className={className} />;
    default:
      return <File className={className} />;
  }
};

interface AssetTableProps {
  assets: Asset[];
  loading: boolean;
  deletingId: string | null;
  onDelete: (id: string) => void;
  onUploadClick: () => void;
  currentPath: string;
  setCurrentPath: (path: string) => void;
  onSelectAsset?: (asset: Asset) => void;
  multiSelect?: boolean;
  selectedAssets?: Asset[];
  onToggleAsset?: (asset: Asset) => void;
}

export function AssetTable({ assets, loading, deletingId, onDelete, onUploadClick, currentPath, setCurrentPath, onSelectAsset, multiSelect = false, selectedAssets = [], onToggleAsset }: AssetTableProps) {
  // Ensure currentPath is normalized (e.g. always ends with slash if not empty)
  const normalizedPath = React.useMemo(() => 
    currentPath && !currentPath.endsWith("/") ? currentPath + "/" : currentPath,
  [currentPath]);

  const { folders, files } = React.useMemo(() => {
    const folderSet = new Set<string>();
    const fileList: Asset[] = [];

    assets.forEach(asset => {
      const pathValue = asset.full_path || asset.file_name;
      // If we are in a subpath, only show files that start with it
      if (normalizedPath && !pathValue.startsWith(normalizedPath)) return;

      const relativePath = normalizedPath ? pathValue.slice(normalizedPath.length) : pathValue;
      const parts = relativePath.split("/");

      if (parts.length > 1) {
        folderSet.add(parts[0]);
      } else if (parts.length === 1 && parts[0] !== "") {
        fileList.push(asset);
      }
    });

    return { folders: Array.from(folderSet).sort(), files: fileList };
  }, [assets, normalizedPath]);

  const breadcrumbs = currentPath.split("/").filter(Boolean);

  return (
    <div className="glass-panel overflow-hidden animate-in fade-in slide-in-from-bottom-8 duration-700 flex flex-col max-h-[70vh]">
      <div className="px-6 py-4 flex items-center gap-2 border-b border-white/10 text-sm overflow-x-auto whitespace-nowrap sticky top-0 z-20 bg-[#0a0a09]/95 backdrop-blur-md">
        <button
          onClick={() => setCurrentPath("")}
          className="text-muted-foreground hover:text-white transition-colors"
        >
          Home
        </button>
        {breadcrumbs.map((crumb, idx) => {
          const path = breadcrumbs.slice(0, idx + 1).join("/") + "/";
          return (
            <React.Fragment key={path}>
              <ChevronRight className="w-4 h-4 text-muted-foreground/50" />
              <button
                onClick={() => setCurrentPath(path)}
                className="text-muted-foreground hover:text-white transition-colors"
              >
                {crumb}
              </button>
            </React.Fragment>
          );
        })}
      </div>
      <div className="w-full overflow-x-auto overflow-y-auto flex-1">
        <table className="w-full text-sm text-left border-collapse">
          <thead className="bg-[#121212]/95 backdrop-blur-md text-xs uppercase text-muted-foreground border-b border-white/10 sticky top-0 z-10 transition-colors">
            <tr>
              {multiSelect && <th className="px-6 py-5 font-semibold tracking-wider w-12 text-center"></th>}
              <th className="px-6 py-5 font-semibold tracking-wider">File Name</th>
              <th className="px-6 py-5 font-semibold tracking-wider">Type</th>
              <th className="px-6 py-5 font-semibold tracking-wider">Size</th>
              <th className="px-6 py-5 font-semibold tracking-wider">Uploaded</th>
              <th className="px-6 py-5 font-semibold tracking-wider text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5 text-white/90">
            {loading && assets.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-20 text-center text-muted-foreground">
                  <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-primary" />
                  Fetching assets from S3...
                </td>
              </tr>
            ) : folders.length === 0 && files.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-24 text-center">
                  <div className="flex flex-col items-center justify-center gap-4 text-muted-foreground">
                    <div className="p-5 rounded-full bg-white/5">
                      <Database className="w-10 h-10 opacity-50" />
                    </div>
                    <div>
                      <p className="text-white font-medium mb-1">No assets found</p>
                      <p className="text-sm">Upload media or folders to use in your video projects.</p>
                    </div>
                    <button
                      onClick={onUploadClick}
                      className="mt-2 text-sm text-primary hover:text-white transition-colors underline underline-offset-4"
                    >
                      Upload a file now
                    </button>
                  </div>
                </td>
              </tr>
            ) : (
              <React.Fragment>
                {/* Render Folders */}
                {folders.map(folder => (
                  <tr key={`folder-${folder}`} className="hover:bg-white/[0.02] transition-colors group cursor-pointer" onClick={() => setCurrentPath(normalizedPath + folder + "/")}>
                    {multiSelect && <td className="px-6 py-4"></td>}
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="p-2.5 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 group-hover:text-indigo-300 group-hover:border-indigo-400/30 transition-all">
                          <Folder className="w-5 h-5 fill-indigo-500/20" />
                        </div>
                        <span className="font-medium text-white">{folder}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="inline-flex items-center px-2.5 py-1 rounded-md bg-white/5 border border-white/10 text-xs font-semibold capitalize tracking-wide text-muted-foreground">
                        Folder
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-muted-foreground font-mono text-xs">--</td>
                    <td className="px-6 py-4 whitespace-nowrap text-muted-foreground text-xs">--</td>
                    <td className="px-6 py-4 whitespace-nowrap text-right"></td>
                  </tr>
                ))}

                {/* Render Files */}
                {files.map((asset) => {
                  const isSelected = selectedAssets.some(a => a.id === asset.id);
                  return (
                    <tr key={asset.id} className={cn("hover:bg-white/[0.02] transition-colors group", multiSelect ? "cursor-pointer" : "", isSelected ? "bg-primary/5" : "")} onClick={(e) => {
                      if (multiSelect && onToggleAsset) {
                        e.stopPropagation();
                        onToggleAsset(asset);
                      }
                    }}>
                      {multiSelect && (
                        <td className="px-6 py-4">
                          <div className="flex items-center justify-center">
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={(e) => {
                                e.stopPropagation();
                                if (onToggleAsset) onToggleAsset(asset);
                              }}
                              className="w-4 h-4 rounded border-white/20 bg-black/40 text-primary focus:ring-primary/50 cursor-pointer appearance-none checked:bg-primary checked:border-primary relative
                            before:content-[''] before:absolute before:inset-0 before:bg-[url('data:image/svg+xml;base64,PHN2ZyB2aWV3Qm94PSIwIDAgMjQgMjQiIGZpbGw9Im5vbmUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iNCIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjxwb2x5bGluZSBwb2ludHM9IjIwIDYgOSAxNyA0IDEyIj48L3BvbHlsaW5lPjwvc3ZnPg==')] 
                            before:bg-no-repeat before:bg-center before:bg-[length:80%] before:opacity-0 checked:before:opacity-100 transition-all"
                            />
                          </div>
                        </td>
                      )}
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className="p-2.5 rounded-xl bg-white/5 border border-white/10 text-muted-foreground group-hover:text-primary group-hover:border-primary/30 transition-all">
                            {getAssetIcon(asset.asset_type)}
                          </div>
                          <div className="flex flex-col">
                            <span className="font-medium text-white line-clamp-1 max-w-[300px]" title={normalizedPath ? (asset.full_path || asset.file_name).slice(normalizedPath.length) : (asset.full_path || asset.file_name)}>
                              {normalizedPath ? (asset.full_path || asset.file_name).slice(normalizedPath.length) : (asset.full_path || asset.file_name)}
                            </span>
                            <span className="text-xs text-muted-foreground/50 mt-0.5" title={asset.id}>{asset.id.slice(0, 8)}...</span>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className="inline-flex items-center px-2.5 py-1 rounded-md bg-white/5 border border-white/10 text-xs font-semibold capitalize tracking-wide text-indigo-300">
                          {asset.asset_type}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-muted-foreground font-mono text-xs">
                        {formatBytes(asset.file_size_bytes)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-muted-foreground text-xs">
                        {format(new Date(asset.created_at), "MMM dd, yyyy HH:mm")}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right">
                        <div className="flex items-center justify-end gap-2 opacity-50 group-hover:opacity-100 transition-opacity">
                          {onSelectAsset && (
                            <button
                              onClick={(e) => { e.stopPropagation(); onSelectAsset(asset); }}
                              className="px-3 py-1.5 rounded-lg bg-primary/20 text-primary border border-primary/30 hover:bg-primary/30 transition-colors text-xs font-medium mr-2"
                            >
                              Select
                            </button>
                          )}
                          {asset.presigned_url && (asset.asset_type === "video" || asset.asset_type === "audio" || asset.asset_type === "image") && (
                            <a
                              href={asset.presigned_url}
                              target="_blank"
                              rel="noreferrer"
                              className="p-2 rounded-lg hover:bg-emerald-500/10 text-muted-foreground hover:text-emerald-400 transition-colors"
                              title="View Media"
                            >
                              <Play className="h-4 w-4" />
                            </a>
                          )}

                          <a
                            href={asset.presigned_url || getMinioDownloadUrl(asset.s3_url)}
                            target="_blank"
                            rel="noreferrer"
                            download
                            className="p-2 rounded-lg hover:bg-emerald-500/10 text-muted-foreground hover:text-emerald-400 transition-colors"
                            title="Download Asset"
                          >
                            <Download className="h-4 w-4" />
                          </a>
                          <a
                            href={getMinioBrowserUrl(asset.s3_url)}
                            target="_blank"
                            rel="noreferrer"
                            className="p-2 rounded-lg hover:bg-blue-500/10 text-muted-foreground hover:text-blue-400 transition-colors"
                            title="View S3 URL"
                          >
                            <ExternalLink className="h-4 w-4" />
                          </a>
                          <div className="w-px h-4 bg-white/10 mx-1"></div>
                          <button
                            onClick={() => onDelete(asset.id)}
                            disabled={deletingId === asset.id}
                            className="p-2 rounded-lg hover:bg-rose-500/10 text-muted-foreground hover:text-rose-400 transition-colors disabled:opacity-50"
                            title="Delete permanently"
                          >
                            {deletingId === asset.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </React.Fragment>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
