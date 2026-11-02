"""Build replay frames + manifest from Frigate timelines (see README.md).

usage: python3 -I fetch_frames.py <work_dir> <target_event_id>
  <work_dir> must contain tl_<event_id>.json files (from /api/timeline?source_id=<id>).
  The target event is sampled every 0.5 s (kind="cat"); person events at their timeline
  points (kind="person"); any other label at its timeline points (kind="fp").
"""
import json, sys, os, glob, urllib.request
base = sys.argv[1]; TARGET = sys.argv[2]; os.chdir(base)
F = os.environ.get("FRIGATE", "http://192.168.1.14:5000")
man = []
def grab(cam, ts, tag):
    p = f"frames/{tag}_{ts:.2f}.jpg"
    if not os.path.exists(p):
        try:
            urllib.request.urlretrieve(f"{F}/api/{cam}/recordings/{ts}/snapshot.jpg", p)
        except Exception as e:
            print("skip", tag, cam, round(ts, 2), e); return None
    return p
for tl in sorted(glob.glob("tl_*.json")):
    eid = tl[3:-5]; t = json.load(open(tl))
    if not t: continue
    cam = t[0]["camera"]; lab = t[0]["data"]["label"]
    kind = "cat" if eid == TARGET else ("person" if lab == "person" else "fp")
    if kind == "cat":
        t0 = t[0]["timestamp"]; t_end = [x for x in t if x["class_type"] == "gone"][0]["timestamp"]
        n = int((t_end - t0) / 0.5)
        for i in range(1, n):
            ts = t0 + i * 0.5
            box = min(t, key=lambda x: abs(x["timestamp"] - ts))["data"]["box"]
            p = grab(cam, ts, "cat")
            if p: man.append(dict(kind=kind, eid=eid, cam=cam, ts=ts, box=box, path=p))
    else:
        for x in t:
            if x["class_type"] == "gone": continue   # object already left
            p = grab(cam, x["timestamp"], kind)
            if p: man.append(dict(kind=kind, eid=eid, cam=cam, ts=x["timestamp"], box=x["data"]["box"], path=p))
json.dump(man, open("manifest.json", "w"), indent=1)
from collections import Counter
print(Counter(m["kind"] for m in man), len(man))
