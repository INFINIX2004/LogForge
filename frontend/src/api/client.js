import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

export const logsAPI = {
  search: (params) => axios.get(`${API_BASE}/logs`, { params }),
  stats: (params) => axios.get(`${API_BASE}/stats`, { params }),
  services: () => axios.get(`${API_BASE}/services`),
  health: () => axios.get(`${API_BASE.replace('/api', '')}/health`)
};