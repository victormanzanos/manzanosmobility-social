"""Hash perceptual DCT (pHash 64 bits) en Python puro (sin numpy).

WHY no aHash: con fotos de mar (cielo claro arriba, agua oscura abajo) el aHash
16x16 daba distancia <=6 entre fotos DISTINTAS, así que el dedup las tiraba como
repetidas y el guard del motor habría bloqueado tarjetas frescas. El pHash DCT
compara la estructura de frecuencias baja, no el reparto de luz.
WHY sin numpy: el numpy del user-site de /usr/bin/python3 es x86_64 y no carga en
arm64 (bajo launchd el motor corre con /usr/bin/python3).
"""
import math
from PIL import Image

_N = 32
_C = [[math.cos(math.pi * (2 * x + 1) * u / (2 * _N)) for x in range(_N)] for u in range(8)]

def phash(im):
    im = im.convert("L").resize((_N, _N), Image.LANCZOS)
    px = list(im.getdata())
    rows = [px[i * _N:(i + 1) * _N] for i in range(_N)]
    # DCT por filas (solo 8 frecuencias) y luego por columnas
    r1 = [[sum(c * v for c, v in zip(_C[u], row)) for u in range(8)] for row in rows]
    coef = [[sum(_C[v][y] * r1[y][u] for y in range(_N)) for u in range(8)] for v in range(8)]
    flat = [coef[v][u] for v in range(8) for u in range(8)][1:]   # sin el término DC
    med = sorted(flat)[len(flat) // 2]
    return sum(1 << i for i, c in enumerate(flat) if c > med)

def ham(a, b):
    return bin(int(a) ^ int(b)).count("1")
