import ffmpeg
def get_duration_ffmpeg(file_path):
   probe = ffmpeg.probe(file_path)
   stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)
   duration = float(stream['duration'])
   return duration
file_path = 'input_audios\Kill_Bill_Volume_2_eng.ac3'
duration = get_duration_ffmpeg(file_path)
print(f"Duration: {duration:.2f} seconds")
