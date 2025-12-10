
import whisper  
from whisper.utils import format_timestamp # Fonction de formatage des timestamps
#test whisper
model = whisper.load_model("turbo")
result = model.transcribe("input_audios/00001.wav")

segments = result["segments"] 

print("\n--- Transcription horodatée (Format Terminal) ---")
for segment in segments:
    start_time_seconds = segment["start"]
    end_time_seconds = segment["end"]
    text = segment["text"]
    
    # Conversion du temps en format HH:MM:SS.ms
    start_formatted = format_timestamp(start_time_seconds, always_include_hours=True, decimal_marker=',')
    end_formatted = format_timestamp(end_time_seconds, always_include_hours=True, decimal_marker=',')
    
    # Affichage du format terminal désiré
    print(f"[{start_formatted} --> {end_formatted}] {text.strip()}")