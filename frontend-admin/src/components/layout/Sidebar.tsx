import { useState, useEffect } from "react";
import { useLocation, Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { cn } from "../../lib/utils";
import {
  LayoutDashboard,
  Video,
  Zap,
  LogOut,
  User as UserIcon,
  FolderHeart,
  Database,
  Activity,
  Wand2,
  BookOpen,
  DownloadCloud,
  Sparkles,
  Bot,
  Languages,
  Volume2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Settings
} from "lucide-react";

interface SidebarLink {
  name: string;
  path: string;
  icon: React.ComponentType<any>;
  description: string;
}

interface SidebarGroup {
  id: string;
  title: string;
  links: SidebarLink[];
}

export default function Sidebar() {
  const location = useLocation();
  const { user, logout } = useAuth();

  // 1. Phân nhóm danh mục liên kết với đầy đủ mô tả chi tiết cho tooltips
  const groups: SidebarGroup[] = [
    {
      id: "workspace",
      title: "Tổng quan & Dự án",
      links: [
        { name: "Command Center", path: "/", icon: LayoutDashboard, description: "Bảng điều khiển & Giám sát hệ thống render" },
        { name: "Dự án Video", path: "/projects", icon: FolderHeart, description: "Danh sách và chi tiết các dự án video của bạn" },
        { name: "AI Cá Nhân (BYOK)", path: "/personal-ai", icon: UserIcon, description: "Quản lý API Keys cá nhân và cấu hình AI riêng" },
        { name: "Kho Tư Liệu", path: "/assets", icon: Database, description: "Quản lý cơ sở dữ liệu và tệp tin tư liệu thô" }
      ]
    },
    {
      id: "video_factory",
      title: "Xưởng Video AI",
      links: [
        { name: "AI Leader Agent", path: "/create-leader", icon: Bot, description: "AI Leader phân tích kịch bản & tự đề xuất worker thích hợp" },
        { name: "Unbox Factory", path: "/create-unbox", icon: Video, description: "Tạo video unbox tiêu chuẩn không lời bám nhạc nền" },
        { name: "Viral Unbox", path: "/create-viral", icon: Zap, description: "Tạo shorts/viral giật giật theo nhịp beat cực mạnh" },
        { name: "Review Studio", path: "/create-review", icon: Wand2, description: "Dựng video review chi tiết, ghép cảnh theo voiceover thuyết minh" },
        { name: "Promotion Viral", path: "/create-promotion", icon: Sparkles, description: "Tạo video quảng bá sản phẩm thu hút và lan truyền nhanh" },
        { name: "Slideshow", path: "/create-slideshow", icon: Zap, description: "Ghép chuỗi ảnh chất lượng cao thành video khớp beat nhạc" },
        { name: "Dịch thuật Video", path: "/create-translify", icon: Languages, description: "Dịch, thuyết minh & lồng tiếng video đa ngôn ngữ với Editor" }
      ]
    },
    {
      id: "creative",
      title: "AI Studio Hỗ Trợ",
      links: [
        { name: "Image Studio", path: "/image-studio", icon: Sparkles, description: "Tạo và biên tập hình ảnh AI nghệ thuật chất lượng cao" },
        { name: "Speech Studio", path: "/speech-studio", icon: Volume2, description: "Chuyển văn bản thành giọng nói tiếng Việt tự nhiên (MeloTTS)" },
        { name: "Sưu tầm Video", path: "/download", icon: DownloadCloud, description: "Thu thập & tải video tài nguyên từ Youtube, Tiktok, v.v." }
      ]
    },
    {
      id: "system",
      title: "Hệ thống & Tài liệu",
      links: [
        { name: "Agent Studio", path: "/agent-studio", icon: Bot, description: "Thiết lập danh tính, tính cách và chỉ thị cho AI Agents" },
        { name: "Cấu hình Model", path: "/settings/models", icon: Settings, description: "Quản lý các mô hình LLM (Ollama, OpenAI) kết nối vào hệ thống" },
        { name: "Cấu hình CapCut", path: "/settings/capcut", icon: Settings, description: "Quản lý mô hình LLM dịch tham số & Kỹ năng CapCut" },

        { name: "Hướng Dẫn Kỹ Thuật", path: "/guides", icon: BookOpen, description: "Tài liệu kỹ thuật định dạng cấu trúc JSON API cho Workers" },
        { name: "System Health", path: "/health", icon: Activity, description: "Giám sát trạng thái hoạt động của Render Farm & các Workers" }
      ]
    }
  ];

  // 2. Trạng thái thu gọn Accordions (Lưu vào localStorage)
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>(() => {
    const saved = localStorage.getItem("sidebar_expanded_groups");
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {
        console.error("Error parsing saved sidebar state", e);
      }
    }
    return {
      workspace: true,
      video_factory: true,
      creative: false,
      system: false
    };
  });

  // 3. Trạng thái thu nhỏ Sidebar (Slim Mode - Lưu vào localStorage)
  const [isSlim, setIsSlim] = useState<boolean>(() => {
    return localStorage.getItem("sidebar_is_slim") === "true";
  });

  // Đồng bộ trạng thái đóng/mở Accordions vào localstorage
  useEffect(() => {
    localStorage.setItem("sidebar_expanded_groups", JSON.stringify(expandedGroups));
  }, [expandedGroups]);

  // Đồng bộ trạng thái Slim Mode vào localstorage
  useEffect(() => {
    localStorage.setItem("sidebar_is_slim", String(isSlim));
  }, [isSlim]);

  const toggleGroup = (groupId: string) => {
    if (isSlim) return; // Không đóng mở Accordion khi ở chế độ thu nhỏ
    setExpandedGroups((prev) => ({
      ...prev,
      [groupId]: !prev[groupId]
    }));
  };

  return (
    <div
      className={cn(
        "border-r border-white/10 bg-black/30 backdrop-blur-2xl flex flex-col min-h-screen z-10 shadow-[4px_0_24px_rgba(0,0,0,0.3)] transition-all duration-300 ease-in-out relative shrink-0",
        isSlim ? "w-20" : "w-64"
      )}
    >
      {/* Nút Toggle Slim Sidebar */}
      <button
        onClick={() => setIsSlim(!isSlim)}
        className="absolute top-24 -right-3 w-6 h-6 rounded-full bg-primary border border-white/20 text-white flex items-center justify-center shadow-[0_0_10px_rgba(124,58,237,0.5)] hover:scale-110 transition-transform z-20 cursor-pointer"
        title={isSlim ? "Mở rộng thanh menu" : "Thu nhỏ thanh menu"}
      >
        {isSlim ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronLeft className="w-3.5 h-3.5" />}
      </button>

      {/* Header thương hiệu */}
      <div className={cn("p-6 border-b border-white/10 flex items-center gap-3 overflow-hidden", isSlim ? "justify-center p-5" : "")}>
        <div className="p-2.5 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-xl shadow-[0_0_15px_rgba(124,58,237,0.5)] shrink-0 transition-transform duration-300 hover:rotate-12">
          <Zap className="w-6 h-6 text-white" />
        </div>
        {!isSlim && (
          <div className="animate-in fade-in duration-300">
            <h1 className="text-lg font-extrabold text-white tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-white/70">
              VidGenius
            </h1>
            <p className="text-[9px] uppercase tracking-widest text-primary font-bold">AI Orchestrator</p>
          </div>
        )}
      </div>

      {/* Danh sách các link điều hướng */}
      <nav className="flex-1 p-4 space-y-4 overflow-y-auto custom-scrollbar select-none">
        {groups.map((group) => {
          const isExpanded = expandedGroups[group.id];

          return (
            <div key={group.id} className="space-y-1">
              {/* Tiêu đề nhóm (Accordion Trigger) */}
              {!isSlim ? (
                <button
                  onClick={() => toggleGroup(group.id)}
                  className="w-full flex items-center justify-between px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-muted-foreground hover:text-white transition-colors cursor-pointer group"
                >
                  <span className="group-hover:text-primary transition-colors">{group.title}</span>
                  <ChevronDown
                    className={cn(
                      "w-3 h-3 transition-transform duration-300 text-muted-foreground/60 group-hover:text-white",
                      isExpanded ? "transform rotate-180" : ""
                    )}
                  />
                </button>
              ) : (
                <div className="border-t border-white/5 my-3 first:mt-0 shrink-0" />
              )}

              {/* Các liên kết bên trong nhóm */}
              <div
                className={cn(
                  "space-y-1 transition-all duration-300 ease-in-out overflow-hidden",
                  !isSlim && !isExpanded ? "max-h-0 opacity-0 pointer-events-none" : "max-h-[500px] opacity-100"
                )}
              >
                {group.links.map((link) => {
                  const Icon = link.icon;
                  const isActive = location.pathname === link.path;

                  return (
                    <Link
                      key={link.name}
                      to={link.path}
                      className={cn(
                        "flex items-center gap-3 rounded-xl transition-all duration-300 group relative border",
                        isSlim ? "justify-center p-3" : "px-3.5 py-2.5 text-sm font-medium",
                        isActive
                          ? "bg-primary/10 text-primary border-primary/30 shadow-[0_0_15px_rgba(124,58,237,0.15)]"
                          : "text-muted-foreground hover:bg-white/5 hover:text-white border-transparent"
                      )}
                    >
                      {/* Active Indicator bên trái */}
                      {isActive && !isSlim && (
                        <div className="absolute left-0 top-1/4 bottom-1/4 w-1 bg-primary rounded-r-full shadow-[0_0_8px_rgba(124,58,237,0.8)]" />
                      )}

                      <Icon
                        className={cn(
                          "h-5 w-5 shrink-0 transition-all duration-300",
                          isActive
                            ? "text-primary drop-shadow-[0_0_8px_rgba(124,58,237,0.8)] scale-105"
                            : "opacity-70 group-hover:opacity-100 group-hover:scale-105"
                        )}
                      />

                      {!isSlim && <span className="truncate">{link.name}</span>}

                      {/* Tooltip nổi dành riêng cho Slim Mode */}
                      {isSlim && (
                        <div className="pointer-events-none absolute left-full ml-4 z-50 w-56 p-3.5 bg-black/90 backdrop-blur-xl border border-white/10 rounded-xl shadow-[0_10px_30px_rgba(0,0,0,0.5)] opacity-0 -translate-x-3 scale-95 group-hover:opacity-100 group-hover:translate-x-0 group-hover:scale-100 transition-all duration-300 ease-out origin-left">
                          <h4 className="text-xs font-bold text-white flex items-center gap-1.5 mb-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-primary shadow-[0_0_6px_rgba(124,58,237,0.8)]"></span>
                            {link.name}
                          </h4>
                          <p className="text-[10px] text-muted-foreground leading-relaxed">
                            {link.description}
                          </p>
                        </div>
                      )}
                    </Link>
                  );
                })}
              </div>
            </div>
          );
        })}
      </nav>

      {/* Footer quản lý tài khoản & hệ thống */}
      <div className={cn("p-4 border-t border-white/10 space-y-3 shrink-0 bg-black/10", isSlim ? "p-3 flex flex-col items-center gap-2" : "")}>
        {user && (
          <div
            className={cn(
              "flex items-center justify-between bg-black/40 p-2.5 rounded-xl border border-white/5 relative group/profile",
              isSlim ? "justify-center w-12 h-12 p-0 cursor-pointer" : ""
            )}
          >
            <div className={cn("flex items-center gap-2 overflow-hidden", isSlim ? "justify-center" : "")}>
              <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center border border-primary/30 shrink-0 transition-transform duration-300 hover:scale-105">
                <UserIcon className="w-4 h-4 text-primary" />
              </div>
              {!isSlim && (
                <div className="flex flex-col truncate max-w-[130px] animate-in fade-in duration-300">
                  <span className="text-xs font-bold text-white truncate" title={user.email}>
                    {user.email}
                  </span>
                  <span className="text-[9px] text-muted-foreground/70 uppercase tracking-wider font-semibold">Creator</span>
                </div>
              )}
            </div>

            {!isSlim ? (
              <button
                onClick={logout}
                className="p-1.5 hover:bg-red-500/10 hover:text-red-400 text-muted-foreground/70 rounded-lg transition-colors cursor-pointer"
                title="Đăng xuất"
              >
                <LogOut className="w-4 h-4" />
              </button>
            ) : (
              /* Tooltip hiển thị Email + Nút Logout khi di chuột vào Avatar ở Slim Mode */
              <div className="pointer-events-none absolute left-full ml-4 z-50 w-48 p-3 bg-black/95 backdrop-blur-xl border border-white/10 rounded-xl shadow-[0_10px_30px_rgba(0,0,0,0.5)] opacity-0 -translate-x-3 scale-95 group-hover/profile:opacity-100 group-hover/profile:translate-x-0 group-hover/profile:scale-100 transition-all duration-300 ease-out origin-left flex flex-col gap-2">
                <div className="flex flex-col truncate">
                  <span className="text-[10px] font-bold text-white truncate">{user.email}</span>
                  <span className="text-[9px] text-muted-foreground">Creator</span>
                </div>
                <button
                  onClick={logout}
                  className="pointer-events-auto w-full flex items-center justify-center gap-2 px-2.5 py-1.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 text-[10px] font-bold uppercase tracking-wider transition-colors cursor-pointer"
                >
                  <LogOut className="w-3.5 h-3.5" /> Đăng xuất
                </button>
              </div>
            )}
          </div>
        )}

        {/* Trạng thái hệ thống */}
        <div
          className={cn(
            "flex items-center gap-2.5 bg-black/40 p-2.5 rounded-xl border border-white/5 select-none transition-all duration-300 relative group/status",
            isSlim ? "w-12 h-12 p-0 justify-center cursor-pointer" : ""
          )}
        >
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)] animate-pulse shrink-0"></div>
          {!isSlim ? (
            <span className="text-xs font-semibold text-emerald-400 animate-in fade-in duration-300">System Online</span>
          ) : (
            /* Tooltip trạng thái hệ thống */
            <div className="pointer-events-none absolute left-full ml-4 z-50 p-2.5 bg-black/90 backdrop-blur-md border border-white/10 rounded-lg shadow-[0_10px_30px_rgba(0,0,0,0.5)] opacity-0 -translate-x-2 group-hover/status:opacity-100 group-hover/status:translate-x-0 transition-all duration-300 ease-out text-[10px] font-bold text-emerald-400 whitespace-nowrap">
              System Online (Active)
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
