import React from "react";
import { CheckCircle2 } from "lucide-react";
import type { UploadedFile } from "./types";

interface FileDropzoneProps {
  label: string;
  sublabel: string;
  icon: React.ReactNode;
  accept: string;
  selectedFile: UploadedFile | null;
  onSelect: (file: File | undefined) => void;
  required?: boolean;
}

export function FileDropzone({
  label, sublabel, icon, accept, selectedFile, onSelect, required
}: FileDropzoneProps) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-semibold text-white/90 uppercase tracking-wider flex items-center gap-1">
        {label} {required && <span className="text-primary">*</span>}
      </label>
      <label className="flex flex-col items-center justify-center w-full h-36 border-2 border-dashed border-white/20 rounded-2xl cursor-pointer hover:bg-white/5 hover:border-primary/50 transition-all duration-300 group">
        <div className="flex flex-col items-center justify-center py-4 text-center px-4">
          <div className="p-3 mb-2 rounded-full bg-white/5 group-hover:bg-primary/20 transition-colors">
            {icon}
          </div>
          <p className="text-xs text-muted-foreground">{sublabel}</p>
        </div>
        <input type="file" className="hidden" accept={accept} onChange={e => onSelect(e.target.files?.[0])} />
      </label>
      {selectedFile && (
        <div className="flex items-center gap-2 text-xs text-green-400 bg-green-400/10 p-2 rounded-lg border border-green-400/20">
          <CheckCircle2 className="w-3.5 h-3.5" /> {(selectedFile.file?.name || selectedFile.asset?.file_name || "").length > 30 ? (selectedFile.file?.name || selectedFile.asset?.file_name || "").slice(0, 30) + '...' : (selectedFile.file?.name || selectedFile.asset?.file_name || "")}
        </div>
      )}
    </div>
  );
}
