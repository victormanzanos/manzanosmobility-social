#!/usr/bin/env python3
"""Manzanos Mobility — DAILY ENGINE para @manzanosmobility.

Clonado del motor de @manzanosmobility (mismas defensas: idempotencia local +
server-side, estado persistido justo tras publicar, api() nunca propaga errores
de red) con:
- Credenciales propias (MANZANOSMOBILITY_IG_ACCESS_TOKEN / _ACCOUNT_ID)
- Repo público propio: github.com/victormanzanos/manzanosmobility-social
- Captions parseadas de CAPTIONS.md (single source of truth)
- Cadencia cada 2 días: ordinal%2==1 (ver CYCLE_DIV). Habitat publica pares (%2==0), Palacio
  impares (%2==1), MW %4==0, JMC %4==2 → mobility solo coincide con Palacio
  1 de cada 4 días (cuentas distintas, sin problema).
- Idempotencia (1 publicación/día), jitter, defer aleatorio, foto real opcional
  (drop folder ~/manzanosmobility-social/reales).

Variables de entorno:
  DRY=1     → preview sin publicar ni email (no necesita credenciales)
  FORCE=1   → salta la guardia de "día de descanso"
"""
import datetime, json, os, random, re, ssl, smtplib, subprocess, time
import urllib.request, urllib.parse, urllib.error
import base64, hashlib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage

# ── CONFIG ────────────────────────────────────────────────────────────────
LOCAL    = os.path.expanduser("~/manzanosmobility-social")
SECRETS  = os.path.expanduser("~/Code/CyberSecurity/scripts/secrets.sh")
STATE    = os.path.join(LOCAL, ".daily_state.json")
CAPTIONS_FILE = os.path.join(LOCAL, "CAPTIONS.md")
RAW      = "https://raw.githubusercontent.com/victormanzanos/manzanosmobility-social/main"
BASE     = "https://graph.instagram.com/v23.0"
REPO     = "victormanzanos/manzanosmobility-social"
H        = "#ManzanosMobility"   # brand hashtag — siempre se mantiene

# Cadencia: cada 2 días, en días IMPARES (julian ordinal % 2 == 1).
# WHY impares: Habitat ocupa los pares (%2==0); compartimos día con Palacio
# (también impares) pero en horas distintas (ver com.manzanosmobility.dailyig.plist),
# así que nunca hay dos publicaciones simultáneas desde esta misma IP.
CYCLE_DIV = 2
CYCLE_DAY = 1

# Foto real intercalada — 1 real cada N posts de marca (drop folder ~/manzanosmobility-social/reales)
REAL_EVERY = 3
TDIR     = os.path.join(LOCAL, "reales")
DONE_DIR = os.path.join(TDIR, "published")
IMG_EXT  = (".jpg", ".jpeg", ".png")
DEFAULT_REAL_CAPTION = (
    "Movilidad de lujo, en tierra y en el mar ✨\n"
    "DBoat, alquiler de Porsche y vehículos premium. Más en el link de la bio.\n\n"
    "#ManzanosMobility #DBoat #AlquilerPorsche #LuxuryMobility"
)

DRY = os.environ.get("DRY") == "1"

# Credenciales — lazy load para que DRY=1 funcione sin credenciales
TOK = None
IGID = None
def _secret(n):
    return subprocess.check_output([SECRETS, "get", n]).decode().strip()
def ensure_creds():
    global TOK, IGID
    if TOK is None:
        TOK  = _secret("MANZANOSMOBILITY_IG_ACCESS_TOKEN")
        IGID = _secret("MANZANOSMOBILITY_IG_ACCOUNT_ID")


