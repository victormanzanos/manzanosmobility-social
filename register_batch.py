#!/usr/bin/env python3
"""Da de alta en bloque las candidatas de Pexels YA REVISADAS A OJO.

Entrada: cand/_decisions.json → {"px-123.jpg": "post:mar" | "story" | "reject:<motivo>"}
Cada alta pasa por add_images.cmd_add (dedup md5 + aHash contra toda la baraja)
y añade su entrada a CAPTIONS.md. Los posts se intercalan por familia para que la
rotación no saque diez barcos seguidos.

Uso: python3 register_batch.py [--dry]
"""
import os, sys, json, re, itertools
LOCAL = os.path.expanduser("~/manzanosmobility-social")
sys.path.insert(0, LOCAL)
import add_images as A
import caption_bank as CB

CAND = os.path.join(LOCAL, "cand")
DEC = os.path.join(CAND, "_decisions.json")
USED = os.path.join(LOCAL, ".caption_hooks_used.json")   # familia → nº de ganchos gastados

STORY_LABEL = {
    "mar": "Chárter de yate · Tu itinerario, tu ritmo",
    "ruta": "Ruta en Porsche · Navarra y La Rioja",
    "vino": "Ruta entre viñedos · Alquiler de Porsche",
    "taycan": "Porsche Taycan · 100% eléctrico",
    "cayenne": "Porsche Cayenne · SUV con alma deportiva",
    "import": "Importación premium desde EE.UU.",
}

def theme_family(fname):
    meta = json.load(open(os.path.join(CAND, ".meta.json"))).get(fname, {})
    t = meta.get("theme", "")
    return {"taycan": "taycan", "cayenne": "cayenne", "escalade": "import", "suburban": "import",
            "road": "ruta", "badlands": "ruta", "village": "ruta", "vineyard": "vino"}.get(t, "mar"), t

def next_post_num():
    nums = [int(m) for m in re.findall(r"^### `(\d+)-", open(os.path.join(LOCAL, "CAPTIONS.md"), encoding="utf-8").read(), re.M)]
    return max(nums) + 1

def next_story_num():
    nums = [int(m) for m in re.findall(r"^### `s(\d{3})-", open(os.path.join(LOCAL, "CAPTIONS.md"), encoding="utf-8").read(), re.M)]
    return (max(nums) + 1) if nums else 1

def interleave(groups):
    out = []
    for batch in itertools.zip_longest(*groups.values()):
        out += [b for b in batch if b]
    return out

def main(dry=False):
    dec = json.load(open(DEC))
    used = A.load(USED, {})
    posts, stories = {}, {}
    for f, d in sorted(dec.items()):
        src = os.path.join(CAND, json.load(open(os.path.join(CAND, ".meta.json")))[f]["theme"], f)
        if not os.path.exists(src):
            continue
        if d.startswith("post:"):
            posts.setdefault(d.split(":", 1)[1], []).append((f, src))
        elif d == "story" or d.startswith("story:"):
            fam = d.split(":", 1)[1] if ":" in d else theme_family(f)[0]
            stories.setdefault(theme_family(f)[1], []).append((f, src, fam))
    n = next_post_num(); ok = 0
    for f, src in interleave(posts):
        fam = next(k for k, v in posts.items() if (f, src) in v)
        i = used.get(fam, 0)
        cap = CB.build(fam, i)
        pid = f[3:-4]
        name = f"{n:02d}-px-{fam}-{pid}"
        if dry:
            print("POST ", name); n += 1; used[fam] = i + 1; continue
        if A.cmd_add("post", src, name, cap) == 0:
            used[fam] = i + 1; n += 1; ok += 1
            json.dump(used, open(USED, "w"))
    k = next_story_num(); oks = 0
    for f, src, fam in interleave(stories):
        name = f"s{k:03d}-px-{f[3:-4]}"
        if dry:
            print("STORY", name); k += 1; continue
        if A.cmd_add("story", src, name, STORY_LABEL.get(fam, STORY_LABEL["mar"])) == 0:
            k += 1; oks += 1
    print(f"altas: {ok} posts · {oks} stories")

if __name__ == "__main__":
    main("--dry" in sys.argv)
