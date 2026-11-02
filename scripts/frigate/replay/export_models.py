import sys, os
os.chdir(sys.argv[1])
from ultralytics import YOLO
for name in sys.argv[2:]:
    m = YOLO(f"{name}.pt")
    out = m.export(format="onnx", imgsz=320, opset=12, simplify=True, nms=False, dynamic=False, half=False)
    print("exported", name, out)
