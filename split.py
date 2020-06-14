import os
from util import get_frames, ffmpeg
from mkv_keyframes import get_mkv_keyframes
from aom_keyframes import get_aom_keyframes

# returns splits, total frames, segments
# splits are contained like so:
# {
#   "00000": {                # aom segment
#     "segment": "00000.mkv", # split segment
#     "start": 0,             # starting frame within the split segment
#     "frames": 5             # number of frames for the aom segment
#   }
# }
# segments are contained like so:
# {
#   "00000.mkv": {
#     "start": 0,
#     "length": 10
#   }
# }
def split(video, path_split, min_frames=-1, max_frames=-1, cb=None):
  mkv_keyframes, total_frames = get_mkv_keyframes(video)
  mkv_keyframes.append(total_frames)

  aom_keyframes = get_aom_keyframes(video)
  
  skip_keyframes = 0

  if min_frames != -1 and max_frames != -1:
    final_scenes = []
    last_scene = aom_keyframes[skip_keyframes]
    previous_scene = aom_keyframes[skip_keyframes]
    for scene in aom_keyframes[skip_keyframes + 1:]:
      if scene - last_scene >= max_frames and previous_scene - last_scene > min_frames:
        final_scenes.append(previous_scene)
        last_scene = previous_scene
      previous_scene = scene
    aom_keyframes = aom_keyframes[:skip_keyframes + 1] + final_scenes
    
  aom_keyframes.append(total_frames)
  
  splits = {}
  last_end = 0
  frames = []

  for i in range(len(aom_keyframes) - 1):
    frame = aom_keyframes[i]
    next_frame = aom_keyframes[i+1]
    segment_n = len(frames)
    start = 0
    length = next_frame - frame
    if frame in mkv_keyframes:
      frames.append(frame)
    else:
      largest = 0
      for j in mkv_keyframes:
        if j < frame:
          largest = j
        else:
          break
      start = frame - largest
      if largest in frames or largest < last_end:
        segment_n -= 1
        start = frame - frames[len(frames)-1]
      else:
        frames.append(largest)
      
    splits[f"{len(splits):05d}"] = ({"segment": f"{segment_n:05d}.mkv", "start": start, "frames": length, "filesize": 0})
    last_end = frame + length

  segments = {}

  for segment_n in range(len(frames)):
    segments[f"{segment_n:05d}.mkv"] = {
      "start": frames[segment_n],
      "length": (total_frames if segment_n == len(frames) - 1 else frames[segment_n + 1]) - frames[segment_n]
    }

  frames = [str(f) for f in frames][1:]

  cmd = [
    "ffmpeg", "-y",
    "-i", video,
    "-map", "0:v:0",
    "-an",
    "-c", "copy",
    "-avoid_negative_ts", "1"
  ]

  if len(frames) > 0:
    cmd.extend([
      "-f", "segment",
      "-segment_frames", ",".join(frames)
    ])

  cmd.append(os.path.join(path_split, "%05d.mkv"))

  os.makedirs(path_split, exist_ok=True)
  ffmpeg(cmd, lambda x: cb(x, total_frames))

  return splits, total_frames, segments

def correct_split(path_in, path_out, start, length):
  cmd = [
    "ffmpeg", "-hide_banner",
    "-i", path_in,
    "-map", "0:v:0",
    "-c:v", "libx265",
    "-x265-params", "lossless=1",
    "-vf", f"select=gte(n\\,{start})",
    "-frames:v", str(length),
    "-y", path_out
  ]
  ffmpeg(cmd, lambda x: print(f"{x}/{length}", end="\r"))

# input the source and segments produced by split()
def verify_split(path_in, path_split, segments, cb=None):
  for i, segment in enumerate(segments, start=1):
    print(segment)
    segment_n = str(os.path.splitext(segment)[0])
    num_frames = get_frames(os.path.join(path_split, segment))
    if num_frames != segments[segment]["length"]:
      print("bad framecount", segment, "expected:", segments[segment]["length"], "got:", num_frames)
      correct_split(path_in, os.path.join(path_split, segment), segments[segment]["start"], segments[segment]["length"])
    else:
      num_frames_slow = get_frames(os.path.join(path_split, segment), False)
      if num_frames != num_frames_slow:
        print("bad framecount", segment, "expected:", num_frames, "got:", num_frames_slow)
        correct_split(path_in, os.path.join(path_split, segment), segments[segment]["start"], segments[segment]["length"])
    
    if cb: cb(i)

# this is an example program
if __name__ == "__main__":
  import argparse, json

  parser = argparse.ArgumentParser()
  parser.add_argument("-i", dest="input", required=True)
  parser.add_argument("-o", dest="split_path", required=True)
  parser.add_argument("-s", "--splits", dest="splits", required=True)
  parser.add_argument("--min_frames", default=-1)
  parser.add_argument("--max_frames", default=-1)
  
  args = parser.parse_args()

  splits, total_frames, segments = split(
    args.input,
    args.split_path,
    min_frames=args.min_frames,
    max_frames=args.max_frames,
    cb=lambda x: print(f"{x}/{total_frames}", end="\r")
  )
  
  print(total_frames, "frames")
  print("verifying split")

  verify_split(
    args.input,
    args.split_path,
    segments,
    cb=lambda x: print(f"{x}/{len(segments)}", end="\r")
  )

  json.dump(splits, open(args.splits, "w+"))
