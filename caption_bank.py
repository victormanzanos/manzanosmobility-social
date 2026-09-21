#!/usr/bin/env python3
"""Banco de captions para las tarjetas de post de banco de imágenes (Pexels).

Regla de provenance (Constitución Art. I): la foto de banco ILUSTRA una línea de
negocio, nunca se presenta como nuestra unidad ni como un lugar concreto.
- Ninguna caption dice que el barco de la foto es un DBoat ni que el coche es "el nuestro".
- Ninguna caption nombra el lugar de la foto (una cala no es "Menorca", una carretera
  no es "el puerto de Belate").
- Solo cifras ya publicadas en manzanosmobility.com y en CAPTIONS.md:
  alquiler Porsche desde 950 €/día o 2.500 €/semana con impuestos y seguro incluidos;
  Taycan 4S 530 CV y hasta 512 km; Taycan Turbo 680 CV y 0-100 en 3,2 s;
  Cayenne S 440 CV; Cayenne E-Hybrid 519 CV con modo 100% eléctrico;
  DBoat: certificación CE, más de 30 años de astillero, exclusiva en España y EE.UU.;
  importación desde EE.UU. con verificación, informe de historial y homologación;
  empresa familiar desde 1890.
- Sin rayas largas.

Cada familia tiene ganchos ÚNICOS (primera línea + desarrollo) y un cierre de negocio
que rota. build(family, i) devuelve la caption i-ésima; nunca repite gancho.
"""

CTA = "Más información en el link de la bio."

PRICE = ("Alquiler de Porsche en Navarra y La Rioja desde 950 € al día o 2.500 € a la "
         "semana, con impuestos y seguro incluidos.")

CLOSE = {
    "mar": [
        "Diseñamos chárters de yate con tripulación profesional y sin paquetes cerrados: tus fechas, tu grupo y tu ritmo.",
        "Alquiler de yates de lujo con tripulación profesional: escuchamos qué viaje buscas y construimos contigo el itinerario.",
        "Chárter a medida: nada de paquetes cerrados, el itinerario y el ritmo de a bordo los decides tú.",
        "Y si lo que buscas es un barco propio, comercializamos DBoat en exclusiva en España y EE.UU.: diseño de superyate, certificación CE y más de 30 años de astillero.",
    ],
    "ruta": [
        PRICE,
        "Taycan 4S de 530 CV y hasta 512 km de autonomía, o Cayenne S de 440 CV. " + PRICE,
        "Elige entre la calma eléctrica del Taycan o la versatilidad del Cayenne. " + PRICE,
    ],
    "vino": [
        "Entre viñedos, el Cayenne E-Hybrid de 519 CV permite rodar en modo 100% eléctrico. " + PRICE,
        "La mejor forma de recorrer Navarra y La Rioja es sin prisa y al volante de un Porsche. " + PRICE,
        PRICE,
    ],
    "taycan": [
        "Taycan 4S: 530 CV y hasta 512 km de autonomía. Taycan Turbo: 680 CV y de 0 a 100 en 3,2 segundos. " + PRICE,
        "100% eléctrico, par instantáneo y silencio absoluto. " + PRICE,
    ],
    "cayenne": [
        "Cayenne S de 440 CV o Cayenne E-Hybrid de 519 CV con modo 100% eléctrico. " + PRICE,
        "Espacio para cuatro y su equipaje, con alma de deportivo. " + PRICE,
    ],
    "import": [
        "Seleccionamos la unidad en EE.UU., verificamos su historial y su estado real, y gestionamos la importación con homologación incluida.",
        "Importación directa llave en mano: verificación de la unidad, informe de historial y homologación incluida.",
    ],
}

TAGS = {
    "mar":    "#ManzanosMobility #AlquilerYates #CharterYate #Yates #Mediterraneo #Nautica #LuxuryMobility #VidaEnElMar",
    "ruta":   "#ManzanosMobility #AlquilerPorsche #RoadTrip #Navarra #LaRioja #Porsche #CochesDeLujo #Escapadas",
    "vino":   "#ManzanosMobility #AlquilerPorsche #Vinedos #Navarra #LaRioja #Enoturismo #Porsche #RoadTrip",
    "taycan": "#ManzanosMobility #PorscheTaycan #AlquilerPorsche #CocheElectrico #Navarra #LaRioja #Porsche #CochesDeLujo",
    "cayenne":"#ManzanosMobility #PorscheCayenne #AlquilerPorsche #SUVDeportivo #Navarra #LaRioja #Porsche #CochesDeLujo",
    "import": "#ManzanosMobility #ImportacionCoches #CochesPremium #CompraventaVehiculos #USA #España #LuxuryMobility #CochesDeLujo",
}

import os
_HD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "caption_hooks")
# WHY ficheros aparte: una línea por gancho ("primera línea|desarrollo"); así la
# rutina semanal puede añadir ganchos sin tocar código.
HOOKS = {}
for _f in ("mar", "ruta", "vino", "taycan", "cayenne", "import"):
    _p = os.path.join(_HD, f"hooks_{_f}.txt")
    HOOKS[_f] = [l.strip().replace("|", "\n") for l in open(_p, encoding="utf-8") if l.strip()]


def build(family, i):
    hooks = HOOKS[family]
    if i >= len(hooks):
        raise IndexError(f"Faltan ganchos en la familia {family}: pedido {i}, hay {len(hooks)}")
    hook = hooks[i]
    close = CLOSE[family][i % len(CLOSE[family])]
    cap = f"{hook}\n{close}\n{CTA}\n\n{TAGS[family]}"
    assert "—" not in cap
    return cap
