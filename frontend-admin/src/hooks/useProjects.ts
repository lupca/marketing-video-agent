import { useState, useEffect, useCallback } from "react";
import api from "../lib/api";

export interface Project {
  id: string;
  name: string;
  description?: string;
  created_at: string;
  jobs_count: number;
}

export function useProjects() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProjects = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.get("/api/projects");
      setProjects(res.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || "Failed to fetch projects");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const createProject = async (name: string, description: string = "") => {
    const res = await api.post("/api/projects", { name, description });
    setProjects(prev => [res.data, ...prev]);
    return res.data;
  };

  const deleteProject = async (id: string) => {
    await api.delete(`/api/projects/${id}`);
    setProjects(prev => prev.filter(p => p.id !== id));
  };

  const getProject = useCallback(async (id: string) => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.get(`/api/projects/${id}`);
      return res.data;
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || "Failed to fetch project");
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { projects, loading, error, fetchProjects, createProject, deleteProject, getProject };
}
