import { useState, useEffect } from "react";
import { 
  User, 
  Cpu, 
  Key, 
  Plus, 
  Trash2, 
  ShieldCheck, 
  Settings, 
  Loader2, 
  Globe, 
  Activity,
  AlertCircle,
  Zap,
  Save,
  Wand2
} from "lucide-react";
import api from "../lib/api";
import { cn } from "../lib/utils";

interface LLMModelConfig {
  id: string;
  name: string;
  provider: string;
  base_url: string;
  model_name: string;
  api_key: string;
}

export default function PersonalAI() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRoutingSaving, setIsRoutingSaving] = useState(false);

  // User Preferences State
  const [customModels, setCustomModels] = useState<LLMModelConfig[]>([]);
  const [routing, setRouting] = useState<Record<string, string>>({});
  
  // Global models (for selection in routing)
  const [systemModels, setSystemModels] = useState<any[]>([]);

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    provider: "openai",
    base_url: "https://api.openai.com",
    model_name: "",
    api_key: ""
  });

  const fetchData = async () => {
    setLoading(true);
    try {
      // 1. Fetch User LLM Preferences
      const prefRes = await api.get("/api/user/llm-preferences");
      setCustomModels(prefRes.data.custom_models || []);
      setRouting(prefRes.data.routing || {});

      // 2. Fetch System Models for routing selection
      const sysRes = await api.get("/api/system/chat-models");
      setSystemModels(sysRes.data);
    } catch (err) {
      console.error("Failed to fetch personal AI settings:", err);
      setError("Không thể tải cấu hình AI cá nhân.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleAddCustomModel = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      const newModel = {
        ...formData,
        id: `user-${Date.now()}`
      };
      const updatedModels = [...customModels, newModel];
      await api.put("/api/user/llm-preferences", {
        custom_models: updatedModels,
        routing
      });
      setCustomModels(updatedModels);
      setIsModalOpen(false);
      setFormData({
        name: "",
        provider: "openai",
        base_url: "https://api.openai.com",
        model_name: "",
        api_key: ""
      });
    } catch (err) {
      alert("Lỗi khi lưu model cá nhân.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteModel = async (id: string) => {
    if (!confirm("Xóa model này?")) return;
    const updatedModels = customModels.filter(m => m.id !== id);
    try {
      await api.put("/api/user/llm-preferences", {
        custom_models: updatedModels,
        routing
      });
      setCustomModels(updatedModels);
    } catch (err) {
      alert("Lỗi khi xóa.");
    }
  };

  const saveRouting = async () => {
    setIsRoutingSaving(true);
    try {
      await api.put("/api/user/llm-preferences", {
        custom_models: customModels,
        routing
      });
      alert("Đã cập nhật lựa chọn model cá nhân!");
    } catch (err) {
      alert("Lỗi khi lưu routing.");
    } finally {
      setIsRoutingSaving(false);
    }
  };

  if (loading) return (
    <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
      <Loader2 className="w-10 h-10 animate-spin text-primary" />
      <p className="text-muted-foreground font-medium">Đang tải cấu hình cá nhân...</p>
    </div>
  );

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8 pb-20">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 border-b border-white/10 pb-8">
        <div className="flex items-center gap-4">
          <div className="p-4 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-2xl shadow-[0_0_30px_rgba(124,58,237,0.4)] text-white">
            <User className="w-8 h-8" />
          </div>
          <div>
            <h1 className="text-3xl font-black text-white tracking-tight">AI Cá Nhân (BYOK)</h1>
            <p className="text-muted-foreground mt-1 font-medium">
              Tự quản lý API Keys và tùy chỉnh mô hình AI cho riêng bạn.
            </p>
          </div>
        </div>
        
        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-2 px-6 py-3.5 bg-white text-black hover:bg-zinc-200 transition-all rounded-2xl text-sm font-bold shadow-xl active:scale-95 cursor-pointer"
        >
          <Plus className="w-5 h-5" /> Thêm API Key Cá Nhân
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left: Routing Overrides */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-black/40 border border-white/10 rounded-[2.5rem] p-8 backdrop-blur-xl space-y-8">
            <div className="flex items-center gap-3 border-b border-white/5 pb-4">
              <Zap className="w-5 h-5 text-amber-400" />
              <h2 className="text-xl font-bold text-white tracking-tight">Tùy Chỉnh Phân Luồng AI</h2>
            </div>

            <div className="grid grid-cols-1 gap-8">
              {[
                { key: "leader_script_analysis", name: "AI Leader Agent", desc: "Phân tích kịch bản từ TMCP" },
                { key: "video_orchestrator", name: "Agent Điều Phối", desc: "Tìm kiếm video/audio & dựng flow" },
                { key: "chat_assistant", name: "Trợ Lý Chat", desc: "Hỗ trợ viết prompt & kịch bản" }
              ].map(feature => (
                <div key={feature.key} className="space-y-3 group">
                  <div className="flex justify-between items-end">
                    <div>
                      <label className="text-sm font-bold text-white block">{feature.name}</label>
                      <p className="text-[11px] text-muted-foreground font-medium">{feature.desc}</p>
                    </div>
                    {routing[feature.key] && (
                      <button 
                        onClick={() => setRouting({...routing, [feature.key]: ""})}
                        className="text-[10px] font-bold text-red-400/60 hover:text-red-400 uppercase tracking-tighter"
                      >
                        Reset về hệ thống
                      </button>
                    )}
                  </div>
                  <select
                    value={routing[feature.key] || ""}
                    onChange={(e) => setRouting({...routing, [feature.key]: e.target.value})}
                    className={cn(
                      "w-full bg-white/5 border rounded-2xl px-5 py-4 text-sm text-white focus:outline-none transition-all cursor-pointer",
                      routing[feature.key] ? "border-primary/50 bg-primary/5 ring-1 ring-primary/20" : "border-white/10"
                    )}
                  >
                    <option value="">Mặc định: Theo cấu hình của Hệ thống</option>
                    
                    {/* User Custom Models Group */}
                    {customModels.length > 0 && (
                      <optgroup label="API Key Cá Nhân Của Bạn">
                        {customModels.map(m => (
                          <option key={m.id} value={m.id}>⭐ {m.name} ({m.model_name})</option>
                        ))}
                      </optgroup>
                    )}

                    {/* System Models Group */}
                    <optgroup label="Sử dụng Model Hệ Thống">
                      {systemModels.map(m => (
                        <option key={m.id} value={m.id}>{m.name}</option>
                      ))}
                    </optgroup>
                  </select>
                </div>
              ))}
            </div>

            <div className="pt-6">
              <button
                onClick={saveRouting}
                disabled={isRoutingSaving}
                className="w-full flex items-center justify-center gap-3 py-4 bg-primary text-white hover:bg-primary/90 disabled:opacity-50 transition-all rounded-2xl text-sm font-extrabold shadow-lg shadow-primary/20 cursor-pointer"
              >
                {isRoutingSaving ? <Loader2 className="w-5 h-5 animate-spin" /> : <Save className="w-5 h-5" />}
                Lưu Thay Đổi Cá Nhân
              </button>
            </div>
          </div>
        </div>

        {/* Right: Personal API Keys List */}
        <div className="space-y-6">
          <div className="bg-black/40 border border-white/10 rounded-[2rem] p-6 backdrop-blur-xl h-fit">
            <div className="flex items-center gap-2 mb-6">
              <ShieldCheck className="w-5 h-5 text-emerald-400" />
              <h2 className="text-lg font-bold text-white tracking-tight">API Keys Đã Lưu</h2>
            </div>

            {customModels.length === 0 ? (
              <div className="p-8 text-center border border-dashed border-white/10 rounded-3xl opacity-50">
                <Key className="w-10 h-10 mx-auto mb-3 opacity-20" />
                <p className="text-[11px] font-bold text-white uppercase tracking-wider">Chưa có Key nào</p>
                <p className="text-[10px] text-muted-foreground mt-1">Hãy thêm key cá nhân để dùng model xịn hơn.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {customModels.map(model => (
                  <div key={model.id} className="p-4 bg-white/5 border border-white/10 rounded-2xl group relative overflow-hidden">
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 bg-white/5 border border-white/10 rounded-lg flex items-center justify-center">
                          <Globe className="w-4 h-4 text-primary" />
                        </div>
                        <div>
                          <p className="text-xs font-bold text-white truncate max-w-[120px]">{model.name}</p>
                          <p className="text-[9px] text-muted-foreground font-mono">{model.model_name}</p>
                        </div>
                      </div>
                      <button 
                        onClick={() => handleDeleteModel(model.id)}
                        className="p-1.5 text-muted-foreground hover:text-red-400 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></div>
                      <p className="text-[9px] font-bold text-emerald-400/80 uppercase tracking-widest">Active & Secure</p>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="mt-8 p-4 bg-amber-500/10 border border-amber-500/20 rounded-2xl">
              <div className="flex gap-2 text-amber-400 mb-1">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                <span className="text-[10px] font-bold uppercase">Lưu ý bảo mật</span>
              </div>
              <p className="text-[10px] text-amber-400/70 leading-relaxed font-medium">
                API Key của bạn được mã hóa và lưu trữ an toàn trên server. Chúng tôi không bao giờ hiển thị lại key sau khi lưu.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Modal Thêm Model */}
      {isModalOpen && (
        <div className="fixed inset-0 flex items-center justify-center z-50 p-4">
          <div onClick={() => setIsModalOpen(false)} className="absolute inset-0 bg-black/80 backdrop-blur-md" />
          <div className="bg-zinc-950 border border-white/10 rounded-[2.5rem] w-full max-w-md p-8 relative z-10 shadow-2xl animate-in zoom-in-95 duration-200">
            <h2 className="text-xl font-black text-white mb-6 tracking-tight flex items-center gap-3">
              <Key className="w-6 h-6 text-primary" /> Thêm API Key Cá Nhân
            </h2>

            <form onSubmit={handleAddCustomModel} className="space-y-5">
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider ml-1">Tên gợi nhớ</label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="Ví dụ: My OpenAI Personal"
                  className="w-full bg-white/5 border border-white/10 rounded-2xl px-5 py-3.5 text-xs text-white focus:ring-1 focus:ring-primary outline-none"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider ml-1">Nhà cung cấp</label>
                <select
                  value={formData.provider}
                  onChange={(e) => setFormData({ ...formData, provider: e.target.value })}
                  className="w-full bg-zinc-900 border border-white/10 rounded-2xl px-5 py-3.5 text-xs text-white outline-none"
                >
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic (Claude)</option>
                  <option value="groq">Groq</option>
                  <option value="ollama">Ollama (Custom URL)</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider ml-1">Mã Model (Model ID)</label>
                <input
                  type="text"
                  required
                  value={formData.model_name}
                  onChange={(e) => setFormData({ ...formData, model_name: e.target.value })}
                  placeholder="Ví dụ: gpt-4o, claude-3-5-sonnet"
                  className="w-full bg-white/5 border border-white/10 rounded-2xl px-5 py-3.5 text-xs text-white outline-none font-mono"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider ml-1">API Key Cá Nhân</label>
                <input
                  type="password"
                  required
                  value={formData.api_key}
                  onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                  placeholder="sk-..."
                  className="w-full bg-white/5 border border-white/10 rounded-2xl px-5 py-3.5 text-xs text-white outline-none font-mono"
                />
              </div>

              <div className="flex gap-4 pt-4">
                <button 
                  type="button" 
                  onClick={() => setIsModalOpen(false)} 
                  className="flex-1 py-4 bg-white/5 hover:bg-white/10 text-xs font-bold text-white rounded-2xl transition-all"
                >
                  Hủy
                </button>
                <button 
                  type="submit" 
                  disabled={isSubmitting} 
                  className="flex-1 py-4 bg-primary text-white text-xs font-black rounded-2xl transition-all shadow-lg shadow-primary/20"
                >
                  {isSubmitting ? "Đang lưu..." : "Lưu API Key"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
