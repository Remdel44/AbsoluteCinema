import whisper

result = []
for i in range(1, 5):
    input_file = f"input_audio_files/0000{i}.wav"
    model = whisper.load_model("turbo")
    res = model.transcribe(str(input_file))
    result.append(res["text"])
    print(f"Text n°{i}: {res["text"]}")
    