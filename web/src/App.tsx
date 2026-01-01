import { useEffect, useState, useCallback } from 'react';
import { getStatus, toggle, setBrightness, type Status } from './api';
import './App.css';

function App() {
	const [status, setStatus] = useState<Status | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [brightness, setBrightnessLocal] = useState(50);

	const fetchStatus = useCallback(async () => {
		try {
			const s = await getStatus();
			setStatus(s);
			if (s.brightness) setBrightnessLocal(s.brightness);
			setError(null);
		} catch (e) {
			setError('Could not connect to server');
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		fetchStatus();
		const interval = setInterval(fetchStatus, 5000);
		return () => clearInterval(interval);
	}, [fetchStatus]);

	const handleToggle = async () => {
		try {
			setLoading(true);
			const result = await toggle();
			setStatus(prev => prev ? { ...prev, power: result.power } : null);
		} catch (e) {
			setError('Failed to toggle light');
		} finally {
			setLoading(false);
		}
	};

	const handleBrightness = async (value: number) => {
		setBrightnessLocal(value);
		try {
			await setBrightness(value);
			setStatus(prev => prev ? { ...prev, brightness: value } : null);
		} catch (e) {
			setError('Failed to set brightness');
		}
	};

	const isOn = status?.power === 'on';
	const isConnected = status?.connected ?? false;

	return (
		<div className="app">
			<header>
				<h1>Hue Light</h1>
				<div className={`status-indicator ${isConnected ? 'connected' : 'disconnected'}`}>
					{isConnected ? 'Connected' : 'Disconnected'}
				</div>
			</header>

			{error && <div className="error">{error}</div>}

			<main>
				<button
					className={`power-button ${isOn ? 'on' : 'off'}`}
					onClick={handleToggle}
					disabled={loading || !isConnected}
				>
					<div className="power-icon">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
							<path d="M12 2v10M18.4 6.6a9 9 0 1 1-12.8 0" />
						</svg>
					</div>
					<span>{isOn ? 'ON' : 'OFF'}</span>
				</button>

				<div className="brightness-control">
					<label>Brightness: {brightness}%</label>
					<input
						type="range"
						min="1"
						max="100"
						value={brightness}
						onChange={(e) => handleBrightness(Number(e.target.value))}
						disabled={!isConnected || !isOn}
					/>
				</div>
			</main>
		</div>
	);
}

export default App;
