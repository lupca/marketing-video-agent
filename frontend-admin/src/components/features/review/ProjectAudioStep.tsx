import { Folder, Plus, Mic, FileText, Music, ChevronRight } from "lucide-react";
import { cn } from "../../../lib/utils";
import { FileDropzone } from "./FileDropzone";
import type { UploadedFile } from "./types";
import type { Project } from "../../../hooks/useProjects";
import { Button } from "../../ui/Button";

interface ProjectAudioStepProps {
  projects: Project[];
  selectedProjectId: string;
  setSelectedProjectId: (id: string) => void;
  isCreatingProject: boolean;
  setIsCreatingProject: (val: boolean) => void;
  newProjectName: string;
  setNewProjectName: (val: string) => void;
  voiceover: UploadedFile | null;
  setVoiceover: (f: UploadedFile | null) => void;
  script: UploadedFile | null;
  setScript: (f: UploadedFile | null) => void;
  bgm: UploadedFile | null;
  setBgm: (f: UploadedFile | null) => void;
  language: string;
  setLanguage: (val: string) => void;
  onNext: () => void;
  canGoNext: boolean;
}

export function ProjectAudioStep(props: ProjectAudioStepProps) {
  const handleAudioFile = (file: File | undefined, setter: (f: UploadedFile | null) => void) => {
    if (!file) return;
    setter({ file, id: null, s3_url: null, uploading: false, progress: 0 });
  };

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-right-8 duration-500">
      <div className="space-y-4">
        <label className="text-sm font-semibold text-white/90 uppercase tracking-wider flex items-center gap-2">
          <Folder className="w-4 h-4 text-primary" /> Dự án
        </label>

        <div className="flex flex-col sm:flex-row gap-4">
          <button
            type="button"
            onClick={() => props.setIsCreatingProject(false)}
            className={cn("flex-1 px-4 py-3 rounded-xl border flex items-center gap-2 justify-center transition-all", !props.isCreatingProject ? "bg-primary/20 border-primary text-white shadow-[0_0_15px_rgba(124,58,237,0.3)]" : "bg-white/5 border-white/10 text-muted-foreground hover:bg-white/10")}
          >
            <Folder className="w-4 h-4" /> Chọn dự án có sẵn
          </button>
          <button
            type="button"
            onClick={() => props.setIsCreatingProject(true)}
            className={cn("flex-1 px-4 py-3 rounded-xl border flex items-center gap-2 justify-center transition-all", props.isCreatingProject ? "bg-primary/20 border-primary text-white shadow-[0_0_15px_rgba(124,58,237,0.3)]" : "bg-white/5 border-white/10 text-muted-foreground hover:bg-white/10")}
          >
            <Plus className="w-4 h-4" /> Tạo dự án mới
          </button>
        </div>

        {props.isCreatingProject ? (
          <div className="space-y-2 animate-in fade-in slide-in-from-top-2">
            <input
              type="text"
              value={props.newProjectName}
              onChange={e => props.setNewProjectName(e.target.value)}
              placeholder="Tên dự án mới..."
              className="flex h-12 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-base text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all placeholder:text-muted-foreground/50"
            />
          </div>
        ) : (
          <div className="space-y-2 animate-in fade-in slide-in-from-top-2">
            <select
              value={props.selectedProjectId}
              onChange={e => props.setSelectedProjectId(e.target.value)}
              className="flex h-12 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-base text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all appearance-none"
            >
              {props.projects.length === 0 ? (
                <option disabled value="" className="bg-[#1A1A24]">Bạn chưa có dự án nào</option>
              ) : (
                props.projects.map(p => (
                  <option key={p.id} value={p.id} className="bg-[#1A1A24]">{p.name}</option>
                ))
              )}
            </select>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <FileDropzone
          label="Giọng đọc (Voiceover)"
          sublabel="MP3 — File thu âm chính"
          icon={<Mic className="w-6 h-6 text-primary" />}
          accept="audio/mpeg,audio/*"
          selectedFile={props.voiceover}
          onSelect={f => handleAudioFile(f, props.setVoiceover)}
          required
        />
        <FileDropzone
          label="Kịch bản (Script)"
          sublabel="TXT — Nội dung đọc 100%"
          icon={<FileText className="w-6 h-6 text-indigo-400" />}
          accept=".txt,text/plain"
          selectedFile={props.script}
          onSelect={f => handleAudioFile(f, props.setScript)}
          required
        />
        <FileDropzone
          label="Nhạc nền (BGM)"
          sublabel="MP3 — Tùy chọn"
          icon={<Music className="w-6 h-6 text-cyan-400" />}
          accept="audio/mpeg,audio/*"
          selectedFile={props.bgm}
          onSelect={f => handleAudioFile(f, props.setBgm)}
        />
      </div>

      <div className="flex items-center gap-4 bg-white/5 p-4 rounded-xl border border-white/10">
        <label className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Ngôn ngữ</label>
        <select
          value={props.language}
          onChange={e => props.setLanguage(e.target.value)}
          className="h-10 rounded-xl border border-white/10 bg-white/5 px-4 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50 appearance-none"
        >
          <option value="vi" className="bg-[#1A1A24]">🇻🇳 Tiếng Việt</option>
          <option value="en" className="bg-[#1A1A24]">🇺🇸 English</option>
        </select>
      </div>

      <div className="flex justify-end pt-4">
        <Button onClick={props.onNext} disabled={!props.canGoNext} className="glowing-button px-8 py-3 rounded-xl font-medium">
          Tiếp tục <ChevronRight className="w-5 h-5 ml-2" />
        </Button>
      </div>
    </div>
  );
}
