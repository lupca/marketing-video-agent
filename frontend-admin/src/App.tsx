import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";

import Dashboard from "./pages/Dashboard";
import CreateUnboxJob from "./pages/CreateUnboxJob";
import CreateUnboxViralJob from "./pages/CreateUnboxViralJob";
import CreateReviewJob from "./pages/CreateReviewJob";
import ImageStudio from "./pages/ImageStudio";
import SpeechStudio from "./pages/SpeechStudio";
import CreateSlideshowJob from "./pages/CreateSlideshowJob";
import CreatePromotionJob from "./pages/CreatePromotionJob";
import DownloadVideo from "./pages/DownloadVideo";
import Projects from "./pages/Projects";
import ProjectDetails from "./pages/ProjectDetails";
import Assets from "./pages/Assets";
import SystemHealth from "./pages/SystemHealth";
import Guides from "./pages/Guides";
import AgentStudio from "./pages/AgentStudio";
import TranslifyEditor from "./pages/TranslifyEditor";
import CreateTranslifyJob from "./pages/CreateTranslifyJob";
import CreateLeaderJob from "./pages/CreateLeaderJob";
import Login from "./pages/Login";
import Register from "./pages/Register";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { AIStudioAddonProvider } from "./context/AIStudioAddonContext";

import Sidebar from "./components/layout/Sidebar";
import AIAddonDock from "./components/layout/addons/AIAddonDock";
import AIAddonDrawer from "./components/layout/addons/AIAddonDrawer";

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



function MainLayout() {
  return (
    <div className="flex min-h-screen w-full text-foreground relative selection:bg-primary/30">
      <Sidebar />
      <main className="flex-1 h-screen overflow-y-auto z-0 custom-scrollbar">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/image-studio" element={<ImageStudio />} />
          <Route path="/speech-studio" element={<SpeechStudio />} />
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
          <Route path="/agent-studio" element={<AgentStudio />} />
          <Route path="/health" element={<SystemHealth />} />
          <Route path="/translify/editor/:id" element={<TranslifyEditor />} />
          <Route path="/create-translify" element={<CreateTranslifyJob />} />
          <Route path="/create-leader" element={<CreateLeaderJob />} />
        </Routes>
      </main>
      <AIAddonDock />
      <AIAddonDrawer />
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <AIStudioAddonProvider>
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
      </AIStudioAddonProvider>
    </AuthProvider>
  );
}

export default App;
