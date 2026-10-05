"""Guardia comun anti-duplicados para los motores de Instagram (Victor, 5-oct-2026).

WHY: del 1 al 5 de octubre de 2026 OTRO ordenador con copias de los motores (commits
con zona horaria +0100/+0200 en los repos *-social) publico de nuevo el post de dos
dias antes en @agolfcars, @manzanosenterprises, @manzanoshabitat, @manzanosmobility y
@electricidadjmc. Cada maquina tiene su propio .daily_state.json, asi que la otra no
sabia que este Mac ya lo habia publicado. Dos redes, independientes del estado local:

1. host_ok(): solo publica el Mac cuyo IOPlatformUUID esta en ~/.ig_publisher_host
   (fichero FUERA del repo, asi no viaja por git). Fail-closed: sin fichero, no publica.
2. feed_block(): lee el feed REAL (fuente de verdad compartida por todas las maquinas)
   y bloquea si la cuenta ya publico un post hoy (fecha local) o si el cuerpo del
   caption ya esta entre los ultimos FEED_LOOKBACK posts. Fail-open si la API no
   responde: la red 1 sigue protegiendo.
"""
import os, re, json, subprocess, datetime, urllib.request, urllib.parse

HOST_FILE = os.path.expanduser("~/.ig_publisher_host")
FEED_LOOKBACK = 30   # ~2 meses a 1 post cada 2 dias; repetir texto antes seria un fallo de rotacion

def machine_id():
    try:
        out = subprocess.run(["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                             capture_output=True, text=True, timeout=10).stdout
        m = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', out)
        return m.group(1) if m else None
    except Exception:
        return None

def host_ok():
    """(ok, motivo). Solo el Mac designado publica."""
    try:
        want = open(HOST_FILE).read().strip()
    except OSError:
        return False, f"falta {HOST_FILE}: este ordenador no es el publicador designado"
    me = machine_id()
    if not me or me != want:
        return False, f"este ordenador ({me}) no es el publicador designado ({want})"
    return True, "ok"

def body(cap):
    """Caption sin lineas de solo hashtags ni la linea de cumplimiento (estable)."""
    keep = []
    for ln in (cap or "").split("\n"):
        t = ln.split()
        if t and all(x.startswith("#") for x in t):
            continue
        keep.append(ln.strip())
    return re.sub(r"\s+", " ", " ".join(keep)).strip().lower()

def recent_feed(igid, token, base="https://graph.instagram.com/v21.0", limit=FEED_LOOKBACK):
    """[(datetime_local, body)] de los ultimos posts del feed, o None si falla la API."""
    q = urllib.parse.urlencode({"fields": "caption,timestamp", "limit": str(limit), "access_token": token})
    try:
        with urllib.request.urlopen(f"{base}/{igid}/media?{q}", timeout=30) as r:
            data = json.load(r).get("data")
    except Exception as e:
        print(f"ig_guard: no pude leer el feed ({type(e).__name__}); sigo solo con el bloqueo de host")
        return None
    out = []
    for m in data or []:
        try:
            ts = datetime.datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z").astimezone()
        except Exception:
            continue
        out.append((ts, body(m.get("caption"))))
    return out

def feed_block(igid, token, caption, base="https://graph.instagram.com/v21.0", check_today=True):
    """Motivo (str) si NO hay que publicar, o None. caption=None solo mira 'ya hay post hoy'."""
    feed = recent_feed(igid, token, base)
    if feed is None:
        return None
    today = datetime.date.today()
    if check_today:
        for ts, _ in feed:
            if ts.date() == today:
                return f"la cuenta ya publico un post hoy ({ts:%H:%M}), desde este u otro ordenador"
    b = body(caption) if caption else ""
    if b:
        for ts, fb in feed:
            if fb and fb == b:
                return f"ese mismo texto ya esta en el feed ({ts:%Y-%m-%d %H:%M})"
    return None
