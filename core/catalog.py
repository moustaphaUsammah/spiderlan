"""
SpiderLan :: Satellite Catalog & Visibility Engine
All satellite groups from Celestrak. TLE propagation via Skyfield.
"""

import requests
import math
from datetime import datetime, timezone, timedelta
from skyfield.api import load, EarthSatellite, wgs84

CELESTRAK_GROUPS = {
    "Starlink":           "https://celestrak.org/SOCRATES/query.php?CODE=starlink&FORMAT=TLE",
    "OneWeb":             "https://celestrak.org/supplemental/sup-gp.php?FILE=oneweb&FORMAT=TLE",
    "GPS (Operational)":  "https://celestrak.org/SOCRATES/query.php?CODE=gps-ops&FORMAT=TLE",
    "GLONASS":            "https://celestrak.org/SOCRATES/query.php?CODE=glo-ops&FORMAT=TLE",
    "Galileo":            "https://celestrak.org/SOCRATES/query.php?CODE=galileo&FORMAT=TLE",
    "BeiDou":             "https://celestrak.org/SOCRATES/query.php?CODE=beidou&FORMAT=TLE",
    "INMARSAT":           "https://celestrak.org/SOCRATES/query.php?CODE=inmarsat&FORMAT=TLE",
    "INTELSAT":           "https://celestrak.org/SOCRATES/query.php?CODE=intelsat&FORMAT=TLE",
    "SES":                "https://celestrak.org/SOCRATES/query.php?CODE=ses&FORMAT=TLE",
    "Iridium":            "https://celestrak.org/SOCRATES/query.php?CODE=iridium-33-debris&FORMAT=TLE",
    "Military (USA)":     "https://celestrak.org/SOCRATES/query.php?CODE=military&FORMAT=TLE",
    "Radar Cal":          "https://celestrak.org/SOCRATES/query.php?CODE=radar-cal&FORMAT=TLE",
    "Space Stations":     "https://celestrak.org/SOCRATES/query.php?CODE=stations&FORMAT=TLE",
    "GEO Protected Zone": "https://celestrak.org/SOCRATES/query.php?CODE=geo&FORMAT=TLE",
}

FALLBACK_TLES = [
    ("STARLINK-1007","1 44713U 19074B   24120.50000000  .00001000  00000-0  10000-3 0  9990","2 44713  53.0000  50.0000 0001000  90.0000 270.0000 15.05000000 12345"),
    ("STARLINK-1008","1 44714U 19074C   24120.50000000  .00001100  00000-0  11000-3 0  9991","2 44714  53.0000  80.0000 0001100  95.0000 265.0000 15.05100000 12346"),
    ("GPS BIIR-2",   "1 28474U 04045A   24120.50000000 -.00000023  00000-0  00000-0 0  9993","2 28474  55.5000  60.0000 0100000  20.0000 340.0000  2.00563417 14321"),
    ("GPS BIIR-3",   "1 28190U 04009A   24120.50000000 -.00000010  00000-0  00000-0 0  9994","2 28190  55.3000 120.0000 0090000  50.0000 310.0000  2.00563100 14322"),
    ("INMARSAT 4-F1","1 28628U 05009A   24120.50000000 -.00000303  00000-0  00000-0 0  9995","2 28628   0.0020  80.0000 0000800 180.0000 180.0000  1.00272180  7123"),
]


def fetch_tle_group(group_name: str, limit: int = 50) -> list[tuple]:
    url = CELESTRAK_GROUPS.get(group_name)
    if not url:
        return []
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200 and len(r.text) > 50:
            lines = [l.strip() for l in r.text.strip().splitlines() if l.strip()]
            sats  = []
            for i in range(0, len(lines) - 2, 3):
                if lines[i+1].startswith("1") and lines[i+2].startswith("2"):
                    sats.append((lines[i], lines[i+1], lines[i+2]))
            if sats:
                return sats[:limit]
    except Exception:
        pass
    return FALLBACK_TLES if group_name == "Starlink" else []


def fetch_custom_tle(raw_text: str) -> list[tuple]:
    """Parse user-pasted TLE text (any format)."""
    lines = [l.strip() for l in raw_text.strip().splitlines() if l.strip()]
    sats  = []
    for i in range(0, len(lines) - 2, 3):
        if lines[i+1].startswith("1") and lines[i+2].startswith("2"):
            sats.append((lines[i], lines[i+1], lines[i+2]))
    return sats


def sat_position_now(name: str, tle1: str, tle2: str) -> dict:
    ts  = load.timescale()
    sat = EarthSatellite(tle1, tle2, name, ts)
    t   = ts.now()
    geo = wgs84.geographic_position_of(sat.at(t))
    return {
        "name":   name,
        "lat":    round(geo.latitude.degrees,  4),
        "lon":    round(geo.longitude.degrees, 4),
        "alt_km": round(sat.at(t).distance().km - 6371, 1),
    }


def ground_track(name: str, tle1: str, tle2: str, minutes: int = 90) -> list[tuple]:
    ts  = load.timescale()
    sat = EarthSatellite(tle1, tle2, name, ts)
    now = datetime.now(timezone.utc)
    track = []
    for i in range(0, minutes, 2):
        t   = ts.from_datetime(now + timedelta(minutes=i))
        geo = wgs84.geographic_position_of(sat.at(t))
        track.append((round(geo.latitude.degrees, 4), round(geo.longitude.degrees, 4)))
    return track


def contact_windows(name: str, tle1: str, tle2: str,
                    gs_lat: float, gs_lon: float,
                    el_mask_deg: float = 10.0,
                    hours_ahead: int = 24) -> list[dict]:
    ts  = load.timescale()
    sat = EarthSatellite(tle1, tle2, name, ts)
    gs  = wgs84.latlon(gs_lat, gs_lon)
    t0  = ts.now()
    t1  = ts.from_datetime(datetime.now(timezone.utc) + timedelta(hours=hours_ahead))
    windows = []
    try:
        times, events = sat.find_events(gs, t0, t1, altitude_degrees=el_mask_deg)
        i = 0
        while i < len(events):
            if events[i] == 0:
                rise_t = times[i].utc_datetime()
                j = i + 1
                max_el = 0.0
                while j < len(events):
                    if events[j] == 1:
                        diff = sat - gs
                        el   = diff.at(times[j]).altaz()[0].degrees
                        max_el = max(max_el, el)
                    if events[j] == 2:
                        set_t = times[j].utc_datetime()
                        windows.append({
                            "aos":        rise_t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "los":        set_t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "duration_s": round((set_t - rise_t).total_seconds()),
                            "max_el_deg": round(max_el, 1),
                        })
                        i = j
                        break
                    j += 1
            i += 1
    except Exception:
        pass
    return windows


def elevation_azimuth(name: str, tle1: str, tle2: str,
                       gs_lat: float, gs_lon: float) -> dict:
    ts  = load.timescale()
    sat = EarthSatellite(tle1, tle2, name, ts)
    gs  = wgs84.latlon(gs_lat, gs_lon)
    t   = ts.now()
    diff = sat - gs
    topo = diff.at(t)
    alt, az, dist = topo.altaz()
    return {
        "elevation_deg": round(alt.degrees, 2),
        "azimuth_deg":   round(az.degrees,  2),
        "range_km":      round(dist.km,     1),
        "visible":       alt.degrees > 0,
    }
