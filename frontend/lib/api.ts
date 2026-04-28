import axios from "axios";
import Cookies from "js-cookie";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
  withCredentials: false,
});

api.interceptors.request.use((config) => {
  const token = Cookies.get("axon_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      Cookies.remove("axon_token");
      Cookies.remove("axon_user");
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  }
);

// Auth
export const authApi = {
  signup: (email: string, password: string, name: string) =>
    api.post("/api/auth/signup", { email, password, name }),

  login: (email: string, password: string) =>
    api.post("/api/auth/login", { email, password }),

  logout: () => api.post("/api/auth/logout"),

  me: () => api.get("/api/auth/me"),
};

// Agents
export const agentsApi = {
  list: () => api.get("/api/agents"),

  create: (name: string, description?: string) =>
    api.post("/api/agents", { name, description }),

  get: (id: string) => api.get(`/api/agents/${id}`),

  start: (id: string) => api.post(`/api/agents/${id}/start`),

  stop: (id: string) => api.post(`/api/agents/${id}/stop`),

  delete: (id: string) => api.delete(`/api/agents/${id}`),

  history: (id: string) => api.get(`/api/agents/${id}/history`),
};

export default api;
