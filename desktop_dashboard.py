import argparse
import html
import json
import os
import socket
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


DEFAULT_PICO_HOST = "192.168.1.100"
DEFAULT_PICO_PORT = 5050
DEMO_MODE = False
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.join(BASE_DIR, "assets")
HTMX_CDN = (
    "https://cdn.jsdelivr.net/npm/htmx.org@2.0.10/dist/htmx.min.js"
)
HTMX_INTEGRITY = (
    "sha384-H5SrcfygHmAuTDZphMHqBJLc3FhssKjG7w/CeCpFReSfwBWDTKpkzPP8c+cLsK+V"
)


class PicoClient:
    def __init__(self, host, port, timeout=3):
        self.host = host
        self.port = port
        self.timeout = timeout

    def send_command(self, command):
        with socket.create_connection((self.host, self.port), self.timeout) as pico:
            pico.settimeout(self.timeout)
            pico.sendall((command.strip().upper() + "\n").encode("utf-8"))
            chunks = []
            while True:
                chunk = pico.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
                if b"\n" in chunk:
                    break

        raw_response = b"".join(chunks).decode("utf-8").strip()
        return json.loads(raw_response)


class DemoPicoClient:
    state = "CLOSED_IDLE"
    last_close_reason = None
    manual_hold_until = 0
    started_at = time.time()
    events = []

    def __init__(self, host=None, port=None, timeout=3):
        self.host = host
        self.port = port
        self.timeout = timeout
        if not self.events:
            self._record("BOOT_COMPLETE", "CLOSED_IDLE")

    def send_command(self, command):
        command = command.strip().upper()

        if command == "PING":
            return {"ok": True, "message": "pong"}

        if command == "OPEN":
            self.state = "OPEN_MONITORING"
            self.last_close_reason = None
            self.manual_hold_until = 0
            self._record("MANUAL_OPEN", "OPEN_MONITORING")
            self._record("OPEN_CONFIRMED", "OPEN_MONITORING")
            return {"ok": True, "command": command, "status": self._status()}

        if command == "CLOSE":
            self.state = "CLOSED_IDLE"
            self.last_close_reason = "MANUAL_CLOSE"
            self.manual_hold_until = time.time() + 300
            self._record("MANUAL_CLOSE", "CLOSED_IDLE")
            self._record("CLOSE_CONFIRMED", "CLOSED_IDLE")
            return {"ok": True, "command": command, "status": self._status()}

        if command == "RESET":
            self.state = "CLOSED_IDLE"
            self.last_close_reason = None
            self.manual_hold_until = 0
            self._record("RESET_FAULT", "CLOSED_IDLE")
            return {"ok": True, "command": command, "status": self._status()}

        if command == "STATUS":
            return {"ok": True, "status": self._status()}

        return {"ok": False, "error": "Unknown command"}

    def _status(self):
        now = time.time()
        elapsed = int(now - self.started_at)
        local_time = time.localtime(now)
        feeding_window_active = 7 <= local_time.tm_hour < 19
        manual_hold_remaining = max(0, int(self.manual_hold_until - now))
        if manual_hold_remaining == 0 and self.last_close_reason == "MANUAL_CLOSE":
            self.last_close_reason = None

        return {
            "state": self.state,
            "last_close_reason": self.last_close_reason,
            "feeding_window_active": feeding_window_active,
            "manual_hold_active": manual_hold_remaining > 0,
            "manual_hold_remaining_seconds": manual_hold_remaining,
            "sensors": {
                "force_value": 40 + (elapsed % 20),
                "impact_value": 120 + ((elapsed * 37) % 240),
                "motion_detected": elapsed % 9 in (0, 1),
                "moisture_value": 80 + ((elapsed * 11) % 35),
                "battery_voltage": 4.86,
                "temperature_c": 22 + (elapsed % 4),
                "humidity_percent": 39 + (elapsed % 7),
                "acceleration_x": 80 + (elapsed % 20),
                "acceleration_y": -40 + (elapsed % 16),
                "acceleration_z": 16384,
            },
            "settings": {
                "feeding_start_hour": 7,
                "feeding_end_hour": 19,
                "cooldown_seconds": 1800,
                "manual_close_cooldown_seconds": 300,
                "impact_threshold": 9000,
                "moisture_threshold": 600,
                "low_battery_voltage": 3.4,
            },
            "recent_events": list(self.events),
        }

    def _record(self, event_type, details):
        now = time.localtime()
        self.events.append(
            {
                "time": [
                    now.tm_year,
                    now.tm_mon,
                    now.tm_mday,
                    now.tm_hour,
                    now.tm_min,
                    now.tm_sec,
                ],
                "type": event_type,
                "details": details,
            }
        )
        if len(self.events) > 50:
            self.events.pop(0)


