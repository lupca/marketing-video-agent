import { useEffect, useState } from "react"
import api from "../lib/api"
import { format } from "date-fns"
import { FolderHeart, Plus, RefreshCw, AlertCircle, FileText, Loader2, CheckCircle2 } from "lucide-react"
import { cn } from "../lib/utils"

interface Project {
  id: number
  name: string
  description: string
  created_at: string
}

export default function Projects() {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)

  // Form state
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchProjects = async () => {
    try {
      const res = await api.get("/api/projects")
      setProjects(res.data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  const handleRefresh = () => {
    setRefreshing(true)
    fetchProjects()
  }

  useEffect(() => {
    fetchProjects()
  }, [])

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return

    setCreating(true)
    setError(null)
    try {
      await api.post("/api/projects", { name, description })
      setShowCreateModal(false)
      setName("")
      setDescription("")
      fetchProjects()
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to create project")
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="max-w-7xl mx-auto p-8 lg:p-12 space-y-10">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <h2 className="text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60 flex items-center gap-3">
            <FolderHeart className="w-8 h-8 text-primary" /> Projects
          </h2>
          <p className="text-muted-foreground text-lg">
            Manage your video workspaces and collections.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleRefresh}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-white transition-all text-sm font-medium"
          >
            <RefreshCw className={cn("w-4 h-4", refreshing && "animate-spin")} />
            Refresh
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl glowing-button text-white font-medium shadow-[0_0_15px_rgba(124,58,237,0.3)] transition-all"
          >
            <Plus className="w-4 h-4" /> New Project
          </button>
        </div>
      </div>

      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="glass-panel p-8 max-w-md w-full animate-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-bold text-white flex items-center gap-2">
                <FolderHeart className="h-5 w-5 text-primary" /> Create Project
              </h3>
              <button onClick={() => setShowCreateModal(false)} className="text-muted-foreground hover:text-white transition-colors">
                ✕
              </button>
            </div>
            
            {error && (
              <div className="mb-4 p-3 bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm rounded-lg flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" /> {error}
              </div>
            )}

            <form onSubmit={handleCreateProject} className="space-y-5">
              <div className="space-y-2">
                <label className="text-sm font-medium text-white/80">Project Name <span className="text-rose-400">*</span></label>
                <input
                  type="text"
                  required
                  placeholder="e.g., Summer Campaign 2026"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full flex h-11 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all placeholder:text-muted-foreground/50"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-white/80">Description</label>
                <textarea
                  placeholder="Optional details about this project..."
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full flex rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all placeholder:text-muted-foreground/50 resize-none"
                />
              </div>
              
              <div className="flex justify-end gap-3 pt-4 border-t border-white/10">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-5 py-2.5 rounded-xl font-medium text-muted-foreground hover:bg-white/5 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating || !name.trim()}
                  className="px-6 py-2.5 rounded-xl glowing-button text-white font-medium flex items-center gap-2 disabled:opacity-50 disabled:shadow-none"
                >
                  {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />} 
                  {creating ? "Creating..." : "Create Project"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Grid of Projects */}
      {loading && projects.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3 text-muted-foreground">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
          Loading your workspaces...
        </div>
      ) : projects.length === 0 ? (
        <div className="glass-panel p-16 flex flex-col items-center justify-center text-center gap-4 border-dashed border-white/20">
          <div className="p-5 rounded-full bg-white/5">
            <FolderHeart className="w-10 h-10 text-muted-foreground/50" />
          </div>
          <div>
            <h3 className="text-xl font-bold text-white mb-2">No Projects Yet</h3>
            <p className="text-muted-foreground max-w-sm mx-auto">Get started by creating a new video project to organize your generative assets.</p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="mt-4 px-6 py-3 rounded-xl glowing-button text-white font-medium inline-flex items-center gap-2"
          >
            <Plus className="w-4 h-4" /> Create First Project
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 animate-in fade-in slide-in-from-bottom-8 duration-700">
          {projects.map((proj) => (
            <div key={proj.id} className="glass-panel p-6 flex flex-col group hover:-translate-y-1 transition-transform duration-300">
              <div className="flex items-start justify-between mb-4">
                <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-primary/20 to-indigo-500/20 flex items-center justify-center border border-white/10 group-hover:border-primary/30 transition-colors">
                  <FolderHeart className="w-6 h-6 text-primary group-hover:drop-shadow-[0_0_8px_rgba(124,58,237,0.8)] transition-all" />
                </div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70 bg-white/5 px-2 py-1 rounded-md">
                  ID: {proj.id}
                </span>
              </div>
              <h3 className="text-xl font-bold text-white mb-2 line-clamp-1">{proj.name}</h3>
              <p className="text-sm text-muted-foreground line-clamp-2 flex-grow mb-6 min-h-[40px]">
                {proj.description || <span className="italic text-muted-foreground/50">No description provided</span>}
              </p>
              <div className="flex items-center justify-between border-t border-white/10 pt-4 mt-auto">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <FileText className="w-3.5 h-3.5" />
                  {format(new Date(proj.created_at), "MMM dd, yyyy")}
                </div>
                <button className="text-xs font-semibold text-primary hover:text-white transition-colors">
                  View Setup →
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
