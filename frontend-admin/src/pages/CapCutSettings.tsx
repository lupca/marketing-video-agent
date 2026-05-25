import { useState, useEffect } from "react";
import { 
  Settings, 
  Check, 
  Loader2, 
  Cpu, 
  Activity,
  ArrowRight,
  Sparkles,
  BookOpen,
  Info
} from "lucide-react";
import api from "../lib/api";
import { cn } from "../lib/utils";

interface LLMModelConfig {
  id: string;
  name: string;
  base_url: string;
  model_name: string;
  api_key?: string;
}

interface CapCutSettings {
  selected_model_id: string;
  custom_base_url: string;
  custom_model_name: string;
  custom_api_key: string;
  source: string;
}

export default function CapCutSettings() {
  const [activeTab, setActiveTab] = useState<"llm" | "skills">("llm");
  
  // Settings & Models state
  const [settings, setSettings] = useState<CapCutSettings>({
    selected_model_id: "default",
    custom_base_url: "",
    custom_model_name: "",
    custom_api_key: "",
    source: "environment"
  });
  const [models, setModels] = useState<LLMModelConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Fetch CapCut Settings and LLM Models list
  const fetchData = async () => {
    setLoading(true);
    try {
      const [settingsRes, modelsRes] = await Promise.all([
        api.get("/api/system/capcut-settings"),
        api.get("/api/system/chat-models")
      ]);
      setSettings(settingsRes.data);
      setModels(modelsRes.data);
    } catch (err) {
      console.error("Failed to fetch CapCut settings:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaveSuccess(false);
    try {
      const res = await api.put("/api/system/capcut-settings", settings);
      setSettings(res.data);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2000);
    } catch (err) {
      console.error("Failed to save CapCut settings:", err);
      alert("Lỗi khi lưu cấu hình!");
    } finally {
      setSaving(false);
    }
  };

  // Lists of supported metadata for the skills reference tab
  const transitionList = [
    "Mix", "Black_Fade", "White_Flash", "Dissolve", "Slide", "Glitch",
    "Inhale", "Pull_in", "Pull_Out", "Flame", "Rainbow_Warp", "RGB_Glitch",
    "Cartoon_Swirl", "Cube", "Shutter", "Whirlpool", "Distortion", "Squeeze"
  ];

  const introAnimList = [
    "Fade_In", "Zoom_1", "Slide_Down", "Slide_Up", "Slide_Right", "Slide_Left",
    "Rotate", "Zoom_Out", "Zoom_In", "Shake_3", "Shake_1", "Shake_2", "Flip",
    "Mini_Zoom"
  ];

  const outroAnimList = [
    "Fade_Out", "Slide_Down", "Slide_Up", "Slide_Right", "Slide_Left",
    "Zoom_In", "Zoom_Out", "Rotate", "Flip", "Mini_Zoom"
  ];

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/10 pb-6">
        <div className="flex items-center gap-3.5">
          <div className="p-3 bg-violet-500/20 rounded-2xl border border-violet-500/20 shadow-[0_0_20px_rgba(124,58,237,0.3)] text-violet-400">
            <Settings className="w-6 h-6 animate-spin-slow" />
          </div>
          <div>
            <h1 className="text-2xl font-extrabold text-white tracking-tight">Cấu Hình CapCut Worker</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Quản lý mô hình LLM chuyên biệt dịch tham số dựng phim và kiểm soát tài liệu kỹ năng CapCut.
            </p>
          </div>
        </div>

        {/* Tab switcher */}
        <div className="flex gap-2 p-1.5 bg-black/40 border border-white/10 rounded-2xl w-fit">
          <button
            onClick={() => setActiveTab("llm")}
            className={cn(
              "flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold transition-all cursor-pointer",
              activeTab === "llm" 
                ? "bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-lg shadow-violet-600/20" 
                : "text-muted-foreground hover:text-white"
            )}
          >
            <Cpu className="w-4 h-4" /> Cấu hình LLM
          </button>
          <button
            onClick={() => setActiveTab("skills")}
            className={cn(
              "flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold transition-all cursor-pointer",
              activeTab === "skills" 
                ? "bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-lg shadow-violet-600/20" 
                : "text-muted-foreground hover:text-white"
            )}
          >
            <BookOpen className="w-4 h-4" /> Kỹ năng CapCut
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center min-h-[300px] gap-4">
          <Loader2 className="w-10 h-10 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground font-semibold">Đang tải cấu hình CapCut...</p>
        </div>
      ) : (
        <>
          {activeTab === "llm" && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-in fade-in duration-200">
              {/* Form Settings */}
              <div className="lg:col-span-2 space-y-6">
                <form onSubmit={handleSave} className="bg-black/40 border border-white/10 rounded-3xl p-6 backdrop-blur-xl space-y-6">
                  <div className="flex items-center gap-2 pb-4 border-b border-white/5">
                    <Sparkles className="w-5 h-5 text-violet-400" />
                    <h3 className="text-sm font-extrabold text-white">Chỉ định Mô hình LLM</h3>
                  </div>

                  <div className="space-y-4">
                    {/* Select Model */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-muted-foreground">Mô hình hoạt động (Model Assign) *</label>
                      <select
                        value={settings.selected_model_id}
                        onChange={(e) => setSettings({ ...settings, selected_model_id: e.target.value })}
                        className="w-full bg-zinc-900 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer"
                      >
                        <option value="default">Sử dụng mô hình mặc định của hệ thống (Global Default)</option>
                        {models.map((m) => (
                          <option key={m.id} value={m.id}>
                            {m.name} ({m.model_name})
                          </option>
                        ))}
                        <option value="custom">-- Cấu hình chuyên biệt thủ công (Manual Custom) --</option>
                      </select>
                      <p className="text-[10px] text-muted-foreground leading-relaxed mt-1">
                        AI Leader sẽ đưa ra kịch bản thô. CapCut Worker sẽ sử dụng mô hình LLM được gán ở đây làm "Người dịch thuật tham số" để chuyển đổi chính xác các chuyển cảnh, hoạt cảnh thô thành tập lệnh CapCut chuẩn.
                      </p>
                    </div>

                    {/* Custom overrides (only if selected_model_id is "custom") */}
                    {settings.selected_model_id === "custom" && (
                      <div className="p-4 bg-zinc-950/60 border border-white/5 rounded-2xl space-y-4 animate-in slide-in-from-top-4 duration-200">
                        <div className="space-y-1.5">
                          <label className="text-[11px] font-semibold text-muted-foreground">Custom Endpoint URL *</label>
                          <input
                            type="text"
                            required={settings.selected_model_id === "custom"}
                            value={settings.custom_base_url}
                            onChange={(e) => setSettings({ ...settings, custom_base_url: e.target.value })}
                            placeholder="Ví dụ: http://localhost:11434"
                            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 text-xs text-white placeholder:text-muted-foreground/45 focus:outline-none focus:ring-1 focus:ring-primary font-mono text-[11px]"
                          />
                        </div>

                        <div className="space-y-1.5">
                          <label className="text-[11px] font-semibold text-muted-foreground">Custom Model Name *</label>
                          <input
                            type="text"
                            required={settings.selected_model_id === "custom"}
                            value={settings.custom_model_name}
                            onChange={(e) => setSettings({ ...settings, custom_model_name: e.target.value })}
                            placeholder="Ví dụ: qwen2.5:3b"
                            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 text-xs text-white placeholder:text-muted-foreground/45 focus:outline-none focus:ring-1 focus:ring-primary font-mono text-[11px]"
                          />
                        </div>

                        <div className="space-y-1.5">
                          <label className="text-[11px] font-semibold text-muted-foreground">Custom API Key</label>
                          <input
                            type="password"
                            value={settings.custom_api_key}
                            onChange={(e) => setSettings({ ...settings, custom_api_key: e.target.value })}
                            placeholder="Để trống nếu là Ollama local"
                            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 text-xs text-white placeholder:text-muted-foreground/45 focus:outline-none focus:ring-1 focus:ring-primary text-[11px]"
                          />
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Submit buttons */}
                  <div className="pt-4 border-t border-white/5 flex justify-end">
                    <button
                      type="submit"
                      disabled={saving}
                      className={cn(
                        "flex items-center gap-2 px-6 py-3 rounded-xl text-xs font-bold text-white transition-all cursor-pointer",
                        saveSuccess 
                          ? "bg-emerald-600 shadow-lg shadow-emerald-600/20" 
                          : "bg-gradient-to-r from-violet-600 to-indigo-600 hover:scale-[1.02] active:scale-[0.98] shadow-lg shadow-violet-600/20"
                      )}
                    >
                      {saving ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : saveSuccess ? (
                        <Check className="w-4 h-4" />
                      ) : (
                        <Activity className="w-4 h-4" />
                      )}
                      {saveSuccess ? "Đã lưu thành công!" : "Lưu cấu hình"}
                    </button>
                  </div>
                </form>
              </div>

              {/* Sidebar Context */}
              <div className="space-y-6">
                <div className="bg-black/40 border border-white/10 rounded-3xl p-6 backdrop-blur-xl">
                  <div className="flex items-center gap-2 pb-4 border-b border-white/5 text-violet-400">
                    <Info className="w-5 h-5" />
                    <h3 className="text-sm font-extrabold text-white">Kiến trúc Dịch thuật</h3>
                  </div>

                  <div className="space-y-4 text-xs leading-relaxed text-muted-foreground pt-4">
                    <div className="flex gap-2">
                      <div className="w-1.5 h-1.5 bg-violet-500 rounded-full mt-1.5 shrink-0" />
                      <p>
                        <strong>Tách biệt trách nhiệm:</strong> AI Leader chỉ phân tích nhu cầu và lập kịch bản nội dung trừu tượng. Nó không cần biết các thuộc tính dựng phim kỹ thuật.
                      </p>
                    </div>

                    <div className="flex gap-2">
                      <div className="w-1.5 h-1.5 bg-violet-500 rounded-full mt-1.5 shrink-0" />
                      <p>
                        <strong>Biên dịch thông minh:</strong> CapCut Worker Agent tiếp nhận kịch bản thô và sử dụng thư viện Skill để dịch chính xác các hoạt cảnh như <em>"fade_in"</em> sang lệnh chuyển cảnh <em>"Dissolve"</em> + hoạt cảnh bắt đầu <em>"Fade_In"</em>.
                      </p>
                    </div>

                    <div className="flex gap-2">
                      <div className="w-1.5 h-1.5 bg-violet-500 rounded-full mt-1.5 shrink-0" />
                      <p>
                        <strong>An toàn và bảo mật:</strong> Nếu LLM bị gián đoạn, cơ chế Heuristic nội bộ của Worker sẽ tự động kích hoạt để sửa chữa các chuyển tiếp cơ bản, đảm bảo dự án luôn được render trơn tru.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === "skills" && (
            <div className="bg-black/40 border border-white/10 rounded-3xl p-6 backdrop-blur-xl space-y-6 animate-in fade-in duration-200">
              <div className="flex items-center gap-2 pb-4 border-b border-white/5">
                <BookOpen className="w-5 h-5 text-violet-400" />
                <h3 className="text-sm font-extrabold text-white">Thư Viện Skill & Từ Vựng CapCut Hợp Lệ</h3>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Transitions */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-xs font-bold text-violet-400 bg-violet-500/10 border border-violet-500/20 px-3.5 py-2 rounded-xl w-fit">
                    Hiệu ứng chuyển cảnh (Transitions)
                  </div>
                  <p className="text-[10px] text-muted-foreground leading-relaxed">
                    Chỉ được áp dụng ở giữa hai phân cảnh trên timeline chính.
                  </p>
                  <div className="max-h-[300px] overflow-y-auto border border-white/5 bg-zinc-950/40 rounded-2xl p-3.5 custom-scrollbar grid grid-cols-1 gap-1">
                    {transitionList.map((t) => (
                      <span key={t} className="font-mono text-[10px] text-white/80 hover:text-white py-1 border-b border-white/5 flex items-center justify-between">
                        {t} <ArrowRight className="w-2.5 h-2.5 opacity-40" />
                      </span>
                    ))}
                  </div>
                </div>

                {/* Intro Animations */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-xs font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-3.5 py-2 rounded-xl w-fit">
                    Hoạt cảnh Bắt đầu (Intro Animations)
                  </div>
                  <p className="text-[10px] text-muted-foreground leading-relaxed">
                    Chạy ngay khi phân cảnh bắt đầu xuất hiện trên màn hình.
                  </p>
                  <div className="max-h-[300px] overflow-y-auto border border-white/5 bg-zinc-950/40 rounded-2xl p-3.5 custom-scrollbar grid grid-cols-1 gap-1">
                    {introAnimList.map((i) => (
                      <span key={i} className="font-mono text-[10px] text-white/80 hover:text-white py-1 border-b border-white/5 flex items-center justify-between">
                        {i} <ArrowRight className="w-2.5 h-2.5 opacity-40" />
                      </span>
                    ))}
                  </div>
                </div>

                {/* Outro Animations */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-xs font-bold text-amber-400 bg-amber-500/10 border border-amber-500/20 px-3.5 py-2 rounded-xl w-fit">
                    Hoạt cảnh Kết thúc (Outro Animations)
                  </div>
                  <p className="text-[10px] text-muted-foreground leading-relaxed">
                    Chạy trước khi phân cảnh biến mất hoặc chuyển sang cảnh tiếp.
                  </p>
                  <div className="max-h-[300px] overflow-y-auto border border-white/5 bg-zinc-950/40 rounded-2xl p-3.5 custom-scrollbar grid grid-cols-1 gap-1">
                    {outroAnimList.map((o) => (
                      <span key={o} className="font-mono text-[10px] text-white/80 hover:text-white py-1 border-b border-white/5 flex items-center justify-between">
                        {o} <ArrowRight className="w-2.5 h-2.5 opacity-40" />
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