class DashboardHandler(BaseHTTPRequestHandler):
    default_pico_host = DEFAULT_PICO_HOST
    default_pico_port = DEFAULT_PICO_PORT

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self._send_html(self._page_html())
            return

        if parsed.path == "/assets/seed_safe_logo.png":
            self._send_file(
                os.path.join(ASSET_DIR, "seed_safe_logo.png"),
                "image/png",
            )
            return

        if parsed.path == "/partials/dashboard":
            self._send_html(self._dashboard_fragments(parsed.query))
            return

        if parsed.path == "/api/status":
            context = self._dashboard_context(parsed.query, "STATUS")
            if context["ok"]:
                self._send_json({"ok": True, "status": context["status"]})
            else:
                self._send_json(
                    {"ok": False, "error": context["error"]},
                    status=502,
                )
            return

        self._send_json({"ok": False, "error": "Not found"}, status=404)

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/partials/command":
            params = parse_qs(parsed.query)
            command = self._first(params, "command", "").upper()
            if command not in ("OPEN", "CLOSE", "RESET"):
                self._send_html(self._dashboard_fragments(parsed.query, error="Unsupported command"))
                return
            self._send_html(self._dashboard_fragments(parsed.query, command=command))
            return

        if parsed.path == "/api/command":
            params = parse_qs(parsed.query)
            command = self._first(params, "command", "").upper()
            if command not in ("OPEN", "CLOSE", "RESET"):
                self._send_json({"ok": False, "error": "Unsupported command"}, status=400)
                return

            context = self._dashboard_context(parsed.query, command)
            if context["ok"]:
                self._send_json(
                    {
                        "ok": True,
                        "command": command,
                        "status": context["status"],
                    }
                )
            else:
                self._send_json(
                    {"ok": False, "error": context["error"]},
                    status=502,
                )
            return

        self._send_json({"ok": False, "error": "Not found"}, status=404)

    def log_message(self, format, *args):
        print("{} - {}".format(self.address_string(), format % args))

    def _dashboard_context(self, query, command="STATUS"):
        params = parse_qs(query)
        pico_host = self._first(params, "pico_host", self.default_pico_host)
        pico_port = int(self._first(params, "pico_port", self.default_pico_port))

        try:
            client_type = DemoPicoClient if DEMO_MODE else PicoClient
            response = client_type(pico_host, pico_port).send_command(command)
            if not response.get("ok"):
                raise RuntimeError(response.get("error", "Unknown Pico error"))

            status = response.get("status")
            if status is None and command == "STATUS":
                raise RuntimeError("Pico did not return status data")

            return {
                "ok": True,
                "status": status,
                "error": "",
                "pico_host": pico_host,
                "pico_port": pico_port,
                "command": command,
            }
        except Exception as exc:
            return {
                "ok": False,
                "status": None,
                "error": "Could not reach Pico at {}:{} ({})".format(
                    pico_host,
                    pico_port,
                    exc,
                ),
                "pico_host": pico_host,
                "pico_port": pico_port,
                "command": command,
            }

    def _dashboard_fragments(self, query, command="STATUS", error=None):
        context = self._dashboard_context(query, command) if error is None else {
            "ok": False,
            "status": None,
            "error": error,
            "pico_host": self._first(parse_qs(query), "pico_host", self.default_pico_host),
            "pico_port": int(self._first(parse_qs(query), "pico_port", self.default_pico_port)),
            "command": command,
        }

        parts = [
            self._render_online_pill(context),
            self._render_status_panel(context),
            self._render_overview_panel(context),
            self._render_controls_panel(context),
            self._render_events_panel(context),
            self._render_connection_state(context),
        ]
        return "".join(parts)

    def _page_html(self):
        return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Seed Safe Dashboard</title>
