import subprocess, re

# returns list of keyframes, total_frames
def get_mkv_keyframes(src, cb=None):
  ff = [
    "ffmpeg", "-hide_banner",
    "-i", src,
    "-map", "0:v:0",
    "-vf", "select=eq(pict_type\,PICT_TYPE_I)",
    "-f", "null",
    "-loglevel", "debug", "-"
  ]

  ffmpeg_pipe = subprocess.Popen(ff,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT)

  mkv_keyframes = []
  total_frames = 0

  while True:
    line = ffmpeg_pipe.stdout.readline().strip().decode("utf-8")

    if len(line) == 0 and ffmpeg_pipe.poll() is not None:
      break

    match = re.search(r"n:([0-9]+)\.[0-9]+ pts:.+key:1.+pict_type:I", line)
    if match:
      frame = int(match.group(1))
      mkv_keyframes.append(frame)
      if cb: cb(frame)
    else:
      match = re.search(r"video.+?([0-9]+?) frames decoded", line)
      if match:
        total_frames = int(match.group(1))

  return mkv_keyframes, total_frames
