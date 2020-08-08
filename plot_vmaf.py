#!/usr/bin/env python3

import subprocess, os, json, re
import numpy as np
import matplotlib.pyplot as plt
import xml.etree.ElementTree as Xml

def read_vmaf_xml(file):
  root = Xml.parse(file).getroot()
  frames = []
  header = ["frame", "vmaf"]

  for child in root:
    if child.tag == "frames":
      for frame in child:
        frame_n = int(frame.get("frameNum"))
        vmaf = float(frame.get("vmaf"))
        psnr = float(frame.get("psnr"))
        ssim = float(frame.get("ssim"))
        ms_ssim = float(frame.get("ms_ssim"))

        row = [frame_n, vmaf]

        if psnr:
          if "psnr" not in header:
            header.append("psnr")
          row.append(psnr)
        if ssim:
          if "ssim" not in header:
            header.append("ssim")
          row.append(ssim)
        if ms_ssim:
          if "ms_ssim" not in header:
            header.append("ms_ssim")
          row.append(ms_ssim)

        frames.append(row)

  return header, frames

def create_log(source, encoded, frames, vmaf, extra_metrics=[], xml="plot.xml"):
  extra = ":".join(extra_metrics)
  extra += ":" if len(extra) > 0 else ""

  ffmpeg = ["ffmpeg",
    "-hide_banner",
    "-r", "24",
    "-i", encoded,
    "-r", "24",
    "-i", source,
    "-map", "0:v:0",
    "-map", "1:v:0",
    "-lavfi", f"libvmaf={extra}log_path={xml}" + f":model_path={vmaf}" if vmaf else "",
  ]

  if frames:
    ffmpeg.extend(["-vframes", frames])

  ffmpeg.extend([
    "-f", "null", "-"
  ])

  pipe = subprocess.Popen(ffmpeg, 
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT,
      universal_newlines=True)
  
  while True:
    line = pipe.stdout.readline().strip()

    if len(line) == 0 and pipe.poll() is not None:
      break

    match = re.search(r"frame= *?([0-9]+)", line)
    if match:
      frames = int(match.group(1))
      print(f"frame {frames}", end="\r")

def calculate(xml, output=None, png=False, svg=False, csv=False, psnr=False, ssim=False, ms_ssim=False):
  header, frames = read_vmaf_xml(xml)

  if not output:
    return header, frames

  frames = [",".join([str(f) for f in frame]) for frame in frames]
  if csv:
    header = ",".join(header)
    open(f"{output}.csv", "w+").write(f"{header}\n" + "\n".join(frames))

# examples
# python3 plot_vmaf.py --xml plot.xml -o metrics.csv --psnr --ssim -ms_ssim
# python3 plot_vmaf.py raw.mkv encoded.mkv --frames 10 -o metrics.csv
if __name__ == "__main__":
  import argparse

  parser = argparse.ArgumentParser()

  parser.add_argument("source", nargs="?")
  parser.add_argument("encoded", nargs="?")

  parser.add_argument("--frames", default=None)
  parser.add_argument("-o", dest="output", default=None)
  parser.add_argument("--vmaf-model-path", dest="vmaf_path", default="vmaf_v0.6.1.pkl" if os.name == "nt" else None)

  parser.add_argument("--psnr", action="store_true")
  parser.add_argument("--ssim", action="store_true")
  parser.add_argument("--ms_ssim", action="store_true")

  #parser.add_argument("--png", action="store_true")
  #parser.add_argument("--svg", action="store_true")
  parser.add_argument("--csv", action="store_true")

  #parser.add_argument("--title", default=None)
  #parser.add_argument("--dpi", default=100)

  parser.add_argument("--xml", default=None)

  args = parser.parse_args()

  if not args.xml or (args.source or args.encoded):
    missing = []
    if not args.source:
      missing.append("source")
    if not args.encoded:
      missing.append("encoded")
    
    if missing:
      parser.error("the following arguments are required: " + ", ".join(missing))

  elif not args.source and not args.encoded:
    if not os.path.isfile(args.xml):
      parser.error(f"{args.xml} could not be found")

  extra_metrics = []

  if args.psnr:
    extra_metrics.append("psnr")

  if args.ssim:
    extra_metrics.append("ssim")

  if args.ms_ssim:
    extra_metrics.append("ms_ssim")

  print("metrics:", ", ".join(["vmaf"] + extra_metrics))

  extra_metrics = [f"{m}=1" for m in extra_metrics]

  source = args.source
  encoded = args.encoded

  if source and encoded:
    if os.path.isdir(source):
      parser.error(f"{source} is a directory")
    if os.path.isdir(encoded):
      parser.error(f"{encoded} is a directory")
  
  #if not args.output and not args.png and not args.svg and not args.csv:
  if not args.output and not args.csv:
    #parser.error("An output file or output types --png, --svg, and --csv must be provided")
    parser.error("An output file or output types --csv must be provided")

  out_filename, ext = os.path.splitext(args.output)
  ext = ext.lower()

  #if ext == ".png":
  #  args.png = True
  #if ext == ".svg":
  #  args.svg = True
  if ext == ".csv":
    args.csv = True
  
  if ext in [".png", ".svg", ".csv"]:
    args.output = out_filename
  #elif not args.png and not args.svg and not args.csv:
  elif not args.csv:
    #parser.error("Could not detect output file type\nSpecify --png, --svg, or --csv")
    parser.error("Could not detect output file type\nSpecify --csv")

  if source and encoded:
    create_log(
      source,
      encoded,
      args.frames,
      args.vmaf_path,
      extra_metrics,
      args.xml if args.xml else "plot.xml"
    )

  calculate(
    args.xml if args.xml else "plot.xml", args.output,
    #args.png, args.svg, args.csv,
    False, False, args.csv,
    args.psnr, args.ssim, args.ms_ssim
  )
