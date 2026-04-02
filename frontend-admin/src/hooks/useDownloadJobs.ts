import { useState, useEffect, useCallback } from "react";
import api from "../lib/api";

export interface DownloadJob {
  id: number;
  user_id: string;
  source_url: string;
  format_type: "video" | "audio";
  status: "PENDING" | "PROCESSING" | "SUCCESS" | "FAILED";
  progress_percent: number;
  result_url: string | null;
  error_message: string | null;
  custom_filename: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface DownloadJobLog {
  id: number;
  job_id: number;
  log_level: string;
  message: string;
  created_at: string;
}

export function useDownloadJobs(autoRefresh: boolean = false, refreshIntervalMs: number = 5000) {
  const [jobs, setJobs] = useState<DownloadJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchJobs = useCallback(async (isRefreshing = false) => {
    try {
      if (isRefreshing) setRefreshing(true);
      else setLoading(true);
      const res = await api.get("/api/downloads");
      setJobs(res.data);
    } catch (err: any) {
      console.error("Failed to fetch download jobs:", err);
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
    const hasActive = jobs.some(j => j.status === "PROCESSING" || j.status === "PENDING");
    if (!hasActive) return;
    const interval = setInterval(() => fetchJobs(true), refreshIntervalMs);
    return () => clearInterval(interval);
  }, [autoRefresh, refreshIntervalMs, fetchJobs, jobs]);

  const deleteJob = async (id: number) => {
    await api.delete(`/api/downloads/${id}`);
    setJobs(prev => prev.filter(j => j.id !== id));
  };

  const getDownloadUrl = async (id: number): Promise<string> => {
    const res = await api.get(`/api/downloads/${id}/download`);
    return res.data.download_url;
  };

  const getJobLogs = async (id: number): Promise<DownloadJobLog[]> => {
    const res = await api.get(`/api/downloads/${id}/logs`);
    return res.data;
  };

  const hasActive = jobs.some(j => j.status === "PROCESSING" || j.status === "PENDING");

  return { jobs, loading, refreshing, fetchJobs, deleteJob, getDownloadUrl, getJobLogs, hasActive };
}