# ── PARSE CAPTIONS.md → POSTS, STORIES ────────────────────────────────────
def parse_captions(path):
    text = open(path, encoding="utf-8").read()
    sections = re.split(r"^## ", text, flags=re.M)
    posts, stories = [], []
    for sec in sections:
        head = sec.splitlines()[0].strip().upper() if sec.strip() else ""
        if "POSTS" in head and "STOR" not in head:
            target = posts
        elif "STOR" in head:
            target = stories
        else:
            continue
        for entry in re.split(r"^### ", sec, flags=re.M)[1:]:
            lines = entry.splitlines()
            if not lines:
                continue
            m = re.search(r"`([^`]+\.jpg)`", lines[0])
            if not m:
                continue
            filename = m.group(1)
            body = []
            for ln in lines[1:]:
                if ln.startswith("##") or ln.startswith("---"):
                    break
                body.append(ln)
            target.append((filename, "\n".join(body).strip()))
    return posts, stories

POSTS, STORIES = parse_captions(CAPTIONS_FILE)
STORY_FILES = [fn for fn, _ in STORIES]
assert POSTS,   "No se parsearon posts de CAPTIONS.md"
assert STORIES, "No se parsearon stories de CAPTIONS.md"


# ── STATE ─────────────────────────────────────────────────────────────────
def state():
    s = json.load(open(STATE)) if os.path.exists(STATE) else {}
    s.setdefault("post", 0)
    s.setdefault("story", 0)
    s.setdefault("since_real", 0)
    return s
def save_state(s):
    json.dump(s, open(STATE, "w"))


# ── FOTO REAL intercalada (drop folder) ───────────────────────────────────
def real_collect():
    if not os.path.isdir(TDIR):
        return []
    out = []
    for name in sorted(os.listdir(TDIR)):
        path = os.path.join(TDIR, name)
        if not os.path.isfile(path):
            continue
        base, ext = os.path.splitext(name)
        if ext.lower() not in IMG_EXT:
            continue
        cap_file = os.path.join(TDIR, base + ".txt")
        cap = open(cap_file, encoding="utf-8").read().strip() if os.path.exists(cap_file) else DEFAULT_REAL_CAPTION
        out.append((path, cap))
    return out

def gh_upload(local_path, remote_name):
    with open(local_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode()
    remote_path = f"reales/{remote_name}"
    sha = None
    probe = subprocess.run(["gh", "api", f"/repos/{REPO}/contents/{remote_path}"],
                           capture_output=True, text=True)
    if probe.returncode == 0:
        try:    sha = json.loads(probe.stdout).get("sha")
        except: sha = None
        # WHY: el cuerpo va por STDIN (--input -), NUNCA como argumento -f content=<b64>.
    # Incidencia 2026-08-20 (@manzanosenterprises): una foto de 899 KB da un base64 de
    # ~1,20 MB y revienta el ARG_MAX de macOS (1.048.576 B) con "[Errno 7] Argument list
    # too long". Toda foto real de mas de ~780 KB fallaba SIEMPRE y caia al post de marca,
    # en silencio. Por stdin no hay limite de tamano.
    body = {"message": f"Add real photo {remote_name}", "content": content_b64}
    if sha: body["sha"] = sha
    args = ["gh", "api", "--method", "PUT", f"/repos/{REPO}/contents/{remote_path}",
            "--input", "-"]
    r = subprocess.run(args, input=json.dumps(body), capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"gh upload failed: {r.stderr.strip()[:300]}")
    return f"{RAW}/{remote_path}"

def archive_real(path):
    os.makedirs(DONE_DIR, exist_ok=True)
    name = os.path.basename(path)
    os.rename(path, os.path.join(DONE_DIR, name))
    cap_file = os.path.join(TDIR, os.path.splitext(name)[0] + ".txt")
    if os.path.exists(cap_file):
        os.rename(cap_file, os.path.join(DONE_DIR, os.path.basename(cap_file)))


# ── INSTAGRAM GRAPH API ───────────────────────────────────────────────────
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
def api(path, params, method="POST"):
    data = urllib.parse.urlencode(params).encode()
    hdr  = {"User-Agent": UA}
    if method == "GET":
        req = urllib.request.Request(f"{BASE}/{path}?{data.decode()}", headers=hdr)
    else:
        req = urllib.request.Request(f"{BASE}/{path}", data=data, method="POST", headers=hdr)
    try:
        with urllib.request.urlopen(req) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "body": e.read().decode()}
    except Exception as e:
        # WHY: un fallo de red (URLError/DNS/timeout) NUNCA debe propagar y matar el
        # script. El 2026-07-05 un URLError al pedir el permalink DESPUÉS de que
        # media_publish ya había publicado el post crasheó main() antes de save_state();
        # el estado no se guardó y el post de Haro se republicó el 07-07 (duplicado).
        return {"_net_error": str(e)}

