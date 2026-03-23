import { useState, useEffect, useCallback } from "react";
import api from "../lib/api";

export interface Asset {
  id: string;
  asset_type: string; // Used to be strictly "video" | "audio" | "image" | "font" but it's dynamic ("voiceover", "clip", "bgm", "script", "doc", etc)
  file_name: string;
  file_size_bytes: number;
  s3_url: string;
  presigned_url?: string;
  mime_type: string;
  full_path?: string;
  created_at: string;
}

export function useAssets(typeFilter?: string) {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAssets = useCallback(async (isRefreshing = false) => {
    try {
      if (isRefreshing) setRefreshing(true);
      else setLoading(true);
      setError(null);
      const res = await api.get("/api/assets", {
        params: typeFilter && typeFilter !== "all" ? { asset_type: typeFilter } : {}
      });
      setAssets(res.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || "Failed to fetch assets");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [typeFilter]);

  useEffect(() => {
    fetchAssets();
  }, [fetchAssets]);

  const deleteAsset = async (id: string) => {
    await api.delete(`/api/assets/${id}`);
    setAssets(prev => prev.filter(a => a.id !== id));
  };

  const uploadAsset = async (file: File, assetType: string, segmentName?: string, folderPath?: string) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("asset_type", assetType);
    if (segmentName) formData.append("segment_name", segmentName);
    if (folderPath) formData.append("folder_path", folderPath);

    const res = await api.post("/api/assets/upload", formData);
    // Refresh the list after upload
    await fetchAssets(true);
    return { s3_url: res.data.s3_url, id: res.data.id };
  };

  return { assets, loading, refreshing, error, fetchAssets, deleteAsset, uploadAsset };
}
