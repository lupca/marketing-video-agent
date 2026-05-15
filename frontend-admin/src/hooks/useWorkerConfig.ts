import { useState, useEffect, useCallback } from "react";
import api from "../lib/api";

export interface WorkerConfig {
  id: string;
  worker_type: string;
  is_enabled: boolean;
  min_replicas: number;
  max_replicas: number;
  priority: number;
  config_data: any;
  created_at: string;
  updated_at: string | null;
  last_modified_by: string | null;
}

export interface WorkerStatusSummary {
  total_workers: number;
  enabled_workers: number;
  disabled_workers: number;
  configs: WorkerConfig[];
}

export function useWorkerConfig(autoRefresh: boolean = true, refreshIntervalMs: number = 10000) {
  const [summary, setSummary] = useState<WorkerStatusSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchConfigs = useCallback(async (isRefreshing = false) => {
    try {
      if (isRefreshing) setRefreshing(true);
      else setLoading(true);
      setError(null);
      const res = await api.get("/api/worker-config/");
      setSummary(res.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || "Failed to fetch worker configs");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchConfigs();
  }, [fetchConfigs]);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => fetchConfigs(true), refreshIntervalMs);
    return () => clearInterval(interval);
  }, [autoRefresh, refreshIntervalMs, fetchConfigs]);

  const toggleWorker = async (workerType: string, enabled: boolean) => {
    const endpoint = enabled ? "enable" : "disable";
    // Optimistic UI update
    if (summary) {
      const nextConfigs = summary.configs.map(c => 
        c.worker_type === workerType ? { ...c, is_enabled: enabled } : c
      );
      const enabledCount = nextConfigs.filter(c => c.is_enabled).length;
      
      setSummary({
        ...summary,
        enabled_workers: enabledCount,
        disabled_workers: summary.total_workers - enabledCount,
        configs: nextConfigs
      });
    }

    try {
      await api.post(`/api/worker-config/${workerType}/${endpoint}`);
      await fetchConfigs(true);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to update worker status");
      await fetchConfigs(true); // Revert on failure
    }
  };

  const batchUpdate = async (updates: Record<string, boolean>) => {
    try {
      setRefreshing(true);
      await api.post("/api/worker-config/batch/update", { updates });
      await fetchConfigs(true);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to batch update workers");
    } finally {
      setRefreshing(false);
    }
  };

  return { summary, loading, refreshing, error, fetchConfigs, toggleWorker, batchUpdate };
}
