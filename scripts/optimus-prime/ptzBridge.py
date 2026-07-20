#!/usr/bin/env python3
"""
Tiny HTTP -> ONVIF PTZ bridge for the Jooan (NVT JA-A12 / BK-family) camera.

Frigate and Home Assistant both use python-onvif-zeep, which this camera's
non-compliant ONVIF stack rejects (ActionNotSupported / onvif_error). Raw SOAP
with a WS-Security digest works, though (verified: the camera physically moves).
This bridge exposes simple HTTP endpoints that HA rest_command can call:

  GET /move?dir=left|right|up|down[&speed=0.6&t=0.5]   nudge then auto-stop
  GET /stop                                            stop PTZ
  GET /health                                          -> ok

Camera settings come from env (see /home/matteo/.config/ptzbridge.env):
  CAM_HOST, CAM_PORT, CAM_USER, CAM_PASS, BRIDGE_PORT
"""
import os, base64, hashlib, datetime, time, urllib.request, re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

CAM_HOST = os.environ.get("CAM_HOST", "192.168.20.117")
CAM_PORT = int(os.environ.get("CAM_PORT", "8899"))
CAM_USER = os.environ.get("CAM_USER", "admin")
CAM_PASS = os.environ.get("CAM_PASS", "password")
BRIDGE_PORT = int(os.environ.get("BRIDGE_PORT", "8790"))
PTZ_EP = f"http://{CAM_HOST}:{CAM_PORT}/onvif/Ptz"
PTZ_NS = "http://www.onvif.org/ver20/ptz/wsdl"
PROFILE = os.environ.get("CAM_PROFILE", "profile_0")


def _security():
    n = os.urandom(16)
    c = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    d = base64.b64encode(hashlib.sha1(n + c.encode() + CAM_PASS.encode()).digest()).decode()
    return (
        '<Security s:mustUnderstand="1" xmlns="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">'
        f"<UsernameToken><Username>{CAM_USER}</Username>"
        f'<Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest">{d}</Password>'
        f'<Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">{base64.b64encode(n).decode()}</Nonce>'
        f'<Created xmlns="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">{c}</Created>'
        "</UsernameToken></Security>"
    )


def _soap(body):
    env = (
        '<?xml version="1.0"?><s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">'
        f"<s:Header>{_security()}</s:Header><s:Body>{body}</s:Body></s:Envelope>"
    )
    req = urllib.request.Request(PTZ_EP, env.encode(), {"Content-Type": "application/soap+xml; charset=utf-8"})
    try:
        r = urllib.request.urlopen(req, timeout=6).read().decode(errors="replace")
        return ("Fault" not in r), r
    except Exception as e:
        return False, getattr(e, "read", lambda: b"")().decode(errors="replace") or str(e)


def move(x, y):
    return _soap(
        f'<ContinuousMove xmlns="{PTZ_NS}"><ProfileToken>{PROFILE}</ProfileToken>'
        f'<Velocity><PanTilt x="{x}" y="{y}" xmlns="http://www.onvif.org/ver10/schema"/></Velocity></ContinuousMove>'
    )


def stop():
    return _soap(
        f'<Stop xmlns="{PTZ_NS}"><ProfileToken>{PROFILE}</ProfileToken>'
        f"<PanTilt>true</PanTilt><Zoom>true</Zoom></Stop>"
    )


DIRS = {"left": (-1, 0), "right": (1, 0), "up": (0, 1), "down": (0, -1)}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, msg):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(msg.encode())

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/health":
            return self._send(200, "ok")
        if u.path == "/stop":
            ok, _ = stop()
            return self._send(200 if ok else 502, "stopped" if ok else "stop failed")
        if u.path == "/move":
            d = (q.get("dir", [""])[0]).lower()
            if d not in DIRS:
                return self._send(400, "bad dir")
            speed = float(q.get("speed", ["0.6"])[0])
            t = float(q.get("t", ["0.5"])[0])
            sx, sy = DIRS[d]
            ok, _ = move(sx * speed, sy * speed)
            if not ok:
                return self._send(502, "move failed")
            time.sleep(min(t, 3.0))
            stop()
            return self._send(200, f"moved {d}")
        return self._send(404, "not found")


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", BRIDGE_PORT), H).serve_forever()
