import { BrowserRouter as Router, Routes, Route, Link, useLocation } from "react-router-dom";
import { LayoutDashboard,  Video, PlusSquare, Zap } from "lucide-react";
import Dashboard from "./pages/Dashboard";
import CreateUnboxJob from "./pages/CreateUnboxJob";
import CreateReviewJob from "./pages/CreateReviewJob";
import { cn } from "./lib/utils";

function Sidebar() {
  const location = useLocation();

  const links = [
    { name: "Command Center", href: "/", icon: LayoutDashboard },
    { name: "Unbox Factory", href: "/create-unbox", icon: Video },
    { name: "Review Studio", href: "/create-review", icon: PlusSquare },
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
          const isActive = location.pathname === link.href;
          return (
            <Link
              key={link.name}
              to={link.href}
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
      
      <div className="p-6 border-t border-white/10">
        <div className="flex items-center gap-3 bg-black/40 p-3 rounded-xl border border-white/5">
          <div className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_10px_rgba(16,185,129,0.8)] animate-pulse"></div>
          <span className="text-xs font-medium text-emerald-400">System Online</span>
        </div>
      </div>
    </div>
  );
}

function App() {
  return (
    <Router>
      <div className="flex min-h-screen w-full text-foreground relative selection:bg-primary/30">
        <Sidebar />
        <main className="flex-1 h-screen overflow-y-auto z-0 custom-scrollbar">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/create-unbox" element={<CreateUnboxJob />} />
            <Route path="/create-review" element={<CreateReviewJob />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
