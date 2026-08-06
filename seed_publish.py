#!/usr/bin/env python3
"""SIEMBRA del feed de @manzanosmobility (una sola vez, 2026-08-06).

Publica los 6 primeros posts de CAPTIONS.md (marca, Porsche, DBoat, Escalade,
yates, Suburban) con espaciado aleatorio entre publicaciones para no disparar
los limites de Meta (6 publicaciones, muy por debajo del limite de 25/24h del
content publishing API).

Al terminar deja `.daily_state.json` con post=6, story=0 y last_date=hoy, para
que el motor diario NO republique hoy y siga la rotacion normal a partir del
proximo dia impar continuando por el 7o post (04-cayenne).
"""
import datetime, json, os, random, sys, time
from daily_engine import publish_image, POSTS, STATE, rotate_caption, RAW

SEED_N = 6

# WHY 60-150 s entre publicaciones: humano-plausible y deja la siembra completa
# en ~8-12 min sin acercarse al rate limit del content publishing API
def pause():
    d = random.randint(60, 150)
    print(f"    (espera {d}s)", flush=True)
    time.sleep(d)


def main():
    if len(POSTS) < SEED_N:
        sys.exit(f"Solo hay {len(POSTS)} posts en CAPTIONS.md, se necesitan {SEED_N}")

    results = []
    for i, (fn, cap) in enumerate(POSTS[:SEED_N], 1):
        if i > 1:
            pause()
        r = publish_image(f"{RAW}/posts/{fn}", caption=rotate_caption(cap))
        ok = bool(r.get("permalink") or r.get("id"))
        results.append((fn, ok, r))
        print(f"[{i}/{SEED_N}] {fn}: {r.get('permalink') or r.get('id') or r}", flush=True)

    ok_n = sum(1 for _, ok, _ in results if ok)
    print(f"\nSIEMBRA: {ok_n}/{SEED_N} publicadas", flush=True)

    # WHY: persistir el estado SIEMPRE que se haya publicado algo, aunque alguna
    # fallase — si no, el motor de hoy/manana republicaria lo ya publicado
    # (leccion del duplicado de habitat 2026-07-05/07).
    if ok_n:
        s = json.load(open(STATE)) if os.path.exists(STATE) else {}
        s["post"] = ok_n
        s["story"] = 0
        s["since_real"] = ok_n
        s["last_date"] = str(datetime.date.today())
        json.dump(s, open(STATE, "w"))
        print("estado:", json.dumps(s), flush=True)


if __name__ == "__main__":
    main()
