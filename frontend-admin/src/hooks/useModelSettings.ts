import { useState, useEffect, useCallback } from "react";
import api from "../lib/api";

export interface ModelSettings {
  base_url: string;
  model_name: string;
  source: "database" | "environment";
}

export function useModelSettings() {
  const [settings, setSettings] = useState<ModelSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSettings = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.get("/api/system/model-settings");
      setSettings(res.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || "Failed to fetch model settings");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const updateSettings = async (base_url: string, model_name: string) => {
    try {
      setUpdating(true);
      setError(null);
      const res = await api.put("/api/system/model-settings", { base_url, model_name });
      setSettings(res.data);
      return res.data;
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "Failed to update model settings";
      setError(msg);
      throw new Error(msg);
    } finally {
      setUpdating(false);
    }
  };

  return { settings, loading, updating, error, fetchSettings, updateSettings };
}
