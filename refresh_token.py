#!/usr/bin/env python3
"""Manzanos Mobility — refresh del long-lived Instagram access token (~60 días).
Endpoint: GET https://graph.instagram.com/refresh_access_token
  ?grant_type=ig_refresh_token&access_token=<TOKEN>
Guarda el nuevo token en Keychain sobrescribiendo MANZANOSMOBILITY_IG_ACCESS_TOKEN.
Se ejecuta los domingos por LaunchAgent.
"""
import datetime, json, os, subprocess, urllib.request, urllib.parse
SECRETS = os.path.expanduser("~/Code/CyberSecurity/scripts/secrets.sh")
LOG     = os.path.expanduser("~/manzanosmobility-social/token-refresh.log")
def secret(n): return subprocess.check_output([SECRETS, "get", n]).decode().strip()
def set_secret(n, v): subprocess.run([SECRETS, "set", n, v], check=True)
def main():
    tok = secret("MANZANOSMOBILITY_IG_ACCESS_TOKEN")
    params = urllib.parse.urlencode({"grant_type": "ig_refresh_token", "access_token": tok})
    url = f"https://graph.instagram.com/refresh_access_token?{params}"
    with urllib.request.urlopen(url) as r:
        body = json.load(r)
    new, exp = body.get("access_token"), body.get("expires_in")
    line = f"[{datetime.datetime.now().isoformat(timespec='seconds')}] "
    if new:
        set_secret("MANZANOSMOBILITY_IG_ACCESS_TOKEN", new)
        line += f"OK · nuevo token · expira en {exp}s (~{int(exp)//86400} días)"
    else:
        line += f"FALLO · {json.dumps(body)[:300]}"
    print(line)
    with open(LOG, "a") as f: f.write(line + "\n")
if __name__ == "__main__":
    main()