def wait_ready(cid):
    for _ in range(20):
        st = api(cid, {"fields": "status_code", "access_token": TOK}, "GET").get("status_code")
        if st in ("FINISHED", "ERROR", "EXPIRED"): return st
        time.sleep(4)
    return "TIMEOUT"

def publish_image(url, caption=None, story=False):
    ensure_creds()
    p = {"image_url": url, "access_token": TOK}
    if story:   p["media_type"] = "STORIES"
    if caption: p["caption"]    = caption
    c = api(f"{IGID}/media", p); cid = c.get("id")
    if not cid: return {"error": c}
    if wait_ready(cid) != "FINISHED": return {"error": "container not ready"}
    r = api(f"{IGID}/media_publish", {"creation_id": cid, "access_token": TOK})
    mid = r.get("id")
    if not mid: return {"error": r}
    # El post YA está publicado (tenemos mid). El permalink es informativo: si su
    # fetch falla (red), devolvemos igualmente el id para que el caller marque el
    # post como OK y persista el estado — así no se republica al día siguiente.
    perma = api(mid, {"fields": "permalink", "access_token": TOK}, "GET")
    return {"id": mid, "permalink": perma.get("permalink")}


# ── EMAIL RESUMEN ─────────────────────────────────────────────────────────
def email_summary(html, post_path, story_path, subject):
    pw = _secret("VICTORIA_STERLING_EMAIL_PASSWORD")
    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["From"]    = "victoriasterling@manzanos.eu"
    msg["To"]      = "victor@manzanos.com"
    msg.attach(MIMEText(html, "html", "utf-8"))
    for cid, path in (("postimg", post_path), ("storyimg", story_path)):
        try:
            with open(path, "rb") as f: img = MIMEImage(f.read())
            img.add_header("Content-ID", f"<{cid}>")
            img.add_header("Content-Disposition", "inline", filename=os.path.basename(path))
            msg.attach(img)
        except Exception as e: print("attach failed", path, e)
    with smtplib.SMTP_SSL("manzanos-eu.correoseguro.dinaserver.com", 465,
                          context=ssl.create_default_context()) as srv:
        srv.login("victoriasterling@manzanos.eu", pw)
        srv.send_message(msg)


# ── IDEMPOTENCIA SERVER-SIDE (evita post duplicado aunque falle el estado) ─
def caption_body(cap):
    """Cuerpo del caption sin las líneas de hashtags (estable frente a rotación)."""
    lines = []
    for ln in (cap or "").split("\n"):
        toks = ln.split()
        if toks and all(t.startswith("#") for t in toks):
            continue
        lines.append(ln)
    return "\n".join(lines).strip()

def latest_post_body():
    """Cuerpo (sin hashtags) del último post del feed, o None si no se puede leer.
    Fail-open: ante cualquier error de red devuelve None y NO bloquea la publicación."""
    ensure_creds()
    r = api(f"{IGID}/media", {"fields": "caption", "limit": "1", "access_token": TOK}, "GET")
    data = r.get("data") if isinstance(r, dict) else None
    if not data:
        return None
    return caption_body(data[0].get("caption"))


