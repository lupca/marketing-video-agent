import { useState } from "react"
import { format } from "date-fns"
import { FolderHeart, Plus, RefreshCw, FileText, Trash2, AlertCircle, CheckCircle2, Video } from "lucide-react"
import { Link } from "react-router-dom"
import { useProjects } from "../hooks/useProjects"
import { Button } from "../components/ui/Button"
import { Modal } from "../components/ui/Modal"
import { Card } from "../components/ui/Card"

export default function Projects() {
  const { projects, loading, fetchProjects, createProject, deleteProject } = useProjects()

  const [refreshing, setRefreshing] = useState(false)
  const [isModalOpen, setIsModalOpen] = useState(false)

  // Form state
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [creating, setCreating] = useState(false)
  const [errorProps, setErrorProps] = useState("")

  const handleRefresh = async () => {
    setRefreshing(true)
    await fetchProjects()
    setRefreshing(false)
  }

  const handleDeleteProject = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm("Are you SURE you want to delete this Project? All associated jobs and resources will be permanently erased.")) return
    try {
      await deleteProject(id)
    } catch (e: any) {
      console.error(e)
      alert("Failed to delete project")
    }
  }

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return

    setCreating(true)
    setErrorProps("")
    try {
      await createProject(name, description)
      setIsModalOpen(false)
      setName("")
      setDescription("")
    } catch (err: any) {
      setErrorProps(err?.response?.data?.detail || err.message || "Failed to create project")
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
          <Button onClick={handleRefresh} variant="secondary" isLoading={refreshing}>
            {!refreshing && <RefreshCw className="w-4 h-4 mr-2" />}
            Refresh
          </Button>
          <Button
            onClick={() => setIsModalOpen(true)}
            className="glowing-button font-medium shadow-[0_0_15px_rgba(124,58,237,0.3)]"
          >
            <Plus className="w-4 h-4 mr-2" /> New Project
          </Button>
        </div>
      </div>

      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={
          <div className="flex items-center gap-2">
            <FolderHeart className="h-5 w-5 text-primary" /> Create Project
          </div>
        }
      >
        <div className="p-6">
          {errorProps && (
            <div className="mb-4 p-3 bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm rounded-lg flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" /> {errorProps}
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

            <div className="flex justify-end gap-3 pt-4 border-t border-white/10 mt-6">
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="px-5 py-2.5 rounded-xl font-medium text-muted-foreground hover:bg-white/5 transition-colors"
              >
                Cancel
              </button>
              <Button type="submit" isLoading={creating} disabled={!name.trim()} className="glowing-button">
                {!creating && <CheckCircle2 className="w-4 h-4 mr-2" />}
                {creating ? "Creating..." : "Create Project"}
              </Button>
            </div>
          </form>
        </div>
      </Modal>

      {/* Grid of Projects */}
      {loading && projects.length === 0 ? (
        <div className="flex items-center justify-center py-20 text-muted-foreground">
          Loading your workspaces...
        </div>
      ) : projects.length === 0 ? (
        <Card className="p-16 flex flex-col items-center justify-center text-center gap-4 border-dashed border-white/20">
          <div className="p-5 rounded-full bg-white/5">
            <FolderHeart className="w-10 h-10 text-muted-foreground/50" />
          </div>
          <div>
            <h3 className="text-xl font-bold text-white mb-2">No Projects Yet</h3>
            <p className="text-muted-foreground max-w-sm mx-auto">Get started by creating a new video project to organize your generative assets.</p>
          </div>
          <Button
            onClick={() => setIsModalOpen(true)}
            className="mt-4 glowing-button"
          >
            <Plus className="w-4 h-4 mr-2" /> Create First Project
          </Button>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 animate-in fade-in slide-in-from-bottom-8 duration-700">
          {projects.map((proj) => (
            <Card key={proj.id} className="p-6 flex flex-col group hover:-translate-y-2 hover:shadow-[0_8px_30px_rgba(124,58,237,0.15)] hover:border-primary/40 transition-all duration-300 relative overflow-hidden bg-white/5 backdrop-blur-md">
              <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-full blur-3xl -mr-10 -mt-10 group-hover:bg-primary/20 transition-colors duration-500"></div>
              
              <div className="flex items-start justify-between mb-4 relative z-10">
                <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-primary/20 to-indigo-500/20 flex items-center justify-center border border-white/10 group-hover:border-primary/50 transition-colors shadow-inner group-hover:shadow-[inset_0_0_20px_rgba(124,58,237,0.2)]">
                  <FolderHeart className="w-6 h-6 text-primary group-hover:drop-shadow-[0_0_12px_rgba(124,58,237,0.8)] transition-all" />
                </div>
                <div className="flex flex-col items-end gap-1.5">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70 bg-black/40 px-2 py-1 rounded-md border border-white/5">
                    ID: {proj.id.split('-')[0]}
                  </span>
                  <div className="flex items-center gap-1.5 bg-blue-500/10 text-blue-400 text-xs font-bold px-2 py-1 rounded-md border border-blue-500/20 group-hover:bg-blue-500/20 transition-colors">
                    <Video className="w-3.5 h-3.5" />
                    {proj.jobs_count} Videos
                  </div>
                </div>
              </div>
              <h3 className="text-xl font-bold text-white mb-2 line-clamp-1 relative z-10 group-hover:text-primary-100 transition-colors">{proj.name}</h3>
              <p className="text-sm text-muted-foreground line-clamp-2 flex-grow mb-6 min-h-[40px] relative z-10">
                {proj.description || <span className="italic text-muted-foreground/50">No description provided</span>}
              </p>
              <div className="flex items-center justify-between border-t border-white/10 pt-4 mt-auto relative z-10">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground bg-black/20 px-2.5 py-1.5 rounded-lg border border-white/5">
                  <FileText className="w-3.5 h-3.5" />
                  {format(new Date(proj.created_at), "MMM dd, yyyy")}
                </div>
                <div className="flex items-center gap-2 bg-black/20 p-1 rounded-xl border border-white/5">
                  <Link 
                    to={`/projects/${proj.id}`}
                    className="text-xs font-bold text-primary hover:text-white hover:bg-primary px-3 py-1.5 rounded-lg transition-all"
                  >
                    View Project
                  </Link>
                  <div className="w-px h-4 bg-white/10 mx-1"></div>
                  <button
                    onClick={(e) => handleDeleteProject(proj.id, e)}
                    className="p-1.5 rounded-lg text-rose-400/50 hover:text-rose-400 hover:bg-rose-500/20 transition-colors"
                    title="Delete Project"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
