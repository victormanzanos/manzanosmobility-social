#!/usr/bin/env python3
"""Candidatas de Pexels para la baraja de @manzanosmobility (gratis, sin cuota SerpAPI).

Baja fotos a cand/<tema>/px-<id>.jpg para REVISARLAS A OJO (hojas de contacto)
antes de darlas de alta con add_images.py. Nunca publica nada ni toca posts/ o stories/.

Uso:
  python3 fetch_pexels.py <tema> "<query>" <n> [portrait|landscape|square] [regex_alt]
  python3 fetch_pexels.py sheet <tema>        # hoja de contacto numerada en cand/_sheets/

Dedup: id de Pexels ya visto (cand/.seen.json, incluye rechazadas para que no
vuelvan), md5 y aHash contra raw/ y contra todas las candidatas ya bajadas.
⚠️ Pexels da 403 al User-Agent de urllib y a las ráfagas: UA de navegador y 1,6 s
entre llamadas. Límite 200 peticiones/hora (429 = esperar a la hora siguiente).
"""
import os, sys, json, re, time, hashlib, subprocess, urllib.request, urllib.parse
from PIL import Image, ImageDraw

LOCAL = os.path.expanduser("~/manzanosmobility-social")
CAND = os.path.join(LOCAL, "cand")
SEEN = os.path.join(CAND, ".seen.json")
META = os.path.join(CAND, ".meta.json")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAUSE = 1.6          # WHY: por debajo de ~1,5 s Pexels empieza a responder 403
MIN_SHORT = 1000     # WHY: la story es 1080 de ancho; menos se nota blando al reescalar
PHASH_NEAR = 10      # mismo umbral que el motor


sys.path.insert(0, os.path.expanduser("~/manzanosmobility-social"))
from imghash import phash as ahash   # pHash DCT, ver imghash.py

def load(p, d):
    try:
        return json.load(open(p))
    except Exception:
        return d

def known():
    md5s, ph = set(), []
    dirs = [os.path.join(LOCAL, "raw")] + [os.path.join(CAND, t) for t in os.listdir(CAND)
                                          if os.path.isdir(os.path.join(CAND, t)) and not t.startswith("_")]
    for d in dirs:
        for f in os.listdir(d):
            if f.lower().endswith(".jpg"):
                p = os.path.join(d, f)
                md5s.add(hashlib.md5(open(p, "rb").read()).hexdigest())
                ph.append(ahash(Image.open(p)))
    return md5s, ph

def api(url, key):
    req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def _download(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=60).read()

def fetch(theme, query, n, orient="portrait", alt_rx=None):
    """Busca en la API (secuencial, con pausa) y descarga en paralelo desde el CDN.
    WHY paralelo: cada descarga tarda 2-5 s y en serie 600 fotos eran ~2 h; el
    límite de 200/h y los 403 por ráfaga son de la API, no del CDN de imágenes."""
    from concurrent.futures import ThreadPoolExecutor
    os.makedirs(os.path.join(CAND, theme), exist_ok=True)
    key = subprocess.check_output([os.path.expanduser("~/Code/CyberSecurity/scripts/secrets.sh"),
                                   "get", "PEXELS_API_KEY"]).decode().strip()
    seen = set(load(SEEN, [])); meta = load(META, {})
    md5s, ph = known()
    got, page = 0, 1
    rx = re.compile(alt_rx, re.I) if alt_rx else None
    while got < n and page <= 8:
        q = urllib.parse.urlencode({"query": query, "per_page": 80, "page": page, "orientation": orient})
        try:
            data = api(f"https://api.pexels.com/v1/search?{q}", key)
        except Exception as e:
            print("API error:", e, flush=True); break
        photos = data.get("photos", [])
        if not photos:
            break
        todo = []
        for p in photos:
            pid = str(p["id"])
            if pid in seen or (rx and not rx.search(p.get("alt") or "")):
                continue
            if min(p["width"], p["height"]) < MIN_SHORT:
                continue
            seen.add(pid)
            todo.append(p)
        todo = todo[: max(0, int((n - got) * 1.3) + 2)]
        with ThreadPoolExecutor(6) as ex:
            blobs = list(ex.map(lambda p: _safe(p), todo))
        for p, blob in zip(todo, blobs):
            if got >= n or not blob or len(blob) < 40000:
                continue
            pid = str(p["id"])
            md5 = hashlib.md5(blob).hexdigest()
            out = os.path.join(CAND, theme, f"px-{pid}.jpg")
            open(out, "wb").write(blob)
            try:
                h = ahash(Image.open(out))
            except Exception:
                os.remove(out); continue
            if md5 in md5s or any(bin(h ^ o).count("1") <= PHASH_NEAR for o in ph):
                os.remove(out); print("  dup", pid, flush=True); continue
            md5s.add(md5); ph.append(h)
            meta[f"px-{pid}.jpg"] = {"theme": theme, "alt": p.get("alt") or "", "by": p.get("photographer"),
                                     "url": p.get("url"), "query": query}
            got += 1
        json.dump(sorted(seen), open(SEEN, "w"))
        json.dump(meta, open(META, "w"), indent=1)
        page += 1
        time.sleep(PAUSE)
    print(f"{theme}: +{got} ({query}, {orient})", flush=True)

def _safe(p):
    try:
        return _download(p["src"]["original"] + "?auto=compress&cs=tinysrgb&w=1600")
    except Exception as e:
        print("  descarga falló", p["id"], e, flush=True)
        return None

def sheet(theme, cols=5, rows=4, tw=300):
    d = os.path.join(CAND, theme)
    dec = load(os.path.join(CAND, "_decisions.json"), {})
    # WHY solo las pendientes: la hoja se rotula con el ID de Pexels, y las ya
    # decididas no se vuelven a mirar.
    fs = sorted(f for f in os.listdir(d) if f.endswith(".jpg") and f not in dec)
    os.makedirs(os.path.join(CAND, "_sheets"), exist_ok=True)
    th = int(tw * 1.25)
    per = cols * rows
    for k in range(0, len(fs), per):
        S = Image.new("RGB", (cols * tw, rows * (th + 22)), "white")
        dr = ImageDraw.Draw(S)
        for i, f in enumerate(fs[k:k + per]):
            im = Image.open(os.path.join(d, f)).convert("RGB")
            s = max(tw / im.width, th / im.height)
            im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1))
            x0, y0 = (im.width - tw) // 2, (im.height - th) // 2
            im = im.crop((x0, y0, x0 + tw, y0 + th))
            x, y = (i % cols) * tw, (i // cols) * (th + 22)
            S.paste(im, (x, y + 22))
            dr.text((x + 4, y + 4), f"{k + i}: {f[3:-4]}", fill="black")
        out = os.path.join(CAND, "_sheets", f"{theme}-{k // per}.jpg")
        S.save(out, quality=80); print(out)

if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "sheet":
        sheet(a[1])
    elif len(a) >= 3:
        fetch(a[0], a[1], int(a[2]), a[3] if len(a) > 3 else "portrait", a[4] if len(a) > 4 else None)
    else:
        print(__doc__)