# ── ANTI-REPETICIÓN 360 DÍAS (Victor, 21-sep-2026) ───────────────────────
# Regla: ninguna FOTO se publica dos veces, ni en post ni en story, en 360 días.
# Antes el motor elegía con POSTS[s["post"] % len(POSTS)]: contador circular sobre
# 18 posts y 17 stories a cadencia 2 días, así que el post se repetía cada ~36
# días y la story cada ~34. El ledger reconstruido del log y del feed real lo
# confirmaba: 03-mobility, 01-taycan, 04-cayenne... ya habían salido 2 veces, y
# 01-taycan-story 4 veces. Además 02-dboat-diamond y 06-dboat-puesto-mando son
# tarjetas distintas con la MISMA foto, que ningún nombre de fichero delataba.
#
# Identidad de la foto = fichero fuente en raw/ + hash perceptual DCT de 64 bits
# (imghash.py), para que la misma foto reescalada/recomprimida/recompuesta cuente
# como la misma. NO aHash: confundía fotos de mar distintas entre sí.
NO_REPEAT_DAYS = 360
IMAGE_INDEX = os.path.join(LOCAL, ".image_index.json")   # tarjeta → {src, phash, kind}
LEDGER      = os.path.join(LOCAL, ".published_images.json")
# WHY 10: medido el 21-sep-2026 sobre raw/: la misma foto recompuesta (post vs
# story de 15-taycan-turbo y 16-charter) da 4-8; dos fotos distintas, 16 o más.
PHASH_NEAR  = 10

def _ham(a, b):
    return bin(int(a) ^ int(b)).count("1")

_IDX_CACHE = None
def image_index():
    # WHY cache: se consulta por cada candidato al escoger; el fichero no cambia
    # durante la ejecución.
    global _IDX_CACHE
    if _IDX_CACHE is None:
        try:
            _IDX_CACHE = json.load(open(IMAGE_INDEX))
        except Exception:
            _IDX_CACHE = {}
    return _IDX_CACHE

def ledger_load():
    try:
        return json.load(open(LEDGER))
    except Exception:
        return []

def ledger_add(card, kind, date):
    """Registra una publicación JUSTO tras confirmarla (igual que save_state)."""
    ent = image_index().get(card)
    if not ent:
        print(f"⚠️ {card} no está en .image_index.json: publicada SIN registrar su foto")
        return
    led = ledger_load()
    led.append({"date": date, "kind": kind, "card": card,
                "src": ent["src"], "phash": ent["phash"]})
    json.dump(led, open(LEDGER, "w"), indent=1)

def recent_window(days=NO_REPEAT_DAYS, today=None):
    today = today or datetime.date.today()
    cut = str(today - datetime.timedelta(days=days))
    srcs, ph = set(), []
    for e in ledger_load():
        if e.get("date", "") >= cut:
            srcs.add(e.get("src"))
            if e.get("phash"):
                ph.append(e["phash"])
    return srcs, ph

def is_repeat(card, srcs, phashes, extra_phashes=()):
    ent = image_index().get(card)
    if not ent:
        # WHY fail-closed: una tarjeta sin identidad es una foto que nadie ha
        # comparado; publicarla es justo el agujero que se cierra aquí.
        return True
    if ent["src"] in srcs:
        return True
    return any(_ham(ent["phash"], p) <= PHASH_NEAR for p in list(phashes) + list(extra_phashes))

def card_phash(card):
    ent = image_index().get(card)
    return ent["phash"] if ent else None

def pick_fresh(items, idx, srcs, phashes, extra_phashes=()):
    """Primera entrada desde idx cuya foto no salió en la ventana.
    Devuelve (entrada, índice_siguiente, agotado). Devolver el índice USADO evita
    el fallo de [[ig-rotation-tail-latency]] (proponer siempre la misma tarjeta)."""
    n = len(items)
    for step in range(n):
        i = (idx + step) % n
        it = items[i]
        card = it[0] if isinstance(it, (tuple, list)) else it
        if not is_repeat(card, srcs, phashes, extra_phashes):
            return it, i + 1, False
    return items[idx % n], idx + 1, True


# ── CAPTION ROTATION (anti-spam hashtags) ─────────────────────────────────
def rotate_caption(cap):
    body, tags = [], []
    for ln in cap.split("\n"):
        toks = ln.split()
        if toks and all(t.startswith("#") for t in toks):
            tags.extend(toks)
        else:
            body.append(ln)
    if not tags:
        return cap
    brand = [t for t in tags if t.lower() == H.lower()]
    rest  = [t for t in tags if t.lower() != H.lower()]
    random.shuffle(rest)
    k = min(len(rest), random.randint(4, 8))
    chosen = brand + rest[:k]
    random.shuffle(chosen)
    return "\n".join(body).rstrip() + "\n" + " ".join(chosen)


