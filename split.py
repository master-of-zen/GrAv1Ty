import os
from util import get_frames, ffmpeg
from mkv_keyframes import get_mkv_keyframes
from aom_keyframes import get_aom_keyframes

# splits are contained like so:
# {
#   "00000": {                # aom segment
#     "segment": "00000.mkv", # split segment
#     "start": 0,             # starting frame within the split segment
#     "frames": 5             # number of frames for the aom segment
#   }
# }
def split(video, path_split, total_frames, min_frames=-1, max_frames=-1, cb=None):
  aom_keyframes = get_aom_keyframes(video)
  
  if min_frames != -1 and max_frames != -1:
    final_scenes = []
    last_scene = 0
    previous_scene = aom_keyframes[1]
    for scene in aom_keyframes[1:]:
      if scene - last_scene >= max_frames and previous_scene - last_scene > min_frames:
        final_scenes.append(previous_scene)
        last_scene = previous_scene
      previous_scene = scene
    aom_keyframes = [0] + final_scenes + [total_frames]
  else:
    aom_keyframes.append(total_frames)

  mkv_keyframes = get_mkv_keyframes(video, total_frames, cb) + [total_frames]

  splits = {}
  last_end = 0
  frames = []

  for i in range(len(aom_keyframes) - 1):
    frame = aom_keyframes[i]
    next_frame = aom_keyframes[i + 1]
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
        start = frame - frames[len(frames) - 1]
      else:
        frames.append(largest)
        
      print(segment_n, start, length)
      
    splits[f"{len(splits):05d}"] = {
      "segment": f"{segment_n:05d}.mkv",
      "start": start,
      "frames": length
    }
    last_end = frame + length

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

  ffmpeg(cmd, cb)

  return splits

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

  total_frames = get_frames(args.input)
  print(f"{total_frames} frames")

  splits = split(
    args.input,
    args.split_path,
    total_frames,
    min_frames=args.min_frames,
    max_frames=args.max_frames,
    cb=lambda x: print(f"{x}/{total_frames}", end="\r"))

  json.dump(splits, open(args.splits, "w+"))
