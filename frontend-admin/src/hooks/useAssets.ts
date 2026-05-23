import { useState, useEffect, useCallback } from "react";
import api from "../lib/api";

export interface Folder {
  id: string;
  user_id: string;
  name: string;
  parent_id?: string | null;
  is_job_folder: boolean;
  job_id?: number | null;
  created_at: string;
  updated_at?: string | null;
}

export interface Asset {
  id: string;
  user_id?: string;
  asset_type: string;
  file_name: string;
  display_name: string;
  file_size_bytes: number;
  s3_url: string;
  presigned_url?: string;
  mime_type: string;
  folder_id?: string | null;
  source: string; // "upload" | "generated"
  full_path?: string;
  created_at: string;
}

export function useAssets(typeFilter?: string, initialFolderId: string | null = null) {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [currentFolderId, setCurrentFolderId] = useState<string | null>(initialFolderId);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchFolders = useCallback(async () => {
    try {
      const res = await api.get("/api/folders");
      setFolders(res.data);
    } catch (err: any) {
      console.error("Failed to fetch folders", err);
    }
  }, []);

  const fetchAssets = useCallback(async (isRefreshing = false, folderIdOverride?: string | null) => {
    try {
      if (isRefreshing) setRefreshing(true);
      else setLoading(true);
      setError(null);

      const targetFolderId = folderIdOverride !== undefined ? folderIdOverride : currentFolderId;
      const params: any = {};
      
      if (typeFilter && typeFilter !== "all") {
        params.asset_type = typeFilter;
      }
      
      if (targetFolderId) {
        params.folder_id = targetFolderId;
      }

      const res = await api.get("/api/assets", { params });
      setAssets(res.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || "Failed to fetch assets");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [typeFilter, currentFolderId]);

  // Load initially
  useEffect(() => {
    fetchFolders();
    fetchAssets(false, currentFolderId);
  }, [fetchFolders, fetchAssets, currentFolderId]);

  const deleteAsset = async (id: string) => {
    await api.delete(`/api/assets/${id}`);
    setAssets(prev => prev.filter(a => a.id !== id));
  };

  const uploadAsset = async (file: File, assetType: string, segmentName?: string, folderPath?: string, folderId?: string | null) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("asset_type", assetType);
    if (segmentName) formData.append("segment_name", segmentName);
    if (folderPath) formData.append("folder_path", folderPath);
    
    // Pass folder ID if uploading into a virtual folder
    const targetFolderId = folderId !== undefined ? folderId : currentFolderId;
    if (targetFolderId) {
      formData.append("folder_id", targetFolderId);
    }

    const res = await api.post("/api/assets/upload", formData);
    // Refresh the list after upload
    await fetchAssets(true);
    return { s3_url: res.data.s3_url, id: res.data.id };
  };

  const createFolder = async (name: string, parentId?: string | null) => {
    const res = await api.post("/api/folders", {
      name,
      parent_id: parentId !== undefined ? parentId : currentFolderId
    });
    await fetchFolders();
    return res.data as Folder;
  };

  const renameFolder = async (folderId: string, newName: string) => {
    const res = await api.put(`/api/folders/${folderId}`, {
      name: newName
    });
    await fetchFolders();
    return res.data as Folder;
  };

  const moveFolder = async (folderId: string, targetParentId: string | null) => {
    const res = await api.put(`/api/folders/${folderId}`, {
      parent_id: targetParentId === null ? "" : targetParentId
    });
    await fetchFolders();
    return res.data as Folder;
  };

  const deleteFolder = async (folderId: string) => {
    await api.delete(`/api/folders/${folderId}`);
    await fetchFolders();
    if (currentFolderId === folderId) {
      setCurrentFolderId(null);
    } else {
      await fetchAssets(true);
    }
  };

  const renameAsset = async (assetId: string, newDisplayName: string) => {
    const res = await api.put(`/api/assets/${assetId}`, {
      display_name: newDisplayName
    });
    // Update local state
    setAssets(prev => prev.map(a => a.id === assetId ? { ...a, display_name: newDisplayName } : a));
    return res.data as Asset;
  };

  const moveAsset = async (assetId: string, targetFolderId: string | null) => {
    const res = await api.put(`/api/assets/${assetId}`, {
      folder_id: targetFolderId === null ? "" : targetFolderId
    });
    // Remove from active list since it moved to another folder
    setAssets(prev => prev.filter(a => a.id !== assetId));
    return res.data as Asset;
  };

  return {
    assets,
    folders,
    currentFolderId,
    setCurrentFolderId,
    loading,
    refreshing,
    error,
    fetchAssets,
    fetchFolders,
    deleteAsset,
    uploadAsset,
    createFolder,
    renameFolder,
    moveFolder,
    deleteFolder,
    renameAsset,
    moveAsset
  };
}
