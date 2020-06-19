import subprocess, re, enzyme

def get_child(parent, *args, is_list=False):
  args = list(args)
  while args:
    name = args.pop(0)
    child = [e for e in parent if e.name == name]
    if is_list and len(child) > 1: return child
    if child: parent = child[0]
    else: return None
  return [parent] if is_list else parent

# returns list of keyframes, total_frames
def get_mkv_keyframes(src):
  frames, total_frames = get_mkv_keyframes_fast(src)
  if not frames:
    print(total_frames, "falling back to ffmpeg")
    return get_mkv_keyframes_slow(src)
  else:
    return frames, total_frames

def get_mkv_keyframes_fast(src):
  mkv = enzyme.parsers.ebml.parse(
    open(src, "rb"),
    enzyme.parsers.ebml.get_matroska_specs(),
    ignore_element_names=["SimpleBlock", "Block", "Void", "Cluster", "FileData"])

  track_uid = None
  track_number = None
  frame_duration = None
  total_frames = None

  timecode_scale = get_child(mkv[1], "Info", "TimecodeScale").data

  for track in get_child(mkv[1], "Tracks"):
    track_type = get_child(track, "TrackType")
    if track_type.data == 1:
      track_number = get_child(track, "TrackNumber")
      if track_number: track_number = track_number.data
      else:
        return None, "Unable to parse track number"

      frame_duration = get_child(track, "DefaultDuration")
      if frame_duration: frame_duration = frame_duration.data
      else:
        return None, "Unable to parse frame duration"

      track_uid = get_child(track, "TrackUID")
      if track_uid: track_uid = track_uid.data
      else:
        return None, "Unable to parse track uid"

  for tag in get_child(mkv[1], "Tags"):
    if get_child(tag, "Targets", "TagTrackUID").data == track_uid:
      for simple_tag in get_child(tag, "SimpleTag", is_list=True):
        if get_child(simple_tag, "TagName").data == "NUMBER_OF_FRAMES":
          total_frames = get_child(simple_tag, "TagString").data
          break

  if not total_frames:
    return None, "Unable to parse total frames"

  cues = [e for e in mkv[1] if e.name == "Cues"]
  cues = cues[0] if cues else None

  timestamps = []
  num_frames = 0

  for e in cues:
    if e[1][0].data == track_number:
      timestamps.append(e[0].data)

  frames = [round(timecode_scale / frame_duration * t) for t in timestamps]

  return frames, int(total_frames)

def get_mkv_keyframes_slow(src):
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
    else:
      match = re.search(r"video.+?([0-9]+?) frames decoded", line)
      if match:
        total_frames = int(match.group(1))

  return mkv_keyframes, total_frames
