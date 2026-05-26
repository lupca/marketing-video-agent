import { useState, useEffect } from "react";
import { 
  Settings, 
  Plus, 
  Trash2, 
  Edit3, 
  Check, 
  AlertCircle, 
  Loader2, 
  Globe, 
  Cpu, 
  Key, 
  ShieldCheck, 
  Activity,
  X,
  Volume2,
  ListMusic
} from "lucide-react";
import api from "../lib/api";
import { cn } from "../lib/utils";

interface LLMModelConfig {
  id: string;
  name: string;
  provider: string; // "openai" | "ollama" | "groq" | "anthropic"
  base_url: string;
  model_name: string;
  api_key?: string;
}

interface TTSModelConfig {
  id: string;
  name: string;
  provider: string; // "melotts" | "edge-tts" | "elevenlabs"
  base_url?: string;
  api_key?: string;
  model_name?: string;
}

export default function ModelSettings() {
  const [activeTab, setActiveTab] = useState<"llm" | "tts">("llm");
  
  // LLM States
  const [llmModels, setLlmModels] = useState<LLMModelConfig[]>([]);
  const [llmLoading, setLlmLoading] = useState(true);
  const [llmError, setLlmError] = useState<string | null>(null);

  // Global Routing State
  const [routing, setRouting] = useState({
    default_model_id: "",
    feature_routing: {
      leader_script_analysis: "",
      video_orchestrator: "",
      chat_assistant: ""
    }
  });
  const [isRoutingSaving, setIsRoutingSaving] = useState(false);

  // TTS States
  const [ttsModels, setTtsModels] = useState<TTSModelConfig[]>([]);
  const [ttsLoading, setTtsLoading] = useState(true);
  const [ttsError, setTtsError] = useState<string | null>(null);

  // LLM Modal State
  const [isLlmModalOpen, setIsLlmModalOpen] = useState(false);
  const [editingLlmModelId, setEditingLlmModelId] = useState<string | null>(null);
  const [llmFormData, setLlmFormData] = useState({
    name: "",
    provider: "ollama",
    base_url: "http://localhost:11434",
    model_name: "",
    api_key: ""
  });

  // TTS Modal State
  const [isTtsModalOpen, setIsTtsModalOpen] = useState(false);
  const [editingTtsModelId, setEditingTtsModelId] = useState<string | null>(null);
  const [ttsFormData, setTtsFormData] = useState({
    name: "",
    provider: "melotts",
    base_url: "http://localhost:8000",
    model_name: "",
    api_key: ""
  });

  // Action/UI States
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [testStatuses, setTestStatuses] = useState<Record<string, { status: "testing" | "ok" | "error"; message?: string }>>({});

  // Fetch LLM Models
  const fetchLlmModels = async () => {
    setLlmLoading(true);
    setLlmError(null);
    try {
      const res = await api.get("/api/system/chat-models");
      setLlmModels(res.data);
      
      const routingRes = await api.get("/api/system/llm-routing");
      setRouting(routingRes.data);
    } catch (err: any) {
      console.error("Failed to fetch LLM models:", err);
      setLlmError("Không thể tải danh sách mô hình LLM từ máy chủ.");
    } finally {
      setLlmLoading(false);
    }
  };

  // Fetch TTS Models
  const fetchTtsModels = async () => {
    setTtsLoading(true);
    setTtsError(null);
    try {
      const res = await api.get("/api/system/tts-models");
      setTtsModels(res.data);
    } catch (err: any) {
      console.error("Failed to fetch TTS models:", err);
      setTtsError("Không thể tải danh sách mô hình TTS từ máy chủ.");
    } finally {
      setTtsLoading(false);
    }
  };

  useEffect(() => {
    fetchLlmModels();
    fetchTtsModels();
  }, []);

  const saveRouting = async () => {
    setIsRoutingSaving(true);
    try {
      await api.put("/api/system/llm-routing", routing);
      alert("Cấu hình routing đã được cập nhật!");
    } catch (err) {
      console.error("Failed to save routing:", err);
      alert("Lỗi khi lưu cấu hình routing.");
    } finally {
      setIsRoutingSaving(false);
    }
  };

  // LLM CRUD
  const openAddLlmModal = () => {
    setEditingLlmModelId(null);
    setLlmFormData({
      name: "",
      provider: "ollama",
      base_url: "http://localhost:11434",
      model_name: "",
      api_key: ""
    });
    setIsLlmModalOpen(true);
  };

  const openEditLlmModal = (model: LLMModelConfig) => {
    setEditingLlmModelId(model.id);
    setLlmFormData({
      name: model.name,
      provider: model.provider || "ollama",
      base_url: model.base_url,
      model_name: model.model_name,
      api_key: model.api_key || ""
    });
    setIsLlmModalOpen(true);
  };

  const handleDeleteLlmModel = async (id: string) => {
    if (!confirm("Bạn có chắc chắn muốn xóa cấu hình mô hình LLM này không?")) return;
    
    try {
      await api.delete(`/api/system/chat-models/${id}`);
      setLlmModels((prev) => prev.filter((m) => m.id !== id));
      // Clean test status
      const updatedStatuses = { ...testStatuses };
      delete updatedStatuses[id];
      setTestStatuses(updatedStatuses);
    } catch (err: any) {
      console.error("Failed to delete LLM model:", err);
      alert("Không thể xóa mô hình LLM: " + (err.response?.data?.detail || err.message));
    }
  };

  const handleLlmSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      if (editingLlmModelId) {
        const res = await api.put(`/api/system/chat-models/${editingLlmModelId}`, llmFormData);
        setLlmModels((prev) => prev.map((m) => (m.id === editingLlmModelId ? res.data : m)));
      } else {
        const res = await api.post("/api/system/chat-models", llmFormData);
        setLlmModels((prev) => [...prev, res.data]);
      }
      setIsLlmModalOpen(false);
    } catch (err: any) {
      console.error("Failed to save LLM model:", err);
      alert("Không thể lưu cấu hình mô hình LLM: " + (err.response?.data?.detail || err.message));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleTestLlmConnection = async (model: LLMModelConfig) => {
    setTestStatuses((prev) => ({ ...prev, [model.id]: { status: "testing" } }));
    try {
      const res = await api.post("/api/system/chat-models/test", {
        name: model.name,
        base_url: model.base_url,
        model_name: model.model_name,
        api_key: model.api_key
      });
      
      if (res.data.status === "ok") {
        setTestStatuses((prev) => ({ 
          ...prev, 
          [model.id]: { status: "ok", message: res.data.message } 
        }));
      } else {
        setTestStatuses((prev) => ({ 
          ...prev, 
          [model.id]: { status: "error", message: res.data.message } 
        }));
      }
    } catch (err: any) {
      setTestStatuses((prev) => ({ 
        ...prev, 
        [model.id]: { status: "error", message: "Kiểm tra kết nối thất bại." } 
      }));
    }
  };

  // TTS CRUD
  const openAddTtsModal = () => {
    setEditingTtsModelId(null);
    setTtsFormData({
      name: "",
      provider: "melotts",
      base_url: "http://localhost:8000",
      model_name: "",
      api_key: ""
    });
    setIsTtsModalOpen(true);
  };

  const openEditTtsModal = (model: TTSModelConfig) => {
    setEditingTtsModelId(model.id);
    setTtsFormData({
      name: model.name,
      provider: model.provider,
      base_url: model.base_url || "",
      model_name: model.model_name || "",
      api_key: model.api_key || ""
    });
    setIsTtsModalOpen(true);
  };

  const handleDeleteTtsModel = async (id: string) => {
    if (!confirm("Bạn có chắc chắn muốn xóa cấu hình mô hình TTS này không?")) return;
    
    try {
      await api.delete(`/api/system/tts-models/${id}`);
      setTtsModels((prev) => prev.filter((m) => m.id !== id));
    } catch (err: any) {
      console.error("Failed to delete TTS model:", err);
      alert("Không thể xóa mô hình TTS: " + (err.response?.data?.detail || err.message));
    }
  };

  const handleTtsSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      if (editingTtsModelId) {
        const res = await api.put(`/api/system/tts-models/${editingTtsModelId}`, ttsFormData);
        setTtsModels((prev) => prev.map((m) => (m.id === editingTtsModelId ? res.data : m)));
      } else {
        const res = await api.post("/api/system/tts-models", ttsFormData);
        setTtsModels((prev) => [...prev, res.data]);
      }
      setIsTtsModalOpen(false);
    } catch (err: any) {
      console.error("Failed to save TTS model:", err);
      alert("Không thể lưu cấu hình mô hình TTS: " + (err.response?.data?.detail || err.message));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleTestTtsConnection = async (model: TTSModelConfig) => {
    setTestStatuses((prev) => ({ ...prev, [model.id]: { status: "testing" } }));
    try {
      const res = await api.post("/api/system/tts-models/test", {
        name: model.name,
        provider: model.provider,
        base_url: model.base_url,
        model_name: model.model_name,
        api_key: model.api_key
      });
      
      if (res.data.status === "ok") {
        setTestStatuses((prev) => ({ 
          ...prev, 
          [model.id]: { status: "ok", message: res.data.message } 
        }));
      } else {
        setTestStatuses((prev) => ({ 
          ...prev, 
          [model.id]: { status: "error", message: res.data.message } 
        }));
      }
    } catch (err: any) {
      setTestStatuses((prev) => ({ 
        ...prev, 
        [model.id]: { status: "error", message: "Kiểm tra kết nối thất bại." } 
      }));
    }
  };

  const handleProviderChange = (provider: string) => {
    let base_url = "";
    let model_name = "";
    if (provider === "melotts") {
      base_url = "http://localhost:8000";
    } else if (provider === "elevenlabs") {
      base_url = "https://api.elevenlabs.io";
      model_name = "eleven_flash_v2_5";
    }
    setTtsFormData({
      ...ttsFormData,
      provider,
      base_url,
      model_name
    });
  };

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/10 pb-6 shrink-0">
        <div className="flex items-center gap-3.5">
          <div className="p-3 bg-primary/20 rounded-2xl border border-primary/20 shadow-[0_0_20px_rgba(124,58,237,0.3)] text-primary">
            <Settings className="w-6 h-6 animate-spin-slow" />
          </div>
          <div>
            <h1 className="text-2xl font-extrabold text-white tracking-tight">Cấu Hình Mô Hình Hệ Thống</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Quản lý các mô hình ngôn ngữ lớn (LLM) và các nhà cung cấp chuyển đổi văn bản thành giọng nói (TTS).
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
            <Cpu className="w-4 h-4" /> Mô Hình LLM
          </button>
          <button
            onClick={() => setActiveTab("tts")}
            className={cn(
              "flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold transition-all cursor-pointer",
              activeTab === "tts" 
                ? "bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-lg shadow-violet-600/20" 
                : "text-muted-foreground hover:text-white"
            )}
          >
            <Volume2 className="w-4 h-4" /> Mô Hình TTS
          </button>
        </div>

        <button
          onClick={activeTab === "llm" ? openAddLlmModal : openAddTtsModal}
          className="flex items-center gap-2 px-5 py-3 bg-gradient-to-r from-violet-600 to-indigo-600 hover:scale-[1.02] active:scale-[0.98] transition-all rounded-xl text-xs font-bold text-white shadow-lg shadow-violet-600/20 cursor-pointer w-fit"
        >
          <Plus className="w-4 h-4" /> Thêm mô hình
        </button>
      </div>

      {/* LLM Tab Content */}
      {activeTab === "llm" && (
        <>
          {llmLoading ? (
            <div className="flex flex-col items-center justify-center min-h-[300px] gap-4">
              <Loader2 className="w-10 h-10 animate-spin text-primary" />
              <p className="text-sm text-muted-foreground font-semibold">Đang tải danh sách mô hình LLM...</p>
            </div>
          ) : llmError ? (
            <div className="p-6 bg-red-500/10 border border-red-500/20 rounded-3xl flex flex-col items-center gap-4 text-center max-w-md mx-auto">
              <AlertCircle className="w-12 h-12 text-red-500" />
              <div>
                <h3 className="text-base font-bold text-white">Lỗi tải dữ liệu</h3>
                <p className="text-xs text-muted-foreground mt-1">{llmError}</p>
              </div>
              <button 
                onClick={fetchLlmModels} 
                className="px-5 py-2.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-xs font-bold text-white transition-all"
              >
                Thử lại
              </button>
            </div>
          ) : llmModels.length === 0 ? (
            <div className="border border-dashed border-white/10 rounded-3xl p-12 text-center text-muted-foreground select-none max-w-lg mx-auto">
              <Cpu className="w-16 h-16 mx-auto opacity-20 mb-4 animate-pulse" />
              <h3 className="text-lg font-bold text-white mb-2">Chưa có mô hình LLM</h3>
              <p className="text-sm leading-relaxed max-w-sm mx-auto mb-6">
                Hệ thống chưa thiết lập các cấu hình model LLM. Hãy thêm một cấu hình mới để bắt đầu chat trong AI Studio.
              </p>
              <button
                onClick={openAddLlmModal}
                className="px-5 py-2.5 bg-primary hover:bg-primary/95 text-xs font-bold text-white rounded-xl cursor-pointer"
              >
                Tạo cấu hình đầu tiên
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-in fade-in duration-200">
              {llmModels.map((model) => {
                const test = testStatuses[model.id];
                const isOllama = model.provider === "ollama" || model.base_url.includes("11434");
                
                return (
                  <div 
                    key={model.id}
                    className="bg-black/40 border border-white/10 hover:border-white/20 transition-all duration-300 rounded-3xl p-6 backdrop-blur-xl flex flex-col justify-between group relative overflow-hidden"
                  >
                    <div className="space-y-4">
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-3">
                          <div className={cn(
                            "p-2.5 rounded-xl border",
                            isOllama 
                              ? "bg-amber-500/10 border-amber-500/20 text-amber-400" 
                              : "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
                          )}>
                            {isOllama ? <Cpu className="w-5 h-5" /> : <Globe className="w-5 h-5" />}
                          </div>
                          <div>
                            <h3 className="text-sm font-extrabold text-white tracking-tight">{model.name}</h3>
                            <span className="text-[9px] uppercase tracking-wider font-bold bg-white/5 border border-white/10 px-2 py-0.5 rounded text-muted-foreground">
                              {model.provider || (isOllama ? "Ollama" : "Cloud")}
                            </span>
                          </div>
                        </div>

                        {/* Actions Toolbar */}
                        <div className="flex gap-1 border border-white/5 p-1 bg-white/5 rounded-xl">
                          <button
                            onClick={() => openEditLlmModal(model)}
                            className="p-2 hover:bg-white/5 hover:text-white text-muted-foreground/70 rounded-lg transition-colors cursor-pointer"
                            title="Chỉnh sửa mô hình"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => handleDeleteLlmModel(model.id)}
                            className="p-2 hover:bg-red-500/10 hover:text-red-400 text-muted-foreground/70 rounded-lg transition-colors cursor-pointer"
                            title="Xóa cấu hình"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>

                      <div className="space-y-2 pt-2 border-t border-white/5">
                        <div className="flex justify-between items-center text-xs">
                          <span className="text-muted-foreground">Model Tag:</span>
                          <span className="font-mono text-white text-[11px] font-semibold">{model.model_name}</span>
                        </div>

                        <div className="flex justify-between items-center text-xs gap-4">
                          <span className="text-muted-foreground">Endpoint:</span>
                          <span className="font-mono text-white/90 text-[10px] truncate max-w-[240px]" title={model.base_url}>{model.base_url}</span>
                        </div>

                        <div className="flex justify-between items-center text-xs">
                          <span className="text-muted-foreground">API Key:</span>
                          {model.api_key ? (
                            <span className="flex items-center gap-1 text-[10px] text-emerald-400 font-semibold uppercase tracking-wider">
                              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" /> Được cấu hình
                            </span>
                          ) : (
                            <span className="text-[10px] text-muted-foreground/60 italic">Không có</span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Connection Test Section */}
                    <div className="pt-4 mt-4 border-t border-white/5 flex items-center justify-between gap-4">
                      <button
                        onClick={() => handleTestLlmConnection(model)}
                        disabled={test?.status === "testing"}
                        className={cn(
                          "flex items-center gap-2 px-4 py-2 rounded-xl text-[10px] font-bold transition-all cursor-pointer",
                          test?.status === "ok" 
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" 
                            : test?.status === "error"
                              ? "bg-red-500/10 text-red-400 border border-red-500/20"
                              : "bg-white/5 hover:bg-white/10 text-white border border-white/10"
                        )}
                      >
                        {test?.status === "testing" ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : test?.status === "ok" ? (
                          <Check className="w-3.5 h-3.5" />
                        ) : test?.status === "error" ? (
                          <AlertCircle className="w-3.5 h-3.5" />
                        ) : (
                          <Activity className="w-3.5 h-3.5" />
                        )}
                        {test?.status === "testing" ? "Đang thử..." : test?.status === "ok" ? "Kết nối tốt" : test?.status === "error" ? "Lỗi kết nối" : "Thử kết nối"}
                      </button>

                      {test?.message && (
                        <p className={cn(
                          "text-[9px] font-medium truncate max-w-[150px]",
                          test.status === "ok" ? "text-emerald-400/70" : "text-red-400/70"
                        )}>
                          {test.message}
                        </p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* LLM Routing Section */}
          {!llmLoading && llmModels.length > 0 && (
            <div className="bg-black/40 border border-white/10 rounded-3xl p-8 backdrop-blur-xl space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 mt-8">
              <div className="flex items-center gap-3 border-b border-white/5 pb-4">
                <div className="p-2 bg-indigo-500/10 border border-indigo-500/20 rounded-xl text-indigo-400">
                  <Activity className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-white tracking-tight">Điều Phối Model Toàn Hệ Thống (Routing)</h2>
                  <p className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">Xác định model mặc định cho từng tính năng AI</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* Default Model */}
                <div className="space-y-3">
                  <label className="text-sm font-bold text-white/80 block">Model Mặc Định Hệ Thống</label>
                  <p className="text-[11px] text-muted-foreground leading-relaxed">Dùng cho tất cả các tính năng nếu không có cấu hình cụ thể.</p>
                  <select
                    value={routing.default_model_id}
                    onChange={(e) => setRouting({...routing, default_model_id: e.target.value})}
                    className="w-full bg-zinc-900 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary/40 transition-all cursor-pointer"
                  >
                    <option value="">-- Chọn Model --</option>
                    {llmModels.map(m => (
                      <option key={m.id} value={m.id}>{m.name} ({m.model_name})</option>
                    ))}
                  </select>
                </div>

                <div className="space-y-6">
                  {/* Leader Agent Routing */}
                  <div className="space-y-2">
                    <label className="text-xs font-bold text-white/70 block uppercase tracking-wider">Leader Agent (Script Analysis)</label>
                    <select
                      value={routing.feature_routing.leader_script_analysis}
                      onChange={(e) => setRouting({
                        ...routing, 
                        feature_routing: {...routing.feature_routing, leader_script_analysis: e.target.value}
                      })}
                      className="w-full bg-zinc-900 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:ring-1 focus:ring-primary/30 cursor-pointer"
                    >
                      <option value="">-- Dùng Model Mặc Định --</option>
                      {llmModels.map(m => (
                        <option key={m.id} value={m.id}>{m.name}</option>
                      ))}
                    </select>
                  </div>

                  {/* Video Orchestrator Routing */}
                  <div className="space-y-2">
                    <label className="text-xs font-bold text-white/70 block uppercase tracking-wider">Video Orchestrator Agent</label>
                    <select
                      value={routing.feature_routing.video_orchestrator}
                      onChange={(e) => setRouting({
                        ...routing, 
                        feature_routing: {...routing.feature_routing, video_orchestrator: e.target.value}
                      })}
                      className="w-full bg-zinc-900 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:ring-1 focus:ring-primary/30 cursor-pointer"
                    >
                      <option value="">-- Dùng Model Mặc Định --</option>
                      {llmModels.map(m => (
                        <option key={m.id} value={m.id}>{m.name}</option>
                      ))}
                    </select>
                  </div>

                  {/* Chat Assistant Routing */}
                  <div className="space-y-2">
                    <label className="text-xs font-bold text-white/70 block uppercase tracking-wider">AI Chat Assistant</label>
                    <select
                      value={routing.feature_routing.chat_assistant}
                      onChange={(e) => setRouting({
                        ...routing, 
                        feature_routing: {...routing.feature_routing, chat_assistant: e.target.value}
                      })}
                      className="w-full bg-zinc-900 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:ring-1 focus:ring-primary/30 cursor-pointer"
                    >
                      <option value="">-- Dùng Model Mặc Định --</option>
                      {llmModels.map(m => (
                        <option key={m.id} value={m.id}>{m.name}</option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              <div className="pt-4 flex justify-end">
                <button
                  onClick={saveRouting}
                  disabled={isRoutingSaving}
                  className="flex items-center gap-2 px-6 py-3 bg-white text-black hover:bg-white/90 disabled:opacity-50 transition-all rounded-xl text-xs font-bold shadow-xl cursor-pointer"
                >
                  {isRoutingSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
                  Lưu Cấu Hình Routing
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {/* TTS Tab Content */}
      {activeTab === "tts" && (
        <>
          {ttsLoading ? (
            <div className="flex flex-col items-center justify-center min-h-[300px] gap-4">
              <Loader2 className="w-10 h-10 animate-spin text-primary" />
              <p className="text-sm text-muted-foreground font-semibold">Đang tải danh sách mô hình TTS...</p>
            </div>
          ) : ttsError ? (
            <div className="p-6 bg-red-500/10 border border-red-500/20 rounded-3xl flex flex-col items-center gap-4 text-center max-w-md mx-auto">
              <AlertCircle className="w-12 h-12 text-red-500" />
              <div>
                <h3 className="text-base font-bold text-white">Lỗi tải dữ liệu</h3>
                <p className="text-xs text-muted-foreground mt-1">{ttsError}</p>
              </div>
              <button 
                onClick={fetchTtsModels} 
                className="px-5 py-2.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-xs font-bold text-white transition-all"
              >
                Thử lại
              </button>
            </div>
          ) : ttsModels.length === 0 ? (
            <div className="border border-dashed border-white/10 rounded-3xl p-12 text-center text-muted-foreground select-none max-w-lg mx-auto">
              <ListMusic className="w-16 h-16 mx-auto opacity-20 mb-4 animate-pulse" />
              <h3 className="text-lg font-bold text-white mb-2">Chưa có mô hình TTS</h3>
              <p className="text-sm leading-relaxed max-w-sm mx-auto mb-6">
                Hệ thống chưa thiết lập các cấu hình TTS. Hãy thêm một cấu hình mới để bắt đầu tạo giọng nói thuyết minh.
              </p>
              <button
                onClick={openAddTtsModal}
                className="px-5 py-2.5 bg-primary hover:bg-primary/95 text-xs font-bold text-white rounded-xl cursor-pointer"
              >
                Tạo cấu hình đầu tiên
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-in fade-in duration-200">
              {ttsModels.map((model) => {
                const test = testStatuses[model.id];
                const isElevenLabs = model.provider === "elevenlabs";
                
                return (
                  <div 
                    key={model.id}
                    className="bg-black/40 border border-white/10 hover:border-white/20 transition-all duration-300 rounded-3xl p-6 backdrop-blur-xl flex flex-col justify-between group relative overflow-hidden"
                  >
                    <div className="space-y-4">
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-3">
                          <div className={cn(
                            "p-2.5 rounded-xl border",
                            model.provider === "melotts" 
                              ? "bg-violet-500/10 border-violet-500/20 text-violet-400" 
                              : model.provider === "elevenlabs"
                                ? "bg-pink-500/10 border-pink-500/20 text-pink-400"
                                : "bg-sky-500/10 border-sky-500/20 text-sky-400"
                          )}>
                            <Volume2 className="w-5 h-5" />
                          </div>
                          <div>
                            <h3 className="text-sm font-extrabold text-white tracking-tight">{model.name}</h3>
                            <span className="text-[9px] uppercase tracking-wider font-bold bg-white/5 border border-white/10 px-2 py-0.5 rounded text-muted-foreground">
                              {model.provider === "melotts" ? "MeloTTS Local" : model.provider === "elevenlabs" ? "ElevenLabs Cloud" : "Microsoft Edge-TTS"}
                            </span>
                          </div>
                        </div>

                        {/* Actions Toolbar */}
                        <div className="flex gap-1 border border-white/5 p-1 bg-white/5 rounded-xl">
                          <button
                            onClick={() => openEditTtsModal(model)}
                            className="p-2 hover:bg-white/5 hover:text-white text-muted-foreground/70 rounded-lg transition-colors cursor-pointer"
                            title="Chỉnh sửa mô hình TTS"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => handleDeleteTtsModel(model.id)}
                            className="p-2 hover:bg-red-500/10 hover:text-red-400 text-muted-foreground/70 rounded-lg transition-colors cursor-pointer"
                            title="Xóa mô hình TTS"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>

                      <div className="space-y-2 pt-2 border-t border-white/5">
                        {/* Provider */}
                        <div className="flex justify-between items-center text-xs">
                          <span className="text-muted-foreground">Provider:</span>
                          <span className="font-semibold text-white capitalize">{model.provider}</span>
                        </div>

                        {/* Model name (Only for cloud/elevenlabs) */}
                        {model.model_name && (
                          <div className="flex justify-between items-center text-xs">
                            <span className="text-muted-foreground">Mô hình:</span>
                            <span className="font-mono text-white text-[11px] font-semibold">{model.model_name}</span>
                          </div>
                        )}

                        {/* Base URL (Only if present) */}
                        {model.base_url && (
                          <div className="flex justify-between items-center text-xs gap-4">
                            <span className="text-muted-foreground">Endpoint:</span>
                            <span className="font-mono text-white/90 text-[10px] truncate max-w-[240px]" title={model.base_url}>{model.base_url}</span>
                          </div>
                        )}

                        {/* API Key Status (Only for ElevenLabs) */}
                        {isElevenLabs && (
                          <div className="flex justify-between items-center text-xs">
                            <span className="text-muted-foreground">API Key:</span>
                            {model.api_key ? (
                              <span className="flex items-center gap-1 text-[10px] text-emerald-400 font-semibold uppercase tracking-wider">
                                <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" /> Đã lưu an toàn
                              </span>
                            ) : (
                              <span className="text-[10px] text-muted-foreground/60 italic">Chưa nhập</span>
                            )}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Connection Test Section */}
                    <div className="pt-4 mt-4 border-t border-white/5 flex items-center justify-between gap-4">
                      <button
                        onClick={() => handleTestTtsConnection(model)}
                        disabled={test?.status === "testing"}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-white/5 hover:bg-white/10 text-[10px] font-bold uppercase tracking-wider text-white border border-white/10 rounded-lg transition-all cursor-pointer"
                      >
                        {test?.status === "testing" ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <Activity className="w-3 h-3 text-primary animate-pulse" />
                        )}
                        Test mô hình
                      </button>

                      {test && (
                        <div className="flex-1 text-right overflow-hidden">
                          {test.status === "testing" && (
                            <span className="text-[10px] text-primary animate-pulse">Đang kết nối...</span>
                          )}
                          {test.status === "ok" && (
                            <span className="text-[10px] text-emerald-400 font-semibold tracking-wide flex items-center justify-end gap-1">
                              <Check className="w-3.5 h-3.5" /> OK
                            </span>
                          )}
                          {test.status === "error" && (
                            <span className="text-[9px] text-red-400 font-medium line-clamp-1 block" title={test.message}>
                              Lỗi: {test.message}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* LLM Model Modal */}
      {isLlmModalOpen && (
        <div className="fixed inset-0 flex items-center justify-center z-50 p-4">
          <div onClick={() => setIsLlmModalOpen(false)} className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity" />
          <div className="bg-zinc-950 border border-white/10 rounded-3xl w-full max-w-md p-6 relative z-10 shadow-2xl animate-in zoom-in-95 duration-200">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-lg font-extrabold text-white tracking-tight">
                {editingLlmModelId ? "Sửa cấu hình Model LLM" : "Thêm cấu hình Model LLM"}
              </h2>
              <button onClick={() => setIsLlmModalOpen(false)} className="p-1 text-muted-foreground hover:text-white rounded-lg hover:bg-white/5 transition-colors cursor-pointer">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleLlmSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground">Tên hiển thị (Friendly Name) *</label>
                <input
                  type="text"
                  required
                  value={llmFormData.name}
                  onChange={(e) => setLlmFormData({ ...llmFormData, name: e.target.value })}
                  placeholder="Ví dụ: Qwen 2.5 3B Local"
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white placeholder:text-muted-foreground/45 focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground">Nhà cung cấp (Provider) *</label>
                <select
                  value={llmFormData.provider}
                  onChange={(e) => setLlmFormData({ ...llmFormData, provider: e.target.value })}
                  className="w-full bg-zinc-900 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer"
                >
                  <option value="ollama">Ollama (Local)</option>
                  <option value="openai">OpenAI (Hoặc OpenAI-Compatible Cloud)</option>
                  <option value="groq">Groq (Siêu tốc)</option>
                  <option value="anthropic">Anthropic (Claude)</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground">Endpoint URL (Base URL) *</label>
                <input
                  type="text"
                  required
                  value={llmFormData.base_url}
                  onChange={(e) => setLlmFormData({ ...llmFormData, base_url: e.target.value })}
                  placeholder="Ví dụ: http://localhost:11434 hoặc https://api.openai.com"
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white placeholder:text-muted-foreground/45 focus:outline-none focus:ring-1 focus:ring-primary font-mono text-[11px]"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground">Mã định danh mô hình (Model Name) *</label>
                <input
                  type="text"
                  required
                  value={llmFormData.model_name}
                  onChange={(e) => setLlmFormData({ ...llmFormData, model_name: e.target.value })}
                  placeholder="Ví dụ: qwen2.5:3b hoặc gpt-4o"
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white placeholder:text-muted-foreground/45 focus:outline-none focus:ring-1 focus:ring-primary font-mono text-[11px]"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground flex items-center gap-1">
                  <Key className="w-3.5 h-3.5 text-primary" /> API Key (Nếu có)
                </label>
                <input
                  type="password"
                  value={llmFormData.api_key}
                  onChange={(e) => setLlmFormData({ ...llmFormData, api_key: e.target.value })}
                  placeholder="Để trống nếu là Ollama local, điền key nếu là Cloud"
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white placeholder:text-muted-foreground/45 focus:outline-none focus:ring-1 focus:ring-primary text-[11px]"
                />
              </div>

              <div className="flex gap-3 pt-4 border-t border-white/5 mt-6">
                <button type="button" onClick={() => setIsLlmModalOpen(false)} className="flex-1 py-3 bg-white/5 hover:bg-white/10 text-xs font-bold text-white border border-white/10 rounded-xl transition-all cursor-pointer">
                  Hủy
                </button>
                <button type="submit" disabled={isSubmitting} className="flex-1 py-3 bg-gradient-to-r from-violet-600 to-indigo-600 hover:scale-[1.02] active:scale-[0.98] text-xs font-bold text-white rounded-xl transition-all cursor-pointer shadow-lg shadow-violet-600/20">
                  {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : (editingLlmModelId ? "Cập nhật" : "Lưu cấu hình")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* TTS Model Modal */}
      {isTtsModalOpen && (
        <div className="fixed inset-0 flex items-center justify-center z-50 p-4">
          <div onClick={() => setIsTtsModalOpen(false)} className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity" />
          <div className="bg-zinc-950 border border-white/10 rounded-3xl w-full max-w-md p-6 relative z-10 shadow-2xl animate-in zoom-in-95 duration-200">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-lg font-extrabold text-white tracking-tight">
                {editingTtsModelId ? "Sửa cấu hình Model TTS" : "Thêm cấu hình Model TTS"}
              </h2>
              <button onClick={() => setIsTtsModalOpen(false)} className="p-1 text-muted-foreground hover:text-white rounded-lg hover:bg-white/5 transition-colors cursor-pointer">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleTtsSubmit} className="space-y-4">
              {/* Name */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground">Tên hiển thị *</label>
                <input
                  type="text"
                  required
                  value={ttsFormData.name}
                  onChange={(e) => setTtsFormData({ ...ttsFormData, name: e.target.value })}
                  placeholder="Ví dụ: ElevenLabs Viết Nam"
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white placeholder:text-muted-foreground/45 focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              {/* Provider Selection */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground">Loại Provider *</label>
                <select
                  value={ttsFormData.provider}
                  onChange={(e) => handleProviderChange(e.target.value)}
                  className="w-full bg-zinc-900 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value="melotts">MeloTTS (Chạy Offline Local)</option>
                  <option value="edge-tts">Microsoft Edge-TTS (Đám mây miễn phí)</option>
                  <option value="elevenlabs">ElevenLabs TTS (Đám mây cao cấp)</option>
                </select>
              </div>

              {/* Base URL (except edge-tts) */}
              {ttsFormData.provider !== "edge-tts" && (
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-muted-foreground">Base URL (Endpoint API) *</label>
                  <input
                    type="text"
                    required
                    value={ttsFormData.base_url}
                    onChange={(e) => setTtsFormData({ ...ttsFormData, base_url: e.target.value })}
                    placeholder={ttsFormData.provider === "melotts" ? "Ví dụ: http://localhost:8000" : "Ví dụ: https://api.elevenlabs.io"}
                    className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white placeholder:text-muted-foreground/45 focus:outline-none focus:ring-1 focus:ring-primary font-mono text-[11px]"
                  />
                </div>
              )}

              {/* Model Tag (Only for ElevenLabs) */}
              {ttsFormData.provider === "elevenlabs" && (
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-muted-foreground">Mã Model (Model ID) *</label>
                  <input
                    type="text"
                    required
                    value={ttsFormData.model_name}
                    onChange={(e) => setTtsFormData({ ...ttsFormData, model_name: e.target.value })}
                    placeholder="Ví dụ: eleven_flash_v2_5 hoặc eleven_multilingual_v2"
                    className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white placeholder:text-muted-foreground/45 focus:outline-none focus:ring-1 focus:ring-primary font-mono text-[11px]"
                  />
                </div>
              )}

              {/* API Key (Only for ElevenLabs) */}
              {ttsFormData.provider === "elevenlabs" && (
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-muted-foreground flex items-center gap-1">
                    <Key className="w-3.5 h-3.5 text-primary" /> API Key của ElevenLabs *
                  </label>
                  <input
                    type="password"
                    required
                    value={ttsFormData.api_key}
                    onChange={(e) => setTtsFormData({ ...ttsFormData, api_key: e.target.value })}
                    placeholder="Nhập sk_... ElevenLabs API Key"
                    className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white placeholder:text-muted-foreground/45 focus:outline-none focus:ring-1 focus:ring-primary text-[11px]"
                  />
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-3 pt-4 border-t border-white/5 mt-6">
                <button type="button" onClick={() => setIsTtsModalOpen(false)} className="flex-1 py-3 bg-white/5 hover:bg-white/10 text-xs font-bold text-white border border-white/10 rounded-xl transition-all cursor-pointer">
                  Hủy
                </button>
                <button type="submit" disabled={isSubmitting} className="flex-1 py-3 bg-gradient-to-r from-violet-600 to-indigo-600 hover:scale-[1.02] active:scale-[0.98] text-xs font-bold text-white rounded-xl transition-all cursor-pointer shadow-lg shadow-violet-600/20">
                  {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : (editingTtsModelId ? "Cập nhật" : "Lưu cấu hình")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
