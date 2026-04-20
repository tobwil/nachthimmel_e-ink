#!/usr/bin/env python3
"""
Nachthimmel Coburg — Web-UI mit Karte, KP-Chart, Status-Indikatoren
"""
import sys, os, json, logging, time
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import nachthimmel as _nm
from nachthimmel import (get_sky_data, get_kp_data, get_dwd_warnings,
                          KP_COBURG_THRESHOLD, PI_IP, WEBUI_PORT)

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

_cache = {}
_cache_ts = 0
CACHE_TTL = 300

def get_all_data():
    global _cache, _cache_ts
    if time.time() - _cache_ts < CACHE_TTL and _cache:
        return _cache
    warnings, dwd_status = get_dwd_warnings()
    kp_data = get_kp_data()
    _cache = {
        "sky":        get_sky_data(),
        "kp":         kp_data,
        "warnings":   warnings,
        "dwd_status": dwd_status,
        "updated":    datetime.now().strftime("%H:%M:%S"),
    }
    _cache_ts = time.time()
    return _cache


HTML = '''<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="300">
<title>Nachthimmel Coburg</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=Syne:wght@400;600;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
:root {
  --bg:#0a0d14; --surface:#111520; --border:#1e2535;
  --text:#c8d4e8; --muted:#4a5568; --accent:#4fc3f7;
  --green:#69f0ae; --amber:#ffb74d; --red:#ef5350; --purple:#ce93d8;
}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:'DM Mono',monospace;
  font-size:14px;min-height:100vh;padding:20px 14px;}
body::before{content:'';position:fixed;inset:0;pointer-events:none;z-index:0;
  background-image:
    radial-gradient(1px 1px at 15% 20%,rgba(255,255,255,.5) 0%,transparent 100%),
    radial-gradient(1px 1px at 70% 10%,rgba(255,255,255,.4) 0%,transparent 100%),
    radial-gradient(1px 1px at 45% 60%,rgba(255,255,255,.3) 0%,transparent 100%),
    radial-gradient(1.5px 1.5px at 85% 40%,rgba(255,255,255,.5) 0%,transparent 100%),
    radial-gradient(1px 1px at 30% 85%,rgba(255,255,255,.3) 0%,transparent 100%),
    radial-gradient(1px 1px at 90% 75%,rgba(255,255,255,.4) 0%,transparent 100%);}
.container{max-width:640px;margin:0 auto;position:relative;z-index:1;}
header{margin-bottom:24px;}
.loc{font-family:'Syne',sans-serif;font-size:11px;font-weight:600;
  letter-spacing:.15em;text-transform:uppercase;color:var(--muted);margin-bottom:6px;}
h1{font-family:'Syne',sans-serif;font-size:26px;font-weight:800;
  color:#fff;letter-spacing:-.02em;}
h1 span{color:var(--accent);}
.updated{font-size:11px;color:var(--muted);margin-top:4px;}

/* Status-Bar */
.status-bar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px;}
.status-dot{display:flex;align-items:center;gap:6px;font-size:11px;
  padding:4px 10px;border-radius:99px;border:1px solid;}
.dot-ok  {background:rgba(105,240,174,.1);border-color:rgba(105,240,174,.3);color:var(--green);}
.dot-err {background:rgba(239,83,80,.1); border-color:rgba(239,83,80,.3); color:var(--red);}
.dot-ico{width:6px;height:6px;border-radius:50%;flex-shrink:0;}
.ok-ico {background:var(--green);}
.err-ico{background:var(--red);}

.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px;}
@media(max-width:480px){.grid{grid-template-columns:1fr;}}
.card{background:var(--surface);border:1px solid var(--border);
  border-radius:12px;padding:16px 18px;}
.card-label{font-size:10px;letter-spacing:.1em;text-transform:uppercase;
  color:var(--muted);margin-bottom:8px;}
.card-value{font-family:'Syne',sans-serif;font-size:28px;font-weight:800;
  color:#fff;line-height:1;margin-bottom:4px;}
.card-sub{font-size:11px;color:var(--muted);}
.pill{display:inline-block;padding:3px 10px;border-radius:99px;
  font-size:11px;margin-top:6px;border:1px solid;}
.green{background:rgba(105,240,174,.1);color:var(--green);border-color:rgba(105,240,174,.3);}
.amber{background:rgba(255,183,77,.1); color:var(--amber);border-color:rgba(255,183,77,.3);}
.red  {background:rgba(239,83,80,.1);  color:var(--red);  border-color:rgba(239,83,80,.3);}
.blue {background:rgba(79,195,247,.1); color:var(--accent);border-color:rgba(79,195,247,.3);}
.moon-icon{font-size:44px;line-height:1;margin:6px 0;}

/* KP Chart */
.kp-bar-wrap{background:var(--border);border-radius:4px;height:8px;
  margin:12px 0 5px;position:relative;}
.kp-bar-fill{height:8px;border-radius:4px;}
.kp-threshold{position:absolute;top:-4px;bottom:-4px;width:2px;
  background:var(--amber);border-radius:1px;}
.kp-scale{display:flex;justify-content:space-between;font-size:10px;color:var(--muted);}
.chart{display:flex;align-items:flex-end;gap:3px;height:60px;margin-top:12px;}
.bar{flex:1;min-width:5px;border-radius:2px 2px 0 0;}
.chart-labels{display:flex;justify-content:space-between;
  font-size:9px;color:var(--muted);margin-top:3px;}

/* Zeitfenster */
.time-row{display:flex;justify-content:space-between;
  padding:7px 0;border-bottom:1px solid var(--border);}
.time-row:last-child{border-bottom:none;}
.tl{color:var(--muted);font-size:12px;}
.tv{font-weight:500;font-size:13px;}

/* Karte */
#map{height:220px;border-radius:10px;margin-bottom:10px;
  border:1px solid var(--border);overflow:hidden;}

/* Warnungen */
.warn{background:rgba(239,83,80,.07);border:1px solid rgba(239,83,80,.2);
  border-radius:8px;padding:10px 12px;margin-bottom:8px;}
.warn-ev{color:var(--red);font-weight:500;font-size:12px;margin-bottom:3px;}
.warn-ds{font-size:11px;color:var(--muted);}
.no-warn{color:var(--green);font-size:12px;}

footer{text-align:center;color:var(--muted);font-size:11px;
  margin-top:24px;padding-top:14px;border-top:1px solid var(--border);}
</style>
</head>
<body>
<div class="container">

<header>
  <div class="loc">&#9679; Coburg · 50.26°N · 10.96°E · 7W3C+63</div>
  <h1>Nachthimmel <span>Coburg</span></h1>
  <div class="updated">Aktualisiert {{ d.updated }} · alle 5 Min</div>
</header>

<!-- Status-Indikatoren -->
<div class="status-bar">
  <div class="status-dot {{ 'dot-ok' if d.kp.status == 'ok' else 'dot-err' }}">
    <div class="dot-ico {{ 'ok-ico' if d.kp.status == 'ok' else 'err-ico' }}"></div>
    NOAA KP-Index
  </div>
  <div class="status-dot {{ 'dot-ok' if d.dwd_status == 'ok' else 'dot-err' }}">
    <div class="dot-ico {{ 'ok-ico' if d.dwd_status == 'ok' else 'err-ico' }}"></div>
    DWD Warnungen
  </div>
  <div class="status-dot dot-ok">
    <div class="dot-ico ok-ico"></div>
    Astronomie (offline)
  </div>
</div>

<!-- Milchstraße + Mond -->
<div class="grid">
  <div class="card">
    <div class="card-label">Milchstraße</div>
    {% if d.sky.mw_visible %}
      <div class="card-value" style="color:var(--green)">Sichtbar</div>
      <div class="card-sub">Dunkel &amp; Mond {{ d.sky.moon_phase }}%</div>
      <span class="pill green">Gute Bedingungen</span>
    {% elif not d.sky.is_night %}
      <div class="card-value" style="color:var(--muted)">Tagsüber</div>
      <div class="card-sub">Dunkel ab {{ d.sky.astro_dark_start }}</div>
      <span class="pill amber">Noch hell</span>
    {% else %}
      <div class="card-value" style="color:var(--amber)">Reduziert</div>
      <div class="card-sub">Mond {{ d.sky.moon_phase }}% beleuchtet</div>
      <span class="pill amber">Mondlicht stört</span>
    {% endif %}
  </div>
  <div class="card">
    <div class="card-label">Mond</div>
    <div class="moon-icon">
      {% set p = d.sky.moon_phase %}
      {% if p < 6 %}🌑{% elif p < 25 %}🌒{% elif p < 45 %}🌓
      {% elif p < 55 %}🌔{% elif p < 75 %}🌕{% elif p < 90 %}🌖
      {% elif p < 97 %}🌗{% else %}🌘{% endif %}
    </div>
    <div class="card-value" style="font-size:20px">{{ d.sky.moon_phase }}%</div>
    <div class="card-sub">
      ↑ {{ d.sky.moon_rise }} &nbsp;↓ {{ d.sky.moon_set }}{% if d.sky.moon_set_next_day %}<span style="font-size:9px;opacity:.6"> +1</span>{% endif %}
    </div>
  </div>
</div>

<!-- KP-Index -->
<div class="card" style="margin-bottom:10px">
  <div class="card-label">KP-Index · Geomagnetische Aktivität (NOAA)</div>
  <div style="display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;">
    <div class="card-value" style="font-size:38px">
      {% if d.kp.kp is not none %}{{ "%.1f"|format(d.kp.kp) }}{% else %}—{% endif %}
    </div>
    {% if d.kp.kp is not none %}
      {% if d.kp.kp >= 6 %}<span class="pill green">Nordlicht möglich!</span>
      {% elif d.kp.kp >= 5 %}<span class="pill amber">Knapp unter Schwelle</span>
      {% elif d.kp.kp >= 4 %}<span class="pill blue">Erhöhte Aktivität</span>
      {% else %}<span class="pill blue">Ruhig</span>{% endif %}
    {% endif %}
  </div>
  {% if d.kp.kp is not none %}
  <div class="kp-bar-wrap">
    <div class="kp-bar-fill" style="width:{{ (d.kp.kp/9*100)|int }}%;
      background:{% if d.kp.kp >= 6 %}var(--green){% elif d.kp.kp >= 4 %}var(--amber){% else %}var(--accent){% endif %}">
    </div>
    <div class="kp-threshold" style="left:{{ (threshold/9*100)|int }}%"></div>
  </div>
  <div class="kp-scale"><span>0</span><span>3</span><span>Coburg ↑</span><span>9</span></div>
  {% endif %}
  {% if d.kp.history %}
  <div class="chart">
    {% for ts, val in d.kp.history %}
    <div class="bar" style="height:{{ [((val/9)*100)|int, 4]|max }}%;
      background:{% if val >= 6 %}var(--green){% elif val >= 4 %}var(--amber){% else %}var(--accent){% endif %};
      opacity:{% if loop.index < (loop.length * 0.6)|int %}0.35{% else %}0.85{% endif %}">
    </div>
    {% endfor %}
  </div>
  <div class="chart-labels"><span>älter</span><span>jetzt</span></div>
  {% endif %}
</div>

<!-- Beobachtungsfenster -->
<div class="card" style="margin-bottom:10px">
  <div class="card-label">Beobachtungsfenster heute · Coburg</div>
  <div class="time-row"><span class="tl">Astronomische Dämmerung</span><span class="tv">{{ d.sky.astro_dark_start }}</span></div>
  <div class="time-row"><span class="tl">Astronomischer Morgen</span><span class="tv">{{ d.sky.astro_dark_end }}</span></div>
  <div class="time-row"><span class="tl">Mondaufgang</span><span class="tv">{{ d.sky.moon_rise }}</span></div>
  <div class="time-row"><span class="tl">Monduntergang</span><span class="tv">{{ d.sky.moon_set }}{% if d.sky.moon_set_next_day %} <span style="font-size:10px;opacity:.55">+1 Tag</span>{% endif %}</span></div>
  <div class="time-row"><span class="tl">KP-Schwelle Coburg</span><span class="tv">KP {{ threshold }}+</span></div>
</div>

<!-- OpenStreetMap -->
<div class="card" style="margin-bottom:10px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
    <div class="card-label" style="margin-bottom:0">Standort · {{ "%.4f"|format(cur_lat) }}°N · {{ "%.4f"|format(cur_lon) }}°E</div>
    <button id="pick-btn" onclick="togglePickMode()"
      style="font-size:11px;padding:4px 10px;background:var(--surface);border:1px solid var(--border);
             color:var(--text);border-radius:99px;cursor:pointer;white-space:nowrap;">
      Standort ändern
    </button>
  </div>
  <div id="pick-info" style="display:none;align-items:center;gap:8px;font-size:11px;
       color:var(--accent);margin-bottom:8px;flex-wrap:wrap;">
    <span>Auf Karte klicken →</span>
    <span id="new-coords" style="font-weight:500">–</span>
    <button id="save-btn" onclick="saveLocation()"
      style="display:none;font-size:11px;padding:3px 10px;background:var(--green);
             color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:600;">
      Übernehmen
    </button>
  </div>
  <div id="map"></div>
  <div style="font-size:10px;color:var(--muted);margin-top:6px">
    Dunkelste Beobachtungsgebiete: Frankenwald (N), Hassberge (SW)
  </div>
</div>

<!-- DWD Warnungen -->
<div class="card" style="margin-bottom:10px">
  <div class="card-label">DWD Wetterwarnungen · Landkreis Coburg</div>
  {% if d.warnings %}
    {% for w in d.warnings %}
    <div class="warn">
      <div class="warn-ev">{{ w.event }}</div>
      <div class="warn-ds">{{ w.description }}</div>
    </div>
    {% endfor %}
  {% else %}
    <div class="no-warn">✓ Keine aktiven Warnungen</div>
  {% endif %}
</div>

<footer>
  NOAA SWPC · Deutscher Wetterdienst · ephem (offline Astronomie)<br>
  Pi Zero 2W · Coburg · 7W3C+63 · 50.2611°N 10.9639°E
</footer>
</div>

<script>
var curLat = {{ cur_lat }}, curLon = {{ cur_lon }};
var pickMode = false, newLat = null, newLon = null;

var map = L.map('map', {zoomControl:true, scrollWheelZoom:false})
  .setView([curLat, curLon], 10);

L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
  attribution:'&copy; OpenStreetMap &copy; CARTO', maxZoom:18
}).addTo(map);

var icon = L.divIcon({
  html: '<div style="width:12px;height:12px;background:#4fc3f7;border-radius:50%;'
      + 'border:2px solid #fff;box-shadow:0 0 8px #4fc3f7"></div>',
  iconSize:[12,12], iconAnchor:[6,6], className:''
});
var marker = L.marker([curLat, curLon], {icon:icon})
  .addTo(map)
  .bindPopup('<b>Standort</b><br>' + curLat.toFixed(4) + '°N · ' + curLon.toFixed(4) + '°E')
  .openPopup();

L.circle([curLat, curLon], {
  radius:50000, color:'#4fc3f7', fillColor:'#4fc3f7',
  fillOpacity:0.05, weight:1, dashArray:'4 4'
}).addTo(map);

function togglePickMode() {
  pickMode = !pickMode;
  document.getElementById('pick-btn').textContent = pickMode ? '✕ Abbrechen' : 'Standort ändern';
  document.getElementById('pick-info').style.display = pickMode ? 'flex' : 'none';
  document.getElementById('save-btn').style.display = 'none';
  document.getElementById('new-coords').textContent = '–';
  newLat = null; newLon = null;
}

map.on('click', function(e) {
  if (!pickMode) return;
  newLat = e.latlng.lat; newLon = e.latlng.lng;
  marker.setLatLng(e.latlng);
  marker.setPopupContent('<b>Neuer Standort</b><br>'
    + newLat.toFixed(4) + '°N · ' + newLon.toFixed(4) + '°E').openPopup();
  document.getElementById('new-coords').textContent =
    newLat.toFixed(4) + '°N, ' + newLon.toFixed(4) + '°E';
  document.getElementById('save-btn').style.display = 'inline-block';
});

function saveLocation() {
  if (newLat === null) return;
  fetch('/api/location', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({lat: newLat, lon: newLon})
  }).then(r => r.json()).then(d => {
    if (d.ok) location.reload();
    else alert('Fehler beim Speichern');
  }).catch(e => alert('Netzwerkfehler: ' + e));
}
</script>
</body>
</html>'''


@app.route("/")
def index():
    d = get_all_data()
    return render_template_string(HTML, d=d, threshold=KP_COBURG_THRESHOLD,
                                   cur_lat=float(_nm.LAT), cur_lon=float(_nm.LON))


@app.route("/api")
def api():
    return json.dumps(get_all_data(), default=str), 200, {'Content-Type': 'application/json'}


@app.route("/api/location", methods=["POST"])
def set_location():
    data = request.get_json()
    lat = round(float(data["lat"]), 6)
    lon = round(float(data["lon"]), 6)
    _nm.LAT = str(lat)
    _nm.LON = str(lon)
    with open(_nm.CONFIG_FILE, "w") as f:
        json.dump({"lat": lat, "lon": lon}, f)
    global _cache_ts
    _cache_ts = 0
    return jsonify({"ok": True, "lat": lat, "lon": lon})


if __name__ == "__main__":
    logging.info(f"Web-UI auf Port {WEBUI_PORT}...")
    app.run(host="0.0.0.0", port=WEBUI_PORT, debug=False)
