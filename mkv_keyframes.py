import subprocess, re

def get_mkv_keyframes(src, total_frames, cb=None):
  ff = [
    "ffmpeg", "-hide_banner",
    "-i", src,
    "-vf", "select=eq(pict_type\,PICT_TYPE_I)",
    "-f", "null",
    "-loglevel", "debug", "-"
  ]

  ffmpeg_pipe = subprocess.Popen(ff,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT)

  mkv_keyframes = []

  while True:
    line = ffmpeg_pipe.stdout.readline().strip().decode("utf-8")

    if len(line) == 0 and ffmpeg_pipe.poll() is not None:
      break

    match = re.search(r"n:([0-9]+)\.[0-9]+ pts:.+key:1.+pict_type:I", line)
    if match:
      frame = int(match.group(1))
      mkv_keyframes.append(frame)
      if cb:
        cb(frame)

  return mkv_keyframes
