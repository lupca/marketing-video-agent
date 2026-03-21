import { useState, useEffect, useCallback } from "react";
import api from "../lib/api";

export interface VideoJob {
  id: number;
  job_type: string;
  status: "PENDING" | "PROCESSING" | "SUCCESS" | "FAILED";
  priority: number;
  progress_percent: number;
  config_data: any;
  result_url: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface JobLog {
  id: number;
  job_id: number;
  log_level: string;
  message: string;
  created_at: string;
}

export function useJobs(autoRefresh: boolean = false, refreshIntervalMs: number = 5000) {
  const [jobs, setJobs] = useState<VideoJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchJobs = useCallback(async (isRefreshing = false) => {
    try {
      if (isRefreshing) setRefreshing(true);
      else setLoading(true);
      setError(null);
      const res = await api.get("/api/jobs");
      setJobs(res.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || "Failed to fetch jobs");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => fetchJobs(true), refreshIntervalMs);
    return () => clearInterval(interval);
  }, [autoRefresh, refreshIntervalMs, fetchJobs]);

  const deleteJob = async (id: number) => {
    await api.delete(`/api/jobs/${id}`);
    setJobs(prev => prev.filter(j => j.id !== id));
  };

  const getDownloadUrl = async (id: number): Promise<string> => {
    const res = await api.get(`/api/jobs/${id}/download`);
    return res.data.download_url;
  };

  const getJobLogs = async (id: number): Promise<JobLog[]> => {
    const res = await api.get(`/api/jobs/${id}/logs`);
    return res.data;
  };

  const hasProcessing = jobs.some(j => j.status === "PROCESSING");

  return { jobs, loading, refreshing, error, fetchJobs, deleteJob, getDownloadUrl, getJobLogs, hasProcessing };
}
