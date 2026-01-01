import { StatusBar } from 'expo-status-bar';
import { useEffect, useState, useCallback } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  TextInput,
  Modal,
  Alert,
} from 'react-native';
import Slider from '@react-native-community/slider';
import {
  getStatus,
  toggle,
  setBrightness,
  getApiUrl,
  setApiUrl,
  checkConnection,
  Status,
} from './lib/api';

export default function App() {
  const [status, setStatus] = useState<Status | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [brightness, setBrightnessLocal] = useState(50);
  const [settingsVisible, setSettingsVisible] = useState(false);
  const [apiUrlInput, setApiUrlInput] = useState('');

  const fetchStatus = useCallback(async () => {
    try {
      const s = await getStatus();
      setStatus(s);
      if (s.brightness) setBrightnessLocal(s.brightness);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Connection failed');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  useEffect(() => {
    getApiUrl().then(setApiUrlInput);
  }, []);

  const handleToggle = async () => {
    try {
      setLoading(true);
      const result = await toggle();
      setStatus((prev) => (prev ? { ...prev, power: result.power } : null));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to toggle');
    } finally {
      setLoading(false);
    }
  };

  const handleBrightness = async (value: number) => {
    setBrightnessLocal(value);
  };

  const handleBrightnessComplete = async (value: number) => {
    try {
      await setBrightness(Math.round(value));
      setStatus((prev) => (prev ? { ...prev, brightness: Math.round(value) } : null));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to set brightness');
    }
  };

  const handleSaveSettings = async () => {
    await setApiUrl(apiUrlInput);
    setSettingsVisible(false);
    const connected = await checkConnection();
    if (connected) {
      Alert.alert('Success', 'Connected to server');
      fetchStatus();
    } else {
      Alert.alert('Error', 'Could not connect to server');
    }
  };

  const isOn = status?.power === 'on';
  const isConnected = status?.connected ?? false;

  return (
    <View style={styles.container}>
      <StatusBar style="light" />

      <View style={styles.header}>
        <Text style={styles.title}>Hue Light</Text>
        <TouchableOpacity onPress={() => setSettingsVisible(true)}>
          <Text style={styles.settingsButton}>Settings</Text>
        </TouchableOpacity>
      </View>

      <View
        style={[
          styles.statusIndicator,
          isConnected ? styles.connected : styles.disconnected,
        ]}
      >
        <Text style={styles.statusText}>
          {isConnected ? 'Connected' : 'Disconnected'}
        </Text>
      </View>

      {error && (
        <View style={styles.errorContainer}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      <TouchableOpacity
        style={[styles.powerButton, isOn ? styles.powerOn : styles.powerOff]}
        onPress={handleToggle}
        disabled={loading || !isConnected}
        activeOpacity={0.8}
      >
        <Text style={[styles.powerIcon, isOn ? styles.powerIconOn : styles.powerIconOff]}>
          ⏻
        </Text>
        <Text style={[styles.powerLabel, isOn ? styles.powerLabelOn : styles.powerLabelOff]}>
          {isOn ? 'ON' : 'OFF'}
        </Text>
      </TouchableOpacity>

      <View style={styles.brightnessContainer}>
        <Text style={styles.brightnessLabel}>Brightness: {Math.round(brightness)}%</Text>
        <Slider
          style={styles.slider}
          minimumValue={1}
          maximumValue={100}
          value={brightness}
          onValueChange={handleBrightness}
          onSlidingComplete={handleBrightnessComplete}
          disabled={!isConnected || !isOn}
          minimumTrackTintColor="#feca57"
          maximumTrackTintColor="#2d2d44"
          thumbTintColor="#feca57"
        />
      </View>

      <Modal visible={settingsVisible} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Settings</Text>
            <Text style={styles.inputLabel}>API Server URL</Text>
            <TextInput
              style={styles.input}
              value={apiUrlInput}
              onChangeText={setApiUrlInput}
              placeholder="http://192.168.1.100:8000"
              placeholderTextColor="#666"
              autoCapitalize="none"
              autoCorrect={false}
            />
            <View style={styles.modalButtons}>
              <TouchableOpacity
                style={styles.modalButton}
                onPress={() => setSettingsVisible(false)}
              >
                <Text style={styles.modalButtonText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalButton, styles.modalButtonPrimary]}
                onPress={handleSaveSettings}
              >
                <Text style={styles.modalButtonTextPrimary}>Save</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1a1a2e',
    alignItems: 'center',
    paddingTop: 60,
    paddingHorizontal: 20,
  },
  header: {
    width: '100%',
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
  },
  title: {
    fontSize: 28,
    fontWeight: '300',
    color: '#fff',
    letterSpacing: 2,
  },
  settingsButton: {
    color: '#feca57',
    fontSize: 16,
  },
  statusIndicator: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    marginBottom: 30,
  },
  connected: {
    backgroundColor: 'rgba(46, 213, 115, 0.2)',
  },
  disconnected: {
    backgroundColor: 'rgba(255, 107, 107, 0.2)',
  },
  statusText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '500',
  },
  errorContainer: {
    backgroundColor: 'rgba(255, 107, 107, 0.2)',
    padding: 12,
    borderRadius: 8,
    marginBottom: 20,
    width: '100%',
  },
  errorText: {
    color: '#ff6b6b',
    textAlign: 'center',
  },
  powerButton: {
    width: 180,
    height: 180,
    borderRadius: 90,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 40,
  },
  powerOff: {
    backgroundColor: '#2d2d44',
  },
  powerOn: {
    backgroundColor: '#feca57',
    shadowColor: '#feca57',
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.4,
    shadowRadius: 20,
    elevation: 10,
  },
  powerIcon: {
    fontSize: 60,
  },
  powerIconOff: {
    color: '#666',
  },
  powerIconOn: {
    color: '#1a1a2e',
  },
  powerLabel: {
    fontSize: 20,
    fontWeight: '600',
    marginTop: 8,
  },
  powerLabelOff: {
    color: '#666',
  },
  powerLabelOn: {
    color: '#1a1a2e',
  },
  brightnessContainer: {
    width: '100%',
    alignItems: 'center',
  },
  brightnessLabel: {
    color: '#aaa',
    fontSize: 16,
    marginBottom: 10,
  },
  slider: {
    width: '100%',
    height: 40,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  modalContent: {
    backgroundColor: '#1a1a2e',
    padding: 24,
    borderRadius: 16,
    width: '90%',
    maxWidth: 400,
  },
  modalTitle: {
    fontSize: 24,
    fontWeight: '600',
    color: '#fff',
    marginBottom: 20,
  },
  inputLabel: {
    color: '#aaa',
    marginBottom: 8,
  },
  input: {
    backgroundColor: '#2d2d44',
    color: '#fff',
    padding: 12,
    borderRadius: 8,
    fontSize: 16,
    marginBottom: 20,
  },
  modalButtons: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 12,
  },
  modalButton: {
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 8,
  },
  modalButtonPrimary: {
    backgroundColor: '#feca57',
  },
  modalButtonText: {
    color: '#aaa',
    fontSize: 16,
  },
  modalButtonTextPrimary: {
    color: '#1a1a2e',
    fontSize: 16,
    fontWeight: '600',
  },
});
