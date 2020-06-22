# grav1ty

please add more if you have any

## split
This splits a video file into segments using mkv keyframes and aom keyframes.  
`split(video, path_split, min_frames=-1, cb=None)`  
returns: splits, total frames, segments  

splits:
```
{
  "00000": {                  # segment name
    "segment": "00000.mkv",   # segment file
    "start": 0,               # starting frame within the segment
    "frames": 10              # number of frames
  },
  "00001": {
    "segment": "00000.mkv",
    "start": 10,
    "frames": 20
  }
}
```

total frames: total number of frames in the sequence

segments: these are the split up video files
```
{
  "00000.mkv": {  # filename
    "start": 0,   # starting frame within the entire video
    "length": 10  # number of frames of the segment
  }
}
```

## aom keyframes
Uses libaom 1 pass to generate a log file  
`get_aom_keyframes(video)`  
returns: list of keyframes

## mkv keyframes
Uses ebml mkv header / ffmpeg to determine location of keyframes  
`get_mkv_keyframes(video)`  
returns: list of keyframes, total number of frames  

## plot vmaf
Plots vmaf of two video files  
Example program:  
`python3 plot_vmaf.py raw.mkv encoded.mkv --frames 10 --open`  
`python3 plot_vmaf.py raw.mkv encoded.mkv --title "the encoded file" -o image.png --open`  
`python3 plot_vmaf.py raws/ encoded/ --frames 10 -o vmafs`  

Arguments:  
Name | Required | Description
- | - | -
source | True | Source video file/directory
encoded | True | Encoded video file/directory to compare
--title | False | Title of the plot
--frames | False | Number of frames to compare
--dpi | False | DPI of rendered plot
-o | False | Specified location to save the plots, defaults to encoded_name.png
--open | False | Open the plot in an image viewer right after completing analysis
--vmaf-model-path | False | Required if vmaf is in the path