# ── MAIN ──────────────────────────────────────────────────────────────────
def main():
    s = state()
    real_items = real_collect()
    do_real    = bool(real_items) and s.get("since_real", 0) >= REAL_EVERY
    real_path  = real_items[0][0] if real_items else None
    real_cap   = real_items[0][1] if real_items else None

    # Guardia de 360 días: ni post ni story repiten foto, y la story no puede
    # llevar la foto del post de HOY (entra como extra_phashes).
    # WHY: normalizar el contador; la baraja crece cada semana y un contador
    # mayor que la lista hace ilegible el "salta N" del log.
    s["post"] %= len(POSTS); s["story"] %= len(STORY_FILES)
    _srcs, _ph = recent_window()
    (pf, cap), post_idx, post_stale = pick_fresh(POSTS, s["post"], _srcs, _ph)
    _post_ph = [p for p in (card_phash(pf),) if p]
    sf, story_idx, story_stale = pick_fresh(STORY_FILES, s["story"], _srcs, _ph, _post_ph)
    cap = rotate_caption(cap)
    post_url  = f"{RAW}/posts/{pf}"
    story_url = f"{RAW}/stories/{sf}"
    stale_msg = ""
    if post_stale or story_stale:
        stale_msg = ("⚠️ BARAJA AGOTADA: toda la rotación se publicó en los últimos "
                     f"{NO_REPEAT_DAYS} días (post={post_stale}, story={story_stale}). "
                     "Faltan imágenes nuevas: python3 add_images.py check")
        print(stale_msg)

    if do_real:
        print(f"NEXT = FOTO REAL: {os.path.basename(real_path)}  (since_real={s.get('since_real',0)} ≥ {REAL_EVERY})")
        print(f"--- CAPTION ---\n{real_cap}\n---  (story: {sf})")
    else:
        _ix = image_index()
        print(f"NEXT = POST MARCA: {pf}  [foto: {_ix.get(pf,{}).get('src','?')}]"
              f"\nSTORY: {sf}  [foto: {_ix.get(sf,{}).get('src','?')}]"
              f"\n(anti-repetición {NO_REPEAT_DAYS}d: post salta {post_idx-1-s['post']} entradas, "
              f"story salta {story_idx-1-s['story']}; ledger {len(ledger_load())} publicaciones)"
              f"\n--- CAPTION ---\n{cap}\n---  (real en {REAL_EVERY - s.get('since_real',0)} posts)")

    if DRY:
        print("DRY RUN — nada publicado.")
        return

    today = str(datetime.date.today())
    if os.environ.get("FORCE") != "1" and datetime.date.today().toordinal() % CYCLE_DIV != CYCLE_DAY:
        print(f"Día de descanso ({today}) — Manzanos Mobility publica cuando ordinal%{CYCLE_DIV}=={CYCLE_DAY}.")
        return
    if s.get("last_date") == today:
        print(f"Ya se publicó hoy ({today}).")
        return
    # Idempotencia server-side: si el post de marca de hoy YA es el último del feed
    # (p. ej. el estado se perdió/corrompió), NO republicar — solo re-sincronizar el
    # estado y salir. Defensa extra contra el duplicado del 07-07. Solo para posts de
    # marca (la foto real cambia de imagen cada vez). Fail-open ante error de red.
    if not do_real:
        body_today = caption_body(cap)
        if body_today and latest_post_body() == body_today:
            print("Post de hoy YA es el último del feed (idempotencia API) — re-sincronizo estado, no republico.")
            s["last_date"] = today
            s["post"] = post_idx
            s["since_real"] = s.get("since_real", 0) + 1
            save_state(s)
            ledger_add(pf, "post", today)   # ya está en el feed: cuenta para los 360 días
            return
    if datetime.datetime.now().hour < 14 and random.random() < 0.40:
        print("Aplazo a franja posterior (rompe patrón horario).")
        return
    time.sleep(random.randint(30, 480))  # jitter

    # ── Publicar POST ──────────────────────────────────────────────────────
    is_real = False
    if do_real:
        try:
            h = hashlib.sha1(open(real_path, "rb").read()).hexdigest()[:8]
            base, ext = os.path.splitext(os.path.basename(real_path))
            url = gh_upload(real_path, f"{base}-{h}{ext.lower()}")
            time.sleep(5)
            pr = publish_image(url, caption=real_cap)
            # WHY: id basta — el post YA está publicado aunque el fetch del permalink
            # falle por red; sin esto se publicaba TAMBIÉN el post de marca (duplicado)
            if pr.get("permalink") or pr.get("id"):
                is_real = True; cap = real_cap; post_url = url
            else:
                print("Foto real falló, fallback a marca:", json.dumps(pr)[:200])
                pr = publish_image(post_url, caption=cap)
        except Exception as e:
            print("EXCEPCIÓN foto real, fallback a marca:", e)
            pr = publish_image(post_url, caption=cap)
    else:
        pr = publish_image(post_url, caption=cap)

    # WHY: persistir el estado JUSTO cuando el post está confirmado publicado
    # (tenemos permalink o id), ANTES de publicar el story / enviar el email. Si
    # algún paso posterior crashea (red, etc.), last_date ya está guardado y el post
    # NO se republicará al día siguiente. `id` cuenta como OK aunque falte permalink.
    post_ok = bool(pr.get("permalink") or pr.get("id"))
    if post_ok:
        s["last_date"] = today
        if is_real:
            archive_real(real_path); s["since_real"] = 0
        else:
            s["post"] = post_idx
            s["since_real"] = s.get("since_real", 0) + 1
            ledger_add(pf, "post", today)
        save_state(s)

    time.sleep(random.randint(20, 120))  # gap humano antes del story
    sr = publish_image(story_url, story=True)
    story_ok = bool(sr.get("permalink") or sr.get("id"))
    if story_ok:
        s["story"] = story_idx
        save_state(s)
        ledger_add(sf, "story", today)

    plink = (pr.get("permalink")
             or (f"publicado (id {pr.get('id')}, permalink no disponible)" if pr.get("id")
                 else "ERROR: " + json.dumps(pr)[:220]))
    sok   = "publicada ✅" if story_ok else ("ERROR: " + json.dumps(sr)[:220])
    print("post:", plink, "(real)" if is_real else "(marca)")
    print("story:", sok)

    subj = ("📲 Instagram diario — Manzanos Mobility"
            if post_ok else
            "⚠️ FALLO al publicar — Instagram Manzanos Mobility (revisar)")
    post_path  = real_path if is_real else os.path.join(LOCAL, "posts", pf)
    story_path = os.path.join(LOCAL, "stories", sf)
    kind = "Foto real (drop folder)" if is_real else f"Post {s['post']}/{len(POSTS)}"
    email_summary(
        f"<p>Publicado hoy en <b>@manzanosmobility</b> · <b>{kind}</b>:</p>"
        f"<p>📸 <b>Post:</b> <a href='{plink}'>{plink}</a><br>📱 <b>Story:</b> {sok}</p>"
        f"<table cellpadding='6'><tr>"
        f"<td valign='top' align='center'><div style='color:#888;font-size:11px;letter-spacing:1px'>POST</div>"
        f"<img src='cid:postimg' width='300' style='border-radius:10px;border:1px solid #ddd'></td>"
        f"<td valign='top' align='center'><div style='color:#888;font-size:11px;letter-spacing:1px'>STORY</div>"
        f"<img src='cid:storyimg' width='210' style='border-radius:10px;border:1px solid #ddd'></td>"
        f"</tr></table>"
        f"<p style='color:#888;font-size:12px'>Caption:</p>"
        f"<pre style='white-space:pre-wrap;color:#555;font-size:12px'>{cap}</pre>"
        f"<p style='color:#aaa;font-size:11px'>Cadencia cada 2 días (días impares) · rotación sin repetir foto en 360 días.</p>"
        + (f"<p style='color:#b00'><b>{stale_msg}</b></p>" if stale_msg else ""),
        post_path, story_path, subject=subj
    )


if __name__ == "__main__":
    main()
