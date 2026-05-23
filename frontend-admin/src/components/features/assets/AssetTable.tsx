import React, { useState, useMemo } from "react";
import { format } from "date-fns";
import { 
  Database, FileAudio, FileVideo, FileText, File, Loader2, 
  Download, ExternalLink, Trash2, Folder, ChevronRight, Play, 
  Edit3, FolderSymlink 
} from "lucide-react";
import { cn } from "../../../lib/utils";
import type { Asset, Folder as FolderType } from "../../../hooks/useAssets";
import { Pagination } from "../../ui/Pagination";

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
  folders?: FolderType[]; // Optional for backward compatibility (Modals)
  currentFolderId?: string | null; // Optional for backward compatibility (Modals)
  setCurrentFolderId?: (id: string | null) => void; // Optional for backward compatibility (Modals)
  loading: boolean;
  deletingId: string | null;
  onDeleteAsset?: (id: string) => void; // Optional
  onDeleteFolder?: (id: string) => void; // Optional
  onRenameAsset?: (id: string, newName: string) => Promise<any>; // Optional
  onRenameFolder?: (id: string, newName: string) => Promise<any>; // Optional
  onOpenMoveModal?: (item: { type: "file" | "folder"; id: string; name: string; parent_id?: string | null; folder_id?: string | null }) => void; // Optional
  onUploadClick: () => void;
  onCreateFolderClick?: () => void; // Optional
  
  // Backward compatibility selectors
  onDelete?: (id: string) => void;
  currentPath?: string;
  setCurrentPath?: (path: string) => void;
  onSelectAsset?: (asset: Asset) => void;
  multiSelect?: boolean;
  selectedAssets?: Asset[];
  onToggleAsset?: (asset: Asset) => void;
}

