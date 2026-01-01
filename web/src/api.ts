const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface Status {
  ok: boolean;
  power: 'on' | 'off' | null;
  brightness: number | null;
  connected: boolean;
  error?: string;
}

export async function getStatus(): Promise<Status> {
  const res = await fetch(`${API_BASE}/status`);
  if (!res.ok) throw new Error('Failed to get status');
  return res.json();
}

export async function turnOn(): Promise<void> {
  const res = await fetch(`${API_BASE}/on`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to turn on');
}

export async function turnOff(): Promise<void> {
  const res = await fetch(`${API_BASE}/off`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to turn off');
}

export async function toggle(): Promise<{ power: 'on' | 'off' }> {
  const res = await fetch(`${API_BASE}/toggle`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to toggle');
  return res.json();
}

export async function setBrightness(level: number): Promise<void> {
  const res = await fetch(`${API_BASE}/brightness`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ level }),
  });
  if (!res.ok) throw new Error('Failed to set brightness');
}
