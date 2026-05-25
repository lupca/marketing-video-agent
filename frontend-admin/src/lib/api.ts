import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:9100',
});

// Request interceptor to add the auth token header to every request
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);


// Response interceptor to automatically clean up draft job if delete_draft param is in URL
api.interceptors.response.use(
  async (response) => {
    if (response.config.method === 'post' && response.config.url?.includes('/api/jobs')) {
      const urlParams = new URLSearchParams(window.location.search);
      const deleteDraftId = urlParams.get('delete_draft');
      if (deleteDraftId) {
        console.log("Auto-cleaning draft job ID:", deleteDraftId);
        try {
          // Use direct axios to avoid circular hook calls if any, using the same Authorization header
          const token = localStorage.getItem('token');
          const headers: Record<string, string> = {};
          if (token) {
            headers['Authorization'] = `Bearer ${token}`;
          }
          await axios.delete(`http://localhost:9100/api/jobs/${deleteDraftId}`, { headers });
          console.log("Draft job successfully deleted:", deleteDraftId);
        } catch (err) {
          console.error("Failed to delete draft job:", err);
        }
      }
    }
    return response;
  },
  (error) => {
    if (error.response && error.response.data && Array.isArray(error.response.data.detail)) {
      const formattedMsg = error.response.data.detail
        .map((d: any) => {
          const field = d.loc ? d.loc.filter((l: any) => l !== "body").join(".") : "field";
          return `${field}: ${d.msg}`;
        })
        .join(", ");
      error.response.data.detail = formattedMsg;
    }
    return Promise.reject(error);
  }
);

export default api;