export function AssetTable({
  assets,
  folders,
  currentFolderId,
  setCurrentFolderId,
  loading,
  deletingId,
  onDeleteAsset,
  onDeleteFolder,
  onRenameAsset,
  onRenameFolder,
  onOpenMoveModal,
  onUploadClick,
  onCreateFolderClick,
  onDelete,
  currentPath,
  setCurrentPath,
  onSelectAsset,
  multiSelect = false,
  selectedAssets = [],
  onToggleAsset
}: AssetTableProps) {
  // Local state for inline renaming
  const [renamingItemId, setRenamingItemId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [savingRename, setSavingRename] = useState(false);

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);

  // Determine if we are running in DB-backed folders mode or Virtual path fallback mode
  const isDbMode = folders !== undefined;
  
  const safeFolders = folders || [];
  const safeCurrentFolderId = currentFolderId !== undefined ? currentFolderId : null;
  const safeCurrentPath = currentPath !== undefined ? currentPath : "";
  
  const safeSetCurrentFolderId = setCurrentFolderId || (() => {});
  const safeSetCurrentPath = setCurrentPath || (() => {});
  
  const normalizedPath = useMemo(() => 
    safeCurrentPath && !safeCurrentPath.endsWith("/") ? safeCurrentPath + "/" : safeCurrentPath,
  [safeCurrentPath]);

  // Fallback Mode (Virtual Slices): Parse directories in memory
  const { virtualFolders, virtualFiles } = useMemo(() => {
    if (isDbMode) return { virtualFolders: [], virtualFiles: [] };
    
    const folderSet = new Set<string>();
    const fileList: Asset[] = [];

    assets.forEach(asset => {
      const pathValue = asset.full_path || asset.file_name;
      // Filter files by active subpath
      if (normalizedPath && !pathValue.startsWith(normalizedPath)) return;

      const relativePath = normalizedPath ? pathValue.slice(normalizedPath.length) : pathValue;
      const parts = relativePath.split("/");

      if (parts.length > 1) {
        folderSet.add(parts[0]);
      } else if (parts.length === 1 && parts[0] !== "") {
        fileList.push(asset);
      }
    });

    return { virtualFolders: Array.from(folderSet).sort(), virtualFiles: fileList };
  }, [assets, normalizedPath, isDbMode]);

  // DB Mode: Filter folders directly
  const currentFolders = useMemo(() => {
    if (!isDbMode) return [];
    return safeFolders
      .filter(f => f.parent_id === safeCurrentFolderId)
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [safeFolders, safeCurrentFolderId, isDbMode]);

  // DB Mode breadcrumbs
  const dbBreadcrumbs = useMemo(() => {
    if (!isDbMode) return [];
    const list: Array<{ id: string | null; name: string }> = [];
    let currId = safeCurrentFolderId;
    while (currId) {
      const folder = safeFolders.find(f => f.id === currId);
      if (folder) {
        list.unshift({ id: folder.id, name: folder.name });
        currId = folder.parent_id || null;
      } else {
        break;
      }
    }
    return list;
  }, [safeCurrentFolderId, safeFolders, isDbMode]);

  // Virtual breadcrumbs list
  const virtualBreadcrumbs = safeCurrentPath.split("/").filter(Boolean);

  // Reset page when directory changes
  React.useEffect(() => {
    setCurrentPage(1);
  }, [currentFolderId, safeCurrentPath]);

  // Merge folders and files
  const allItems = useMemo(() => {
    if (isDbMode) {
      const folderItems = currentFolders.map(f => ({ isFolder: true, folder: f, id: `folder-${f.id}` }));
      const fileItems = assets.map(a => ({ isFolder: false, asset: a, id: a.id }));
      return [...folderItems, ...fileItems];
    } else {
      const folderItems = virtualFolders.map(f => ({ isFolder: true, name: f, id: `folder-${f}` }));
      const fileItems = virtualFiles.map(f => ({ isFolder: false, asset: f, id: f.id }));
      return [...folderItems, ...fileItems];
    }
  }, [isDbMode, currentFolders, assets, virtualFolders, virtualFiles]);

  const paginatedItems = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    const end = currentPage * itemsPerPage;
    return allItems.slice(start, end);
  }, [allItems, currentPage, itemsPerPage]);

  const handleStartRename = (id: string, currentName: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setRenamingItemId(id);
    setRenameValue(currentName);
  };

  const handleSaveRename = async (id: string, isFolder: boolean) => {
    if (!renameValue.trim()) return;
    setSavingRename(true);
    try {
      if (isFolder) {
        if (onRenameFolder) await onRenameFolder(id, renameValue.trim());
      } else {
        if (onRenameAsset) await onRenameAsset(id, renameValue.trim());
      }
      setRenamingItemId(null);
    } catch (err) {
      alert("Failed to rename");
    } finally {
      setSavingRename(false);
    }
  };

  return (
    <div className="glass-panel overflow-hidden animate-in fade-in slide-in-from-bottom-8 duration-700 flex flex-col max-h-[70vh]">
      
      {/* Dynamic Breadcrumbs Nav */}
      <div className="px-4 py-3 flex items-center gap-1.5 border-b border-white/10 text-xs overflow-x-auto whitespace-nowrap sticky top-0 z-20 bg-[#0a0a09]/95 backdrop-blur-md">
        {isDbMode ? (
          <React.Fragment>
            <button
              onClick={() => safeSetCurrentFolderId(null)}
              className={cn(
                "text-muted-foreground hover:text-white transition-colors",
                safeCurrentFolderId === null ? "text-white font-semibold" : ""
              )}
            >
              My Files
            </button>
            {dbBreadcrumbs.map((crumb, idx) => (
              <React.Fragment key={crumb.id}>
                <ChevronRight className="w-3.5 h-3.5 text-muted-foreground/30" />
                <button
                  onClick={() => safeSetCurrentFolderId(crumb.id)}
                  className={cn(
                    "text-muted-foreground hover:text-white transition-colors",
                    idx === dbBreadcrumbs.length - 1 ? "text-white font-semibold" : ""
                  )}
                >
                  {crumb.name}
                </button>
              </React.Fragment>
            ))}
          </React.Fragment>
        ) : (
          <React.Fragment>
            <button
              onClick={() => safeSetCurrentPath("")}
              className={cn(
                "text-muted-foreground hover:text-white transition-colors",
                safeCurrentPath === "" ? "text-white font-semibold" : ""
              )}
            >
              Home
            </button>
            {virtualBreadcrumbs.map((crumb, idx) => {
              const path = virtualBreadcrumbs.slice(0, idx + 1).join("/") + "/";
              return (
                <React.Fragment key={path}>
                  <ChevronRight className="w-3.5 h-3.5 text-muted-foreground/30" />
                  <button
                    onClick={() => safeSetCurrentPath(path)}
                    className={cn(
                      "text-muted-foreground hover:text-white transition-colors",
                      idx === virtualBreadcrumbs.length - 1 ? "text-white font-semibold" : ""
                    )}
                  >
                    {crumb}
                  </button>
                </React.Fragment>
              );
            })}
          </React.Fragment>
        )}
      </div>

      {/* Directory Table View */}
      <div className="w-full overflow-x-auto overflow-y-auto flex-1 custom-scrollbar">
        <table className="w-full text-sm text-left border-collapse">
          <thead className="bg-[#121212]/95 backdrop-blur-md text-xs uppercase text-muted-foreground border-b border-white/10 sticky top-0 z-10">
            <tr>
              {multiSelect && <th className="px-4 py-4 font-semibold tracking-wider w-10 text-center"></th>}
              <th className="px-4 py-4 font-semibold tracking-wider">File Name</th>
              <th className="px-4 py-4 font-semibold tracking-wider hidden sm:table-cell">Type</th>
              <th className="px-4 py-4 font-semibold tracking-wider hidden md:table-cell">Size</th>
              <th className="px-4 py-4 font-semibold tracking-wider hidden lg:table-cell">Created</th>
              <th className="px-4 py-4 font-semibold tracking-wider text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5 text-white/90">
            {loading && allItems.length === 0 ? (
              <tr>
                <td colSpan={multiSelect ? 6 : 5} className="px-4 py-16 text-center text-muted-foreground">
                  <Loader2 className="w-7 h-7 animate-spin mx-auto mb-3 text-primary" />
                  Loading items...
                </td>
              </tr>
            ) : allItems.length === 0 ? (
              <tr>
                <td colSpan={multiSelect ? 6 : 5} className="px-4 py-20 text-center">
                  <div className="flex flex-col items-center justify-center gap-3 text-muted-foreground">
                    <div className="p-4 rounded-full bg-white/5">
                      <Database className="w-8 h-8 opacity-40" />
                    </div>
                    <div>
                      <p className="text-white font-medium text-sm">Folder is empty</p>
                      <p className="text-xs">No folders or files found here.</p>
                    </div>
                    {isDbMode && (
                      <div className="flex items-center gap-2 mt-2">
                        {onCreateFolderClick && (
                          <button
                            onClick={onCreateFolderClick}
                            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg border border-white/10 hover:border-primary text-white hover:text-primary transition-all bg-white/5"
                          >
                            <Folder className="w-3.5 h-3.5" /> New Folder
                          </button>
                        )}
                        <button
                          onClick={onUploadClick}
                          className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg bg-primary text-black hover:bg-primary/80 transition-all font-semibold"
                        >
                          Upload File
                        </button>
                      </div>
                    )}
                  </div>
                </td>
              </tr>
            ) : (
              paginatedItems.map(item => {
                if (item.isFolder) {
                  // DB Mode folder vs Virtual Mode folder
                  const folderId = isDbMode ? item.folder!.id : `virtual-${item.name}`;
                  const folderName = isDbMode ? item.folder!.name : item.name!;
                  const isJobFolder = isDbMode ? item.folder!.is_job_folder : false;
                  
                  const isRenaming = renamingItemId === folderId;
                  const isDeleting = deletingId === folderId;

                  return (
                    <tr 
                      key={`folder-${folderId}`} 
                      className="hover:bg-white/[0.015] transition-colors group cursor-pointer" 
                      onClick={() => {
                        if (isRenaming) return;
                        if (isDbMode) {
                          safeSetCurrentFolderId(item.folder!.id);
                        } else {
                          safeSetCurrentPath(normalizedPath + item.name + "/");
                        }
                      }}
                    >
                      {multiSelect && <td className="px-4 py-3.5"></td>}
                      <td className="px-4 py-3.5">
                        <div className="flex items-center gap-2.5">
                          <div className={cn(
                            "p-2 rounded-xl border transition-all",
                            isJobFolder 
                              ? "bg-amber-500/10 border-amber-500/20 text-amber-400 group-hover:text-amber-300"
                              : "bg-indigo-500/10 border-indigo-500/20 text-indigo-400 group-hover:text-indigo-300"
                          )}>
                            <Folder className="w-4 h-4 fill-current/10" />
                          </div>

                          {isRenaming ? (
                            <div className="flex items-center gap-1.5" onClick={e => e.stopPropagation()}>
                              <input
                                type="text"
                                value={renameValue}
                                onChange={e => setRenameValue(e.target.value)}
                                className="px-2 py-0.5 rounded bg-[#121212] border border-white/20 text-white text-xs focus:outline-none focus:ring-1 focus:ring-primary w-36"
                                autoFocus
                                onKeyDown={e => {
                                  if (e.key === "Enter") handleSaveRename(folderId, true);
                                  if (e.key === "Escape") setRenamingItemId(null);
                                }}
                              />
                              <button
                                onClick={() => handleSaveRename(folderId, true)}
                                disabled={savingRename}
                                className="text-[11px] text-primary font-semibold hover:text-white"
                              >
                                {savingRename ? "Saving..." : "Save"}
                              </button>
                            </div>
                          ) : (
                            <div className="flex flex-col min-w-0">
                              <span className="font-semibold text-white group-hover:text-primary transition-all truncate text-sm">
                                {folderName}
                              </span>
                              {isJobFolder && (
                                <span className="text-[9px] text-amber-400/60 mt-0.5 font-normal">
                                  AI Output Project
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3.5 whitespace-nowrap hidden sm:table-cell text-xs">
                        <span className={cn(
                          "inline-flex items-center px-2 py-0.5 rounded border text-[10px] font-semibold uppercase tracking-wider text-muted-foreground bg-white/5 border-white/10",
                          isJobFolder && "bg-amber-500/5 border-amber-500/15 text-amber-300"
                        )}>
                          {isJobFolder ? "Project Folder" : "Folder"}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 whitespace-nowrap hidden md:table-cell text-muted-foreground font-mono text-xs">--</td>
                      <td className="px-4 py-3.5 whitespace-nowrap hidden lg:table-cell text-muted-foreground text-xs">
                        {isDbMode && item.folder!.created_at ? format(new Date(item.folder!.created_at), "MMM dd, yyyy") : "--"}
                      </td>
                      <td className="px-4 py-3.5 whitespace-nowrap text-right" onClick={e => e.stopPropagation()}>
                        {isDbMode ? (
                          <div className="flex items-center justify-end gap-1.5 opacity-50 group-hover:opacity-100 transition-opacity">
                            <button
                              onClick={(e) => handleStartRename(folderId, folderName, e)}
                              className="p-1.5 rounded-lg hover:bg-white/5 text-muted-foreground hover:text-white transition-colors"
                              title="Rename"
                            >
                              <Edit3 className="h-3.5 w-3.5" />
                            </button>
                            {onOpenMoveModal && (
                              <button
                                onClick={() => onOpenMoveModal({ type: "folder", id: folderId, name: folderName, parent_id: item.folder!.parent_id })}
                                className="p-1.5 rounded-lg hover:bg-white/5 text-muted-foreground hover:text-white transition-colors"
                                title="Move Folder"
                              >
                                <FolderSymlink className="h-3.5 w-3.5" />
                              </button>
                            )}
                            {onDeleteFolder && (
                              <button
                                onClick={() => {
                                  if (confirm(`Are you sure you want to permanently delete "${folderName}" and ALL its content?`)) {
                                    onDeleteFolder(folderId);
                                  }
                                }}
                                disabled={isDeleting}
                                className="p-1.5 rounded-lg hover:bg-rose-500/10 text-muted-foreground hover:text-rose-400 transition-colors disabled:opacity-50"
                                title="Delete"
                              >
                                {isDeleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                              </button>
                            )}
                          </div>
                        ) : (
                          <span className="text-xs text-muted-foreground italic">Virtual Directory</span>
                        )}
                      </td>
                    </tr>
                  );
                } else {
                  const asset = item.asset!;
                  const isRenaming = renamingItemId === asset.id;
                  const isDeleting = deletingId === asset.id;
                  const displayNameValue = asset.display_name || asset.file_name;
                  const isSelected = selectedAssets.some(a => a.id === asset.id);

                  return (
                    <tr 
                      key={asset.id} 
                      className={cn(
                        "hover:bg-white/[0.015] transition-colors group",
                        multiSelect ? "cursor-pointer bg-primary/[0.01]" : "",
                        isSelected ? "bg-primary/[0.04] border-l-2 border-primary/60" : ""
                      )}
                      onClick={(e) => {
                        if (multiSelect && onToggleAsset) {
                          e.stopPropagation();
                          onToggleAsset(asset);
                        }
                      }}
                    >
                      {multiSelect && (
                        <td className="px-4 py-3.5">
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
                      <td className="px-4 py-3.5">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <div className="p-2 rounded-xl bg-white/5 border border-white/10 text-muted-foreground group-hover:text-primary group-hover:border-primary/20 transition-all shrink-0">
                            {getAssetIcon(asset.asset_type, "w-4 h-4")}
                          </div>
                          
                          {isRenaming ? (
                            <div className="flex items-center gap-1.5" onClick={e => e.stopPropagation()}>
                              <input
                                type="text"
                                value={renameValue}
                                onChange={e => setRenameValue(e.target.value)}
                                className="px-2 py-0.5 rounded bg-[#121212] border border-white/20 text-white text-xs focus:outline-none focus:ring-1 focus:ring-primary w-40"
                                autoFocus
                                onKeyDown={e => {
                                  if (e.key === "Enter") handleSaveRename(asset.id, false);
                                  if (e.key === "Escape") setRenamingItemId(null);
                                }}
                              />
                              <button
                                onClick={() => handleSaveRename(asset.id, false)}
                                disabled={savingRename}
                                className="text-[11px] text-primary font-semibold hover:text-white"
                              >
                                {savingRename ? "Saving..." : "Save"}
                              </button>
                            </div>
                          ) : (
                            <div className="flex flex-col min-w-0">
                              <div className="flex items-center gap-1.5">
                                <span className="font-semibold text-white max-w-[200px] sm:max-w-[280px] md:max-w-[340px] truncate text-sm" title={displayNameValue}>
                                  {displayNameValue}
                                </span>
                                {asset.source === "generated" && (
                                  <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-primary/20 text-primary border border-primary/30 text-[8px] font-bold tracking-wide shrink-0 scale-95 shadow-[0_0_10px_rgba(238,76,124,0.15)]">
                                    ✨ AI
                                  </span>
                                )}
                              </div>
                              <span className="text-[9px] text-muted-foreground/30 mt-0.5 font-mono">
                                {asset.id.slice(0, 8)}
                              </span>
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3.5 whitespace-nowrap hidden sm:table-cell">
                        <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-white/5 border border-white/10 text-[10px] font-bold capitalize tracking-wide text-indigo-300">
                          {asset.asset_type}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 whitespace-nowrap hidden md:table-cell text-muted-foreground font-mono text-xs">
                        {formatBytes(asset.file_size_bytes)}
                      </td>
                      <td className="px-4 py-3.5 whitespace-nowrap hidden lg:table-cell text-muted-foreground text-xs">
                        {format(new Date(asset.created_at), "MMM dd, yyyy HH:mm")}
                      </td>
                      <td className="px-4 py-3.5 whitespace-nowrap text-right" onClick={e => e.stopPropagation()}>
                        <div className="flex items-center justify-end gap-1.5 opacity-55 group-hover:opacity-100 transition-opacity">
                          
                          {/* Selection Button inside modal */}
                          {onSelectAsset && (
                            <button
                              onClick={(e) => { e.stopPropagation(); onSelectAsset(asset); }}
                              className="px-2.5 py-1 rounded-lg bg-primary/20 text-primary border border-primary/30 hover:bg-primary/30 transition-colors text-xs font-semibold mr-1.5"
                            >
                              Select
                            </button>
                          )}

                          {asset.presigned_url && (asset.asset_type === "video" || asset.asset_type === "audio" || asset.asset_type === "image") && (
                            <a
                              href={asset.presigned_url}
                              target="_blank"
                              rel="noreferrer"
                              className="p-1.5 rounded-lg hover:bg-emerald-500/10 text-muted-foreground hover:text-emerald-400 transition-colors"
                              title="View Preview"
                            >
                              <Play className="h-3.5 w-3.5" />
                            </a>
                          )}
                          <a
                            href={asset.presigned_url || getMinioDownloadUrl(asset.s3_url)}
                            target="_blank"
                            rel="noreferrer"
                            download
                            className="p-1.5 rounded-lg hover:bg-white/5 text-muted-foreground hover:text-white transition-colors"
                            title="Download File"
                          >
                            <Download className="h-3.5 w-3.5" />
                          </a>
                          
                          {/* Regular File Actions (only enabled in full DB mode) */}
                          {isDbMode && (
                            <>
                              <button
                                onClick={(e) => handleStartRename(asset.id, displayNameValue, e)}
                                className="p-1.5 rounded-lg hover:bg-white/5 text-muted-foreground hover:text-white transition-colors"
                                title="Rename"
                              >
                                <Edit3 className="h-3.5 w-3.5" />
                              </button>
                              {onOpenMoveModal && (
                                <button
                                  onClick={() => onOpenMoveModal({ type: "file", id: asset.id, name: displayNameValue, folder_id: asset.folder_id })}
                                  className="p-1.5 rounded-lg hover:bg-white/5 text-muted-foreground hover:text-white transition-colors"
                                  title="Move File"
                                >
                                  <FolderSymlink className="h-3.5 w-3.5" />
                                </button>
                              )}
                            </>
                          )}

                          <a
                            href={getMinioBrowserUrl(asset.s3_url)}
                            target="_blank"
                            rel="noreferrer"
                            className="p-1.5 rounded-lg hover:bg-white/5 text-muted-foreground hover:text-white transition-colors"
                            title="Open S3 Console"
                          >
                            <ExternalLink className="h-3.5 w-3.5" />
                          </a>

                          {(onDeleteAsset || onDelete) && (
                            <>
                              <div className="w-px h-3.5 bg-white/10 mx-0.5"></div>
                              <button
                                onClick={() => {
                                  if (confirm(`Are you sure you want to permanently delete this asset file?`)) {
                                    if (onDeleteAsset) onDeleteAsset(asset.id);
                                    else if (onDelete) onDelete(asset.id);
                                  }
                                }}
                                disabled={isDeleting}
                                className="p-1.5 rounded-lg hover:bg-rose-500/10 text-muted-foreground hover:text-rose-400 transition-colors disabled:opacity-50"
                                title="Delete"
                              >
                                {isDeleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                }
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      {allItems.length > 0 && (
        <div className="p-3 border-t border-white/10 bg-black/25">
          <Pagination
            currentPage={currentPage}
            totalItems={allItems.length}
            itemsPerPage={itemsPerPage}
            onPageChange={setCurrentPage}
            onItemsPerPageChange={setItemsPerPage}
          />
        </div>
      )}
    </div>
  );
}
