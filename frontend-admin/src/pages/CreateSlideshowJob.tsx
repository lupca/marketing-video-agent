import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Plus, Folder, Trash2, ChevronRight, CheckCircle2, ImagePlus, FileText, Send, Copy, UploadCloud } from "lucide-react";
import api from "../lib/api";
import { cn } from "../lib/utils";
import { useAssets } from "../hooks/useAssets";
import { useProjects } from "../hooks/useProjects";
import { Button } from "../components/ui/Button";
import { AssetSelector } from "../components/ui/AssetSelector";
import type { UploadedFile } from "../components/features/review/types";

interface ProductInput {
  image: UploadedFile | null;
  text: string;
  hook: string;
}

export default function CreateSlideshowJob() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const cloneJobId = searchParams.get("clone");
  const { uploadAsset } = useAssets();
  const { projects, createProject } = useProjects();
  const [step, setStep] = useState(1);
  const [cloneLoading, setCloneLoading] = useState(!!cloneJobId);
  const clonedFromId = cloneJobId;

  // Data State
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [newProjectName, setNewProjectName] = useState("");
  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const [priority, setPriority] = useState<number>(0);

  const [introText, setIntroText] = useState("Top sản phẩm nổi bật");
  const [outroText, setOutroText] = useState("Mua ngay hôm nay!");
  const [variant, setVariant] = useState("A");

  const [bgMusic, setBgMusic] = useState<UploadedFile | null>(null);
  const [logo, setLogo] = useState<UploadedFile | null>(null);

  const [products, setProducts] = useState<ProductInput[]>([
    { image: null, text: "Sản phẩm 1", hook: "Mới" },
    { image: null, text: "Sản phẩm 2", hook: "Sale" },
  ]);

  useEffect(() => {
    if (projects.length > 0 && !selectedProjectId) setSelectedProjectId(projects[0].id);
    if (projects.length === 0) setIsCreatingProject(true);
  }, [projects, selectedProjectId]);

  // UI State
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState("");

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
        if (cfg.variant) setVariant(cfg.variant);
        
        if (cfg.assets) {
          if (cfg.assets.bg_music) {
            setBgMusic({
              file: undefined, id: null, s3_url: cfg.assets.bg_music, uploading: false, progress: 0,
              asset: { id: "", s3_url: cfg.assets.bg_music, file_name: "bg_music.mp3", file_size_bytes: 0, asset_type: "audio", mime_type: "audio/mpeg", created_at: "" }
            });
          }
          if (cfg.assets.logo) {
            setLogo({
              file: undefined, id: null, s3_url: cfg.assets.logo, uploading: false, progress: 0,
              asset: { id: "", s3_url: cfg.assets.logo, file_name: "logo.png", file_size_bytes: 0, asset_type: "image", mime_type: "image/png", created_at: "" }
            });
          }
        }
        
        if (cfg.input_json) {
          if (cfg.input_json.intro_text) setIntroText(cfg.input_json.intro_text);
          if (cfg.input_json.outro_text) setOutroText(cfg.input_json.outro_text);
          if (cfg.input_json.products && Array.isArray(cfg.input_json.products)) {
            const clonedProducts: ProductInput[] = cfg.input_json.products.map((p: any) => ({
              image: p.image ? {
                file: undefined,
                id: null,
                s3_url: p.image,
                asset: { id: "", s3_url: p.image, file_name: p.image.split("/").pop() || "image", file_size_bytes: 0, asset_type: "image", mime_type: "image/jpeg", created_at: "" },
                uploading: false,
                progress: 0,
              } : null,
              text: p.text || "",
              hook: p.hook || "",
            }));
            setProducts(clonedProducts);
          }
        }
      } catch (err) {
        console.error("Failed to load cloned job:", err);
      } finally {
        if (!cancelled) setCloneLoading(false);
      }
    };
    loadClone();
    return () => { cancelled = true; };
  }, [cloneJobId]);

  const addProduct = () => {
    if (products.length >= 10) return;
    setProducts([...products, { image: null, text: `Sản phẩm ${products.length + 1}`, hook: "" }]);
  };

  const removeProduct = (idx: number) => {
    setProducts(products.filter((_, i) => i !== idx));
  };

  const updateProduct = (idx: number, field: keyof ProductInput, value: any) => {
    const newProducts = [...products];
    newProducts[idx] = { ...newProducts[idx], [field]: value };
    setProducts(newProducts);
  };

  const handleSubmit = async () => {
    if (!isCreatingProject && !selectedProjectId) return setError("Vui lòng chọn dự án");
    if (isCreatingProject && !newProjectName.trim()) return setError("Vui lòng nhập tên dự án mới");
    if (products.length < 2) return setError("Cần ít nhất 2 sản phẩm");
    for (let i = 0; i < products.length; i++) {
      if (!products[i].image) return setError(`Sản phẩm ${i + 1} thiếu ảnh`);
      if (!products[i].text) return setError(`Sản phẩm ${i + 1} thiếu mô tả`);
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
      const finalProducts: any[] = [];
      
      const customAssets: Record<string, string> = {};

      if (bgMusic) {
        setUploadStatus("Đang upload nhạc nền...");
        if (bgMusic.file) {
          const res = await uploadAsset(bgMusic.file as File, "audio");
          customAssets.bg_music = res.s3_url;
          allAssetIds.push(res.id);
        } else if (bgMusic.asset) {
          customAssets.bg_music = bgMusic.asset.s3_url;
          allAssetIds.push(bgMusic.asset.id);
        }
      }

      if (logo) {
        setUploadStatus("Đang upload logo...");
        if (logo.file) {
          const res = await uploadAsset(logo.file as File, "image");
          customAssets.logo = res.s3_url;
          allAssetIds.push(res.id);
        } else if (logo.asset) {
          customAssets.logo = logo.asset.s3_url;
          allAssetIds.push(logo.asset.id);
        }
      }

      for (let i = 0; i < products.length; i++) {
        setUploadStatus(`Đang upload ảnh ${i + 1}/${products.length}...`);
        const item = products[i];
        let imageUrl = "";
        if (item.image?.file) {
          const res = await uploadAsset(item.image.file as File, "image");
          imageUrl = res.s3_url;
          allAssetIds.push(res.id);
        } else if (item.image?.asset) {
          imageUrl = item.image.asset.s3_url;
          allAssetIds.push(item.image.asset.id);
        }
        
        finalProducts.push({
          image: imageUrl,
          text: item.text,
          hook: item.hook
        });
      }

      setUploadStatus("Đang tạo job...");
      const payload = {
        job_type: "slideshow",
        priority,
        project_id: targetProjectId,
        asset_ids: allAssetIds,
        config_data: {
          variant,
          assets: Object.keys(customAssets).length > 0 ? customAssets : undefined,
          input_json: {
            intro_text: introText,
            outro_text: outroText,
            products: finalProducts
          }
        }
      };

      await api.post("/api/jobs", payload);
      navigate("/");
    } catch (err: any) {
      console.error(err);
      setError(err?.response?.data?.detail || err.message || "Failed to create slideshow job");
    } finally {
      setLoading(false);
      setUploadStatus("");
    }
  };

  const steps = [
    { id: 1, name: "Cài đặt chung", icon: FileText },
    { id: 2, name: "Danh sách sản phẩm", icon: ImagePlus },
    { id: 3, name: "Kiểm tra & Gửi", icon: Send }
  ];

  return (
    <div className="max-w-5xl mx-auto p-8 lg:p-12 space-y-10">
      <div className="space-y-2">
        <h2 className="text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-pink-400 to-rose-400">
          Tạo Slideshow 🖼️
        </h2>
      <p className="text-muted-foreground text-lg">
          Tạo video sản phẩm dạng lướt mượt mà với nhiều template (A, B, C). AI sẽ tự động điều chỉnh tốc độ, nhạc nền và chữ.
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
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="space-y-3">
                <label className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Intro Text</label>
                <input
                  type="text"
                  value={introText}
                  onChange={e => setIntroText(e.target.value)}
                  placeholder="Ví dụ: Top 5 sản phẩm nổi bật"
                  className="flex h-11 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all placeholder:text-muted-foreground/50"
                  required
                />
              </div>
              <div className="space-y-3">
                <label className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Outro Text</label>
                <input
                  type="text"
                  value={outroText}
                  onChange={e => setOutroText(e.target.value)}
                  placeholder="Ví dụ: Link dưới comment!"
                  className="flex h-11 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all placeholder:text-muted-foreground/50"
                  required
                />
              </div>
            </div>

            <div className="space-y-3">
              <label className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Variant Phối cảnh</label>
              <select
                value={variant}
                onChange={e => setVariant(e.target.value)}
                className="flex h-12 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-base text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all appearance-none"
              >
                  <option value="A" className="bg-[#1A1A24]">A - Energetic (Nhanh, Năng động)</option>
                  <option value="B" className="bg-[#1A1A24]">B - Smooth (Mượt mà, Vừa phải)</option>
                  <option value="C" className="bg-[#1A1A24]">C - Dramatic (Chậm rãi, Sang trọng)</option>
              </select>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <AssetSelector
                label="Nhạc nền"
                sublabel="MP3, WAV (Bắt buộc)"
                icon={<UploadCloud className="w-8 h-8 text-indigo-400" />}
                accept="audio/*"
                assetTypeFilter="audio"
                selectedFile={bgMusic}
                onSelect={(file, asset) => {
                  if (file || asset) setBgMusic({ file, asset, id: asset?.id || null, s3_url: asset?.s3_url || null, uploading: false, progress: 0 });
                  else setBgMusic(null);
                }}
              />
              <AssetSelector
                label="Logo Góc"
                sublabel="PNG, WebP trong suốt (Bắt buộc)"
                icon={<ImagePlus className="w-8 h-8 text-blue-400" />}
                accept="image/png,image/webp"
                assetTypeFilter="image"
                selectedFile={logo}
                onSelect={(file, asset) => {
                  if (file || asset) setLogo({ file, asset, id: asset?.id || null, s3_url: asset?.s3_url || null, uploading: false, progress: 0 });
                  else setLogo(null);
                }}
              />
            </div>

            <div className="flex justify-end pt-4">
              <Button
                onClick={() => setStep(2)}
                disabled={(isCreatingProject && !newProjectName) || (!isCreatingProject && !selectedProjectId)}
                className="glowing-button border-rose-500/50 bg-rose-500/20 text-rose-300 hover:bg-rose-500/30 px-8 py-3 rounded-xl font-medium"
              >
                Tiếp tục: Sản phẩm <ChevronRight className="w-5 h-5 ml-2" />
              </Button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-8 animate-in fade-in slide-in-from-right-8 duration-500">
            <div className="flex items-center justify-between border-b border-white/10 pb-4">
              <div>
                <h3 className="text-xl font-semibold text-white">Danh sách Ảnh Sản Phẩm</h3>
                <p className="text-sm text-muted-foreground">Ít nhất 2 sản phẩm, nhiều nhất 10 sản phẩm.</p>
              </div>
              <button
                type="button"
                onClick={addProduct}
                disabled={products.length >= 10}
                className="inline-flex items-center bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-sm font-medium transition-colors h-10 px-4 text-white disabled:opacity-50"
              >
                <Plus className="mr-2 h-4 w-4 text-rose-400" /> Thêm Sản phẩm
              </button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 max-h-[500px] overflow-y-auto pr-2 custom-scrollbar">
              {products.map((p, idx) => (
                <div key={idx} className="flex gap-4 p-5 rounded-2xl bg-black/40 border border-white/10 relative group hover:border-white/20 transition-all">
                  <div className="w-24 shrink-0">
                    <AssetSelector
                      label=""
                      sublabel="1080x1920"
                      icon={<ImagePlus className="w-6 h-6 text-rose-400" />}
                      accept="image/*"
                      assetTypeFilter="image"
                      selectedFile={p.image}
                      onSelect={(file, asset) => {
                        if (file || asset) {
                          updateProduct(idx, "image", { file, asset, id: asset?.id || null, s3_url: asset?.s3_url || null, uploading: false, progress: 0 });
                        }
                      }}
                    />
                  </div>

                  <div className="flex-1 space-y-3 pr-8">
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-muted-foreground uppercase">Tên / Mô tả</label>
                      <input
                        type="text"
                        value={p.text}
                        onChange={e => updateProduct(idx, "text", e.target.value)}
                        placeholder="Quần Jean Nam"
                        className="flex h-9 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-1 text-sm text-white focus:outline-none focus:ring-1 focus:ring-primary/50 transition-all"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-muted-foreground uppercase">Hook Badge</label>
                      <input
                        type="text"
                        value={p.hook}
                        onChange={e => updateProduct(idx, "hook", e.target.value)}
                        placeholder="Giảm 50%"
                        className="flex h-9 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-1 text-sm text-white focus:outline-none focus:ring-1 focus:ring-primary/50 transition-all"
                      />
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => removeProduct(idx)}
                    className="absolute top-4 right-4 p-2 text-muted-foreground hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>

            <div className="flex justify-between pt-4 border-t border-white/10">
              <button
                onClick={() => setStep(1)}
                className="px-6 py-3 rounded-xl font-medium text-white/80 hover:text-white hover:bg-white/5 transition-colors"
              >
                Trở lại
              </button>
              <Button
                onClick={() => setStep(3)}
                disabled={products.length < 2 || products.some(p => !p.image || !p.text) || !bgMusic || !logo}
                className="glowing-button border-rose-500/50 bg-rose-500/20 text-rose-300 hover:bg-rose-500/30 px-8 py-3 rounded-xl font-medium"
              >
                Kiểm tra & Render <ChevronRight className="w-5 h-5 ml-2" />
              </Button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-8 animate-in fade-in slide-in-from-right-8 duration-500">
            <div className="rounded-2xl bg-black/40 border border-white/10 p-8 space-y-6">
              <h3 className="text-2xl font-bold text-white flex items-center gap-3">
                <CheckCircle2 className="w-8 h-8 text-rose-400" /> Chuẩn Bị Render
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
                  className={cn("px-5 py-2 rounded-xl transition-all text-sm font-medium", priority === 1 ? "bg-rose-500/20 border border-rose-500/50 text-rose-400 shadow-[0_0_15px_rgba(244,63,94,0.2)]" : "border border-transparent text-muted-foreground hover:bg-rose-500/10 hover:text-rose-400/70")}
                >
                  Ưu tiên cao
                </button>
              </div>

              <div className="grid grid-cols-2 gap-8 text-sm">
                <div className="space-y-2">
                  <p className="text-muted-foreground">General Settings</p>
                  <p className="text-white font-medium flex justify-between border-b border-white/10 pb-2">
                    <span>Variant Code:</span> <span>{variant}</span>
                  </p>
                  <p className="text-white font-medium flex justify-between border-b border-white/10 pb-2">
                    <span>Số sản phẩm:</span> <span>{products.length} ảnh</span>
                  </p>
                  <p className="text-white font-medium flex justify-between border-b border-white/10 pb-2">
                    <span>Nhạc nền tùy chỉnh:</span> <span>Có</span>
                  </p>
                  <p className="text-white font-medium flex justify-between border-b border-white/10 pb-2">
                    <span>Logo tùy chỉnh:</span> <span>Có</span>
                  </p>
                </div>
                <div className="space-y-2">
                  <p className="text-muted-foreground">Mẫu hội thoại</p>
                  <p className="text-white font-medium flex justify-between border-b border-white/10 pb-2">
                    <span>Intro:</span> <span className="truncate ml-4">{introText}</span>
                  </p>
                  <p className="text-white font-medium flex justify-between border-b border-white/10 pb-2">
                    <span>Outro:</span> <span className="truncate ml-4">{outroText}</span>
                  </p>
                </div>
              </div>
            </div>

            <div className="flex justify-between pt-4">
              <button
                onClick={() => setStep(2)}
                className="px-6 py-3 rounded-xl font-medium text-white/80 hover:text-white hover:bg-white/5 transition-colors"
                disabled={loading}
              >
                Trở lại
              </button>
              <Button
                onClick={handleSubmit}
                isLoading={loading}
                className="glowing-button border-rose-500/50 bg-rose-500/20 text-white hover:bg-rose-500/40 px-10 py-3 rounded-xl font-medium shadow-[0_0_30px_rgba(244,63,94,0.4)]"
              >
                {!loading && <Send className="w-5 h-5 mr-2" />}
                {loading ? (uploadStatus || "Đang xử lý...") : "Bắt đầu Render"}
              </Button>
            </div>
          </div>
        )}
      </div>
      )}
    </div>
  );
}
