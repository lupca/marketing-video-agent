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
  X
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

export default function ModelSettings() {
  const [models, setModels] = useState<LLMModelConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal Form State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingModelId, setEditingModelId] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    name: "",
    base_url: "http://localhost:11434",
    model_name: "",
    api_key: ""
  });

  // Action/UI States
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [testStatuses, setTestStatuses] = useState<Record<string, { status: "testing" | "ok" | "error"; message?: string }>>({});

  // Fetch models on mount
  const fetchModels = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get("/api/system/chat-models");
      setModels(res.data);
    } catch (err: any) {
      console.error("Failed to fetch LLM models:", err);
      setError("Không thể tải danh sách cấu hình model từ máy chủ.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchModels();
  }, []);

  const openAddModal = () => {
    setEditingModelId(null);
    setFormData({
      name: "",
      base_url: "http://localhost:11434",
      model_name: "",
      api_key: ""
    });
    setIsModalOpen(true);
  };

  const openEditModal = (model: LLMModelConfig) => {
    setEditingModelId(model.id);
    setFormData({
      name: model.name,
      base_url: model.base_url,
      model_name: model.model_name,
      api_key: model.api_key || ""
    });
    setIsModalOpen(true);
  };

  const handleDeleteModel = async (id: string) => {
    if (!confirm("Bạn có chắc chắn muốn xóa cấu hình mô hình này không?")) return;
    
    try {
      await api.delete(`/api/system/chat-models/${id}`);
      setModels((prev) => prev.filter((m) => m.id !== id));
      // Clean test status
      const updatedStatuses = { ...testStatuses };
      delete updatedStatuses[id];
      setTestStatuses(updatedStatuses);
    } catch (err: any) {
      console.error("Failed to delete model:", err);
      alert("Không thể xóa mô hình: " + (err.response?.data?.detail || err.message));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim() || !formData.base_url.trim() || !formData.model_name.trim()) {
      alert("Vui lòng điền đầy đủ các thông tin bắt buộc!");
      return;
    }

    setIsSubmitting(true);
    try {
      if (editingModelId) {
        // Update
        const res = await api.put(`/api/system/chat-models/${editingModelId}`, formData);
        setModels((prev) => prev.map((m) => m.id === editingModelId ? res.data : m));
      } else {
        // Create
        const res = await api.post("/api/system/chat-models", formData);
        setModels((prev) => [...prev, res.data]);
      }
      setIsModalOpen(false);
    } catch (err: any) {
      console.error("Failed to save LLM model:", err);
      alert("Lỗi khi lưu cấu hình: " + (err.response?.data?.detail || err.message));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleTestConnection = async (model: LLMModelConfig) => {
    setTestStatuses((prev) => ({ ...prev, [model.id]: { status: "testing" } }));
    
    try {
      const res = await api.post("/api/system/chat-models/test", {
        name: model.name,
        base_url: model.base_url,
        model_name: model.model_name,
        api_key: model.api_key || ""
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
        [model.id]: { status: "error", message: "Kết nối thất bại hoặc quá thời gian chờ." } 
      }));
    }
  };

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 pb-6 shrink-0">
        <div className="flex items-center gap-3.5">
          <div className="p-3 bg-primary/20 rounded-2xl border border-primary/20 shadow-[0_0_20px_rgba(124,58,237,0.3)] text-primary">
            <Settings className="w-6 h-6 animate-spin-slow" />
          </div>
          <div>
            <h1 className="text-2xl font-extrabold text-white tracking-tight">Cấu Hình Mô Hình LLM</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Quản lý các mô hình ngôn ngữ lớn (Ollama, OpenAI compatible) dùng để hỗ trợ viết kịch bản và chat trong AI Studio.
            </p>
          </div>
        </div>

        <button
          onClick={openAddModal}
          className="flex items-center gap-2 px-5 py-3 bg-gradient-to-r from-violet-600 to-indigo-600 hover:scale-[1.02] active:scale-[0.98] transition-all rounded-xl text-xs font-bold text-white shadow-lg shadow-violet-600/20 cursor-pointer"
        >
          <Plus className="w-4 h-4" /> Thêm mô hình
        </button>
      </div>

      {/* Main List */}
      {loading ? (
        <div className="flex flex-col items-center justify-center min-h-[300px] gap-4">
          <Loader2 className="w-10 h-10 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground font-semibold">Đang tải danh sách mô hình...</p>
        </div>
      ) : error ? (
        <div className="p-6 bg-red-500/10 border border-red-500/20 rounded-3xl flex flex-col items-center gap-4 text-center max-w-md mx-auto">
          <AlertCircle className="w-12 h-12 text-red-500" />
          <div>
            <h3 className="text-base font-bold text-white">Lỗi tải dữ liệu</h3>
            <p className="text-xs text-muted-foreground mt-1">{error}</p>
          </div>
          <button 
            onClick={fetchModels} 
            className="px-5 py-2.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-xs font-bold text-white transition-all"
          >
            Thử lại
          </button>
        </div>
      ) : models.length === 0 ? (
        <div className="border border-dashed border-white/10 rounded-3xl p-12 text-center text-muted-foreground select-none max-w-lg mx-auto">
          <Cpu className="w-16 h-16 mx-auto opacity-20 mb-4 animate-pulse" />
          <h3 className="text-lg font-bold text-white mb-2">Chưa có mô hình nào</h3>
          <p className="text-sm leading-relaxed max-w-sm mx-auto mb-6">
            Hệ thống chưa thiết lập các cấu hình model LLM. Hãy thêm một cấu hình mới để bắt đầu chat trong AI Studio.
          </p>
          <button
            onClick={openAddModal}
            className="px-5 py-2.5 bg-primary hover:bg-primary/95 text-xs font-bold text-white rounded-xl cursor-pointer"
          >
            Tạo cấu hình đầu tiên
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {models.map((model) => {
            const test = testStatuses[model.id];
            const isOllama = model.base_url.includes("11434") || model.base_url.includes("ollama");
            
            return (
              <div 
                key={model.id}
                className="bg-black/40 border border-white/10 hover:border-white/20 transition-all duration-300 rounded-3xl p-6 backdrop-blur-xl flex flex-col justify-between group relative overflow-hidden"
              >
                {/* Body */}
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
                          {isOllama ? "Ollama Local" : "OpenAI Compatible"}
                        </span>
                      </div>
                    </div>

                    {/* Actions Toolbar */}
                    <div className="flex gap-1 border border-white/5 p-1 bg-white/5 rounded-xl">
                      <button
                        onClick={() => openEditModal(model)}
                        className="p-2 hover:bg-white/5 hover:text-white text-muted-foreground/70 rounded-lg transition-colors cursor-pointer"
                        title="Chỉnh sửa mô hình"
                      >
                        <Edit3 className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => handleDeleteModel(model.id)}
                        className="p-2 hover:bg-red-500/10 hover:text-red-400 text-muted-foreground/70 rounded-lg transition-colors cursor-pointer"
                        title="Xóa cấu hình"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  <div className="space-y-2 pt-2 border-t border-white/5">
                    {/* Model tag */}
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-muted-foreground">Model Tag:</span>
                      <span className="font-mono text-white text-[11px] font-semibold">{model.model_name}</span>
                    </div>

                    {/* Base URL */}
                    <div className="flex justify-between items-center text-xs gap-4">
                      <span className="text-muted-foreground">Endpoint:</span>
                      <span className="font-mono text-white/90 text-[10px] truncate max-w-[240px]" title={model.base_url}>{model.base_url}</span>
                    </div>

                    {/* API Key Status */}
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
                    onClick={() => handleTestConnection(model)}
                    disabled={test?.status === "testing"}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-white/5 hover:bg-white/10 text-[10px] font-bold uppercase tracking-wider text-white border border-white/10 rounded-lg transition-all cursor-pointer"
                  >
                    {test?.status === "testing" ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <Activity className="w-3 h-3 text-primary animate-pulse" />
                    )}
                    Ping Test
                  </button>

                  {/* Status output */}
                  {test && (
                    <div className="flex-1 text-right overflow-hidden">
                      {test.status === "testing" && (
                        <span className="text-[10px] text-primary animate-pulse">Đang kiểm tra...</span>
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

      {/* Model Add/Edit Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 flex items-center justify-center z-50 p-4">
          {/* Overlay */}
          <div 
            onClick={() => setIsModalOpen(false)}
            className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity" 
          />

          {/* Modal Container */}
          <div className="bg-zinc-950 border border-white/10 rounded-3xl w-full max-w-md p-6 relative z-10 shadow-2xl animate-in zoom-in-95 duration-200">
            {/* Header */}
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-lg font-extrabold text-white tracking-tight">
                {editingModelId ? "Sửa cấu hình Model LLM" : "Thêm cấu hình Model LLM"}
              </h2>
              <button 
                onClick={() => setIsModalOpen(false)}
                className="p-1 text-muted-foreground hover:text-white rounded-lg hover:bg-white/5 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Model Friendly Name */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground">Tên hiển thị (Friendly Name) *</label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="Ví dụ: Qwen 2.5 3B Local"
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white placeholder:text-muted-foreground/45 focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              {/* Base URL */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground">Endpoint URL (Base URL) *</label>
                <input
                  type="text"
                  required
                  value={formData.base_url}
                  onChange={(e) => setFormData({ ...formData, base_url: e.target.value })}
                  placeholder="Ví dụ: http://localhost:11434 hoặc https://api.openai.com"
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white placeholder:text-muted-foreground/45 focus:outline-none focus:ring-1 focus:ring-primary font-mono text-[11px]"
                />
              </div>

              {/* Model Tag */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground">Mã định danh mô hình (Model Name) *</label>
                <input
                  type="text"
                  required
                  value={formData.model_name}
                  onChange={(e) => setFormData({ ...formData, model_name: e.target.value })}
                  placeholder="Ví dụ: qwen2.5:3b hoặc gpt-4o"
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white placeholder:text-muted-foreground/45 focus:outline-none focus:ring-1 focus:ring-primary font-mono text-[11px]"
                />
              </div>

              {/* API Key */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground flex items-center gap-1">
                  <Key className="w-3.5 h-3.5 text-primary" /> API Key (Nếu có)
                </label>
                <input
                  type="password"
                  value={formData.api_key}
                  onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                  placeholder="Để trống nếu là Ollama local, điền key nếu là Cloud"
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white placeholder:text-muted-foreground/45 focus:outline-none focus:ring-1 focus:ring-primary text-[11px]"
                />
              </div>

              {/* Actions */}
              <div className="flex gap-3 pt-4 border-t border-white/5 mt-6">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="flex-1 py-3 bg-white/5 hover:bg-white/10 text-xs font-bold text-white border border-white/10 rounded-xl transition-all cursor-pointer"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="flex-1 py-3 bg-gradient-to-r from-violet-600 to-indigo-600 hover:scale-[1.02] active:scale-[0.98] text-xs font-bold text-white rounded-xl transition-all cursor-pointer shadow-lg shadow-violet-600/20"
                >
                  {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : (editingModelId ? "Cập nhật" : "Lưu cấu hình")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
