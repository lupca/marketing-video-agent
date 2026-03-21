import { useState, useMemo, useEffect } from "react";
import { Modal } from "./Modal";
import { AssetTable } from "../features/assets/AssetTable";
import { useAssets, type Asset } from "../../hooks/useAssets";

interface AssetSelectModalProps {
  isOpen: boolean;
  onClose: () => void;
  assetTypeFilter: string;
  onSelect?: (asset: Asset) => void;
  multiple?: boolean;
  onSelectMultiple?: (assets: Asset[]) => void;
}

export function AssetSelectModal({ isOpen, onClose, assetTypeFilter, onSelect, multiple, onSelectMultiple }: AssetSelectModalProps) {
  // Fetch all to avoid dropping generic "audio" or "video" uploaded via the Assets page
  const { assets, loading, deleteAsset } = useAssets("all");
  const [currentPath, setCurrentPath] = useState("");
  const [selectedAssets, setSelectedAssets] = useState<Asset[]>([]);

  useEffect(() => {
    if (isOpen) {
      setSelectedAssets([]);
    }
  }, [isOpen]);

  const handleToggleAsset = (asset: Asset) => {
    setSelectedAssets(prev => {
      const isSelected = prev.some(a => a.id === asset.id);
      if (isSelected) {
        return prev.filter(a => a.id !== asset.id);
      } else {
        return [...prev, asset];
      }
    });
  };

  const handleConfirmMulti = () => {
    if (onSelectMultiple) {
      onSelectMultiple(selectedAssets);
    }
    onClose();
  };

  const filteredAssets = useMemo(() => {
    if (!assets) return [];
    if (!assetTypeFilter || assetTypeFilter === "all") return assets;
    
    return assets.filter(asset => {
      const type = asset.asset_type;
      if (assetTypeFilter === "clip" || assetTypeFilter === "video") {
        return type === "video" || type === "clip";
      }
      if (assetTypeFilter === "voiceover" || assetTypeFilter === "bgm" || assetTypeFilter === "audio") {
        return type === "audio" || type === "voiceover" || type === "bgm";
      }
      if (assetTypeFilter === "script" || assetTypeFilter === "doc") {
        return type === "script" || type === "doc";
      }
      if (assetTypeFilter === "image") {
        return type === "image";
      }
      return type === assetTypeFilter;
    });
  }, [assets, assetTypeFilter]);

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Chọn Asset từ Thư viện" maxWidth="4xl">
      <div className="p-4 bg-black/40">
        <AssetTable 
          assets={filteredAssets}
          loading={loading}
          deletingId={null}
          onDelete={deleteAsset}
          onUploadClick={() => {}}
          currentPath={currentPath}
          setCurrentPath={setCurrentPath}
          onSelectAsset={multiple ? undefined : (asset) => {
            if (onSelect) onSelect(asset);
            onClose();
          }}
          multiSelect={multiple}
          selectedAssets={selectedAssets}
          onToggleAsset={handleToggleAsset}
        />
        {multiple && (
          <div className="mt-4 pt-4 border-t border-white/10 flex justify-end gap-3">
            <button onClick={onClose} className="px-4 py-2 text-sm font-medium text-white/80 hover:text-white transition-colors bg-white/5 rounded-lg border border-white/10 hover:bg-white/10">Hủy</button>
            <button
              onClick={handleConfirmMulti}
              disabled={selectedAssets.length === 0}
              className="px-6 py-2 bg-primary hover:bg-primary/80 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors shadow-[0_0_15px_rgba(124,58,237,0.3)]"
            >
              Chọn {selectedAssets.length} file
            </button>
          </div>
        )}
      </div>
    </Modal>
  );
}
