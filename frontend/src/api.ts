import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export const api = axios.create({
  baseURL: API_URL,
});

export interface WorkItem {
  id: string;
  component_id: string;
  component_type: string;
  severity: string;
  status: string;
  title: string;
  signal_count: number;
  first_signal_at: string;
  last_signal_at: string;
  created_at: string;
  updated_at: string;
}

export interface Signal {
  _id: string;
  signal_id: string;
  component_id: string;
  component_type: string;
  error_type: string;
  message: string;
  payload: any;
  timestamp: string;
  latency_ms: number;
}

export interface Health {
  status: string;
  uptime_seconds: number;
  signals_per_sec: number;
  pg_pool_size: number;
}

export const fetchWorkItems = async (): Promise<WorkItem[]> => {
  const { data } = await api.get('/work_items');
  return data;
};

export const fetchSignals = async (itemId: string): Promise<Signal[]> => {
  const { data } = await api.get(`/work_items/${itemId}/signals`);
  return data;
};

export const fetchHealth = async (): Promise<Health> => {
  const { data } = await api.get('/health');
  return data;
};

export const submitRca = async (itemId: string, rca: any) => {
  const { data } = await api.post(`/work_items/${itemId}/rca`, rca);
  return data;
};
