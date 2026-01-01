import AsyncStorage from '@react-native-async-storage/async-storage';

const API_URL_KEY = 'hue_api_url';
const DEFAULT_API_URL = 'http://192.168.1.100:8000';

export interface Status {
  ok: boolean;
  power: 'on' | 'off' | null;
  brightness: number | null;
  connected: boolean;
  error?: string;
}

export async function getApiUrl(): Promise<string> {
  const url = await AsyncStorage.getItem(API_URL_KEY);
  return url || DEFAULT_API_URL;
}

export async function setApiUrl(url: string): Promise<void> {
  await AsyncStorage.setItem(API_URL_KEY, url);
}

async function apiRequest<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const baseUrl = await getApiUrl();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);

  try {
    const res = await fetch(`${baseUrl}${endpoint}`, {
      ...options,
      signal: controller.signal,
    });
    clearTimeout(timeout);

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || 'Request failed');
    }
    return res.json();
  } catch (e) {
    clearTimeout(timeout);
    if (e instanceof Error && e.name === 'AbortError') {
      throw new Error('Connection timeout');
    }
    throw e;
  }
}

export async function getStatus(): Promise<Status> {
  return apiRequest<Status>('/status');
}

export async function turnOn(): Promise<void> {
  await apiRequest('/on', { method: 'POST' });
}

export async function turnOff(): Promise<void> {
  await apiRequest('/off', { method: 'POST' });
}

export async function toggle(): Promise<{ power: 'on' | 'off' }> {
  return apiRequest('/toggle', { method: 'POST' });
}

export async function setBrightness(level: number): Promise<void> {
  await apiRequest('/brightness', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ level }),
  });
}

export async function checkConnection(): Promise<boolean> {
  try {
    const baseUrl = await getApiUrl();
    const res = await fetch(`${baseUrl}/health`, { method: 'GET' });
    return res.ok;
  } catch {
    return false;
  }
}
