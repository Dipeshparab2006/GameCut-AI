import numpy as np
from scipy.io import wavfile

def analyze_audio_excitement(audio_path, window_size_sec=1.0):
    """
    Analyzes audio volume/energy over time to find excitement peaks.
    """
    print(f"Analyzing audio excitement for {audio_path}...")
    try:
        sample_rate, data = wavfile.read(audio_path)
    except Exception as e:
        print(f"Could not read audio file: {e}")
        return []
        
    if len(data.shape) > 1:
        data = data.mean(axis=1)
        
    window_samples = int(sample_rate * window_size_sec)
    
    energies = []
    for i in range(0, len(data), window_samples):
        window = data[i:i+window_samples]
        if len(window) == 0:
            break
        window_float = window.astype(np.float32)
        rms = np.sqrt(np.mean(window_float**2))
        energies.append(float(rms))
        
    max_energy = max(energies) if energies else 1
    normalized = [e / max_energy for e in energies]
    
    results = []
    for i, e in enumerate(normalized):
        results.append({
            "start_time": i * window_size_sec,
            "end_time": (i + 1) * window_size_sec,
            "energy": e
        })
        
    return results
