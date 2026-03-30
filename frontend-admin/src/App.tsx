import { BrowserRouter as Router, Routes, Route, Link, useLocation, Navigate } from "react-router-dom";
import { LayoutDashboard, Video, Zap, LogOut, User as UserIcon, FolderHeart, Database, Activity, Wand2, BookOpen, DownloadCloud, Sparkles } from "lucide-react";
import Dashboard from "./pages/Dashboard";
import CreateUnboxJob from "./pages/CreateUnboxJob";
import CreateUnboxViralJob from "./pages/CreateUnboxViralJob";
import CreateReviewJob from "./pages/CreateReviewJob";
import CreateSlideshowJob from "./pages/CreateSlideshowJob";
import CreatePromotionJob from "./pages/CreatePromotionJob";
import DownloadVideo from "./pages/DownloadVideo";
import Projects from "./pages/Projects";
import ProjectDetails from "./pages/ProjectDetails";
import Assets from "./pages/Assets";
import SystemHealth from "./pages/SystemHealth";
import Guides from "./pages/Guides";
import Login from "./pages/Login";
import Register from "./pages/Register";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { cn } from "./lib/utils";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  
  if (loading) {
    return <div className="min-h-screen flex items-center justify-center bg-background text-white">Loading...</div>;
  }
  
  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

function Sidebar() {
  const location = useLocation();
  const { user, logout } = useAuth();

  const links = [
    { name: "Command Center", path: "/", icon: LayoutDashboard },
    { name: "Sưu tầm Video", path: "/download", icon: DownloadCloud },
    { name: "Review Studio", path: "/create-review", icon: Wand2 },
    { name: "Projects", path: "/projects", icon: FolderHeart },
    { name: "Assets", path: "/assets", icon: Database },
    { name: "Unbox Factory", path: "/create-unbox", icon: Video },
    { name: "Viral Unbox", path: "/create-viral", icon: Zap },
    { name: "Slideshow", path: "/create-slideshow", icon: Zap },
    { name: "Promotion Viral", path: "/create-promotion", icon: Sparkles },
    { name: "Content Guides", path: "/guides", icon: BookOpen },
    { name: "System Health", path: "/health", icon: Activity },
  ];

  return (
    <div className="w-64 border-r border-white/10 bg-black/20 backdrop-blur-lg flex flex-col min-h-screen z-10 shadow-[4px_0_24px_rgba(0,0,0,0.2)]">
      <div className="p-8 border-b border-white/10 flex items-center gap-3">
        <div className="p-2 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-xl shadow-[0_0_15px_rgba(124,58,237,0.5)]">
          <Zap className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">VidGenius</h1>
          <p className="text-[10px] uppercase tracking-widest text-primary font-semibold">AI Orchestrator</p>
        </div>
      </div>
      <nav className="flex-1 p-6 space-y-3">
        {links.map((link) => {
          const Icon = link.icon;
          const isActive = location.pathname === link.path;
          return (
            <Link
              key={link.name}
              to={link.path}
              className={cn(
                "flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-all duration-300",
                isActive 
                  ? "bg-primary/10 text-primary border border-primary/30 shadow-[0_0_20px_rgba(124,58,237,0.2)]" 
                  : "text-muted-foreground hover:bg-white/5 hover:text-white border border-transparent"
              )}
            >
              <Icon className={cn("h-5 w-5", isActive ? "text-primary drop-shadow-[0_0_8px_rgba(124,58,237,0.8)]" : "opacity-70")} />
              {link.name}
            </Link>
          );
        })}
      </nav>
      
      <div className="p-6 border-t border-white/10 space-y-4">
        {user && (
          <div className="flex items-center justify-between bg-black/40 p-3 rounded-xl border border-white/5">
            <div className="flex items-center gap-2 overflow-hidden">
              <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center border border-primary/30">
                <UserIcon className="w-4 h-4 text-primary" />
              </div>
              <div className="flex flex-col truncate">
                <span className="text-xs font-semibold text-white truncate">{user.email}</span>
                <span className="text-[10px] text-muted-foreground">Creator</span>
              </div>
            </div>
            <button 
              onClick={logout}
              className="p-2 hover:bg-red-500/10 hover:text-red-400 text-muted-foreground rounded-lg transition-colors"
              title="Đăng xuất"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        )}
        <div className="flex items-center gap-3 bg-black/40 p-3 rounded-xl border border-white/5">
          <div className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_10px_rgba(16,185,129,0.8)] animate-pulse"></div>
          <span className="text-xs font-medium text-emerald-400">System Online</span>
        </div>
      </div>
    </div>
  );
}

function MainLayout() {
  return (
    <div className="flex min-h-screen w-full text-foreground relative selection:bg-primary/30">
      <Sidebar />
      <main className="flex-1 h-screen overflow-y-auto z-0 custom-scrollbar">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/download" element={<DownloadVideo />} />
          <Route path="/create-unbox" element={<CreateUnboxJob />} />
          <Route path="/create-viral" element={<CreateUnboxViralJob />} />
          <Route path="/create-review" element={<CreateReviewJob />} />
          <Route path="/create-slideshow" element={<CreateSlideshowJob />} />
          <Route path="/create-promotion" element={<CreatePromotionJob />} />
          <Route path="/projects" element={<Projects />} />
          <Route path="/projects/:id" element={<ProjectDetails />} />
          <Route path="/assets" element={<Assets />} />
          <Route path="/guides" element={<Guides />} />
          <Route path="/health" element={<SystemHealth />} />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="*" element={
            <ProtectedRoute>
              <MainLayout />
            </ProtectedRoute>
          } />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;
