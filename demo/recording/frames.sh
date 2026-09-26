#!/bin/sh
# Trích các khung hình ở các mốc giây (đối số 2 trở đi) của một clip.
F="$LOCALAPPDATA/ms-playwright/ffmpeg-1011/ffmpeg-win64.exe"
clip="$1"; shift
mkdir -p clips/_tmp
i=0
for t in "$@"; do
  i=$((i+1))
  "$F" -hide_banner -loglevel error -y -ss "$t" -i "clips/$clip.webm" -frames:v 1 -vf scale=768:-1 "clips/_tmp/f$i.png"
done
n=$i
inputs=""; for k in $(seq 1 $n); do inputs="$inputs -i clips/_tmp/f$k.png"; done
rows=$(( (n+1)/2 ))
