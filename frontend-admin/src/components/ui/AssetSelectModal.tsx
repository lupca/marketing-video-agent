import { useState, useMemo } from "react";
import { Modal } from "./Modal";
import { AssetTable } from "../features/assets/AssetTable";
import { useAssets, type Asset } from "../../hooks/useAssets";

interface AssetSelectModalProps {
  isOpen: boolean;
  onClose: () => void;
  assetTypeFilter: string;
  onSelect: (asset: Asset) => void;
}

export function AssetSelectModal({ isOpen, onClose, assetTypeFilter, onSelect }: AssetSelectModalProps) {
  // Fetch all to avoid dropping generic "audio" or "video" uploaded via the Assets page
  const { assets, loading, deleteAsset } = useAssets("all");
  const [currentPath, setCurrentPath] = useState("");

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
          onSelectAsset={(asset) => {
            onSelect(asset);
            onClose();
          }}
        />
      </div>
    </Modal>
  );
}
