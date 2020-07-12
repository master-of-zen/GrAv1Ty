import subprocess, re

vs_core = None

try:
  import vapoursynth
  vs_core = vapoursynth.get_core()
except: pass

def get_frames(src, fast=True):
  if vs_core:
    return vs_core.ffms2.Source(src).num_frames

  cmd = ["ffmpeg", "-hide_banner", "-i", src, "-map", "0:v:0"]
  if fast:
    cmd.extend(["-c", "copy",])
  cmd.extend(["-f", "null", "-"])
  r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  matches = re.findall(r"frame= *([^ ]+?) ", r.stderr.decode("utf-8") + r.stdout.decode("utf-8"))
  return int(matches[-1])

def ffmpeg(cmd, cb):
  pipe = subprocess.Popen(cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    universal_newlines = True)

  try:
    while True:
      line = pipe.stdout.readline().strip()

      if len(line) == 0 and pipe.poll() is not None:
        break

      if not cb: continue
      matches = re.findall(r"frame= *([^ ]+?) ", line)
      if matches:
        cb(int(matches[-1]))

  except KeyboardInterrupt as e:
    pipe.kill()
    raise e
  
def ffmpeg_pipe(cmd1, cmd2, cb):
  pipe1 = subprocess.Popen(cmd1,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT)

  pipe2 = subprocess.Popen(cmd2,
    stdin=pipe1.stdout,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    universal_newlines=True)

  try:
    while True:
      line = pipe2.stdout.readline().strip()

      if len(line) == 0 and pipe2.poll() is not None:
        break

      if not cb: continue
      matches = re.findall(r"frame= *([^ ]+?) ", line)
      if matches:
        cb(int(matches[-1]))

  except KeyboardInterrupt as e:
    pipe2.kill()
    pipe1.kill()
    raise e

def parse_time(search):
  search = re.match(r"[\x20-\x7E]+", search).group()
  return sum([float(t) * 60 ** i for i, t in enumerate(search.split(":")[::-1])])
