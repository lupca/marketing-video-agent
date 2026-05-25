import React, { useState, useMemo } from "react";
import { format } from "date-fns";
import { 
  Database, FileAudio, FileVideo, FileText, File, Loader2, 
  Download, ExternalLink, Trash2, Folder, ChevronRight, Play, 
  Edit3, FolderSymlink, Search, X, SlidersHorizontal, ChevronUp, ChevronDown
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

function getMinioDownloadUrl(s3Url: string): string {
  if (!s3Url) return "";
  return s3Url.replace("s3://", "http://localhost:9000/");
}

function getMinioBrowserUrl(s3Url: string): string {
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

  // Local state for search and advanced filters
  const [searchQuery, setSearchQuery] = useState("");
  const [isFiltersExpanded, setIsFiltersExpanded] = useState(false);
  const [filterFormat, setFilterFormat] = useState("all");
  const [filterSource, setFilterSource] = useState("all");
  const [filterSize, setFilterSize] = useState("all");
  const [filterDate, setFilterDate] = useState("all");

  // Local state for column sorting
  const [sortField, setSortField] = useState<'name' | 'type' | 'size' | 'created_at'>('created_at');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

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

  // Active filters count helper
  const activeFiltersCount = useMemo(() => {
    let count = 0;
    if (filterFormat !== "all") count++;
    if (filterSource !== "all") count++;
    if (filterSize !== "all") count++;
    if (filterDate !== "all") count++;
    return count;
  }, [filterFormat, filterSource, filterSize, filterDate]);

  const hasAnyFilterActive = searchQuery !== "" || activeFiltersCount > 0;

  const resetAllFilters = () => {
    setSearchQuery("");
    setFilterFormat("all");
    setFilterSource("all");
    setFilterSize("all");
    setFilterDate("all");
  };

  // Toggle sorting logic
  const handleSort = (field: 'name' | 'type' | 'size' | 'created_at') => {
    if (sortField === field) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection(field === 'created_at' ? 'desc' : 'asc');
    }
  };

  // Reset page when directory or filters change
  React.useEffect(() => {
    setCurrentPage(1);
  }, [currentFolderId, safeCurrentPath, searchQuery, filterFormat, filterSource, filterSize, filterDate]);

  // Merge folders and files with advanced filtering and sorting
  const allItems = useMemo(() => {
    // 1. Process Folders
    let filteredFolders: any[] = [];
    
    // If any advanced filter is active, folders are hidden
    const isAdvancedFilterActive = activeFiltersCount > 0;
    
    if (!isAdvancedFilterActive) {
      if (isDbMode) {
        let fList = [...currentFolders];
        if (searchQuery.trim() !== "") {
          const query = searchQuery.toLowerCase();
          fList = fList.filter(f => f.name.toLowerCase().includes(query));
        }
        
        // Sort folders
        fList.sort((a, b) => {
          let compareVal = 0;
          if (sortField === "name") {
            compareVal = a.name.localeCompare(b.name);
          } else if (sortField === "created_at") {
            compareVal = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
          } else {
            compareVal = a.name.localeCompare(b.name);
          }
          return sortDirection === "asc" ? compareVal : -compareVal;
        });
        
        filteredFolders = fList.map(f => ({ isFolder: true, folder: f, id: `folder-${f.id}` }));
      } else {
        let fList = [...virtualFolders];
        if (searchQuery.trim() !== "") {
          const query = searchQuery.toLowerCase();
          fList = fList.filter(name => name.toLowerCase().includes(query));
        }
        
        fList.sort((a, b) => {
          const compareVal = a.localeCompare(b);
          return sortDirection === "asc" ? compareVal : -compareVal;
        });
        
        filteredFolders = fList.map(name => ({ isFolder: true, name, id: `folder-${name}` }));
      }
    }

    // 2. Process Files
    let rawFiles = isDbMode ? [...assets] : [...virtualFiles];
    
    // Apply filters to files
    let filteredFilesList = rawFiles.filter(asset => {
      // Name Search query
      if (searchQuery.trim() !== "") {
        const query = searchQuery.toLowerCase();
        const dispName = (asset.display_name || asset.file_name).toLowerCase();
        const fName = asset.file_name.toLowerCase();
        if (!dispName.includes(query) && !fName.includes(query)) return false;
      }
      
      // Format Filter
      if (filterFormat !== "all") {
        const type = asset.asset_type;
        let matches = false;
        if (filterFormat === "video") matches = type === "video" || type === "clip";
        else if (filterFormat === "audio") matches = type === "audio" || type === "bgm" || type === "voiceover" || type === "voice";
        else if (filterFormat === "script") matches = type === "script" || type === "doc" || type === "subtitle";
        else if (filterFormat === "image") matches = type === "image";
        else matches = type === filterFormat;
        if (!matches) return false;
      }
      
      // Source Filter
      if (filterSource !== "all") {
        if (filterSource === "generated" && asset.source !== "generated") return false;
        if (filterSource === "uploaded" && asset.source !== "upload") return false;
      }
      
      // Size Filter
      if (filterSize !== "all") {
        const size = asset.file_size_bytes;
        if (filterSize === "small" && size >= 1024 * 1024) return false;
        if (filterSize === "medium" && (size < 1024 * 1024 || size > 10 * 1024 * 1024)) return false;
        if (filterSize === "large" && (size < 10 * 1024 * 1024 || size > 100 * 1024 * 1024)) return false;
        if (filterSize === "huge" && size <= 100 * 1024 * 1024) return false;
      }
      
      // Date Filter
      if (filterDate !== "all") {
        const now = new Date();
        const created = new Date(asset.created_at);
        const diffMs = now.getTime() - created.getTime();
        const diffDays = diffMs / (1000 * 60 * 60 * 24);
        if (filterDate === "24h" && diffDays > 1) return false;
        if (filterDate === "7d" && diffDays > 7) return false;
        if (filterDate === "30d" && diffDays > 30) return false;
      }
      
      return true;
    });

    // Sort files
    filteredFilesList.sort((a, b) => {
      let compareVal = 0;
      if (sortField === "name") {
        const nameA = (a.display_name || a.file_name).toLowerCase();
        const nameB = (b.display_name || b.file_name).toLowerCase();
        compareVal = nameA.localeCompare(nameB);
      } else if (sortField === "type") {
        compareVal = a.asset_type.localeCompare(b.asset_type);
      } else if (sortField === "size") {
        compareVal = a.file_size_bytes - b.file_size_bytes;
      } else if (sortField === "created_at") {
        compareVal = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      }
      return sortDirection === "asc" ? compareVal : -compareVal;
    });

    const mappedFiles = filteredFilesList.map(a => ({ isFolder: false, asset: a, id: a.id }));

    return [...filteredFolders, ...mappedFiles];
  }, [
    isDbMode,
    currentFolders,
    assets,
    virtualFolders,
    virtualFiles,
    searchQuery,
    filterFormat,
    filterSource,
    filterSize,
    filterDate,
    sortField,
    sortDirection,
    activeFiltersCount
  ]);

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

      {/* Premium Search and Filter Bar */}
      <div className="px-4 py-3 border-b border-white/10 flex flex-col gap-3 bg-[#0a0a09]/60 backdrop-blur-md z-10 sticky top-[38px] select-none">
        {/* Row 1: Search & Toggle Filter Button */}
        <div className="flex items-center justify-between gap-3 flex-wrap sm:flex-nowrap">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground/60" />
            <input 
              type="text" 
              placeholder="Search assets by name..." 
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full bg-white/5 border border-white/10 hover:border-white/20 focus:border-primary/50 text-white placeholder-muted-foreground/40 rounded-xl py-2 pl-10 pr-8 text-xs transition-all focus:outline-none focus:ring-1 focus:ring-primary/20"
            />
            {searchQuery && (
              <button 
                onClick={() => setSearchQuery("")} 
                className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 hover:text-white text-muted-foreground/60 transition-colors"
                title="Clear Search"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
          
          <div className="flex items-center gap-2 shrink-0">
            <button 
              onClick={() => setIsFiltersExpanded(!isFiltersExpanded)} 
              className={cn(
                "flex items-center gap-1.5 px-3.5 py-2 rounded-xl border transition-all text-xs font-semibold shadow-sm",
                isFiltersExpanded 
                  ? "bg-primary/25 text-primary border-primary/40 shadow-[0_0_15px_rgba(238,76,124,0.15)] hover:bg-primary/30" 
                  : "bg-white/5 text-white/80 hover:text-white border-white/10 hover:border-white/20"
              )}
            >
              <SlidersHorizontal className="w-3.5 h-3.5" />
              <span>Advanced Filters</span>
              {activeFiltersCount > 0 && (
                <span className="w-4 h-4 rounded-full bg-primary text-white text-[9px] flex items-center justify-center font-black animate-pulse">
                  {activeFiltersCount}
                </span>
              )}
            </button>
            
            {hasAnyFilterActive && (
              <button 
                onClick={resetAllFilters} 
                className="text-xs text-muted-foreground hover:text-primary transition-all underline decoration-dotted underline-offset-4 font-medium px-1"
              >
                Reset All
              </button>
            )}
          </div>
        </div>

        {/* Row 2: Advanced Collapsible Panel */}
        {isFiltersExpanded && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3 rounded-xl bg-black/40 border border-white/5 animate-in slide-in-from-top-2 duration-300">
            
            {/* Format Filter */}
            <div className="space-y-1">
              <label className="text-[9px] font-bold uppercase tracking-wider text-muted-foreground/60">Format</label>
              <select
                title="Format Filter"
                value={filterFormat}
                onChange={e => setFilterFormat(e.target.value)}
                className="w-full px-2 py-1.5 rounded-lg bg-white/5 border border-white/10 text-white text-xs font-medium focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer transition-colors hover:bg-white/10"
              >
                <option value="all" className="bg-[#121212]">All Formats</option>
                <option value="video" className="bg-[#121212]">Videos & Clips</option>
                <option value="image" className="bg-[#121212]">Images</option>
                <option value="audio" className="bg-[#121212]">Music & Voice</option>
                <option value="script" className="bg-[#121212]">Scripts & Subtitles</option>
              </select>
            </div>

            {/* Source Filter */}
            <div className="space-y-1">
              <label className="text-[9px] font-bold uppercase tracking-wider text-muted-foreground/60">Source</label>
              <select
                title="Source Filter"
                value={filterSource}
                onChange={e => setFilterSource(e.target.value)}
                className="w-full px-2 py-1.5 rounded-lg bg-white/5 border border-white/10 text-white text-xs font-medium focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer transition-colors hover:bg-white/10"
              >
                <option value="all" className="bg-[#121212]">All Sources</option>
                <option value="uploaded" className="bg-[#121212]">Uploaded Files</option>
                <option value="generated" className="bg-[#121212]">AI Generated ✨</option>
              </select>
            </div>

            {/* Size Filter */}
            <div className="space-y-1">
              <label className="text-[9px] font-bold uppercase tracking-wider text-muted-foreground/60">File Size</label>
              <select
                title="Size Filter"
                value={filterSize}
                onChange={e => setFilterSize(e.target.value)}
                className="w-full px-2 py-1.5 rounded-lg bg-white/5 border border-white/10 text-white text-xs font-medium focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer transition-colors hover:bg-white/10"
              >
                <option value="all" className="bg-[#121212]">Any Size</option>
                <option value="small" className="bg-[#121212]">Small (&lt; 1 MB)</option>
                <option value="medium" className="bg-[#121212]">Medium (1 MB - 10 MB)</option>
                <option value="large" className="bg-[#121212]">Large (10 MB - 100 MB)</option>
                <option value="huge" className="bg-[#121212]">Huge (&gt; 100 MB)</option>
              </select>
            </div>

            {/* Upload Date Filter */}
            <div className="space-y-1">
              <label className="text-[9px] font-bold uppercase tracking-wider text-muted-foreground/60">Upload Date</label>
              <select
                title="Upload Date Filter"
                value={filterDate}
                onChange={e => setFilterDate(e.target.value)}
                className="w-full px-2 py-1.5 rounded-lg bg-white/5 border border-white/10 text-white text-xs font-medium focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer transition-colors hover:bg-white/10"
              >
                <option value="all" className="bg-[#121212]">Any Time</option>
                <option value="24h" className="bg-[#121212]">Last 24 Hours</option>
                <option value="7d" className="bg-[#121212]">Last 7 Days</option>
                <option value="30d" className="bg-[#121212]">Last 30 Days</option>
              </select>
            </div>

          </div>
        )}
      </div>

      {/* Directory Table View */}
      <div className="w-full overflow-x-auto overflow-y-auto flex-1 custom-scrollbar">
        <table className="w-full text-sm text-left border-collapse">
          <thead className="bg-[#121212]/95 backdrop-blur-md text-xs uppercase text-muted-foreground border-b border-white/10 sticky top-0 z-10 select-none">
            <tr>
              {multiSelect && <th className="px-4 py-4 font-semibold tracking-wider w-10 text-center"></th>}
              <th 
                onClick={() => handleSort('name')}
                className="px-4 py-4 font-semibold tracking-wider cursor-pointer group hover:text-white transition-colors"
              >
                <div className="flex items-center">
                  <span>File Name</span>
                  {(() => {
                    const isActive = sortField === 'name';
                    if (!isActive) {
                      return (
                        <span className="inline-flex flex-col ml-1.5 opacity-30 group-hover:opacity-75 transition-opacity">
                          <ChevronUp className="w-2.5 h-2.5 -mb-0.5" />
                          <ChevronDown className="w-2.5 h-2.5" />
                        </span>
                      );
                    }
                    return (
                      <span className="inline-flex ml-1.5 text-primary">
                        {sortDirection === 'asc' ? (
                          <ChevronUp className="w-3.5 h-3.5 drop-shadow-[0_0_8px_rgba(238,76,124,0.5)]" />
                        ) : (
                          <ChevronDown className="w-3.5 h-3.5 drop-shadow-[0_0_8px_rgba(238,76,124,0.5)]" />
                        )}
                      </span>
                    );
                  })()}
                </div>
              </th>
              <th 
                onClick={() => handleSort('type')}
                className="px-4 py-4 font-semibold tracking-wider cursor-pointer group hover:text-white transition-colors hidden sm:table-cell"
              >
                <div className="flex items-center">
                  <span>Type</span>
                  {(() => {
                    const isActive = sortField === 'type';
                    if (!isActive) {
                      return (
                        <span className="inline-flex flex-col ml-1.5 opacity-30 group-hover:opacity-75 transition-opacity">
                          <ChevronUp className="w-2.5 h-2.5 -mb-0.5" />
                          <ChevronDown className="w-2.5 h-2.5" />
                        </span>
                      );
                    }
                    return (
                      <span className="inline-flex ml-1.5 text-primary">
                        {sortDirection === 'asc' ? (
                          <ChevronUp className="w-3.5 h-3.5 drop-shadow-[0_0_8px_rgba(238,76,124,0.5)]" />
                        ) : (
                          <ChevronDown className="w-3.5 h-3.5 drop-shadow-[0_0_8px_rgba(238,76,124,0.5)]" />
                        )}
                      </span>
                    );
                  })()}
                </div>
              </th>
              <th 
                onClick={() => handleSort('size')}
                className="px-4 py-4 font-semibold tracking-wider cursor-pointer group hover:text-white transition-colors hidden md:table-cell"
              >
                <div className="flex items-center">
                  <span>Size</span>
                  {(() => {
                    const isActive = sortField === 'size';
                    if (!isActive) {
                      return (
                        <span className="inline-flex flex-col ml-1.5 opacity-30 group-hover:opacity-75 transition-opacity">
                          <ChevronUp className="w-2.5 h-2.5 -mb-0.5" />
                          <ChevronDown className="w-2.5 h-2.5" />
                        </span>
                      );
                    }
                    return (
                      <span className="inline-flex ml-1.5 text-primary">
                        {sortDirection === 'asc' ? (
                          <ChevronUp className="w-3.5 h-3.5 drop-shadow-[0_0_8px_rgba(238,76,124,0.5)]" />
                        ) : (
                          <ChevronDown className="w-3.5 h-3.5 drop-shadow-[0_0_8px_rgba(238,76,124,0.5)]" />
                        )}
                      </span>
                    );
                  })()}
                </div>
              </th>
              <th 
                onClick={() => handleSort('created_at')}
                className="px-4 py-4 font-semibold tracking-wider cursor-pointer group hover:text-white transition-colors hidden lg:table-cell"
              >
                <div className="flex items-center">
                  <span>Created</span>
                  {(() => {
                    const isActive = sortField === 'created_at';
                    if (!isActive) {
                      return (
                        <span className="inline-flex flex-col ml-1.5 opacity-30 group-hover:opacity-75 transition-opacity">
                          <ChevronUp className="w-2.5 h-2.5 -mb-0.5" />
                          <ChevronDown className="w-2.5 h-2.5" />
                        </span>
                      );
                    }
                    return (
                      <span className="inline-flex ml-1.5 text-primary">
                        {sortDirection === 'asc' ? (
                          <ChevronUp className="w-3.5 h-3.5 drop-shadow-[0_0_8px_rgba(238,76,124,0.5)]" />
                        ) : (
                          <ChevronDown className="w-3.5 h-3.5 drop-shadow-[0_0_8px_rgba(238,76,124,0.5)]" />
                        )}
                      </span>
                    );
                  })()}
                </div>
              </th>
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
