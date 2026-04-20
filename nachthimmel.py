#!/usr/bin/env python3
"""
Nachthimmel Coburg — E-Ink Display
Waveshare 2.13" V4, Pi Zero 2W
"""
import sys, os, math, time, logging, requests, calendar, json
from datetime import datetime
import ephem
from PIL import Image, ImageDraw, ImageFont
import qrcode

libdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

# --- Konfiguration ---
LAT      = "50.2611"
LON      = "10.9639"
PI_IP    = "192.168.178.75"
WEBUI_PORT = 5001
# Korrekter NOAA Endpunkt: 3h-Intervalle, letzten 30 Tage
KP_URL   = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
DWD_URL  = "https://www.dwd.de/DWD/warnungen/warnapp/json/warnings.json"
KP_COBURG_THRESHOLD = 6

CONFIG_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'config.json')

def _load_config():
    global LAT, LON
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
            if "lat" in cfg: LAT = str(cfg["lat"])
            if "lon" in cfg: LON = str(cfg["lon"])
        except Exception:
            pass

_load_config()

FONT_BOLD   = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_NORMAL = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
W, H = 250, 122


def get_font(bold=False, size=12):
    path = FONT_BOLD if bold else FONT_NORMAL
    try:    return ImageFont.truetype(path, size)
    except: return ImageFont.load_default()


def utc_to_local(dt_utc):
    """ephem gibt UTC zurück — in lokale Zeit umrechnen"""
    ts = calendar.timegm(dt_utc.timetuple())
    return datetime.fromtimestamp(ts)


# ── Astronomie ───────────────────────────────────────────────

def get_sky_data():
    obs = ephem.Observer()
    obs.lat = LAT
    obs.lon = LON
    obs.elevation = 297
    obs.pressure  = 0
    obs.date = ephem.now()

    moon = ephem.Moon(obs)
    moon_phase = round(moon.phase)

    sun = ephem.Sun(obs)

    # Astro-Dämmerung (-18°)
    obs.horizon = '-18'
    try:
        astro_set_local  = utc_to_local(ephem.Date(obs.next_setting(sun, use_center=True)).datetime())
        astro_rise_local = utc_to_local(ephem.Date(obs.next_rising(sun,  use_center=True)).datetime())
        astro_set_str    = astro_set_local.strftime("%H:%M")
        astro_rise_str   = astro_rise_local.strftime("%H:%M")
    except Exception:
        astro_set_str = astro_rise_str = "--:--"

    obs.horizon = '0'
    obs.date = ephem.now()
    sun2 = ephem.Sun(obs)
    sun2.compute(obs)
    is_night = float(sun2.alt) < math.radians(-18)
    mw_visible = moon_phase < 50 and is_night

    # Mondauf/-untergang im 24h-Format
    moon_set_next_day = False
    try:
        moon_rise_local = utc_to_local(ephem.Date(obs.next_rising(moon)).datetime())
        moon_set_local  = utc_to_local(ephem.Date(obs.next_setting(moon)).datetime())
        moon_set_next_day = moon_set_local.date() > moon_rise_local.date()
        moon_rise_str   = moon_rise_local.strftime("%H:%M")
        moon_set_str    = moon_set_local.strftime("%H:%M")
    except Exception:
        moon_rise_str = moon_set_str = "--:--"

    return {
        "moon_phase":        moon_phase,
        "mw_visible":        mw_visible,
        "is_night":          is_night,
        "astro_dark_start":  astro_set_str,
        "astro_dark_end":    astro_rise_str,
        "moon_rise":         moon_rise_str,
        "moon_set":          moon_set_str,
        "moon_set_next_day": moon_set_next_day,
    }


# ── KP-Index ─────────────────────────────────────────────────

