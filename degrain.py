import os, subprocess, io, re, tempfile
from threading import Thread, Event
from queue import Queue

# vapoursynth desnoise script
# adjust accordingly
vpy = """
import vapoursynth as vs
import mvsfunc as mvf

core = vs.get_core()
core.max_cache_size = 100000

src = core.ffms2.Source("{}")

y = mvf.BM3D(src, radius1=1, sigma=[12, 0, 0])
knl = core.knlm.KNLMeansCL(src, a=2, h=1, d=3, device_type='gpu', device_id=0, channels='UV')
    
flt = core.std.ShufflePlanes([y, knl], planes=[0, 1, 2], colorfamily=vs.YUV)

flt.set_output()
"""

def ff_work(q):
  while True:
    job = q.get()
    for cmd in job[0]:
      subprocess.run(cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    job[1].set()
    q.task_done()

def work(id, q, f_q, noise_model, width, height, block_size, on_complete):
  e = Event()
  
  while True:
    job = q.get()
    print("start", id, job[2])

    if os.name == "nt":
      clean = f"{id}_clean.yuv"
      denoised = f"{id}_denoise.yuv"
      cmds = [
        ["ffmpeg", "-i", job[0], "-y", clean],
        ["ffmpeg", "-i", job[1], "-y", denoised]
      ]

      e.clear()
      f_q.put((cmds, e))
      e.wait()

    else:
      clean = os.path.join(tempfile.gettempdir(), f"pipe1_{id}.yuv")
      denoised = os.path.join(tempfile.gettempdir(), f"pipe2_{id}.yuv")

      if os.path.exists(clean):
        os.unlink(clean)
      if os.path.exists(denoised):
        os.unlink(denoised)

      os.mkfifo(clean)
      os.mkfifo(denoised)

      cmds = [
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", job[0], "-y", clean],
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", job[1], "-y", denoised]
      ]

      [subprocess.Popen(cmd) for cmd in cmds]

    noise_model = [
      noise_model if noise_model else "noise_model",
      f"--input={clean}",
      f"--input-denoised={denoised}",
      f"--output-grain-table={job[2]}",
      f"--width={width}",
      f"--height={height}",
      f"--block-size={block_size}"
    ]

    subprocess.run(noise_model, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    os.unlink(clean)
    os.unlink(denoised)

    on_complete()

    q.task_done()

def denoise_directory(script, path_src, path_denoise):
  os.makedirs(path_denoise, exist_ok=True)

  files = [file for file in os.listdir(path_src) if os.path.splitext(file)[1] in [".mkv", ".mp4"]]
  for i, file in enumerate(files, 1):
    if os.path.isfile(os.path.join(path_denoise, file)): continue
    path = os.path.join(path_src, file)

    with open("tmp_grainremove.vpy", "w+") as f:
      f.write(script.format(path.replace("\\","\\\\")))

    vspipe = ["vspipe", "tmp_grainremove.vpy", "-", "-y"]
    ffmpeg = [
      "ffmpeg", "-hide_banner",
      "-i", "-",
      "-vsync", "0",
      "-c:v", "libx264",
      "-crf", "0",
      "-y", os.path.join(path_denoise, file)
    ]

    print(f"denoising {i - 1}/{len(files)}", end="\r")

    vspipe = subprocess.Popen(vspipe,
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT)

    pipe = subprocess.run(ffmpeg,
      stdin=vspipe.stdout,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      universal_newlines=True)
    
    print(f"denoising {i}/{len(files)}", end="\r")

class Counter:
  def __init__(self, cb):
    self.n = 0
    self.cb = cb
  
  def inc(self, n=1):
    self.n += n
    self.cb(self.n)

def generate_models(noise_model, path_split, path_denoise, output, width, height, block_size=40, workers=6):
  os.makedirs(output, exist_ok=True)

  queue = Queue()
  ffmpeg_queue = Queue()
  total = 0

  for file in os.listdir(path_denoise):
    if os.path.splitext(file)[1] != ".mkv": continue
    
    path = os.path.join(path_split, file)
    denoised = os.path.join(path_denoise, file)
    graintable = os.path.join(output, f"{os.path.splitext(file)[0]}.table")

    if os.path.exists(graintable): continue
    queue.put((path, denoised, graintable))
  
  total = queue.qsize()

  c = Counter(cb=lambda n: print(f"generating grain {n}/{total}", end="\r"))

  for i in range(workers):
    Thread(target=work, args=(i, queue, ffmpeg_queue, noise_model, width, height, block_size, c.inc), daemon=True).start()

  Thread(target=ff_work, args=(ffmpeg_queue,), daemon=True).start()

  queue.join()

def scale_noise_model(graintable, graintable_mod, scale):
  with open(graintable) as f:
    f2 = io.open(graintable_mod, "w+", newline="\n")
    for line in f.readlines():
      match = re.match(r"\tcY (.+)$", line)
      if match:
        params = match.group(1).split(" ")
        params = [int(p) for p in params]
        params = [round(p*scale) for p in params]
        params = [str(p) for p in params]
        print(params)
        line = "\tcY " + " ".join(params) + "\n"
      f2.writelines([line])

def scale_noise_models(graintables, out):
  os.makedirs(out, exist_ok=True)
  for file in os.listdir(graintables):
    gt = os.path.join(graintables, file)
    gt2 = os.path.join(out, file)
    scale_noise_model(gt, gt2, 0.8)

class Degrain:
  def __init__(self):
    parser = argparse.ArgumentParser(
      description="Degrain + generate noise models",
      usage=f"{os.path.basename(__file__)} <command> [<args>]\n"
      "commands:\n"
      "  degrain  \tDenoise a directory\n"
      "  generate \tGenerate grain tables"
    )
    parser.add_argument("command", help="Command to run")

    args = parser.parse_args(sys.argv[1:2])
    if not hasattr(self, args.command):
      print("Unrecognized command")
      parser.print_help()
      exit(1)
    getattr(self, args.command)()

  def degrain(self):
    if not shutil.which("vspipe"):
      print("vspipe not found")
      exit(1)

    parser = argparse.ArgumentParser(
      description="Remove grain from segmented videos\nOnly works for 1 segment per split",
      usage=f"{os.path.basename(__file__)} degrain [-h] [-s SCRIPT] input output",
      formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument("-s", "--script", help="Vapoursynth script")
    parser.add_argument("input", help="Input directory")
    parser.add_argument("output", help="Ouput denoised directory")

    args = parser.parse_args(sys.argv[2:])

    if args.script:
      if not os.path.exists(args.script):
        print(args.script, "can't be found")
        exit(1)
      
      script = open(args.script, "r").read()
      match = re.search(r"ffms2.Source\((\".+\"|\'.+\')\)", script)
      if match:
        script = script.replace(match.group(1), "\"{}\"")

      elif not "\"{}\"" in script:
        print("script requires an ffms2 source or \"{}\" to indicate input segment")
        exit(1)

      print("using script", args.script)
    else:
      script = vpy
      print("using default script")
    
    if not os.path.isdir(args.input):
      print(args.input, "can't be found")
      exit(1)

    denoise_directory(script, args.input, args.output)
  
  def generate(self):
    parser = argparse.ArgumentParser(
      description="Generate grain tables from clean and denoised video",
      usage=f"{os.path.basename(__file__)} generate [-h] --width WIDTH --height HEIGHT [--blocksize BLOCKSIZE] [--workers WORKERS] source denoise output",
      formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument("source", help="Source directory")
    parser.add_argument("denoise", help="Denoised directory")
    parser.add_argument("output", help="Ouput tables directory")
    parser.add_argument("--width", required=True)
    parser.add_argument("--height", required=True)
    parser.add_argument("--blocksize", default=40)
    parser.add_argument("--workers", help=f"default: logical cores / 2 : {round(os.cpu_count()/2)}", default=round(os.cpu_count()/2), required=False)
    parser.add_argument("--noise_model", default=None, help="Location to noise_model example program")

    args = parser.parse_args(sys.argv[2:])

    if not shutil.which("noise_model") and not args.noise_model:
      print("noise_model not found")
      exit(1)

    generate_models(
      args.noise_model,
      args.source,
      args.denoise,
      args.output,
      int(args.width),
      int(args.height),
      int(args.blocksize),
      workers=int(args.workers)
    )

if __name__ == "__main__":
  import argparse, sys, shutil
  Degrain()
