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
  Info,
  GraduationCap,
  Database,
  AlertCircle
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

interface DifySettings {
  base_url: string;
  api_key: string;
  dataset_id: string;
  source: string;
}

interface CapCutDraft {
  id: string;
  name: string;
  updated_at: number;
  status?: "idle" | "learning" | "success" | "failed";
  error?: string;
  learned_at?: string;
  template_name?: string;
}

export default function CapCutSettings() {
  const [activeTab, setActiveTab] = useState<"llm" | "skills" | "learning">("llm");
  
  // Settings & Models state
  const [settings, setSettings] = useState<CapCutSettings>({
    selected_model_id: "default",
    custom_base_url: "",
    custom_model_name: "",
    custom_api_key: "",
    source: "environment"
  });
  const [models, setModels] = useState<LLMModelConfig[]>([]);
  const [difySettings, setDifySettings] = useState<DifySettings>({
    base_url: "https://api.dify.ai/v1",
    api_key: "",
    dataset_id: "",
    source: "environment"
  });
  const [drafts, setDrafts] = useState<CapCutDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  
  const [savingDify, setSavingDify] = useState(false);
  const [difySaveSuccess, setDifySaveSuccess] = useState(false);
  const [learningDraftId, setLearningDraftId] = useState<string | null>(null);
  const [learnSuccessMsg, setLearnSuccessMsg] = useState<string | null>(null);

  // Fetch CapCut Settings, LLM Models, Dify settings, and local CapCut Drafts list
  const fetchData = async () => {
    setLoading(true);
    try {
      const [settingsRes, modelsRes, difyRes, draftsRes] = await Promise.all([
        api.get("/api/system/capcut-settings"),
        api.get("/api/system/chat-models"),
        api.get("/api/system/dify-settings"),
        api.get("/api/system/capcut-drafts")
      ]);
      setSettings(settingsRes.data);
      setModels(modelsRes.data);
      setDifySettings(difyRes.data);
      setDrafts(draftsRes.data);
    } catch (err) {
      console.error("Failed to fetch CapCut / Dify settings:", err);
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

  const handleSaveDify = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingDify(true);
    setDifySaveSuccess(false);
    try {
      const res = await api.put("/api/system/dify-settings", difySettings);
      setDifySettings(res.data);
      setDifySaveSuccess(true);
      setTimeout(() => setDifySaveSuccess(false), 2000);
    } catch (err) {
      console.error("Failed to save Dify settings:", err);
      alert("Lỗi khi lưu cấu hình Dify!");
    } finally {
      setSavingDify(false);
    }
  };

  const handleLearnTemplate = async (draftId: string) => {
    setLearningDraftId(draftId);
    setLearnSuccessMsg(null);
    try {
      const res = await api.post("/api/system/templates/learn", {
        draft_id: draftId,
        dataset_id: difySettings.dataset_id
      });
      if (res.data.status === "dispatched") {
        setLearnSuccessMsg(`Đã kích hoạt tiến trình học cho Template: ${draftId}. Đang xử lý dưới nền...`);
        
        // Polling function to get progress updates
        let pollCount = 0;
        const intervalId = setInterval(async () => {
          try {
            const draftsRes = await api.get("/api/system/capcut-drafts");
            setDrafts(draftsRes.data);
            
            const updatedDraft = draftsRes.data.find((x: any) => x.id === draftId);
            pollCount++;
            
            // Stop polling if the status is no longer "learning" (either success or failed) or after 20 attempts (40s)
            if ((updatedDraft && updatedDraft.status !== "learning") || pollCount >= 20) {
              clearInterval(intervalId);
            }
          } catch (e) {
            clearInterval(intervalId);
          }
        }, 2000);
      }
    } catch (err: any) {
      console.error("Failed to trigger template learning:", err);
      const errMsg = err.response?.data?.detail || "Lỗi kết nối server!";
      alert(`Không thể kích hoạt tiến trình học: ${errMsg}`);
    } finally {
      setLearningDraftId(null);
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
          <button
            onClick={() => setActiveTab("learning")}
            className={cn(
              "flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold transition-all cursor-pointer",
              activeTab === "learning" 
                ? "bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-lg shadow-violet-600/20" 
                : "text-muted-foreground hover:text-white"
            )}
          >
            <GraduationCap className="w-4 h-4" /> Học Template
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

          {activeTab === "learning" && (
            <div className="space-y-6 animate-in fade-in duration-200">
              {/* Dify Settings Form */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                  <form onSubmit={handleSaveDify} className="bg-black/40 border border-white/10 rounded-3xl p-6 backdrop-blur-xl space-y-6">
                    <div className="flex items-center gap-2 pb-4 border-b border-white/5">
                      <Database className="w-5 h-5 text-violet-400" />
                      <h3 className="text-sm font-extrabold text-white">Kết Nối Dify RAG Knowledge Base</h3>
                    </div>

                    <div className="space-y-4">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-1.5">
                          <label className="text-xs font-semibold text-muted-foreground">Dify API Endpoint *</label>
                          <input
                            type="text"
                            required
                            value={difySettings.base_url}
                            onChange={(e) => setDifySettings({ ...difySettings, base_url: e.target.value })}
                            placeholder="Ví dụ: https://api.dify.ai/v1"
                            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 text-xs text-white placeholder:text-muted-foreground/45 focus:outline-none focus:ring-1 focus:ring-primary font-mono text-[11px]"
                          />
                        </div>

                        <div className="space-y-1.5">
                          <label className="text-xs font-semibold text-muted-foreground">Dataset ID (Knowledge Base ID) *</label>
                          <input
                            type="text"
                            required
                            value={difySettings.dataset_id}
                            onChange={(e) => setDifySettings({ ...difySettings, dataset_id: e.target.value })}
                            placeholder="Nhập Dataset ID (UUID) của Dify"
                            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 text-xs text-white placeholder:text-muted-foreground/45 focus:outline-none focus:ring-1 focus:ring-primary font-mono text-[11px]"
                          />
                          <p className="text-[9px] text-muted-foreground/75 leading-relaxed mt-1">
                            Lưu ý: Dataset ID bắt buộc phải là chuỗi <strong>UUID (36 ký tự, ví dụ: 8fbe5f8e-d99c-4977-bc6d-0bb291a5ef8c)</strong> lấy từ thanh địa chỉ trình duyệt khi xem Dataset trong Dify, KHÔNG PHẢI tên Dataset.
                          </p>
                        </div>
                      </div>

                      <div className="space-y-1.5">
                        <label className="text-xs font-semibold text-muted-foreground">Dify Dataset API Key (Bearer Token) *</label>
                        <input
                          type="password"
                          required
                          value={difySettings.api_key}
                          onChange={(e) => setDifySettings({ ...difySettings, api_key: e.target.value })}
                          placeholder="Nhập API Key của Dify Dataset (không phải API key của chat)"
                          className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 text-xs text-white placeholder:text-muted-foreground/45 focus:outline-none focus:ring-1 focus:ring-primary text-[11px]"
                        />
                      </div>
                    </div>

                    <div className="pt-4 border-t border-white/5 flex justify-end">
                      <button
                        type="submit"
                        disabled={savingDify}
                        className={cn(
                          "flex items-center gap-2 px-6 py-3 rounded-xl text-xs font-bold text-white transition-all cursor-pointer",
                          difySaveSuccess 
                            ? "bg-emerald-600 shadow-lg shadow-emerald-600/20" 
                            : "bg-gradient-to-r from-violet-600 to-indigo-600 hover:scale-[1.02] active:scale-[0.98] shadow-lg shadow-violet-600/20"
                        )}
                      >
                        {savingDify ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : difySaveSuccess ? (
                          <Check className="w-4 h-4" />
                        ) : (
                          <Activity className="w-4 h-4" />
                        )}
                        {difySaveSuccess ? "Đã kết nối thành công!" : "Lưu cấu hình Dify"}
                      </button>
                    </div>
                  </form>
                </div>

                <div className="bg-black/40 border border-white/10 rounded-3xl p-6 backdrop-blur-xl">
                  <div className="flex items-center gap-2 pb-4 border-b border-white/5 text-violet-400">
                    <Info className="w-5 h-5" />
                    <h3 className="text-sm font-extrabold text-white">Cơ Chế Học Dify RAG</h3>
                  </div>
                  <div className="space-y-4 text-xs leading-relaxed text-muted-foreground pt-4">
                    <p>
                      Hệ thống tự động đồng bộ hóa bản dịch ngược (Blueprint) của các dự án CapCut bạn chọn sang Dify Knowledge Base.
                    </p>
                    <p>
                      Dify sẽ sử dụng model nhúng <strong>bge-m3</strong> để lưu trữ các Blueprint này dưới dạng Vector.
                    </p>
                    <p>
                      Mỗi khi tạo kịch bản mới, Dify RAG sẽ tự động chọn Template phù hợp nhất để dựng hình ảnh và kỹ xảo tương đương!
                    </p>
                  </div>
                </div>
              </div>

              {/* Ingestion Draft List */}
              <div className="bg-black/40 border border-white/10 rounded-3xl p-6 backdrop-blur-xl space-y-6">
                <div className="flex items-center justify-between pb-4 border-b border-white/5">
                  <div className="flex items-center gap-2">
                    <GraduationCap className="w-5 h-5 text-violet-400" />
                    <h3 className="text-sm font-extrabold text-white">Quét Thư Mục Nháp CapCut Sẵn Có</h3>
                  </div>
                  <button 
                    onClick={fetchData}
                    className="px-4 py-1.5 bg-white/5 border border-white/10 hover:bg-white/10 rounded-xl text-[10px] font-bold text-white transition-all cursor-pointer"
                  >
                    Làm mới danh sách
                  </button>
                </div>

                {learnSuccessMsg && (
                  <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold rounded-2xl animate-in fade-in duration-200">
                    {learnSuccessMsg}
                  </div>
                )}

                {drafts.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-10 gap-3 border border-dashed border-white/10 rounded-2xl">
                    <Info className="w-8 h-8 text-muted-foreground/40" />
                    <p className="text-xs text-muted-foreground">Không phát hiện dự án nháp CapCut nào trong thư mục cấu hình của bạn.</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {drafts.map((d) => {
                      const isLearning = d.status === "learning" || learningDraftId === d.id;
                      return (
                        <div key={d.id} className={cn(
                          "p-5 bg-zinc-900/40 border rounded-3xl flex flex-col justify-between gap-4 transition-all relative overflow-hidden",
                          d.status === "success" ? "border-emerald-500/20 hover:border-emerald-500/30 bg-emerald-950/5" :
                          d.status === "failed" ? "border-rose-500/20 hover:border-rose-500/30 bg-rose-950/5" :
                          isLearning ? "border-violet-500/20 hover:border-violet-500/30 bg-violet-950/5" :
                          "border-white/5 hover:border-white/10"
                        )}>
                          <div className="flex justify-between items-start gap-3">
                            <div className="space-y-1.5 flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <h4 className="text-xs font-bold text-white font-mono break-all">{d.name}</h4>
                                {d.template_name && d.template_name !== d.name && (
                                  <span className="px-2 py-0.5 bg-white/5 text-[9px] rounded-lg text-muted-foreground font-semibold">
                                    {d.template_name}
                                  </span>
                                )}
                              </div>
                              <p className="text-[10px] text-muted-foreground">
                                Cập nhật: {new Date(d.updated_at * 1000).toLocaleString("vi-VN")}
                              </p>
                              {d.learned_at && (
                                <p className="text-[9px] text-muted-foreground/75">
                                  Học lúc: {new Date(d.learned_at).toLocaleString("vi-VN")}
                                </p>
                              )}
                            </div>

                            {/* Status Badge */}
                            <div className="shrink-0">
                              {d.status === "success" && (
                                <span className="flex items-center gap-1 px-2.5 py-1 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-bold rounded-xl">
                                  <Check className="w-3 h-3" /> Đã học
                                </span>
                              )}
                              {d.status === "failed" && (
                                <span className="flex items-center gap-1 px-2.5 py-1 bg-rose-500/10 border border-rose-500/20 text-rose-400 text-[10px] font-bold rounded-xl">
                                  <AlertCircle className="w-3 h-3" /> Lỗi học
                                </span>
                              )}
                              {isLearning && (
                                <span className="flex items-center gap-1 px-2.5 py-1 bg-violet-500/10 border border-violet-500/20 text-violet-400 text-[10px] font-bold rounded-xl animate-pulse">
                                  <Loader2 className="w-3.5 h-3.5 animate-spin" /> Đang học...
                                </span>
                              )}
                              {(d.status === "idle" || !d.status) && !isLearning && (
                                <span className="flex items-center gap-1 px-2.5 py-1 bg-zinc-800 border border-white/5 text-muted-foreground text-[10px] font-semibold rounded-xl">
                                  Chưa học
                                </span>
                              )}
                            </div>
                          </div>

                          {/* Error traceback if failed */}
                          {d.status === "failed" && d.error && (
                            <div className="p-3.5 bg-rose-500/5 border border-rose-500/10 rounded-2xl text-[10px] text-rose-400 leading-relaxed break-words font-medium">
                              <strong>Lỗi:</strong> {d.error}
                            </div>
                          )}

                          <div className="flex justify-end pt-2 border-t border-white/5">
                            <button
                              onClick={() => handleLearnTemplate(d.id)}
                              disabled={isLearning}
                              className={cn(
                                "flex items-center gap-1.5 px-4 py-2 text-[10px] font-bold text-white rounded-xl cursor-pointer transition-all shrink-0 active:scale-[0.98]",
                                d.status === "success" 
                                  ? "bg-white/5 border border-white/10 hover:bg-white/10"
                                  : "bg-gradient-to-r from-violet-600 to-indigo-600 hover:scale-[1.02] disabled:opacity-50"
                              )}
                            >
                              {isLearning ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              ) : (
                                <GraduationCap className="w-3.5 h-3.5" />
                              )}
                              {d.status === "success" ? "Học lại" : "Học Template"}
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
