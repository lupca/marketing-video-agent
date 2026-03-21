import { format } from "date-fns";
import { Database, FileAudio, FileVideo, FileText, File, Loader2, Download, ExternalLink, Trash2 } from "lucide-react";
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
}

export function AssetTable({ assets, loading, deletingId, onDelete, onUploadClick }: AssetTableProps) {
  return (
    <div className="glass-panel overflow-hidden animate-in fade-in slide-in-from-bottom-8 duration-700">
      <div className="w-full overflow-x-auto min-h-[400px]">
        <table className="w-full text-sm text-left">
          <thead className="bg-black/40 text-xs uppercase text-muted-foreground border-b border-white/10">
            <tr>
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
            ) : assets.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-24 text-center">
                  <div className="flex flex-col items-center justify-center gap-4 text-muted-foreground">
                    <div className="p-5 rounded-full bg-white/5">
                      <Database className="w-10 h-10 opacity-50" />
                    </div>
                    <div>
                      <p className="text-white font-medium mb-1">No assets found</p>
                      <p className="text-sm">Upload media to use in your video projects.</p>
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
              assets.map((asset) => (
                <tr key={asset.id} className="hover:bg-white/[0.02] transition-colors group">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="p-2.5 rounded-xl bg-white/5 border border-white/10 text-muted-foreground group-hover:text-primary group-hover:border-primary/30 transition-all">
                        {getAssetIcon(asset.asset_type)}
                      </div>
                      <div className="flex flex-col">
                        <span className="font-medium text-white line-clamp-1 max-w-[300px]" title={asset.file_name}>
                          {asset.file_name}
                        </span>
                        <span className="text-xs text-muted-foreground/50 mt-0.5">{asset.id.slice(0, 8)}...</span>
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
                      <a
                        href={getMinioDownloadUrl(asset.s3_url)}
                        target="_blank"
                        rel="noreferrer"
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
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
