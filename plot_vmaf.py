#!/usr/bin/env python3

import sys, subprocess, os
import numpy as np
import matplotlib.pyplot as plt

# https://github.com/master-of-zen/Plot_Vmaf/blob/master/plot_vmaf.py
def read_vmaf_xml(file, out, title, dpi):
  with open(file, "r") as f:
    file = f.readlines()
    file = [x.strip() for x in file if "vmaf=\"" in x]
    vmafs = []
    for i in file:
      vmf = i[i.rfind("=\"") + 2: i.rfind("\"")]
      vmafs.append(float(vmf))

    vmafs = [round(float(x), 3) for x in vmafs if type(x) == float]

  # Data
  x = [x for x in range(len(vmafs))]
  mean = round(sum(vmafs) / len(vmafs), 3)
  perc_1 = round(np.percentile(vmafs, 1), 3)
  perc_25 = round(np.percentile(vmafs, 25), 3)
  perc_75 = round(np.percentile(vmafs, 75), 3)

  # Plot
  plt.figure(figsize=(15, 4))
  if title: plt.title(title)
  [plt.axhline(i, color="grey", linewidth=0.4) for i in range(0, 100)]
  [plt.axhline(i, color="black", linewidth=0.6) for i in range(0, 100, 5)]
  plt.plot(x, vmafs, label=f"Frames: {len(vmafs)}\nMean: {mean}\n1%: {perc_1}\n25%: {perc_25}\n75%: {perc_75}", linewidth=0.4)
  plt.ylabel("VMAF")
  plt.xlabel("Frame")
  plt.legend(loc="lower right")
  plt.ylim(min(vmafs), 100)
  plt.tight_layout()
  plt.margins(0)

  plt.savefig(out, dpi=dpi)

def calculate(source, encoded, frames, vmaf, title, dpi, output, out_dir, open_image):
  ffmpeg = ["ffmpeg",
    "-hide_banner",
    "-r", "24",
    "-i", source,
    "-r", "24",
    "-i", encoded,
    "-map", "0:v:0",
    "-map", "1:v:0",
    "-filter_complex", "[0:v][1:v]libvmaf=log_path=plot.xml" + f":model_path={vmaf}" if vmaf else "",
  ]

  if frames:
    ffmpeg.extend(["-vframes", frames])

  ffmpeg.extend([
    "-f", "null", "-"
  ])

  subprocess.run(ffmpeg)
  
  if output and out_dir:
    os.makedirs(output, exist_ok=True)
    out = os.path.join(output, f"{os.path.basename(encoded)}.png")
  elif output:
    out = output
  else:
    out = f"{os.path.basename(encoded)}.png"

  read_vmaf_xml("plot.xml", out, title, dpi)

  if open_image:
    Image.open(out).show()

# --open requires Pillow
# example use
# python3 plot_vmaf.py raw.mkv encoded.mkv --frames 10 --open
# python3 plot_vmaf.py raw.mkv encoded.mkv --frames 10 -o image.png --open
# python3 plot_vmaf.py raws/ encoded/ --frames 10 -o vmafs
if __name__ == "__main__":
  import argparse

  parser = argparse.ArgumentParser()
  parser.add_argument(dest="source")
  parser.add_argument(dest="encoded")
  parser.add_argument("--title", default=None)
  parser.add_argument("--frames", default=None)
  parser.add_argument("--dpi", default=100)
  parser.add_argument("-o", dest="output", default=None)
  parser.add_argument("--open", action="store_true")
  parser.add_argument("--vmaf-model-path", dest="vmaf_path", default="vmaf_v0.6.1.pkl" if os.name == "nt" else None)
  
  args = parser.parse_args()

  if args.open:
    from PIL import Image

  source = args.source
  encoded = args.encoded

  if os.path.isdir(source) and os.path.isdir(encoded):
    files_in_source = os.listdir(source)
    files_in_encoded = os.listdir(encoded)
    for file in files_in_encoded:
      if file in files_in_source:
        calculate(
          os.path.join(source, file),
          os.path.join(encoded, file),
          args.frames,
          args.vmaf_path,
          args.title,
          args.dpi,
          args.output,
          True,
          args.open)
  elif os.path.isdir(source) or os.path.isdir(encoded):
    if os.path.isdir(source):
      print(os.path.isdir(source), "is a directory and", os.path.isdir(encoded), "is not")
    if os.path.isdir(encoded):
      print(os.path.isdir(encoded), "is a directory and", os.path.isdir(source), "is not")
  else:    
    calculate(
      source,
      encoded,
      args.frames,
      args.vmaf_path,
      args.title,
      args.dpi,
      args.output,
      False,
      args.open)