def get_kp_data():
    """
    noaa-planetary-k-index.json Format:
    [ ["time_tag", "Kp", ...], ["2026-04-20 00:00:00", "1.33", ...], ... ]
    Erste Zeile = Header, Rest = Daten
    """
    try:
        r = requests.get(KP_URL, timeout=10,
            headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        data = r.json()
        # Erste Zeile überspringen (Header)
        rows = [row for row in data[1:] if row[1] not in (None, "")]
        if not rows:
            return {"kp": None, "history": [], "status": "no_data"}
        kp_now = float(rows[-1][1])
        history = [(row[0], float(row[1])) for row in rows[-16:]]  # letzte 48h (16 × 3h)
        return {"kp": kp_now, "history": history, "status": "ok"}
    except Exception as e:
        logging.warning(f"KP-Fehler: {e}")
        return {"kp": None, "history": [], "status": "error"}


# ── DWD Warnungen ────────────────────────────────────────────

def get_dwd_warnings():
    try:
        r = requests.get(DWD_URL, timeout=10,
            headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        import json
        text = r.text
        if text.startswith("warnWetter.loadWarnings("):
            text = text[len("warnWetter.loadWarnings("):-2]
        data  = json.loads(text)
        warns = data.get("warnings", {}).get("907463000", [])
        result = [{"event": w.get("event",""), "description": w.get("description","")[:120]}
                  for w in warns[:2]]
        return result, "ok"
    except Exception as e:
        logging.warning(f"DWD-Fehler: {e}")
        return [], "error"


# ── QR-Code ──────────────────────────────────────────────────

def make_qr(url, size=52):
    qr = qrcode.QRCode(version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=2, border=1)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("1")
    return img.resize((size, size))


# ── E-Ink rendern ────────────────────────────────────────────

def render(sky, kp_data, warnings, dwd_status):
    img  = Image.new('1', (W, H), 255)
    draw = ImageDraw.Draw(img)

    kp     = kp_data.get("kp")
    kp_ok  = kp_data.get("status") == "ok"
    now    = datetime.now().strftime("%H:%M")

    # Header
    draw.rectangle([(0,0),(W,16)], fill=0)
    draw.text((5,2),   "NACHTHIMMEL COBURG", font=get_font(False,9), fill=255)
    draw.text((205,2), now,                  font=get_font(False,9), fill=255)

    y = 20

    # Milchstraße
    mw_str = "SICHTBAR" if sky["mw_visible"] else "nicht heute"
    draw.text((5,y),  "Milchstr.", font=get_font(False,9), fill=0)
    draw.text((62,y), mw_str,      font=get_font(True,9),  fill=0)
    y += 13

    # Mond
    draw.text((5,y),  "Mond",    font=get_font(False,9), fill=0)
    draw.text((62,y), f"{sky['moon_phase']}%  {sky['moon_rise']}", font=get_font(True,9), fill=0)
    y += 13

    # Dunkel-Fenster
    draw.text((5,y),  "Dunkel", font=get_font(False,9), fill=0)
    draw.text((62,y), f"{sky['astro_dark_start']}-{sky['astro_dark_end']}", font=get_font(True,9), fill=0)
    y += 15

    # KP-Index
    kp_str = f"{kp:.1f}" if kp is not None else "—"
    draw.text((5,y),  "KP-Index", font=get_font(False,9),  fill=0)
    draw.text((62,y), kp_str,     font=get_font(True,13),  fill=0)
    y += 16

    # KP-Balken
    if kp is not None:
        bar_w = int((kp / 9) * 100)
        draw.rectangle([(5,y),(105,y+5)], outline=0)
        if bar_w > 0:
            draw.rectangle([(5,y),(5+bar_w,y+5)], fill=0)
        marker_x = 5 + int((KP_COBURG_THRESHOLD / 9) * 100)
        draw.line([(marker_x,y-2),(marker_x,y+7)], fill=0)
    y += 9

    # Nordlicht / Status
    if kp is not None:
        if kp >= KP_COBURG_THRESHOLD:
            draw.text((5,y), "!! NORDLICHT MOEGLICH", font=get_font(True,9), fill=0)
        else:
            draw.text((5,y), f"KP {KP_COBURG_THRESHOLD} noetig (+{KP_COBURG_THRESHOLD-kp:.1f})", font=get_font(False,9), fill=0)
    else:
        draw.text((5,y), "KP: keine Verbindung", font=get_font(False,9), fill=0)
    y += 11

    # Service-Indikatoren
    kp_dot  = "+" if kp_ok else "!"
    dwd_dot = "+" if dwd_status == "ok" else "!"
    draw.text((5,y), f"NOAA:{kp_dot} DWD:{dwd_dot}", font=get_font(False,8), fill=0)

    # Trennlinie + QR
    draw.line([(152,17),(152,H-13)], fill=0)

    try:
        qr_img = make_qr(f"http://{PI_IP}:{WEBUI_PORT}")
        img.paste(qr_img, (157, 19))
    except Exception as e:
        logging.warning(f"QR: {e}")

    draw.text((157,74), "Web-UI", font=get_font(False,8), fill=0)
    draw.text((157,84), f":{WEBUI_PORT}",  font=get_font(False,8), fill=0)

    # Footer
    draw.line([(0,H-13),(W,H-13)], fill=0)
    draw.text((5,H-11), f"aktualisiert {now}  noaa.gov+dwd.de", font=get_font(False,8), fill=0)

    return img


def update_display(img):
    try:
        from waveshare_epd import epd2in13_V4
        epd = epd2in13_V4.EPD()
        epd.init()
        epd.Clear(0xFF)
        epd.display(epd.getbuffer(img))
        epd.sleep()
        logging.info("Display aktualisiert.")
    except ImportError:
        img.save("/tmp/nachthimmel_preview.png")
        logging.info("Preview: /tmp/nachthimmel_preview.png")
    except Exception as e:
        img.save("/tmp/nachthimmel_preview.png")
        logging.error(f"Display-Fehler: {e}")


def main():
    logging.info("Nachthimmel Coburg startet...")
    sky              = get_sky_data()
    kp_data          = get_kp_data()
    warnings, dwd_st = get_dwd_warnings()

    logging.info(f"Milchstraße: {'sichtbar' if sky['mw_visible'] else 'nicht sichtbar'}")
    logging.info(f"Mond: {sky['moon_phase']}%  auf: {sky['moon_rise']}  unter: {sky['moon_set']}")
    logging.info(f"Dunkel: {sky['astro_dark_start']} – {sky['astro_dark_end']}")
    logging.info(f"KP: {kp_data.get('kp')}  Status: {kp_data.get('status')}")
    logging.info(f"DWD: {dwd_st}  Warnungen: {len(warnings)}")

    img = render(sky, kp_data, warnings, dwd_st)
    update_display(img)


if __name__ == "__main__":
    main()
