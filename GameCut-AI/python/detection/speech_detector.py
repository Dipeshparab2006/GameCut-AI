try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

def transcribe_audio(audio_path, model_size="tiny"):
    """
    Transcribes audio and returns timestamped segments.
    """
    if not WhisperModel:
        print("faster-whisper not installed. Returning mock transcription.")
        return [{"start": 0.0, "end": 2.0, "text": "Mock transcription", "confidence": 0.9}]
        
    print(f"Transcribing {audio_path} with Whisper ({model_size})...")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    
    segments, info = model.transcribe(audio_path, beam_size=5)
    
    results = []
    for segment in segments:
        results.append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text,
            "confidence": getattr(segment, 'avg_logprob', 1.0) 
        })
        
    return results