<script src="{htmx_src}" integrity="{htmx_integrity}" crossorigin="anonymous"></script>
<style>
:root{{
  color-scheme:dark;
  --bg:#080d13;
  --shell:#0c1219;
  --panel:#121922;
  --panel2:#161f2a;
  --line:#2b3440;
  --soft:#1e2732;
  --ink:#f4f7f5;
  --muted:#aab3bc;
  --green:#62e985;
  --green2:#2fb85b;
  --danger:#ff6969;
  --warn:#ffc76d;
}}
*{{box-sizing:border-box}}
body{{
  min-height:100vh;
  margin:0;
  background:
    radial-gradient(circle at 82% 15%, rgba(98,233,133,.10), transparent 28%),
    radial-gradient(circle at 18% 86%, rgba(87,147,255,.08), transparent 30%),
    var(--bg);
  color:var(--ink);
  font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
}}
button,input{{font:inherit}}
button{{cursor:pointer}}
.app{{
  width:min(1380px, calc(100% - 24px));
  min-height:calc(100vh - 24px);
  margin:12px auto;
  display:grid;
  grid-template-columns:260px minmax(0,1fr);
  overflow:hidden;
  border:1px solid var(--line);
  border-radius:16px;
  background:linear-gradient(135deg, rgba(15,22,31,.96), rgba(7,12,18,.96));
  box-shadow:0 24px 70px rgba(0,0,0,.42);
}}
.sidebar{{
  padding:30px 20px;
  border-right:1px solid var(--soft);
  background:rgba(7,12,18,.55);
}}
.brand{{
  display:flex;
  align-items:center;
  margin-bottom:44px;
}}
.logo{{
  width:190px;
  height:68px;
  display:block;
  object-fit:cover;
  object-position:center;
  border-radius:10px;
  mix-blend-mode:screen;
  filter:contrast(1.18) saturate(1.18) brightness(1.28);
  opacity:.94;
}}
.nav{{display:grid;gap:12px}}
.nav a{{
  min-height:56px;
  display:flex;
  align-items:center;
  gap:14px;
  padding:0 18px;
  border-radius:8px;
  color:#c8d0d8;
  text-decoration:none;
}}
.nav a.active{{
  color:var(--green);
  background:linear-gradient(90deg, rgba(67,218,108,.17), rgba(67,218,108,.05));
}}
.nav b{{width:22px;text-align:center}}
.content{{min-width:0;padding:32px 28px 28px}}
.topbar{{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:18px;
  margin-bottom:28px;
}}
h1{{margin:0;font-size:32px;line-height:1.1;letter-spacing:0}}
.subtitle{{margin:10px 0 0;color:var(--muted)}}
.pill{{
  min-height:42px;
  display:inline-flex;
  align-items:center;
  gap:10px;
  padding:0 18px;
  border:1px solid rgba(98,233,133,.18);
  border-radius:12px;
  color:var(--green);
  background:rgba(24,89,54,.36);
  font-weight:800;
}}
.pill.offline{{
  color:var(--danger);
  border-color:rgba(255,105,105,.25);
  background:rgba(106,34,34,.28);
}}
.dot{{
  width:8px;
  height:8px;
  border-radius:50%;
  background:currentColor;
  box-shadow:0 0 12px currentColor;
}}
.grid{{
  display:grid;
  grid-template-columns:minmax(0,1fr) minmax(300px,.92fr);
  gap:18px;
}}
.card{{
  border:1px solid var(--line);
  border-radius:10px;
  background:linear-gradient(145deg, rgba(24,32,43,.94), rgba(14,21,29,.94));
  box-shadow:inset 0 1px 0 rgba(255,255,255,.035);
}}
.pad{{padding:24px}}
.wide{{grid-column:1/-1}}
.card-title{{
  display:flex;
  align-items:center;
  gap:12px;
  margin:0 0 26px;
  font-size:18px;
  font-weight:800;
}}
.mark{{
  width:24px;
  height:24px;
  display:inline-grid;
  place-items:center;
  border:2px solid currentColor;
  border-radius:7px;
  color:var(--green);
  font-size:12px;
  font-weight:900;
}}
.status-row{{
  min-height:48px;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:14px;
  border-top:1px solid var(--soft);
}}
.status-row:first-child{{border-top:0}}
.value{{text-align:right;overflow-wrap:anywhere}}
.badge{{
  max-width:220px;
  padding:7px 12px;
  border-radius:10px;
  color:#eaffef;
  background:linear-gradient(135deg, rgba(87,220,120,.5), rgba(30,102,58,.74));
  font-size:13px;
  font-weight:900;
}}
.overview{{
  min-height:254px;
  display:grid;
  grid-template-columns:1fr 132px;
  align-items:center;
  gap:18px;
}}
.overview h3{{margin:0 0 10px;color:var(--green);font-size:20px}}
.overview p{{margin:0;color:#dce2e6}}
.shield{{width:128px;height:146px;opacity:.22}}
.controls{{
  display:grid;
  grid-template-columns:repeat(3,minmax(130px,1fr));
  gap:18px;
}}
.command{{
  min-height:86px;
  border:1px solid var(--line);
  border-radius:8px;
  color:white;
  background:linear-gradient(145deg, rgba(34,43,55,.96), rgba(18,25,34,.96));
  box-shadow:0 12px 26px rgba(0,0,0,.22);
}}
.command.active{{
  border-color:rgba(98,233,133,.35);
  background:linear-gradient(145deg,#66e186,#25984d);
}}
.command span{{
  display:block;
  margin-bottom:8px;
  font-size:24px;
  font-weight:900;
  line-height:1;
}}
.command.htmx-request{{
  opacity:.75;
}}
.events-head{{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:12px;
  margin-bottom:22px;
}}
.events-head .card-title{{margin:0}}
.refresh{{
  min-height:38px;
  border:1px solid var(--line);
  border-radius:8px;
  padding:0 16px;
  color:white;
  background:linear-gradient(145deg, rgba(54,65,79,.9), rgba(32,39,50,.9));
}}
.events{{
  position:relative;
  margin:0;
  padding:0;
  list-style:none;
}}
.events:before{{
  content:"";
  position:absolute;
  top:14px;
  bottom:28px;
  left:9px;
  width:2px;
  background:rgba(98,233,133,.28);
}}
.events li{{
  position:relative;
  min-height:66px;
  display:grid;
  grid-template-columns:1fr auto;
  gap:16px;
  padding:0 0 20px 36px;
}}
.events li:before{{
  content:"";
  position:absolute;
  left:1px;
  top:7px;
  width:16px;
  height:16px;
  border-radius:50%;
  background:var(--green2);
  box-shadow:0 0 0 5px rgba(98,233,133,.15);
}}
.event-name{{font-weight:800}}
.event-detail{{margin-top:6px;color:#d6dde2}}
.event-time{{color:#c2cbd3;white-space:nowrap}}
.connection-card{{margin-top:18px}}
.fields{{
  display:grid;
  grid-template-columns:1fr 110px;
  gap:12px;
}}
label{{
  display:block;
  margin:0 0 7px;
  color:var(--muted);
  font-size:12px;
  font-weight:800;
  text-transform:uppercase;
}}
input{{
  width:100%;
  min-height:42px;
  padding:9px 11px;
  border:1px solid var(--line);
  border-radius:8px;
  outline:none;
  color:#f7fff9;
  background:#0a1118;
}}
input:focus{{
  border-color:rgba(98,233,133,.6);
  box-shadow:0 0 0 3px rgba(98,233,133,.1);
}}
.connection{{
  min-height:42px;
  display:flex;
  align-items:center;
  margin-top:14px;
  padding:10px 12px;
  border:1px solid var(--soft);
  border-radius:8px;
  color:var(--muted);
  background:rgba(6,10,15,.52);
  overflow-wrap:anywhere;
}}
.connection.ok{{
  color:#dfffe7;
  border-color:rgba(98,233,133,.25);
  background:rgba(21,69,42,.28);
}}
.connection.bad{{
  color:#ffd6d6;
  border-color:rgba(255,105,105,.25);
  background:rgba(83,30,30,.28);
}}
.footer{{margin-top:24px;color:var(--muted);text-align:center;font-size:14px}}
.mobile-nav{{display:none}}
@media (max-width:900px){{
  body{{background:var(--bg)}}
  .app{{width:100%;min-height:100vh;margin:0;display:block;border:0;border-radius:0}}
  .sidebar{{display:none}}
  .content{{padding:24px 18px 104px}}
  .topbar{{margin-bottom:22px}}
  h1{{font-size:20px}}
  .subtitle{{display:none}}
  .grid{{display:block}}
  .card{{margin-bottom:18px}}
  .overview{{display:none}}
  .controls{{grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}}
  .command{{min-height:80px;padding:0 8px}}
  .fields{{grid-template-columns:1fr}}
  .events li{{gap:10px;padding-left:30px}}
  .event-detail{{display:none}}
  .mobile-nav{{
    position:fixed;
    left:0;
    right:0;
    bottom:0;
    z-index:20;
    display:grid;
    grid-template-columns:repeat(3,1fr);
    min-height:76px;
    border-top:1px solid var(--line);
    background:rgba(12,18,25,.96);
    backdrop-filter:blur(16px);
  }}
  .mobile-nav a{{
    display:grid;
    place-items:center;
    align-content:center;
    gap:5px;
    color:#c1cad2;
    text-decoration:none;
    font-size:12px;
  }}
  .mobile-nav a.active{{color:var(--green)}}
}}
@media (max-width:520px){{
  .content{{padding-left:12px;padding-right:12px}}
  .pad{{padding:18px}}
  .pill{{min-height:36px;padding:0 12px;font-size:13px}}
  .badge{{max-width:170px;font-size:11px}}
}}
</style>
</head>
<body>
<div id="dashboardSync"
     hx-get="/partials/dashboard"
     hx-trigger="load, every 2s, refresh"
     hx-include="#connectionForm"
     hx-swap="none"></div>
<div class="app">
  <aside class="sidebar">
    <div class="brand"><img class="logo" src="/assets/seed_safe_logo.png" alt="Seed Safe"></div>
    <nav class="nav" aria-label="Main navigation">
      <a class="active" href="#"><b>H</b>Dashboard</a>
      <a href="#controls"><b>C</b>Controls</a>
      <a href="#events"><b>E</b>Events</a>
      <a href="#connection"><b>S</b>Settings</a>
      <a href="#"><b>i</b>About</a>
    </nav>
  </aside>
  <main class="content">
    <header class="topbar">
      <div>
        <h1>Dashboard</h1>
        <p class="subtitle">Monitor and control your Seed Safe.</p>
      </div>
      <div class="pill offline" id="onlinePill"><span class="dot"></span><span>OFFLINE</span></div>
    </header>
    <div class="grid">
      <section id="statusPanel" class="card pad">
        <h2 class="card-title"><span class="mark">S</span>System Status</h2>
        <div class="status-row"><span>State</span><strong class="badge">LOADING</strong></div>
        <div class="status-row"><span>Last Close Reason</span><span class="value">Waiting for status...</span></div>
        <div class="status-row"><span>Manual Hold</span><span class="value">Waiting for status...</span></div>
        <div class="status-row"><span>Feeding Window</span><span class="value">Waiting for status...</span></div>
      </section>
      <section id="overviewPanel" class="card pad overview">
        <div>
          <h2 class="card-title"><span class="mark">D</span>Device Overview</h2>
          <h3>Waiting for Seed Safe</h3>
          <p>Connect to the Pico command port to see live feeder data.</p>
        </div>
        <svg class="shield" viewBox="0 0 120 140" aria-hidden="true">
          <path d="M60 8 108 30v35c0 34-19 56-48 68-29-12-48-34-48-68V30L60 8Z" fill="none" stroke="#62e985" stroke-width="10"/>
          <path d="M38 70l17 17 31-36" fill="none" stroke="#62e985" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </section>
      <section id="controlsPanel" class="card pad wide">
        <h2 class="card-title"><span class="mark">M</span>Manual Controls</h2>
        <div class="controls">
          <button class="command" type="button">Open</button>
          <button class="command" type="button">Close</button>
          <button class="command" type="button">Reset</button>
        </div>
      </section>
      <section id="eventsPanel" class="card pad wide">
        <div class="events-head">
          <h2 class="card-title"><span class="mark">E</span>Recent Events</h2>
          <button class="refresh" type="button" onclick="htmx.trigger('#dashboardSync', 'refresh')">Refresh</button>
        </div>
        <ul class="events">
          <li><div><div class="event-name">WAITING</div><div class="event-detail">Waiting for Pico status...</div></div><span class="event-time">Now</span></li>
        </ul>
      </section>
      <section class="card pad wide connection-card" id="connection">
        <h2 class="card-title"><span class="mark">N</span>Pico Connection</h2>
        <form id="connectionForm" class="fields">
          <div>
            <label for="picoHost">Pico IP address</label>
            <input id="picoHost" name="pico_host" autocomplete="off">
          </div>
          <div>
            <label for="picoPort">Port</label>
            <input id="picoPort" name="pico_port" inputmode="numeric">
          </div>
        </form>
        <div id="connectionState" class="connection">Not connected yet.</div>
      </section>
    </div>
    <div class="footer">Seed Safe v1.1.0 - HTMX-powered desktop dashboard</div>
  </main>
</div>
<nav class="mobile-nav" aria-label="Mobile navigation">
  <a class="active" href="#"><span>H</span><span>Dashboard</span></a>
  <a href="#events"><span>E</span><span>Events</span></a>
  <a href="#connection"><span>S</span><span>Settings</span></a>
</nav>
<script>
const hostInput = document.querySelector('#picoHost');
const portInput = document.querySelector('#picoPort');

hostInput.value = localStorage.getItem('picoHost') || '{default_host}';
portInput.value = localStorage.getItem('picoPort') || '{default_port}';

function persistConnectionSettings(){{
  localStorage.setItem('picoHost', hostInput.value);
  localStorage.setItem('picoPort', portInput.value);
  refreshDashboard();
}}

hostInput.addEventListener('change', persistConnectionSettings);
portInput.addEventListener('change', persistConnectionSettings);

function connectionParams(){{
  return new URLSearchParams(new FormData(document.querySelector('#connectionForm')));
}}

function applyDashboardFragments(markup){{
  const doc = new DOMParser().parseFromString(markup, 'text/html');
  ['onlinePill', 'statusPanel', 'overviewPanel', 'controlsPanel', 'eventsPanel', 'connectionState'].forEach((id) => {{
    const next = doc.querySelector('#' + id);
    const current = document.querySelector('#' + id);
    if (next && current) current.replaceWith(next);
  }});
}}

async function refreshDashboard(){{
  if (window.htmx) {{
    htmx.trigger('#dashboardSync', 'refresh');
    return;
  }}
  const response = await fetch('/partials/dashboard?' + connectionParams().toString(), {{cache: 'no-store'}});
  applyDashboardFragments(await response.text());
}}

document.body.addEventListener('click', async (event) => {{
  const button = event.target.closest('button.command');
  if (!button || window.htmx) return;
  const match = button.getAttribute('hx-post').match(/command=([A-Z]+)/);
  if (!match) return;
  const params = connectionParams();
  params.set('command', match[1]);
  const response = await fetch('/partials/command?' + params.toString(), {{
    method: 'POST',
    cache: 'no-store',
  }});
  applyDashboardFragments(await response.text());
}});

if (!window.htmx) {{
  refreshDashboard();
  setInterval(refreshDashboard, 2000);
}}
</script>
</body>
</html>""".format(
            htmx_src=HTMX_CDN,
            htmx_integrity=HTMX_INTEGRITY,
            default_host=self.default_pico_host,
            default_port=self.default_pico_port,
        )

    def _render_online_pill(self, context):
        classes = "pill"
        text = "ONLINE"
        if not context["ok"]:
            classes += " offline"
            text = "OFFLINE"
        return '<div id="onlinePill" class="{}" hx-swap-oob="outerHTML"><span class="dot"></span><span>{}</span></div>'.format(
            classes,
            text,
        )

    def _render_status_panel(self, context):
        if not context["ok"]:
            return """<section id="statusPanel" class="card pad" hx-swap-oob="outerHTML">
<h2 class="card-title"><span class="mark">S</span>System Status</h2>
<div class="status-row"><span>State</span><strong class="badge">OFFLINE</strong></div>
<div class="status-row"><span>Last Close Reason</span><span class="value">Unknown</span></div>
<div class="status-row"><span>Manual Hold</span><span class="value">Unknown</span></div>
<div class="status-row"><span>Feeding Window</span><span class="value">Unknown</span></div>
</section>"""

        status = context["status"]
        return """<section id="statusPanel" class="card pad" hx-swap-oob="outerHTML">
<h2 class="card-title"><span class="mark">S</span>System Status</h2>
<div class="status-row"><span>State</span><strong class="badge">{state}</strong></div>
<div class="status-row"><span>Last Close Reason</span><span class="value">{reason}</span></div>
<div class="status-row"><span>Manual Hold</span><span class="value">{hold}</span></div>
<div class="status-row"><span>Feeding Window</span><span class="value">{window}</span></div>
</section>""".format(
            state=self._escape(status.get("state", "UNKNOWN")),
            reason=self._escape(status.get("last_close_reason") or "None"),
            hold=self._escape(self._manual_hold_label(status)),
            window="Active" if status.get("feeding_window_active") else "Inactive",
        )

    def _render_overview_panel(self, context):
        title = "Waiting for Seed Safe"
        detail = "Connect to the Pico command port to see live feeder data."

        if context["ok"]:
            status = context["status"]
            state = status.get("state", "UNKNOWN")
            if state in ("FAULT", "LOW_POWER"):
                title = "Protected state detected"
                detail = "Seed Safe is connected, but the controller is reporting {}.".format(
                    state.replace("_", " ").lower()
                )
            elif status.get("manual_hold_active"):
                title = "Manual close hold active"
                detail = "Seed Safe will stay closed for {} unless you manually reopen it.".format(
                    self._manual_hold_label(status)
                )
            elif status.get("feeding_window_active"):
                title = "Feeding window is active"
                detail = "Seed Safe is connected and ready to reopen when the controller allows it."
            else:
                title = "All systems normal"
                detail = "Seed Safe is operating as expected outside the feeding window."
        else:
            detail = context["error"]

        return """<section id="overviewPanel" class="card pad overview" hx-swap-oob="outerHTML">
<div>
<h2 class="card-title"><span class="mark">D</span>Device Overview</h2>
<h3>{title}</h3>
<p>{detail}</p>
</div>
<svg class="shield" viewBox="0 0 120 140" aria-hidden="true">
  <path d="M60 8 108 30v35c0 34-19 56-48 68-29-12-48-34-48-68V30L60 8Z" fill="none" stroke="#62e985" stroke-width="10"/>
  <path d="M38 70l17 17 31-36" fill="none" stroke="#62e985" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
</section>""".format(
            title=self._escape(title),
            detail=self._escape(detail),
        )

    def _render_controls_panel(self, context):
        active = self._active_command(context["status"]) if context["ok"] else ""
        buttons = []
        for command, label, icon in (
            ("OPEN", "Open", "O"),
            ("CLOSE", "Close", "C"),
            ("RESET", "Reset", "R"),
        ):
            classes = ["command"]
            if command == active:
                classes.append("active")
            buttons.append(
                '<button class="{classes}" type="button" '
                'hx-post="/partials/command?command={command}" '
                'hx-include="#connectionForm" '
                'hx-target="this" hx-swap="none">'
                '<span>{icon}</span>{label}</button>'.format(
                    classes=" ".join(classes),
                    command=command,
                    icon=icon,
                    label=label,
                )
            )

        return """<section id="controlsPanel" class="card pad wide" hx-swap-oob="outerHTML">
<h2 class="card-title"><span class="mark">M</span>Manual Controls</h2>
<div class="controls">{buttons}</div>
</section>""".format(buttons="".join(buttons))

    def _render_events_panel(self, context):
        if not context["ok"]:
            items = (
                '<li><div><div class="event-name">OFFLINE</div>'
                '<div class="event-detail">{}</div></div>'
                '<span class="event-time">Now</span></li>'.format(
                    self._escape(context["error"])
                )
            )
        else:
            events = list(context["status"].get("recent_events", []))[-8:]
            if not events:
                items = (
                    '<li><div><div class="event-name">NO_EVENTS</div>'
                    '<div class="event-detail">No controller events have been recorded yet.</div></div>'
                    '<span class="event-time">Now</span></li>'
                )
            else:
                rendered = []
                for event in reversed(events):
                    rendered.append(
                        '<li><div><div class="event-name">{name}</div>'
                        '<div class="event-detail">{detail}</div></div>'
                        '<span class="event-time">{time}</span></li>'.format(
                            name=self._escape(event.get("type", "UNKNOWN")),
                            detail=self._escape(
                                event.get("details") or self._event_message(event.get("type"))
                            ),
                            time=self._escape(self._format_time(event.get("time"))),
                        )
                    )
                items = "".join(rendered)

        return """<section id="eventsPanel" class="card pad wide" hx-swap-oob="outerHTML">
<div class="events-head">
  <h2 class="card-title"><span class="mark">E</span>Recent Events</h2>
  <button class="refresh" type="button" onclick="htmx.trigger('#dashboardSync', 'refresh')">Refresh</button>
</div>
<ul class="events">{items}</ul>
</section>""".format(items=items)

    def _render_connection_state(self, context):
        classes = "connection ok" if context["ok"] else "connection bad"
        if context["ok"]:
            if DEMO_MODE:
                message = "Demo mode is running locally with simulated Pico data."
            else:
                message = "Connected to {}:{}".format(
                    context["pico_host"],
                    context["pico_port"],
                )
        else:
            message = context["error"]

        return '<div id="connectionState" class="{classes}" hx-swap-oob="outerHTML">{message}</div>'.format(
            classes=classes,
            message=self._escape(message),
        )

    def _active_command(self, status):
        if status is None:
            return ""

        state = status.get("state", "")
        if state in ("FAULT", "LOW_POWER"):
            return "RESET"
        if state in ("OPENING", "OPEN_MONITORING"):
            return "OPEN"
        if state in ("CLOSING", "CLOSED_IDLE", "CLOSED_COOLDOWN"):
            return "CLOSE"
        return ""

    def _manual_hold_label(self, status):
        if not status.get("manual_hold_active"):
            return "Inactive"
        return self._format_duration(status.get("manual_hold_remaining_seconds", 0))

    def _format_duration(self, seconds):
        total = max(0, int(seconds or 0))
        if total < 60:
            return "{}s".format(total)
        minutes = total // 60
        remaining_seconds = total % 60
        if minutes < 60:
            return "{}m {}s".format(minutes, remaining_seconds)
        hours = minutes // 60
        return "{}h {}m".format(hours, minutes % 60)

    def _event_message(self, event_type):
        return {
            "BOOT_COMPLETE": "System boot completed successfully.",
            "FEEDING_WINDOW_STARTED": "Feeding window has started.",
            "FEEDING_WINDOW_ENDED": "Feeding window has ended.",
            "OPEN_CONFIRMED": "Safe is now open.",
            "CLOSE_CONFIRMED": "Safe is now closed.",
            "MANUAL_OPEN": "Manual open command received.",
            "MANUAL_CLOSE": "Manual close command received.",
            "RESET_FAULT": "Reset command received.",
        }.get(event_type, "Controller state changed.")

    def _format_time(self, value):
        if isinstance(value, list) or isinstance(value, tuple):
            parts = list(value)[:6]
            if len(parts) >= 6:
                padded = [str(part).zfill(2) for part in parts]
                return "{}:{}:{}".format(padded[3], padded[4], padded[5])
        return str(value or "")

    def _escape(self, value):
        return html.escape(str(value))

    def _first(self, params, key, default):
        values = params.get(key)
        if not values:
            return default
        return values[0]

    def _send_html(self, body):
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def _send_file(self, path, content_type):
        if not os.path.isfile(path):
            self._send_json({"ok": False, "error": "Asset not found"}, status=404)
            return

        with open(path, "rb") as file:
            data = file.read()

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload, status=200):
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)


def main():
    global DEMO_MODE

    parser = argparse.ArgumentParser(description="Host the Seed Safe dashboard on this computer.")
    parser.add_argument("--host", default="127.0.0.1", help="Dashboard bind address")
    parser.add_argument("--port", type=int, default=8080, help="Dashboard HTTP port")
    parser.add_argument("--pico-host", default=DEFAULT_PICO_HOST, help="Default Pico IP address")
    parser.add_argument("--pico-port", type=int, default=DEFAULT_PICO_PORT, help="Default Pico command port")
    parser.add_argument("--demo", action="store_true", help="Run with simulated Pico data and no hardware")
    args = parser.parse_args()

    DEMO_MODE = args.demo
    DashboardHandler.default_pico_host = args.pico_host
    DashboardHandler.default_pico_port = args.pico_port

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    url = "http://{}:{}".format(args.host, args.port)
    print("Seed Safe dashboard running at {}".format(url))
    if DEMO_MODE:
        print("Demo mode enabled: using simulated Pico data")
    else:
        print("Default Pico target is {}:{}".format(args.pico_host, args.pico_port))
    server.serve_forever()


if __name__ == "__main__":
    main()
