import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Folder, Plus, Bot, Send, AlertTriangle, Megaphone, Palette, FileText, Clock, Copy } from "lucide-react";
import api from "../lib/api";
import { cn } from "../lib/utils";
import { useProjects } from "../hooks/useProjects";
import { Button } from "../components/ui/Button";

export default function CreateLeaderJob() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const cloneJobId = searchParams.get("clone");
  const { projects, createProject } = useProjects();

  // Project State
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [newProjectName, setNewProjectName] = useState("");
  const [isCreatingProject, setIsCreatingProject] = useState(false);

  // Form State - Brand Context
  const [brandName, setBrandName] = useState("");
  const [toneOfVoice, setToneOfVoice] = useState("Professional, enthusiastic, tech-savvy");
  const [brandColors, setBrandColors] = useState("#4F46E5, #06B6D4, #F59E0B");

  // Form State - Campaign Context
  const [campaignName, setCampaignName] = useState("");
  const [targetAudience, setTargetAudience] = useState("");
  const [objective, setObjective] = useState("");

  // Form State - Variant Data
  const [title, setTitle] = useState("");
  const [scriptContent, setScriptContent] = useState("");
  const [mediaHints, setMediaHints] = useState("");
  const [suggestedDuration, setSuggestedDuration] = useState(30);
  const [masterContentsBrief, setMasterContentsBrief] = useState("");

  // Form State - Content Brief Context
  const [angleName, setAngleName] = useState("");
  const [funnelStage, setFunnelStage] = useState("");
  const [psychologicalAngle, setPsychologicalAngle] = useState("");
  const [painPointFocus, setPainPointFocus] = useState("");
  const [keyMessageVariation, setKeyMessageVariation] = useState("");
  const [callToActionDirection, setCallToActionDirection] = useState("");
  const [brief, setBrief] = useState("");

  // UI State
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState("");
  const [cloneLoading, setCloneLoading] = useState(!!cloneJobId);

  // UI accordion state for Content Brief section
  const [showBriefFields, setShowBriefFields] = useState(true);

  useEffect(() => {
    if (projects.length > 0 && !selectedProjectId) setSelectedProjectId(projects[0].id);
    if (projects.length === 0) setIsCreatingProject(true);
  }, [projects, selectedProjectId]);

  // Clone pre-fill: fetch original job data and populate form
  useEffect(() => {
    if (!cloneJobId) return;
    let cancelled = false;
    const loadClone = async () => {
      try {
        setCloneLoading(true);
        const res = await api.get(`/api/jobs/${cloneJobId}`);
        const job = res.data;
        if (cancelled) return;

        // Pre-fill project
        if (job.project_id) setSelectedProjectId(job.project_id);

        const cfg = job.config_data || {};
        if (cfg.brand_context) {
          setBrandName(cfg.brand_context.brand_name || "");
          setToneOfVoice(cfg.brand_context.tone_of_voice || "");
          if (Array.isArray(cfg.brand_context.brand_colors)) {
            setBrandColors(cfg.brand_context.brand_colors.join(", "));
          }
        }

        if (cfg.campaign_context) {
          setCampaignName(cfg.campaign_context.campaign_name || "");
          setTargetAudience(cfg.campaign_context.target_audience || "");
          setObjective(cfg.campaign_context.objective || "");
        }

        // Pre-fill variant content and brief adaptively (supporting both nested variant_data and flat root fields)
        const variant = cfg.variant_data || {};
        setTitle(cfg.title || variant.title || "");
        setScriptContent(cfg.script_content || variant.script_content || "");
        
        const hints = cfg.media_hints || variant.media_hints || [];
        if (Array.isArray(hints)) {
          setMediaHints(hints.join("\n"));
        }
        
        const duration = cfg.suggested_duration !== undefined ? cfg.suggested_duration : variant.suggested_duration;
        if (duration !== undefined) {
          setSuggestedDuration(Number(duration));
        }
        
        const cbContext = cfg.content_brief_context || {};
        setAngleName(cbContext.angle_name || "");
        setFunnelStage(cbContext.funnel_stage || "");
        setPsychologicalAngle(cbContext.psychological_angle || "");
        setPainPointFocus(cbContext.pain_point_focus || "");
        setKeyMessageVariation(cbContext.key_message_variation || "");
        setCallToActionDirection(cbContext.call_to_action_direction || "");
        
        const briefVal = cbContext.brief || cfg.master_contents_brief || variant.master_contents_brief || "";
        setBrief(briefVal);
        setMasterContentsBrief(briefVal);
      } catch (err) {
        console.error("Failed to load cloned leader job:", err);
      } finally {
        if (!cancelled) setCloneLoading(false);
      }
    };
    loadClone();
    return () => {
      cancelled = true;
    };
  }, [cloneJobId]);

  const handleSubmit = async () => {
    if (!isCreatingProject && !selectedProjectId) return setError("Vui lòng chọn một dự án.");
    if (isCreatingProject && !newProjectName.trim()) return setError("Vui lòng nhập tên dự án mới.");
    if (!brandName.trim()) return setError("Vui lòng nhập tên thương hiệu.");
    if (!campaignName.trim()) return setError("Vui lòng nhập tên chiến dịch.");
    if (!title.trim()) return setError("Vui lòng nhập tiêu đề kịch bản.");
    if (!scriptContent.trim()) return setError("Vui lòng nhập nội dung kịch bản.");

    setLoading(true);
    setError(null);
    try {
      let targetProjectId = selectedProjectId;
      if (isCreatingProject && newProjectName.trim()) {
        setStatusMessage("Đang tạo dự án mới...");
        const proj = await createProject(newProjectName.trim());
        targetProjectId = proj.id;
      }

      setStatusMessage("Đang phân tích kịch bản với AI Leader...");

      // Prepare colors array
      const colors = brandColors
        .split(",")
        .map((c) => c.trim())
        .filter((c) => c.startsWith("#") || c.length > 0);

      // Prepare media hints array
      const hints = mediaHints
        .split("\n")
        .map((h) => h.trim())
        .flatMap((h) => h.split(","))
        .map((h) => h.trim())
        .filter(Boolean);

      const payload = {
        job_type: "leader",
        project_id: targetProjectId,
        priority: 0,
        config_data: {
          source_id: `manual_${Date.now()}`,
          brand_context: {
            brand_name: brandName.trim(),
            tone_of_voice: toneOfVoice.trim(),
            brand_colors: colors,
          },
          campaign_context: {
            campaign_name: campaignName.trim(),
            target_audience: targetAudience.trim(),
            objective: objective.trim(),
          },
          variant_data: {
            title: title.trim(),
            script_content: scriptContent.trim(),
            media_hints: hints,
            suggested_duration: Number(suggestedDuration),
          },
          master_contents_brief: brief.trim() || masterContentsBrief.trim(),
          content_brief_context: {
            angle_name: angleName.trim(),
            funnel_stage: funnelStage.trim(),
            psychological_angle: psychologicalAngle.trim(),
            pain_point_focus: painPointFocus.trim(),
            key_message_variation: keyMessageVariation.trim(),
            call_to_action_direction: callToActionDirection.trim(),
            brief: brief.trim() || masterContentsBrief.trim(),
          }
        },
      };

      await api.post("/api/jobs", payload);
      navigate("/projects");
    } catch (err: any) {
      console.error(err);
      setError(err?.response?.data?.detail || err.message || "Không thể phân tích kịch bản.");
    } finally {
      setLoading(false);
      setStatusMessage("");
    }
  };

  return (
    <div className="max-w-5xl mx-auto p-8 lg:p-12 space-y-10 animate-in fade-in duration-300">
      {/* Header section */}
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-2xl shadow-[0_0_20px_rgba(124,58,237,0.4)]">
            <Bot className="w-7 h-7 text-white" />
          </div>
          <span className="text-xs font-mono uppercase bg-primary/20 text-primary px-3 py-1 rounded-md border border-primary/20 font-bold tracking-wider">
            AI Leader Agent
          </span>
        </div>
        <h2 className="text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60">
          Tổng Đạo Diễn AI (AI Leader Agent)
        </h2>
        <p className="text-muted-foreground text-lg max-w-3xl">
          Tự nhập kịch bản thô, định nghĩa bối cảnh thương hiệu và mục tiêu chiến dịch. Leader Agent sẽ tự phân tích và đề xuất Worker Video phù hợp nhất kèm bộ thông số nháp đầy đủ.
        </p>
      </div>

      {error && (
        <div className="p-4 bg-rose-500/10 text-rose-400 rounded-2xl border border-rose-500/20 backdrop-blur-sm flex items-center gap-3 animate-in slide-in-from-top-2">
          <AlertTriangle className="w-5 h-5 shrink-0" />
          <span className="font-medium">{error}</span>
        </div>
      )}

      {cloneJobId && (
        <div className="glass-panel p-4 flex items-center gap-3 bg-amber-500/10 border border-amber-500/20 rounded-xl animate-in fade-in">
          <Copy className="w-5 h-5 text-amber-400 shrink-0" />
          <div>
            <p className="text-sm font-medium text-amber-300">Bản sao từ Job #{cloneJobId}</p>
            <p className="text-xs text-amber-400/70">Chỉnh sửa nội dung bên dưới rồi gửi để chạy AI Leader phân tích mới.</p>
          </div>
        </div>
      )}

      {cloneLoading ? (
        <div className="glass-panel p-16 flex flex-col items-center justify-center gap-4 text-muted-foreground">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
          <p>Đang tải dữ liệu từ Job #{cloneJobId}...</p>
        </div>
      ) : (
        <div className="glass-panel p-6 lg:p-10 flex flex-col space-y-10">
        
        {/* Step 1: Project Selection */}
        <div className="space-y-4">
          <label className="text-xs font-bold text-white/90 uppercase tracking-widest flex items-center gap-2">
            <Folder className="w-4 h-4 text-primary" /> Dự án liên kết
          </label>
          <div className="flex flex-col sm:flex-row gap-4">
            <button
              type="button"
              onClick={() => setIsCreatingProject(false)}
              className={cn(
                "flex-1 px-4 py-3.5 rounded-xl border flex items-center gap-2 justify-center transition-all duration-300 font-semibold text-sm",
                !isCreatingProject
                  ? "bg-primary/20 border-primary text-white shadow-[0_0_15px_rgba(124,58,237,0.3)]"
                  : "bg-white/5 border-white/10 text-muted-foreground hover:bg-white/10 hover:text-white"
              )}
            >
              <Folder className="w-4.5 h-4.5" /> Chọn dự án có sẵn
            </button>
            <button
              type="button"
              onClick={() => setIsCreatingProject(true)}
              className={cn(
                "flex-1 px-4 py-3.5 rounded-xl border flex items-center gap-2 justify-center transition-all duration-300 font-semibold text-sm",
                isCreatingProject
                  ? "bg-primary/20 border-primary text-white shadow-[0_0_15px_rgba(124,58,237,0.3)]"
                  : "bg-white/5 border-white/10 text-muted-foreground hover:bg-white/10 hover:text-white"
              )}
            >
              <Plus className="w-4.5 h-4.5" /> Tạo dự án mới
            </button>
          </div>

          {isCreatingProject ? (
            <div className="space-y-2 animate-in fade-in duration-300">
              <input
                type="text"
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                placeholder="Tên dự án mới..."
                className="flex h-12 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-base text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all placeholder:text-muted-foreground/50"
              />
            </div>
          ) : (
            <div className="space-y-2 animate-in fade-in duration-300">
              <select
                value={selectedProjectId}
                onChange={(e) => setSelectedProjectId(e.target.value)}
                className="flex h-12 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-base text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all appearance-none"
              >
                {projects.length === 0 ? (
                  <option disabled value="" className="bg-[#1A1A24]">
                    Bạn chưa có dự án nào
                  </option>
                ) : (
                  projects.map((p) => (
                    <option key={p.id} value={p.id} className="bg-[#1A1A24]">
                      {p.name}
                    </option>
                  ))
                )}
              </select>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 border-t border-white/10 pt-8">
          
          {/* Brand & Campaign Context column */}
          <div className="space-y-8">
            
            {/* Brand Context Card */}
            <div className="space-y-5 p-6 bg-white/[0.02] border border-white/5 rounded-2xl">
              <h3 className="text-base font-bold text-white flex items-center gap-2.5">
                <Palette className="w-5 h-5 text-indigo-400" />
                Thương hiệu (Brand Context)
              </h3>
              
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-muted-foreground">Tên Thương Hiệu *</label>
                  <input
                    type="text"
                    value={brandName}
                    onChange={(e) => setBrandName(e.target.value)}
                    placeholder="Ví dụ: Antigravity AI, Nike, ..."
                    className="flex h-11 w-full rounded-xl border border-white/10 bg-white/5 px-4 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-semibold text-muted-foreground">Tone Giọng (Tone of voice)</label>
                  <input
                    type="text"
                    value={toneOfVoice}
                    onChange={(e) => setToneOfVoice(e.target.value)}
                    placeholder="Ví dụ: Professional, enthusiastic, tech-savvy"
                    className="flex h-11 w-full rounded-xl border border-white/10 bg-white/5 px-4 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-semibold text-muted-foreground">Màu Sắc Thương Hiệu (Hex list, cách nhau bằng dấu phẩy)</label>
                  <input
                    type="text"
                    value={brandColors}
                    onChange={(e) => setBrandColors(e.target.value)}
                    placeholder="Ví dụ: #4F46E5, #06B6D4, #F59E0B"
                    className="flex h-11 w-full rounded-xl border border-white/10 bg-white/5 px-4 text-sm text-white font-mono focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all"
                  />
                </div>
              </div>
            </div>

            {/* Campaign Context Card */}
            <div className="space-y-5 p-6 bg-white/[0.02] border border-white/5 rounded-2xl">
              <h3 className="text-base font-bold text-white flex items-center gap-2.5">
                <Megaphone className="w-5 h-5 text-cyan-400" />
                Chiến dịch (Campaign Context)
              </h3>
              
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-muted-foreground">Tên Chiến Dịch *</label>
                  <input
                    type="text"
                    value={campaignName}
                    onChange={(e) => setCampaignName(e.target.value)}
                    placeholder="Ví dụ: Productivity Revolution"
                    className="flex h-11 w-full rounded-xl border border-white/10 bg-white/5 px-4 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-semibold text-muted-foreground">Đối Tượng Khách Hàng (Target audience)</label>
                  <input
                    type="text"
                    value={targetAudience}
                    onChange={(e) => setTargetAudience(e.target.value)}
                    placeholder="Ví dụ: Software developers, technical leaders, CTOs"
                    className="flex h-11 w-full rounded-xl border border-white/10 bg-white/5 px-4 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-semibold text-muted-foreground">Mục Tiêu (Objective)</label>
                  <input
                    type="text"
                    value={objective}
                    onChange={(e) => setObjective(e.target.value)}
                    placeholder="Ví dụ: Show WSL speed and double developer velocity"
                    className="flex h-11 w-full rounded-xl border border-white/10 bg-white/5 px-4 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all"
                  />
                </div>
              </div>
            </div>

          </div>

          {/* Variant Content column */}
          <div className="space-y-5 p-6 bg-white/[0.02] border border-white/5 rounded-2xl h-fit">
            <h3 className="text-base font-bold text-white flex items-center gap-2.5">
              <FileText className="w-5 h-5 text-violet-400" />
              Chi tiết kịch bản (Variant Content)
            </h3>
            
            <div className="space-y-4">
              <div className="space-y-2">
                <label className="text-xs font-semibold text-muted-foreground">Tiêu Đề Kịch Bản *</label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Ví dụ: Đánh giá chi tiết Antigravity AI 2.0..."
                  className="flex h-11 w-full rounded-xl border border-white/10 bg-white/5 px-4 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all"
                />
              </div>

              {/* Content Brief Context Collapsible Premium Card */}
              <div className="rounded-xl border border-white/10 bg-white/[0.01] overflow-hidden">
                <button
                  type="button"
                  onClick={() => setShowBriefFields(!showBriefFields)}
                  className="w-full flex items-center justify-between px-4 py-3 bg-white/[0.02] border-b border-white/5 text-xs font-bold text-violet-400 hover:bg-white/5 transition-all animate-in fade-in"
                >
                  <span className="flex items-center gap-2 text-white">
                    <FileText className="w-4 h-4 text-violet-400" />
                    Tài Liệu Nội Dung & Chiến Lược Chiến Dịch (Content Brief)
                  </span>
                  <span className="text-violet-400">{showBriefFields ? "Thu gọn ▲" : "Mở rộng ▼"}</span>
                </button>
                {showBriefFields && (
                  <div className="p-4 space-y-4 animate-in slide-in-from-top-2 duration-200">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Góc Tiếp Cận (Angle Name)</label>
                        <input
                          type="text"
                          value={angleName}
                          onChange={(e) => setAngleName(e.target.value)}
                          placeholder="Ví dụ: Mở hộp Vợt cầu lông Pro 2026"
                          className="flex h-9 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-xs text-white focus:outline-none focus:ring-1 focus:ring-primary/50 transition-all"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Giai Đoạn Phễu (Funnel Stage)</label>
                        <input
                          type="text"
                          value={funnelStage}
                          onChange={(e) => setFunnelStage(e.target.value)}
                          placeholder="Ví dụ: Awareness, Consideration..."
                          className="flex h-9 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-xs text-white focus:outline-none focus:ring-1 focus:ring-primary/50 transition-all"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Tâm Lý Tác Động (Psychological Angle)</label>
                        <input
                          type="text"
                          value={psychologicalAngle}
                          onChange={(e) => setPsychologicalAngle(e.target.value)}
                          placeholder="Ví dụ: Curiosity, Fear of Missing Out..."
                          className="flex h-9 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-xs text-white focus:outline-none focus:ring-1 focus:ring-primary/50 transition-all"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Nỗi Đau Tập Trung (Pain Point Focus)</label>
                        <input
                          type="text"
                          value={painPointFocus}
                          onChange={(e) => setPainPointFocus(e.target.value)}
                          placeholder="Ví dụ: Lo lắng mua phải hàng giả..."
                          className="flex h-9 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-xs text-white focus:outline-none focus:ring-1 focus:ring-primary/50 transition-all"
                        />
                      </div>
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Thông Điệp Cốt Lõi Biến Thể (Key Message Variation)</label>
                      <input
                        type="text"
                        value={keyMessageVariation}
                        onChange={(e) => setKeyMessageVariation(e.target.value)}
                        placeholder="Ví dụ: Đảm bảo chất lượng chính hãng 100%..."
                        className="flex h-9 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-xs text-white focus:outline-none focus:ring-1 focus:ring-primary/50 transition-all"
                      />
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Hướng Đi Kêu Gọi Hành Động (CTA Direction)</label>
                      <input
                        type="text"
                        value={callToActionDirection}
                        onChange={(e) => setCallToActionDirection(e.target.value)}
                        placeholder="Ví dụ: Nhấn vào liên kết để nhận ưu đãi..."
                        className="flex h-9 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-xs text-white focus:outline-none focus:ring-1 focus:ring-primary/50 transition-all"
                      />
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Tóm Tắt Nội Dung Chính / Brief *</label>
                      <textarea
                        value={brief}
                        onChange={(e) => {
                          setBrief(e.target.value);
                          setMasterContentsBrief(e.target.value);
                        }}
                        placeholder="Phân tích đặc tính nổi bật của vợt cầu lông Pro 2026..."
                        rows={4}
                        className="flex w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-white focus:outline-none focus:ring-1 focus:ring-primary/50 resize-none leading-relaxed placeholder:text-muted-foreground/30 transition-all"
                      />
                    </div>
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-muted-foreground">Nội Dung Kịch Bản Thô (Script Content) *</label>
                  <span className="text-[10px] text-muted-foreground font-mono">{scriptContent.length} chars</span>
                </div>
                <textarea
                  value={scriptContent}
                  onChange={(e) => setScriptContent(e.target.value)}
                  placeholder="Nhập hoặc dán toàn bộ kịch bản thô của bạn ở đây..."
                  rows={8}
                  className="flex w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all resize-none placeholder:text-muted-foreground/30 leading-relaxed"
                />
              </div>

              <div className="space-y-2">
                <label className="text-xs font-semibold text-muted-foreground">Gợi Ý Phân Cảnh (Media Hints - xuống dòng hoặc phẩy để phân tách)</label>
                <textarea
                  value={mediaHints}
                  onChange={(e) => setMediaHints(e.target.value)}
                  placeholder="Ví dụ:&#10;Cận cảnh màn hình IDE&#10;Hiển thị biểu đồ hiệu suất&#10;Nút kêu gọi mua ngay..."
                  rows={3}
                  className="flex w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all resize-none placeholder:text-muted-foreground/30"
                />
              </div>

              <div className="space-y-2">
                <div className="flex justify-between items-center mb-1">
                  <label className="text-xs font-semibold text-muted-foreground flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                    Thời lượng gợi ý (Duration):
                  </label>
                  <span className="text-sm font-bold text-primary font-mono">{suggestedDuration} giây</span>
                </div>
                <input
                  type="range"
                  min="10"
                  max="90"
                  step="5"
                  value={suggestedDuration}
                  onChange={(e) => setSuggestedDuration(Number(e.target.value))}
                  className="w-full h-1.5 bg-white/10 rounded-lg appearance-none cursor-pointer accent-primary"
                />
                <div className="flex justify-between text-[10px] text-muted-foreground/50 font-mono">
                  <span>10s</span>
                  <span>30s</span>
                  <span>60s</span>
                  <span>90s</span>
                </div>
              </div>

            </div>
          </div>

        </div>

        {/* Action Button */}
        <div className="flex justify-end pt-6 border-t border-white/10">
          <Button
            onClick={handleSubmit}
            isLoading={loading}
            disabled={!brandName || !campaignName || !title || !scriptContent}
            className="glowing-button px-10 py-4.5 rounded-xl font-bold shadow-[0_0_30px_rgba(124,58,237,0.5)] flex items-center gap-2.5 text-sm hover:scale-[1.02] active:scale-[0.98] transition-all"
          >
            {!loading && <Send className="w-4.5 h-4.5" />}
            {loading ? statusMessage || "Đang xử lý..." : "Chạy AI Leader phân tích kịch bản"}
          </Button>
        </div>

      </div>
      )}
    </div>
  );
}
