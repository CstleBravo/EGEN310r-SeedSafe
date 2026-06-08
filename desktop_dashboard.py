import argparse
import json
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


DEFAULT_PICO_HOST = "192.168.1.100"
DEFAULT_PICO_PORT = 5050


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


class DashboardHandler(BaseHTTPRequestHandler):
    default_pico_host = DEFAULT_PICO_HOST
    default_pico_port = DEFAULT_PICO_PORT

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self._send_html(DASHBOARD_HTML)
            return

        if parsed.path == "/api/status":
            self._proxy_command(parsed.query, "STATUS")
            return

        self._send_json({"ok": False, "error": "Not found"}, status=404)

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/command":
            params = parse_qs(parsed.query)
            command = self._first(params, "command", "").upper()
            if command not in ("OPEN", "CLOSE", "RESET"):
                self._send_json({"ok": False, "error": "Unsupported command"}, status=400)
                return
            self._proxy_command(parsed.query, command)
            return

        self._send_json({"ok": False, "error": "Not found"}, status=404)

    def log_message(self, format, *args):
        print("{} - {}".format(self.address_string(), format % args))

    def _proxy_command(self, query, command):
        params = parse_qs(query)
        pico_host = self._first(params, "pico_host", self.default_pico_host)
        pico_port = int(self._first(params, "pico_port", self.default_pico_port))

        try:
            response = PicoClient(pico_host, pico_port).send_command(command)
        except Exception as exc:
            self._send_json(
                {
                    "ok": False,
                    "error": "Could not reach Pico at {}:{} ({})".format(
                        pico_host,
                        pico_port,
                        exc,
                    ),
                },
                status=502,
            )
            return

        self._send_json(response)

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
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, payload, status=200):
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Seed Safe Dashboard</title>
<style>
:root{
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
}
*{box-sizing:border-box}
body{
  min-height:100vh;
  margin:0;
  background:
    radial-gradient(circle at 82% 15%, rgba(98,233,133,.10), transparent 28%),
    radial-gradient(circle at 18% 86%, rgba(87,147,255,.08), transparent 30%),
    var(--bg);
  color:var(--ink);
  font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
}
button,input{font:inherit}
button{cursor:pointer}
.app{
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
}
.sidebar{
  padding:30px 20px;
  border-right:1px solid var(--soft);
  background:rgba(7,12,18,.55);
}
.brand{
  display:flex;
  align-items:center;
  gap:12px;
  margin-bottom:44px;
  color:#b8ffc8;
  font-size:23px;
  font-weight:800;
}
.logo{
  width:40px;
  height:40px;
  position:relative;
  border-radius:50%;
  background:linear-gradient(145deg,#d7ffe0,#4bd875);
  box-shadow:0 0 24px rgba(98,233,133,.35);
}
.logo:before,.logo:after{
  content:"";
  position:absolute;
  width:12px;
  height:18px;
  top:12px;
  border:2px solid #155f38;
  border-top-left-radius:14px;
  border-bottom-right-radius:14px;
}
.logo:before{left:9px;transform:rotate(-28deg)}
.logo:after{right:9px;transform:rotate(28deg) scaleX(-1)}
.nav{display:grid;gap:12px}
.nav a{
  min-height:56px;
  display:flex;
  align-items:center;
  gap:14px;
  padding:0 18px;
  border-radius:8px;
  color:#c8d0d8;
  text-decoration:none;
}
.nav a.active{
  color:var(--green);
  background:linear-gradient(90deg, rgba(67,218,108,.17), rgba(67,218,108,.05));
}
.nav b{width:22px;text-align:center}
.content{min-width:0;padding:32px 28px 28px}
.topbar{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:18px;
  margin-bottom:28px;
}
h1{margin:0;font-size:32px;line-height:1.1;letter-spacing:0}
.subtitle{margin:10px 0 0;color:var(--muted)}
.pill{
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
}
.pill.offline{
  color:var(--danger);
  border-color:rgba(255,105,105,.25);
  background:rgba(106,34,34,.28);
}
.dot{
  width:8px;
  height:8px;
  border-radius:50%;
  background:currentColor;
  box-shadow:0 0 12px currentColor;
}
.grid{
  display:grid;
  grid-template-columns:minmax(0,1fr) minmax(300px,.92fr);
  gap:18px;
}
.card{
  border:1px solid var(--line);
  border-radius:10px;
  background:linear-gradient(145deg, rgba(24,32,43,.94), rgba(14,21,29,.94));
  box-shadow:inset 0 1px 0 rgba(255,255,255,.035);
}
.pad{padding:24px}
.wide{grid-column:1/-1}
.card-title{
  display:flex;
  align-items:center;
  gap:12px;
  margin:0 0 26px;
  font-size:18px;
  font-weight:800;
}
.mark{
  width:24px;
  height:24px;
  display:inline-grid;
  place-items:center;
  border:2px solid currentColor;
  border-radius:7px;
  color:var(--green);
  font-size:12px;
  font-weight:900;
}
.status-row{
  min-height:48px;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:14px;
  border-top:1px solid var(--soft);
}
.status-row:first-child{border-top:0}
.value{text-align:right;overflow-wrap:anywhere}
.badge{
  max-width:220px;
  padding:7px 12px;
  border-radius:10px;
  color:#eaffef;
  background:linear-gradient(135deg, rgba(87,220,120,.5), rgba(30,102,58,.74));
  font-size:13px;
  font-weight:900;
}
.overview{
  min-height:254px;
  display:grid;
  grid-template-columns:1fr 132px;
  align-items:center;
  gap:18px;
}
.overview h3{
  margin:0 0 10px;
  color:var(--green);
  font-size:20px;
}
.overview p{margin:0;color:#dce2e6}
.shield{width:128px;height:146px;opacity:.22}
.controls{
  display:grid;
  grid-template-columns:repeat(3,minmax(130px,1fr));
  gap:18px;
}
.command{
  min-height:86px;
  border:1px solid var(--line);
  border-radius:8px;
  color:white;
  background:linear-gradient(145deg, rgba(34,43,55,.96), rgba(18,25,34,.96));
  box-shadow:0 12px 26px rgba(0,0,0,.22);
}
.command.primary{
  border-color:rgba(98,233,133,.35);
  background:linear-gradient(145deg,#66e186,#25984d);
}
.command.danger:hover{border-color:rgba(255,105,105,.55)}
.command.warning:hover{border-color:rgba(255,199,109,.6)}
.command span{
  display:block;
  margin-bottom:8px;
  font-size:24px;
  font-weight:900;
  line-height:1;
}
.events-head{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:12px;
  margin-bottom:22px;
}
.events-head .card-title{margin:0}
.refresh{
  min-height:38px;
  border:1px solid var(--line);
  border-radius:8px;
  padding:0 16px;
  color:white;
  background:linear-gradient(145deg, rgba(54,65,79,.9), rgba(32,39,50,.9));
}
.events{
  position:relative;
  margin:0;
  padding:0;
  list-style:none;
}
.events:before{
  content:"";
  position:absolute;
  top:14px;
  bottom:28px;
  left:9px;
  width:2px;
  background:rgba(98,233,133,.28);
}
.events li{
  position:relative;
  min-height:66px;
  display:grid;
  grid-template-columns:1fr auto;
  gap:16px;
  padding:0 0 20px 36px;
}
.events li:before{
  content:"";
  position:absolute;
  left:1px;
  top:7px;
  width:16px;
  height:16px;
  border-radius:50%;
  background:var(--green2);
  box-shadow:0 0 0 5px rgba(98,233,133,.15);
}
.event-name{font-weight:800}
.event-detail{margin-top:6px;color:#d6dde2}
.event-time{color:#c2cbd3;white-space:nowrap}
.connection-card{margin-top:18px}
.fields{
  display:grid;
  grid-template-columns:1fr 110px;
  gap:12px;
}
label{
  display:block;
  margin:0 0 7px;
  color:var(--muted);
  font-size:12px;
  font-weight:800;
  text-transform:uppercase;
}
input{
  width:100%;
  min-height:42px;
  padding:9px 11px;
  border:1px solid var(--line);
  border-radius:8px;
  outline:none;
  color:#f7fff9;
  background:#0a1118;
}
input:focus{
  border-color:rgba(98,233,133,.6);
  box-shadow:0 0 0 3px rgba(98,233,133,.1);
}
.connection{
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
}
.connection.ok{
  color:#dfffe7;
  border-color:rgba(98,233,133,.25);
  background:rgba(21,69,42,.28);
}
.connection.bad{
  color:#ffd6d6;
  border-color:rgba(255,105,105,.25);
  background:rgba(83,30,30,.28);
}
.footer{
  margin-top:24px;
  color:var(--muted);
  text-align:center;
  font-size:14px;
}
.mobile-nav{display:none}
@media (max-width:900px){
  body{background:var(--bg)}
  .app{
    width:100%;
    min-height:100vh;
    margin:0;
    display:block;
    border:0;
    border-radius:0;
  }
  .sidebar{display:none}
  .content{padding:24px 18px 104px}
  .topbar{margin-bottom:22px}
  h1{font-size:20px}
  .subtitle{display:none}
  .grid{display:block}
  .card{margin-bottom:18px}
  .overview{display:none}
  .controls{grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
  .command{min-height:80px;padding:0 8px}
  .fields{grid-template-columns:1fr}
  .events li{gap:10px;padding-left:30px}
  .event-detail{display:none}
  .mobile-nav{
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
  }
  .mobile-nav a{
    display:grid;
    place-items:center;
    align-content:center;
    gap:5px;
    color:#c1cad2;
    text-decoration:none;
    font-size:12px;
  }
  .mobile-nav a.active{color:var(--green)}
}
@media (max-width:520px){
  .content{padding-left:12px;padding-right:12px}
  .pad{padding:18px}
  .pill{min-height:36px;padding:0 12px;font-size:13px}
  .badge{max-width:170px;font-size:11px}
}
</style>
</head>
<body>
<div class="app">
  <aside class="sidebar">
    <div class="brand"><span class="logo" aria-hidden="true"></span><span>Seed Safe</span></div>
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
      <div class="pill offline" id="onlinePill"><span class="dot"></span><span id="onlineText">OFFLINE</span></div>
    </header>
    <div class="grid">
      <section class="card pad">
        <h2 class="card-title"><span class="mark">S</span>System Status</h2>
        <div class="status-row"><span>State</span><strong class="badge" id="stateValue">UNKNOWN</strong></div>
        <div class="status-row"><span>Last Close Reason</span><span class="value" id="reasonValue">None</span></div>
        <div class="status-row"><span>Uptime</span><span class="value" id="uptimeValue">0s</span></div>
      </section>
      <section class="card pad overview">
        <div>
          <h2 class="card-title"><span class="mark">D</span>Device Overview</h2>
          <h3 id="overviewTitle">Waiting for Seed Safe</h3>
          <p id="overviewText">Connect to the Pico command port to see live feeder data.</p>
        </div>
        <svg class="shield" viewBox="0 0 120 140" aria-hidden="true">
          <path d="M60 8 108 30v35c0 34-19 56-48 68-29-12-48-34-48-68V30L60 8Z" fill="none" stroke="#62e985" stroke-width="10"/>
          <path d="M38 70l17 17 31-36" fill="none" stroke="#62e985" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </section>
      <section class="card pad wide" id="controls">
        <h2 class="card-title"><span class="mark">M</span>Manual Controls</h2>
        <div class="controls">
          <button class="command primary" type="button" data-command="OPEN"><span>O</span>Open</button>
          <button class="command danger" type="button" data-command="CLOSE"><span>C</span>Close</button>
          <button class="command warning" type="button" data-command="RESET"><span>R</span>Reset</button>
        </div>
      </section>
      <section class="card pad wide" id="events">
        <div class="events-head">
          <h2 class="card-title"><span class="mark">E</span>Recent Events</h2>
          <button class="refresh" id="refreshButton" type="button">Refresh</button>
        </div>
        <ul class="events" id="eventsList"></ul>
      </section>
      <section class="card pad wide connection-card" id="connection">
        <h2 class="card-title"><span class="mark">N</span>Pico Connection</h2>
        <div class="fields">
          <div>
            <label for="picoHost">Pico IP address</label>
            <input id="picoHost" autocomplete="off">
          </div>
          <div>
            <label for="picoPort">Port</label>
            <input id="picoPort" inputmode="numeric">
          </div>
        </div>
        <div class="connection" id="connectionState">Not connected yet.</div>
      </section>
    </div>
    <div class="footer">Seed Safe v1.0.0 - Built for Raspberry Pi Pico W</div>
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
const connectionState = document.querySelector('#connectionState');
const onlinePill = document.querySelector('#onlinePill');
const onlineText = document.querySelector('#onlineText');
const stateValue = document.querySelector('#stateValue');
const reasonValue = document.querySelector('#reasonValue');
const uptimeValue = document.querySelector('#uptimeValue');
const overviewTitle = document.querySelector('#overviewTitle');
const overviewText = document.querySelector('#overviewText');
const eventsList = document.querySelector('#eventsList');
const pageStartedAt = Date.now();

hostInput.value = localStorage.getItem('picoHost') || '192.168.1.100';
portInput.value = localStorage.getItem('picoPort') || '5050';

function connectionQuery(){
  localStorage.setItem('picoHost', hostInput.value);
  localStorage.setItem('picoPort', portInput.value);
  return new URLSearchParams({pico_host:hostInput.value,pico_port:portInput.value});
}

async function refresh(){
  setConnectionState('Connecting...', 'waiting');
  const response = await fetch('/api/status?' + connectionQuery().toString());
  const payload = await response.json();
  if(!payload.ok){
    setOnline(false);
    setConnectionState(payload.error || 'Connection failed.', 'bad');
    return;
  }
  setOnline(true);
  setConnectionState('Connected to ' + hostInput.value + ':' + portInput.value, 'ok');
  renderStatus(payload.status);
}

async function sendCommand(command){
  setConnectionState('Sending ' + command + '...', 'waiting');
  const response = await fetch('/api/command?command=' + command + '&' + connectionQuery().toString(), {method:'POST'});
  const payload = await response.json();
  if(!payload.ok){
    setOnline(false);
    setConnectionState(payload.error || 'Command failed.', 'bad');
    return;
  }
  setOnline(true);
  setConnectionState(command + ' accepted.', 'ok');
  renderStatus(payload.status);
}

function renderStatus(status){
  const state = status.state || 'UNKNOWN';
  stateValue.textContent = state;
  reasonValue.textContent = status.last_close_reason || 'None';
  uptimeValue.textContent = elapsedSinceLoad();
  if(state === 'FAULT' || state === 'LOW_POWER'){
    overviewTitle.textContent = state === 'FAULT' ? 'Fault needs attention' : 'Low power mode';
    overviewText.textContent = 'Seed Safe is connected, but the controller is reporting a protected state.';
  }else{
    overviewTitle.textContent = 'All systems normal';
    overviewText.textContent = status.feeding_window_active
      ? 'Seed Safe is inside the scheduled feeding window.'
      : 'Seed Safe is operating as expected.';
  }
  renderEvents(status.recent_events || []);
}

function renderEvents(events){
  if(events.length === 0){
    eventsList.innerHTML = '<li><div><div class="event-name">NO_EVENTS</div><div class="event-detail">No controller events have been recorded yet.</div></div><span class="event-time">Now</span></li>';
    return;
  }
  eventsList.innerHTML = events.slice(-8).reverse().map(event => `
    <li>
      <div>
        <div class="event-name">${escapeHtml(event.type)}</div>
        <div class="event-detail">${escapeHtml(event.details || eventMessage(event.type))}</div>
      </div>
      <span class="event-time">${escapeHtml(formatTime(event.time))}</span>
    </li>
  `).join('');
}

function setConnectionState(message, state){
  connectionState.textContent = message;
  connectionState.classList.toggle('ok', state === 'ok');
  connectionState.classList.toggle('bad', state === 'bad');
}

function setOnline(isOnline){
  onlinePill.classList.toggle('offline', !isOnline);
  onlineText.textContent = isOnline ? 'ONLINE' : 'OFFLINE';
}

function elapsedSinceLoad(){
  const seconds = Math.max(0, Math.floor((Date.now() - pageStartedAt) / 1000));
  if(seconds < 60){return seconds + 's'}
  const minutes = Math.floor(seconds / 60);
  if(minutes < 60){return minutes + 'm ' + (seconds % 60) + 's'}
  const hours = Math.floor(minutes / 60);
  return hours + 'h ' + (minutes % 60) + 'm';
}

function eventMessage(type){
  const messages = {
    BOOT_COMPLETE:'System boot completed successfully.',
    FEEDING_WINDOW_STARTED:'Feeding window has started.',
    FEEDING_WINDOW_ENDED:'Feeding window has ended.',
    OPEN_CONFIRMED:'Safe is now open.',
    CLOSE_CONFIRMED:'Safe is now closed.',
    MANUAL_OPEN:'Manual open command received.',
    MANUAL_CLOSE:'Manual close command received.',
    RESET_FAULT:'Reset command received.'
  };
  return messages[type] || 'Controller state changed.';
}

function formatTime(value){
  if(Array.isArray(value)){
    const parts = value.slice(0, 6).map(part => String(part).padStart(2, '0'));
    return parts[3] + ':' + parts[4] + ':' + parts[5];
  }
  return value || '';
}

function escapeHtml(value){
  return String(value ?? 'N/A').replace(/[&<>"']/g, character => ({
    '&':'&amp;',
    '<':'&lt;',
    '>':'&gt;',
    '"':'&quot;',
    "'":'&#39;'
  }[character]));
}

document.querySelector('#refreshButton').addEventListener('click', refresh);
document.querySelectorAll('[data-command]').forEach(button => {
  button.addEventListener('click', () => sendCommand(button.dataset.command));
});
hostInput.addEventListener('change', refresh);
portInput.addEventListener('change', refresh);
setInterval(() => {
  uptimeValue.textContent = elapsedSinceLoad();
}, 1000);
refresh();
</script>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description="Host the Seed Safe dashboard on this computer.")
    parser.add_argument("--host", default="127.0.0.1", help="Dashboard bind address")
    parser.add_argument("--port", type=int, default=8080, help="Dashboard HTTP port")
    parser.add_argument("--pico-host", default=DEFAULT_PICO_HOST, help="Default Pico IP address")
    parser.add_argument("--pico-port", type=int, default=DEFAULT_PICO_PORT, help="Default Pico command port")
    args = parser.parse_args()

    DashboardHandler.default_pico_host = args.pico_host
    DashboardHandler.default_pico_port = args.pico_port

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    url = "http://{}:{}".format(args.host, args.port)
    print("Seed Safe dashboard running at {}".format(url))
    print("Default Pico target is {}:{}".format(args.pico_host, args.pico_port))
    server.serve_forever()


if __name__ == "__main__":
    main()
