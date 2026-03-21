import React, { useState, useRef } from "react";
import { CheckCircle2, FolderSearch } from "lucide-react";
import type { UploadedFile } from "../features/review/types";
import { AssetSelectModal } from "./AssetSelectModal";
import type { Asset } from "../../hooks/useAssets";

interface AssetSelectorProps {
  label: string;
  sublabel: string;
  icon: React.ReactNode;
  accept: string;
  assetTypeFilter: string;
  selectedFile: UploadedFile | null;
  onSelect: (file: File | undefined, asset: Asset | undefined) => void;
  required?: boolean;
}

export function AssetSelector({
  label, sublabel, icon, accept, assetTypeFilter, selectedFile, onSelect, required
}: AssetSelectorProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const displayFileName = selectedFile?.file?.name || selectedFile?.asset?.file_name;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-sm font-semibold text-white/90 uppercase tracking-wider flex items-center gap-1">
          {label} {required && <span className="text-primary">*</span>}
        </label>
        <button
          type="button"
          onClick={() => setIsModalOpen(true)}
          className="text-xs text-primary hover:bg-primary/10 px-2 py-1 rounded-md transition-colors flex items-center gap-1"
        >
          <FolderSearch className="w-3.5 h-3.5" /> Thư viện
        </button>
      </div>

      <div 
        onClick={() => fileInputRef.current?.click()}
        className="flex flex-col items-center justify-center w-full h-36 border-2 border-dashed border-white/20 rounded-2xl cursor-pointer hover:bg-white/5 hover:border-primary/50 transition-all duration-300 group"
      >
        <div className="flex flex-col items-center justify-center py-4 text-center px-4 pointer-events-none">
          <div className="p-3 mb-2 rounded-full bg-white/5 group-hover:bg-primary/20 transition-colors">
            {icon}
          </div>
          <p className="text-xs text-muted-foreground">{sublabel}</p>
        </div>
        <input 
          type="file" 
          ref={fileInputRef}
          className="hidden" 
          accept={accept} 
          onChange={e => {
            if (e.target.files && e.target.files.length > 0) {
              onSelect(e.target.files[0], undefined);
            }
          }} 
        />
      </div>

      {displayFileName && (
        <div className="flex items-center gap-2 text-xs text-green-400 bg-green-400/10 p-2 rounded-lg border border-green-400/20 break-all">
          <CheckCircle2 className="w-3.5 h-3.5 shrink-0" /> 
          {displayFileName.length > 40 ? displayFileName.slice(0, 40) + '...' : displayFileName}
        </div>
      )}

      <AssetSelectModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        assetTypeFilter={assetTypeFilter}
        onSelect={(asset) => onSelect(undefined, asset)}
      />
    </div>
  );
}
