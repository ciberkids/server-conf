"""Replay real Frigate frames through candidate YOLO ONNX models, mimicking Frigate's
region crop (frigate.util.object.calculate_region) and yolo-generic preprocessing.

usage: python -I replay_eval.py <replay_dir>
"""
import json, os, sys, glob, time
import numpy as np, cv2, onnxruntime as ort

base = sys.argv[1]
man = json.load(open(os.path.join(base, "manifest.json")))
models = sorted(glob.glob(os.path.join(base, "weights", "*.onnx")))
RES = {"640x360": (640, 360), "1280x720": (1280, 720), "2304x1296": (2304, 1296)}
M = 320
PERSON, CAT, DOG = 0, 15, 16
TRACKED = {PERSON: "person", CAT: "cat", DOG: "dog"}


def region(fw, fh, x0, y0, x1, y1, mult=2):
    size = int((max(x1 - x0, y1 - y0) * mult) // 4 * 4)
    size = max(size, M)
    size = min(size, fw, fh) if size > min(fw, fh) else size
    xo = int((x1 - x0) / 2 + x0 - size / 2); yo = int((y1 - y0) / 2 + y0 - size / 2)
    xo = min(max(xo, 0), max(0, fw - size)); yo = min(max(yo, 0), max(0, fh - size))
    return xo, yo, size


def infer(sess, crop):
    x = cv2.resize(crop, (M, M), interpolation=cv2.INTER_LINEAR)
    x = cv2.cvtColor(x, cv2.COLOR_BGR2RGB).transpose(2, 0, 1)[None].astype(np.float32) / 255.0
    out = sess.run(None, {sess.get_inputs()[0].name: x})[0][0].T  # (2100, 84)
    cx, cy, w, h = out[:, 0], out[:, 1], out[:, 2], out[:, 3]
    boxes = np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], 1)
    return boxes, out[:, 4:]


def iou(a, b):
    ix0 = np.maximum(a[:, 0], b[0]); iy0 = np.maximum(a[:, 1], b[1])
    ix1 = np.minimum(a[:, 2], b[2]); iy1 = np.minimum(a[:, 3], b[3])
    inter = np.clip(ix1 - ix0, 0, None) * np.clip(iy1 - iy0, 0, None)
    ua = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / np.maximum(ua, 1e-9)


results = []
frames = {m["path"]: cv2.imread(os.path.join(base, m["path"])) for m in man}
for mp in models:
    name = os.path.basename(mp).replace(".onnx", "")
    sess = ort.InferenceSession(mp, providers=["CPUExecutionProvider"])
    t_inf = []
    for rname, (fw, fh) in RES.items():
        for m in man:
            img = cv2.resize(frames[m["path"]], (fw, fh), interpolation=cv2.INTER_AREA)
            bx, by, bw, bh = m["box"]
            gx0, gy0, gx1, gy1 = bx * fw, by * fh, (bx + bw) * fw, (by + bh) * fh
            xo, yo, size = region(fw, fh, gx0, gy0, gx1, gy1)
            crop = img[yo:yo + size, xo:xo + size]
            s = M / size
            gt = np.array([(gx0 - xo) * s, (gy0 - yo) * s, (gx1 - xo) * s, (gy1 - yo) * s])
            t = time.perf_counter(); boxes, cls = infer(sess, crop); t_inf.append(time.perf_counter() - t)
            ov = iou(boxes, gt) >= 0.3
            r = dict(model=name, res=rname, kind=m["kind"], eid=m["eid"], ts=m["ts"],
                     obj_px=round(max(gx1 - gx0, gy1 - gy0), 1), at_model_px=round(max(gt[2] - gt[0], gt[3] - gt[1]), 1))
            if ov.any():
                c = cls[ov]; best = c.max(1).argmax(); row = c[best]
                r.update(top=int(row.argmax()), top_score=float(row.max()), cat=float(c[:, CAT].max()),
                         dog=float(c[:, DOG].max()), person=float(c[:, PERSON].max()))
            else:
                r.update(top=None, top_score=0.0, cat=0.0, dog=0.0, person=0.0)
            results.append(r)
    print(f"{name}: mean CPU inference {1000*np.mean(t_inf):.1f} ms", flush=True)

json.dump(results, open(os.path.join(base, "results.json"), "w"))

# ---------- summary ----------
import collections
def agg(kind):
    g = collections.defaultdict(list)
    for r in results:
        if r["kind"] == kind: g[(r["model"], r["res"])].append(r)
    return g

print("\n=== CAT event (43 frames, real cat; Frigate labelled it dog) ===")
print(f"{'model':26s} {'res':10s} {'px@model':>8s} {'detected':>8s} {'cat>dog':>8s} {'top=cat':>8s} {'med cat':>8s} {'med dog':>8s}")
for (mo, rs), rs_ in sorted(agg("cat").items()):
    det = [r for r in rs_ if max(r["cat"], r["dog"]) >= 0.4]
    catwin = sum(r["cat"] > r["dog"] for r in det)
    topcat = sum(r["top"] == CAT and r["top_score"] >= 0.5 for r in rs_)
    print(f"{mo:26s} {rs:10s} {np.median([r['at_model_px'] for r in rs_]):8.0f} {len(det):5d}/{len(rs_)} {catwin:5d}/{len(det) or 1} "
          f"{topcat:5d}/{len(rs_)} {np.median([r['cat'] for r in rs_]):8.2f} {np.median([r['dog'] for r in rs_]):8.2f}")

print("\n=== PERSON frames (15, must stay person >= 0.5) ===")
for (mo, rs), rs_ in sorted(agg("person").items()):
    ok = sum(r["top"] == PERSON and r["top_score"] >= 0.5 for r in rs_)
    print(f"{mo:26s} {rs:10s} person-ok {ok:2d}/{len(rs_)}  median person {np.median([r['person'] for r in rs_]):.2f}")

print("\n=== OLD FALSE POSITIVES (4 frames: IR bag etc. that yolov8n called dog) ===")
for (mo, rs), rs_ in sorted(agg("fp").items()):
    bad = [(TRACKED.get(r["top"], r["top"]), round(r["top_score"], 2)) for r in rs_ if r["top"] in TRACKED and r["top_score"] >= 0.5]
    print(f"{mo:26s} {rs:10s} tracked-label hits >=0.5: {len(bad)}/{len(rs_)} {bad}")
