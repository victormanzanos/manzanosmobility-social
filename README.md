# Manzanos Mobility — Instagram engine (@manzanosmobility)

Motor de publicación automática en Instagram para Manzanos Mobility
(DBoat · alquiler de Porsche en Navarra/La Rioja · compraventa de vehículos
premium · yates). Clonado del motor probado de @manzanoshabitat.

## Piezas

| Fichero | Qué hace |
|---|---|
| `daily_engine.py` | Publica 1 post + 1 story cada 4 días (ordinal%4==1) vía Instagram Graph API. Idempotente (estado en `.daily_state.json` + check server-side del último caption). `DRY=1` para previsualizar. |
| `make_manzanosmobility.py` | Convierte imágenes de `raw/` en tarjetas de marca: post 1080x1350 / story 1080x1920, marco doble dorado, logo abajo. |
| `CAPTIONS.md` | Fuente única de posts/stories. El motor lo re-parsea en cada ejecución. |
| `refresh_token.py` | Renueva el long-lived IG token (~60 días) cada domingo. |
| `com.manzanosmobility.dailyig.plist` | LaunchAgent del motor diario (12:23/15:07/17:19/19:02). |
| `com.manzanosmobility.igtokenrefresh.plist` | LaunchAgent del refresh de token (domingo 10:41). |
| `reales/` | Drop folder: fotos reales que se intercalan 1 de cada 3 posts (caption opcional en `<nombre>.txt`). |

Las imágenes se publican vía raw URLs del repo público
`github.com/victormanzanos/manzanosmobility-social` (Instagram Graph API exige
URLs públicas).

## ⚠️ Activación pendiente (requiere a Victor)

El motor está construido y probado en DRY, pero **NO publica** hasta que existan
las credenciales en el Keychain:

1. Convertir @manzanosmobility en cuenta **Business** de Instagram y vincularla
   a una página de Facebook del negocio.
2. En Meta for Developers, crear/usar una app con Instagram Graph API y generar
   un **long-lived access token** de la cuenta (igual que se hizo con
   @manzanoshabitat).
3. Guardar en Keychain:
   ```bash
   ~/Code/CyberSecurity/scripts/secrets.sh set MANZANOSMOBILITY_IG_ACCESS_TOKEN '<token>'
   ~/Code/CyberSecurity/scripts/secrets.sh set MANZANOSMOBILITY_IG_ACCOUNT_ID '<ig-user-id>'
   ```
4. Cargar los LaunchAgents:
   ```bash
   cp ~/manzanosmobility-social/com.manzanosmobility.*.plist ~/Library/LaunchAgents/
   launchctl load -w ~/Library/LaunchAgents/com.manzanosmobility.dailyig.plist
   launchctl load -w ~/Library/LaunchAgents/com.manzanosmobility.igtokenrefresh.plist
   ```
5. Probar: `cd ~/manzanosmobility-social && DRY=1 python3 daily_engine.py`
   y después un disparo real con `FORCE=1 python3 daily_engine.py`.

## Contenido nuevo

La tarea programada `manzanosmobility-ig-content-refresh` (semanal) convierte
las imágenes nuevas del blog (`/Users/victor/Code/ManzanosMobility/blog/img/`)
en tarjetas y las añade a `CAPTIONS.md`, para que el feed no se repita.

## Futuro (si se adquiere Art's Golf Cars)

Añadir temas de golf cars: nuevas entradas en `CAPTIONS.md` con imágenes de
agolfcars.com (mismo pipeline; el blog de agolfcars ya genera imágenes en
`/Users/victor/Code/golf-dealer-platform/agolfcars-website/blog/img/`).
