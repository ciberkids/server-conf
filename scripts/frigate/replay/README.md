# Frigate detector replay harness

Replays **real Frigate events** through candidate YOLO ONNX models offline, before changing
the detector on bumblebee. It mimics Frigate's region crop (`calculate_region`, at least
320 px, centred on the box) and `yolo-generic` preprocessing (RGB, NCHW, `/255`), then reads
the class scores of the best anchor that overlaps Frigate's own box.

It was built on 2026-11-02 when the cat at the garage door kept being labelled `dog`.

**Fidelity check:** the deployed yolov8n at 640x360 reproduced Frigate's live "dog" call in
42 of 42 frames. Always rerun that baseline first; if it doesn't reproduce production, the
harness is wrong, not the model.

## Run (on the workstation)

```bash
W=<scratch dir>; mkdir -p $W/{weights,frames,tools}
python3 -m venv $W/tools/venv
$W/tools/venv/bin/pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
$W/tools/venv/bin/pip install ultralytics onnx onnxruntime onnxslim opencv-python-headless

# 1. timelines for the events to test (target + some person events + known false positives)
for id in <event ids>; do curl -s "http://192.168.1.14:5000/api/timeline?source_id=$id&limit=100" -o $W/tl_$id.json; done
# 2. aligned full-res frames via /api/<cam>/recordings/<ts>/snapshot.jpg
python3 -I fetch_frames.py $W <target_event_id>
# 3. candidate models (same export settings as the deployed one) + the deployed baseline
cd $W/weights && $W/tools/venv/bin/python -I <repo>/scripts/frigate/replay/export_models.py $W/weights yolov8s yolov8m
ssh 192.168.1.14 'sudo cat /etc/containers/frigate/config/model_cache/<deployed>.onnx' > $W/weights/deployed_<name>.onnx
# 4. compare models x detect resolutions
$W/tools/venv/bin/python -I <repo>/scripts/frigate/replay/replay_eval.py $W
```

Keep the downloaded `.pt` weights in their own directory, because loading them unpickles code.

## Gotchas learned the hard way

- **The region size matters more than the model.** With yolov8s at 1280x720, the cat (~52 px
  inside a 320 px region) gave cat in 37 of 43 frames. With a 480 px region it dropped to
  1 of 43. Frigate's per-camera **region grid** stores region widths *relative to the
  detect width it learned them at*, so after changing `detect.width` the old grid
  inflates regions. Reset it with `curl -X DELETE http://192.168.1.14:5000/api/<cam>/region_grid`,
  then restart: the camera process only reloads the grid at startup and at 02:00 UTC.
- `threshold` is the **median of the last 10 scores** (padded with zeros), not a per-frame
  cut-off. Check the best rolling 10-frame median against it, not the mean.
- More pixels is not always better. At the native 2304x1296 (~94 px) most models called the
  white cat "sheep", and the bigger yolov8m and yolo11m said "dog" at every resolution.
