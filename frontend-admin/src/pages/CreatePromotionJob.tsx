import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Plus, Folder, Trash2, CheckCircle2, ImagePlus, FileText, Send, Copy } from "lucide-react";
import api from "../lib/api";
import { cn } from "../lib/utils";
import { useAssets } from "../hooks/useAssets";
import { useProjects } from "../hooks/useProjects";
import { Button } from "../components/ui/Button";
import { AssetSelector } from "../components/ui/AssetSelector";
import type { UploadedFile } from "../components/features/review/types";
import { JobActionButtons } from "../components/ui/JobActionButtons";
import { JobCreationLayout } from "../components/ui/JobCreationLayout";

interface ImageInput {
  image: UploadedFile | null;
}

export default function CreatePromotionJob() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const cloneJobId = searchParams.get("clone");
  const clonedFromId = cloneJobId;

  const { uploadAsset } = useAssets();
  const { projects, createProject } = useProjects();
  const [step, setStep] = useState(1);

  // Data State
  const REQUIRED_IMAGES_COUNT = 9;
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [newProjectName, setNewProjectName] = useState("");
  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const [priority, setPriority] = useState<number>(0);
  const [tmcpContext, setTmcpContext] = useState<any>(null);

  const [images, setImages] = useState<ImageInput[]>(
    Array(REQUIRED_IMAGES_COUNT).fill(null).map(() => ({ image: null }))
  );

  // UI State
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState("");
  const [cloneLoading, setCloneLoading] = useState(!!cloneJobId);

  useEffect(() => {
    if (projects.length > 0 && !selectedProjectId) setSelectedProjectId(projects[0].id);
    if (projects.length === 0) setIsCreatingProject(true);
  }, [projects, selectedProjectId]);

  // Clone/Draft loading
  useEffect(() => {
    if (!cloneJobId) return;
    let cancelled = false;
    const loadClone = async () => {
      try {
        setCloneLoading(true);
        const res = await api.get(`/api/jobs/${cloneJobId}`);
        const job = res.data;
        if (cancelled) return;

        if (job.project_id) setSelectedProjectId(job.project_id);
        if (job.priority !== undefined) setPriority(job.priority);

        const cfg = job.config_data || {};
        if (cfg.metadata?.tmcp_context) {
          setTmcpContext(cfg.metadata.tmcp_context);
        }

        if (Array.isArray(cfg.images)) {
          const loadedImages = cfg.images.map((imgUrl: string) => ({
            image: imgUrl ? {
              file: undefined,
              id: null,
              s3_url: imgUrl,
              asset: {
                id: "",
                s3_url: imgUrl,
                file_name: imgUrl.split("/").pop() || "image.jpg",
                file_size_bytes: 0,
                asset_type: "image",
                mime_type: "image/jpeg",
                created_at: ""
              },
              uploading: false,
              progress: 100
            } : null
          }));
          while (loadedImages.length < REQUIRED_IMAGES_COUNT) {
            loadedImages.push({ image: null });
          }
          setImages(loadedImages.slice(0, REQUIRED_IMAGES_COUNT));
        }
      } catch (err) {
        console.error("Failed to load cloned promotion job:", err);
      } finally {
        if (!cancelled) setCloneLoading(false);
      }
    };
    loadClone();
    return () => {
      cancelled = true;
    };
  }, [cloneJobId]);

  const removeImage = (idx: number) => {
    const newImages = [...images];
    newImages[idx] = { image: null };
    setImages(newImages);
  };

  const updateImage = (idx: number, field: keyof ImageInput, value: any) => {
    const newImages = [...images];
    newImages[idx] = { ...newImages[idx], [field]: value };
    setImages(newImages);
  };

  const handleBulkUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    if (!files.length) return;
    
    const newImages = [...images];
    let fileIdx = 0;
    
    // Fill empty slots
    for (let i = 0; i < REQUIRED_IMAGES_COUNT && fileIdx < files.length; i++) {
        if (!newImages[i].image) {
            newImages[i] = { image: { file: files[fileIdx], uploading: false, progress: 0, id: null, s3_url: null } };
            fileIdx++;
        }
    }
    
    // If still have files, overwrite from the beginning
    for (let i = 0; i < REQUIRED_IMAGES_COUNT && fileIdx < files.length; i++) {
        newImages[i] = { image: { file: files[fileIdx], uploading: false, progress: 0, id: null, s3_url: null } };
        fileIdx++;
    }
    
    setImages(newImages);
    event.target.value = '';
  };

  const convertToCapCutConfig = (
    finalImages: string[],
    targetProjectId: string
  ) => {
    const videoFolders: Record<string, string> = {};
    const timelineScript: any[] = [];
    const segmentDuration = 4.0;

    finalImages.forEach((url, idx) => {
      const key = (idx + 1).toString();
      videoFolders[key] = url;
    });

    finalImages.forEach((url, idx) => {
      const key = (idx + 1).toString();
      const timeStart = idx * segmentDuration;
      const timeEnd = (idx + 1) * segmentDuration;

      timelineScript.push({
        segment: `seg_${key}_image`,
        video_source: key,
        time_range: [timeStart, timeEnd],
        text_overlay: `Khung hình ${key}`,
        highlight_words: [],
        visual_effects: [],
        transition: idx > 0 ? "fade_in" : undefined
      });
    });

    return {
      metadata: {
        project_id: targetProjectId,
        ...(tmcpContext ? { tmcp_context: tmcpContext } : {})
      },
      assets: {
        audio: {
          bgm_path: "",
          voiceover_path: ""
        },
        video_folders: videoFolders
      },
      timeline_script: timelineScript,
      render_settings: {
        resolution: [1080, 1920],
        auto_subtitle: false,
        pacing: { min_clip_duration: 1.2, max_clip_duration: 1.8 }
      }
    };
  };

  const handleSaveDraft = async () => {
    if (!cloneJobId) {
      setError("Không thể lưu nháp cho job mới. Chức năng lưu nháp chỉ áp dụng cho job được tạo từ AI Leader hoặc chỉnh sửa Draft.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      let targetProjectId = selectedProjectId;
      if (isCreatingProject && newProjectName.trim()) {
        setUploadStatus("Đang tạo dự án...");
        const proj = await createProject(newProjectName.trim());
        targetProjectId = proj.id;
      }

      const allAssetIds: string[] = [];
      const finalImages: string[] = [];

      for (let i = 0; i < images.length; i++) {
        const item = images[i];
        let imageUrl = "";
        if (item.image?.file) {
          setUploadStatus(`Đang upload ảnh ${i + 1}/${images.length}...`);
          const res = await uploadAsset(item.image.file as File, "image");
          imageUrl = res.s3_url;
          allAssetIds.push(res.id);
        } else if (item.image?.asset) {
          imageUrl = item.image.asset.s3_url;
          allAssetIds.push(item.image.asset.id);
        } else if (item.image?.s3_url) {
          imageUrl = item.image.s3_url;
        }
        finalImages.push(imageUrl || "");
      }

      setUploadStatus("Đang lưu bản nháp...");
      const payload = {
        project_id: targetProjectId || null,
        priority,
        asset_ids: allAssetIds,
        status: "DRAFT",
        config_data: {
          metadata: {
            project_id: targetProjectId || undefined,
            ...(tmcpContext ? { tmcp_context: tmcpContext } : {})
          },
          images: finalImages
        }
      };

      await api.patch(`/api/jobs/${cloneJobId}`, payload);
    } catch (err: any) {
      console.error(err);
      setError(err?.response?.data?.detail || err.message || "Failed to save draft");
      throw err;
    } finally {
      setLoading(false);
      setUploadStatus("");
    }
  };

  const handleCapCutSubmit = async () => {
    if (!isCreatingProject && !selectedProjectId) return setError("Vui lòng chọn dự án");
    if (isCreatingProject && !newProjectName.trim()) return setError("Vui lòng nhập tên dự án mới");
    if (images.length !== REQUIRED_IMAGES_COUNT) return setError(`Cần chính xác ${REQUIRED_IMAGES_COUNT} ảnh`);
    for (let i = 0; i < images.length; i++) {
      if (!images[i].image) return setError(`Ảnh thứ ${i + 1} trống`);
    }

    setLoading(true);
    setError(null);
    try {
      let targetProjectId = selectedProjectId;
      if (isCreatingProject && newProjectName.trim()) {
        setUploadStatus("Đang tạo dự án...");
        const proj = await createProject(newProjectName.trim());
        targetProjectId = proj.id;
      }

      const allAssetIds: string[] = [];
      const finalImages: string[] = [];

      for (let i = 0; i < images.length; i++) {
        setUploadStatus(`Đang upload ảnh ${i + 1}/${images.length}...`);
        const item = images[i];
        let imageUrl = "";
        if (item.image?.file) {
          const res = await uploadAsset(item.image.file as File, "image");
          imageUrl = res.s3_url;
          allAssetIds.push(res.id);
        } else if (item.image?.asset) {
          imageUrl = item.image.asset.s3_url;
          allAssetIds.push(item.image.asset.id);
        } else if (item.image?.s3_url) {
          imageUrl = item.image.s3_url;
        }
        finalImages.push(imageUrl);
      }

      setUploadStatus("Saving draft & creating CapCut job...");
      const capCutConfigData = convertToCapCutConfig(finalImages, targetProjectId);

      if (cloneJobId) {
        const promotionDraftPayload = {
          project_id: targetProjectId,
          priority,
          asset_ids: allAssetIds,
          status: "DRAFT",
          config_data: {
            metadata: {
              project_id: targetProjectId,
              ...(tmcpContext ? { tmcp_context: tmcpContext } : {})
            },
            images: finalImages
          }
        };
        await api.patch(`/api/jobs/${cloneJobId}`, promotionDraftPayload);
      }

      await api.post(`/api/jobs`, {
        job_type: "capcut",
        project_id: targetProjectId,
        priority,
        config_data: capCutConfigData,
        asset_ids: allAssetIds
      });

      navigate("/");
    } catch (err: any) {
      console.error(err);
      setError(err?.response?.data?.detail || err.message || "Failed to create CapCut job");
    } finally {
      setLoading(false);
      setUploadStatus("");
    }
  };

  const handleSubmit = async () => {
    if (!isCreatingProject && !selectedProjectId) return setError("Vui lòng chọn dự án");
    if (isCreatingProject && !newProjectName.trim()) return setError("Vui lòng nhập tên dự án mới");
    if (images.length !== REQUIRED_IMAGES_COUNT) return setError(`Cần chính xác ${REQUIRED_IMAGES_COUNT} ảnh`);
    for (let i = 0; i < images.length; i++) {
      if (!images[i].image) return setError(`Ảnh thứ ${i + 1} trống`);
    }

    setLoading(true);
    setError(null);
    try {
      let targetProjectId = selectedProjectId;
      if (isCreatingProject && newProjectName.trim()) {
        setUploadStatus("Đang tạo dự án...");
        const proj = await createProject(newProjectName.trim());
        targetProjectId = proj.id;
      }

      const allAssetIds: string[] = [];
      const finalImages: string[] = [];

      for (let i = 0; i < images.length; i++) {
        setUploadStatus(`Đang upload ảnh ${i + 1}/${images.length}...`);
        const item = images[i];
        let imageUrl = "";
        if (item.image?.file) {
          const res = await uploadAsset(item.image.file as File, "image");
          imageUrl = res.s3_url;
          allAssetIds.push(res.id);
        } else if (item.image?.asset) {
          imageUrl = item.image.asset.s3_url;
          allAssetIds.push(item.image.asset.id);
        } else if (item.image?.s3_url) {
          imageUrl = item.image.s3_url;
        }
        finalImages.push(imageUrl);
      }

      setUploadStatus("Đang tạo job...");
      const payload = {
        job_type: "promotion",
        priority,
        project_id: targetProjectId,
        asset_ids: allAssetIds,
        config_data: {
          metadata: {
            project_id: targetProjectId,
            ...(tmcpContext ? { tmcp_context: tmcpContext } : {})
          },
          images: finalImages
        }
      };

      if (cloneJobId) {
        await api.patch(`/api/jobs/${cloneJobId}`, {
          ...payload,
          status: "QUEUED"
        });
      } else {
        await api.post("/api/jobs", payload);
      }
      navigate("/");
    } catch (err: any) {
      console.error(err);
      setError(err?.response?.data?.detail || err.message || "Failed to create promotion job");
    } finally {
      setLoading(false);
      setUploadStatus("");
    }
  };

  const steps = [
    { id: 1, name: "Cài đặt chung", icon: FileText },
    { id: 2, name: "Danh sách ảnh", icon: ImagePlus },
    { id: 3, name: "Kiểm tra & Gửi", icon: Send }
  ];

  const canGoStep2 = isCreatingProject ? !!newProjectName.trim() : !!selectedProjectId;
  const canGoStep3 = images.length === REQUIRED_IMAGES_COUNT && images.every(p => p.image);

  return (
    <JobCreationLayout jobType="promotion" tmcpContext={tmcpContext}>
      <div className="max-w-5xl mx-auto p-8 lg:p-12 space-y-10">
        <div className="space-y-2">
          <h2 className="text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-orange-400 to-amber-400">
            Tạo Viral Promotion Video 🌟
          </h2>
          <p className="text-muted-foreground text-lg">
            Tạo video quảng cáo giật giật, chuyển cảnh mạnh với template CapCut tự động. Chỉ cần chọn ảnh, hệ thống lo phần còn lại.
          </p>
        </div>

        {clonedFromId && (
          <div className="glass-panel p-4 flex items-center gap-3 bg-amber-500/10 border border-amber-500/20 rounded-xl animate-in fade-in">
            <Copy className="w-5 h-5 text-amber-400 shrink-0" />
            <div>
              <p className="text-sm font-medium text-amber-300">Bản sao từ Job #{clonedFromId}</p>
              <p className="text-xs text-amber-400/70">Chỉnh sửa nội dung bên dưới rồi gửi để tạo video mới.</p>
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
            <div className="flex items-center justify-between w-full border-b border-white/10 pb-8">
              {steps.map((s, idx) => (
                <div key={s.id} className="flex items-center">
                  <div className={cn(
                    "flex items-center gap-3 transition-all duration-300",
                    step >= s.id ? "text-primary" : "text-muted-foreground"
                  )}>
                    <div className={cn(
                      "flex items-center justify-center w-10 h-10 rounded-full border-2 transition-all duration-300",
                      step > s.id ? "bg-primary border-primary text-white" :
                        step === s.id ? "border-primary bg-primary/20 shadow-[0_0_15px_rgba(124,58,237,0.4)]" : "border-muted-foreground/30"
                    )}>
                      {step > s.id ? <CheckCircle2 className="w-5 h-5" /> : <s.icon className="w-5 h-5" />}
                    </div>
                    <span className={cn(
                      "font-medium text-sm hidden md:block",
                      step >= s.id ? "text-white" : "text-muted-foreground"
                    )}>
                      {s.name}
                    </span>
                  </div>
                  {idx < steps.length - 1 && (
                    <div className="w-12 md:w-24 h-px bg-white/10 mx-4"></div>
                  )}
                </div>
              ))}
            </div>

            {error && (
              <div className="p-4 bg-red-500/10 text-red-400 rounded-xl border border-red-500/20 backdrop-blur-sm animate-in fade-in slide-in-from-top-4">
                {error}
              </div>
            )}

            {step === 1 && (
              <div className="space-y-8 animate-in fade-in slide-in-from-right-8 duration-500">
                <div className="space-y-4">
                  <label className="text-sm font-semibold text-white/90 uppercase tracking-wider flex items-center gap-2">
                    <Folder className="w-4 h-4 text-primary" /> Dự án
                  </label>
                  <div className="flex flex-col sm:flex-row gap-4">
                    <button
                      type="button"
                      onClick={() => setIsCreatingProject(false)}
                      className={cn("flex-1 px-4 py-3 rounded-xl border flex items-center gap-2 justify-center transition-all", !isCreatingProject ? "bg-primary/20 border-primary text-white shadow-[0_0_15px_rgba(124,58,237,0.3)]" : "bg-white/5 border-white/10 text-muted-foreground hover:bg-white/10")}
                    >
                      <Folder className="w-4 h-4" /> Chọn dự án có sẵn
                    </button>
                    <button
                      type="button"
                      onClick={() => setIsCreatingProject(true)}
                      className={cn("flex-1 px-4 py-3 rounded-xl border flex items-center gap-2 justify-center transition-all", isCreatingProject ? "bg-primary/20 border-primary text-white shadow-[0_0_15px_rgba(124,58,237,0.3)]" : "bg-white/5 border-white/10 text-muted-foreground hover:bg-white/10")}
                    >
                      <Plus className="w-4 h-4" /> Tạo dự án mới
                    </button>
                  </div>

                  {isCreatingProject ? (
                    <div className="space-y-2 animate-in fade-in slide-in-from-top-2">
                      <input
                        type="text"
                        value={newProjectName}
                        onChange={e => setNewProjectName(e.target.value)}
                        placeholder="Tên dự án mới..."
                        className="flex h-12 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-base text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all placeholder:text-muted-foreground/50"
                      />
                    </div>
                  ) : (
                    <div className="space-y-2 animate-in fade-in slide-in-from-top-2">
                      <select
                        value={selectedProjectId}
                        onChange={e => setSelectedProjectId(e.target.value)}
                        className="flex h-12 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-base text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all appearance-none"
                      >
                        {projects.length === 0 ? (
                          <option disabled value="" className="bg-[#1A1A24]">Bạn chưa có dự án nào</option>
                        ) : (
                          projects.map(p => (
                            <option key={p.id} value={p.id} className="bg-[#1A1A24]">{p.name}</option>
                          ))
                        )}
                      </select>
                    </div>
                  )}
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="space-y-8 animate-in fade-in slide-in-from-right-8 duration-500">
                <div className="flex items-center justify-between border-b border-white/10 pb-4">
                  <div>
                    <h3 className="text-xl font-semibold text-white">Danh sách Ảnh</h3>
                    <p className="text-sm text-muted-foreground">Yêu cầu chính xác {REQUIRED_IMAGES_COUNT} ảnh để vừa khớp với Video mẫu.</p>
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="file"
                      multiple
                      accept="image/*"
                      onChange={handleBulkUpload}
                      className="hidden"
                      id="bulk-upload-input"
                    />
                    <label
                      htmlFor="bulk-upload-input"
                      className="inline-flex items-center cursor-pointer bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/50 rounded-xl text-sm font-medium transition-colors h-10 px-4 text-amber-300"
                    >
                      <Folder className="mr-2 h-4 w-4" /> Chọn nhiều file ảnh
                    </label>
                  </div>
                </div>

                <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 max-h-[500px] overflow-y-auto pr-2 custom-scrollbar">
                  {images.map((p, idx) => (
                    <div key={idx} className="flex flex-col items-center gap-2 p-4 rounded-2xl bg-black/40 border border-white/10 relative group hover:border-white/20 transition-all">
                      <div className="w-full shrink-0">
                        <AssetSelector
                          label={`Khung hình ${idx + 1}`}
                          sublabel="Bất kỳ"
                          icon={<ImagePlus className="w-6 h-6 text-amber-400" />}
                          accept="image/*"
                          assetTypeFilter="image"
                          selectedFile={p.image}
                          onSelect={(file, asset) => {
                            if (file || asset) {
                              updateImage(idx, "image", { file, asset, id: asset?.id || null, s3_url: asset?.s3_url || null, uploading: false, progress: 0 });
                            }
                          }}
                        />
                      </div>

                      <button
                        type="button"
                        onClick={() => removeImage(idx)}
                        className="absolute top-2 right-2 p-2 bg-black/50 text-muted-foreground hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {step === 3 && (
              <div className="space-y-8 animate-in fade-in slide-in-from-right-8 duration-500">
                <div className="rounded-2xl bg-black/40 border border-white/10 p-8 space-y-6">
                  <h3 className="text-2xl font-bold text-white flex items-center gap-3">
                    <CheckCircle2 className="w-8 h-8 text-amber-400" /> Chuẩn Bị Render
                  </h3>

                  <div className="flex items-center gap-4 bg-white/5 p-4 rounded-xl border border-white/10">
                    <label className="text-white text-sm font-semibold uppercase tracking-wider text-muted-foreground mr-4">Compute Priority</label>
                    <button
                      type="button"
                      onClick={() => setPriority(0)}
                      className={cn("px-5 py-2 rounded-xl transition-all text-sm font-medium", priority === 0 ? "bg-white/10 border border-white/30 text-white shadow-sm" : "border border-transparent text-muted-foreground hover:bg-white/5")}
                    >
                      Bình thường
                    </button>
                    <button
                      type="button"
                      onClick={() => setPriority(1)}
                      className={cn("px-5 py-2 rounded-xl transition-all text-sm font-medium", priority === 1 ? "bg-amber-500/20 border border-amber-500/50 text-amber-400 shadow-[0_0_15px_rgba(245,158,11,0.2)]" : "border border-transparent text-muted-foreground hover:bg-amber-500/10 hover:text-amber-400/70")}
                    >
                      Ưu tiên cao
                    </button>
                  </div>

                  <div className="grid grid-cols-2 gap-8 text-sm">
                    <div className="space-y-2">
                      <p className="text-muted-foreground">Chi tiết Request</p>
                      <p className="text-white font-medium flex justify-between border-b border-white/10 pb-2">
                        <span>Số ảnh Upload:</span> <span>{images.length} ảnh</span>
                      </p>
                      <p className="text-white font-medium flex justify-between border-b border-white/10 pb-2">
                        <span>Hiệu ứng:</span> <span className="text-amber-300">Default CapCut</span>
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            <JobActionButtons
              currentStep={step}
              totalSteps={3}
              loading={loading}
              uploadStatus={uploadStatus}
              isDraft={!!cloneJobId}
              canGoNext={step === 1 ? !!canGoStep2 : step === 2 ? !!canGoStep3 : true}
              onPrev={() => setStep(prev => prev - 1)}
              onNext={() => setStep(prev => prev + 1)}
              onSubmit={handleSubmit}
              onCapCutSubmit={handleCapCutSubmit}
              onSaveDraft={cloneJobId ? handleSaveDraft : undefined}
            />
          </div>
        )}
      </div>
    </JobCreationLayout>
  );
}
