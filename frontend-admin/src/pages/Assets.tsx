import { useEffect, useState, useRef } from "react"
import api from "../lib/api"
import { format } from "date-fns"
import { Database, UploadCloud, RefreshCw, Trash2, FileAudio, FileVideo, FileText, File, Loader2, Download, ExternalLink, Search } from "lucide-react"
import { cn } from "../lib/utils"

interface Asset {
  id: string
  asset_type: string
  file_name: string
  file_size_bytes: number
  s3_url: string
  mime_type: string
  created_at: string
}

function formatBytes(bytes: number, decimals = 2) {
  if (!+bytes) return '0 Bytes'
  const k = 1024
  const dm = decimals < 0 ? 0 : decimals
  const sizes = ['Bytes', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`
}

function getMinioDownloadUrl(s3Url: string): string {
  if (!s3Url) return ""
  return s3Url.replace("s3://", "http://localhost:9000/")
}

function getMinioBrowserUrl(s3Url: string): string {
  if (!s3Url) return ""
  return s3Url.replace("s3://", "http://localhost:9001/browser/")
}

const getAssetIcon = (type: string, className: string = "w-5 h-5") => {
  switch (type) {
    case "video":
    case "clip":
      return <FileVideo className={className} />
    case "voiceover":
    case "bgm":
    case "audio":
      return <FileAudio className={className} />
    case "script":
      return <FileText className={className} />
    default:
      return <File className={className} />
  }
}

export default function Assets() {
  const [assets, setAssets] = useState<Asset[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [filterType, setFilterType] = useState<string>("all")

  const fetchAssets = async () => {
    try {
      const url = filterType === "all" ? "/api/assets" : `/api/assets?asset_type=${filterType}`
      const res = await api.get(url)
      setAssets(res.data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  const handleRefresh = () => {
    setRefreshing(true)
    fetchAssets()
  }

  useEffect(() => {
    fetchAssets()
  }, [filterType])

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to permanently delete this asset?")) return
    setDeletingId(id)
    try {
      await api.delete(`/api/assets/${id}`)
      setAssets(assets.filter(a => a.id !== id))
    } catch (err) {
      console.error(err)
      alert("Failed to delete asset")
    } finally {
      setDeletingId(null)
    }
  }

  const handleUploadClick = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    const formData = new FormData()
    formData.append("file", file)
    
    // Auto detect type
    let assetType = "doc"
    if (file.type.startsWith("video/")) assetType = "video"
    else if (file.type.startsWith("audio/")) assetType = "audio"
    else if (file.type.startsWith("text/")) assetType = "script"
    else if (file.name.endsWith(".srt") || file.name.endsWith(".vtt")) assetType = "script"
    
    formData.append("asset_type", assetType)

    try {
      const res = await api.post("/api/assets/upload", formData)
      setAssets([res.data, ...assets])
    } catch (err) {
      console.error(err)
      alert("Failed to upload asset")
    } finally {
      setUploading(false)
      // Reset input
      if (fileInputRef.current) fileInputRef.current.value = ""
    }
  }

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

          <button
            onClick={handleRefresh}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-white transition-all text-sm font-medium"
          >
            <RefreshCw className={cn("w-4 h-4", refreshing && "animate-spin")} />
          </button>
          
          <button
            onClick={handleUploadClick}
            disabled={uploading}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl glowing-button text-white font-medium shadow-[0_0_15px_rgba(124,58,237,0.3)] transition-all disabled:opacity-50"
          >
            {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <UploadCloud className="w-4 h-4" />}
            {uploading ? "Uploading..." : "Upload Asset"}
          </button>
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            className="hidden"
            title="Upload Media"
          />
        </div>
      </div>

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
                        onClick={handleUploadClick}
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
                          onClick={() => handleDelete(asset.id)}
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
    </div>
  )
}
