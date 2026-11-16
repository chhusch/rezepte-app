# Rezepte-App

Rezeptsammlung für das Handy in der Küche.

| Container | Aufgabe |
|-----------|---------|
| `web`     | Caddy, HTTP auf Port 8080 |
| `api`     | FastAPI, Migrationen beim Start |
| `db`      | PostgreSQL |
| `backup`  | Täglich DB-Dump und Foto-Archiv nach `./backups` |

HTTPS: Nginx Proxy Manager (NPM) davor.

Rezepte erfassen, bearbeiten, löschen; Filter nach Kategorie, Tags,
Zutaten, Text; Original und eigene Version je Rezept; Kochmodus
(Bildschirm bleibt an); Notizen; «gekocht am» mit Sternen; Fotos; Export
als ZIP (Menü «⋯»); Import per URL (schema.org, sonst geraten) mit
Vorschau; Zutaten als Text einfügen; Portionen umrechnen; Timer in
Schritten; Nährwerte; Einkaufsliste mit Vorräten, nach Microsoft To Do;
Teilen per Link; Buchseite per Foto; Teilen aus dem Handy-Browser.

## Installation

Server mit Docker Engine 24+ (Compose-Plugin) und `git`. Prüfen:

```bash
docker compose version
```

Fehlt der Befehl oder gibt es nur `docker-compose` (mit Bindestrich),
Docker von docker.com installieren:

```bash
curl -fsSL https://get.docker.com | sh
```

Danach den eigenen Benutzer freischalten (neu anmelden):

```bash
sudo usermod -aG docker $USER
```

```bash
git clone <URL-dieses-Repositories> rezepte-app
```

```bash
cd rezepte-app
```

```bash
cp .env.example .env
```

`DB_PASSWORD` in `.env` setzen (`openssl rand -hex 24`, kein `$`).

```bash
docker compose up -d --build
```

Baut die Images und startet im Hintergrund. App: `http://SERVER-IP:8080`
(`HTTP_PORT` in `.env`). Beim ersten Öffnen Benutzername und
Passwort festlegen; das ist der einzige Benutzer.

## Zugriff von unterwegs

Eigener Proxmox-Container `zugang` mit WireGuard (wg-easy), NPM und
ddclient. Von aussen offen ist nur UDP 51820; ohne WireGuard-Schlüssel
antwortet er nicht. Die App ist nur im Heimnetz und im Tunnel
erreichbar; öffentlich siehe «Öffentlich erreichbar».

Beispielwerte unten: Domain `deinedomain.ch`, `zugang` auf
`192.168.0.210`, App-Container auf `192.168.0.211`. Eigene Werte
einsetzen; feste Adressen ausserhalb des DHCP-Bereichs des Routers.
Eingerichteter Stand und Rückbau: `docs/ZUGANG.md`.

### Infomaniak

Im Manager der Domain:

1. DynDNS `vpn.deinedomain.ch` anlegen; Benutzer und Passwort nur aus
   Buchstaben und Ziffern, sonst antwortet Infomaniak mit 302.
2. DNS-Eintrag A: `rezepte.deinedomain.ch` → `192.168.0.210`.
3. API-Token mit `domain:read`, `domain:write`, `dns:read`,
   `dns:write` (für Zertifikate; nur «domain» ergibt «Domain not
   found»).

### Proxmox-Host

In der Konsole des Hosts, nicht in einem Container:

```bash
modprobe wireguard
```

Lädt WireGuard in den Kernel.

```bash
echo wireguard > /etc/modules-load.d/wireguard.conf
```

Lädt es auch nach jedem Neustart.

«Create CT»: Hostname `zugang`, unprivilegiert, Vorlage Debian, 1 CPU,
1 GB RAM, 8 GB Disk, IPv4 statisch `192.168.0.210/24`, Gateway = Router.
Danach «Options», «Features»: `nesting` und `keyctl` ein. Starten.

### Container zugang

In der Konsole von `zugang`:

```bash
curl -fsSL https://get.docker.com | sh
```

Installiert Docker.

```bash
mkdir -p /root/zugang/ddclient && cd /root/zugang
```

```bash
cat > compose.yaml <<'EOF'
name: zugang

services:
  wg-easy:
    image: ghcr.io/wg-easy/wg-easy:15.5.0
    restart: unless-stopped
    environment:
      INSECURE: "true"
      DISABLE_IPV6: "true"
    volumes:
      - wireguard:/etc/wireguard
    ports:
      - "51820:51820/udp"
      - "51821:51821/tcp"
    cap_add:
      - NET_ADMIN
    sysctls:
      - net.ipv4.ip_forward=1
      - net.ipv4.conf.all.src_valid_mark=1

  npm:
    image: jc21/nginx-proxy-manager:2.17.0
    restart: unless-stopped
    ports:
      - "80:80"
      - "81:81"
      - "443:443"
    volumes:
      - npm_data:/data
      - npm_certs:/etc/letsencrypt

  ddclient:
    image: lscr.io/linuxserver/ddclient:v4.0.0-ls238
    restart: unless-stopped
    environment:
      TZ: Europe/Zurich
    volumes:
      - ./ddclient:/config

volumes:
  wireguard:
  npm_data:
  npm_certs:
EOF
```

```bash
cat > ddclient/ddclient.conf <<'EOF'
daemon=300
ssl=yes
usev4=webv4, webv4=ipify-ipv4
protocol=infomaniak
login=DYNDNS-BENUTZER
password='DYNDNS-PASSWORT'
vpn.deinedomain.ch
EOF
```

Benutzer, Passwort und Name in `ddclient/ddclient.conf` anpassen:

```bash
nano ddclient/ddclient.conf
```

Ctrl+O speichert, Ctrl+X beendet.

```bash
chmod 600 ddclient/ddclient.conf && docker compose up -d
```

Schützt die Datei und startet die drei Dienste.

```bash
docker compose logs ddclient
```

Muss `SUCCESS` für `vpn.deinedomain.ch` zeigen.

Update: Versionen in `compose.yaml` anpassen, dann:

```bash
docker compose pull && docker compose up -d
```

### Wingo

In myWingo Port-Forwarding: UDP 51820 → `192.168.0.210`. Damit erhält
der Anschluss auch eine öffentliche IPv4 (bis 20 Minuten). Sonst nichts
freigeben.

### WireGuard

`http://192.168.0.210:51821`, nur im Heimnetz:

1. Admin-Benutzer anlegen; Host `vpn.deinedomain.ch`, Port `51820`.
2. «Admin», «Config»: Allowed IPs `192.168.0.210/32`, DNS `9.9.9.9`.
   Durch den Tunnel geht nur der Verkehr zu `zugang`.
3. Je Gerät einen Client anlegen, QR-Code anzeigen.

Handy: App «WireGuard» (App Store, Play Store), «+», QR-Code scannen.
iPhone: im Tunnel «Bei Bedarf aktivieren» für Mobilfunk und fremde WLANs.

### NPM

`http://192.168.0.210:81`, nur im Heimnetz. Beim ersten Öffnen
Admin-Benutzer anlegen.

1. «SSL Certificates», «Add», Let's Encrypt: Domain
   `rezepte.deinedomain.ch`, «DNS Challenge», Anbieter Infomaniak,
   Inhalt `dns_infomaniak_token = API-TOKEN`.
2. «Proxy Hosts», «Add»: Domain `rezepte.deinedomain.ch`, Scheme
   `http`, `192.168.0.211`, Port 8080; SSL: das Zertifikat, «Force SSL».

Dann `COOKIE_SECURE=true` in `.env` der App:

```bash
docker compose up -d api
```

Startet `api` neu. Anmeldung danach nur noch über HTTPS:
`https://rezepte.deinedomain.ch`.

## Öffentlich erreichbar

Statt nur im Tunnel ist die App dann für jeden Browser erreichbar.
Voraussetzung: «Zugriff von unterwegs» eingerichtet, Passwort mit
mindestens 12 Zeichen (sonst unter «Konto» ändern).

1. In `.env` der App `TRUSTED_PROXY=192.168.0.210/32`, dann:

   ```bash
   git pull && docker compose up -d --build
   ```

   Holt die neue Version, baut sie und startet sie neu.
2. Prüfen, ob die App echte Adressen sieht: im Heimnetz einmal mit
   falschem Passwort über `https://rezepte.deinedomain.ch` anmelden.

   ```bash
   docker compose logs api | grep "auth failure"
   ```

   Zeigt die Fehlversuche. Die Adresse muss die des Handys sein. Steht
   dort `172.…`, `TRUSTED_PROXY` wieder auskommentieren und
   `docker compose up -d web` (startet nur Caddy neu). Steht dort
   `192.168.0.210`, stimmt `TRUSTED_PROXY` nicht.
3. Infomaniak, DNS-Zone: A-Eintrag `rezepte` löschen, CNAME `rezepte`
   → `vpn.deinedomain.ch` anlegen. Folgt so der öffentlichen IP.
4. myWingo, Port-Forwarding: TCP 443 → `192.168.0.210`. Nicht 80, 81
   oder 51821.
5. NPM, Proxy Host bearbeiten: «Details» «Block Common Exploits»;
   «SSL» «Force SSL», «HSTS Enabled», «HTTP/2 Support».
6. Testen: Handy im Mobilfunk ohne Tunnel, dann im Heim-WLAN.

Geht es im Heim-WLAN nicht, leitet die Box Anfragen an die eigene
öffentliche IP nicht zurück ins Heimnetz (NAT-Loopback).

Zurück zum Tunnel: Weiterleitung 443 löschen, CNAME durch A `rezepte`
→ `192.168.0.210` ersetzen.

## Benutzer

Angelegt beim ersten Öffnen im Browser, nur aus dem Heimnetz.
Menü, «Konto»: Passwort ändern, alle Geräte abmelden.

Nach 5 Fehlversuchen innert 15 Minuten ist die Anmeldung von dieser
Adresse gesperrt, bis der älteste 15 Minuten zurückliegt. Passwort
vergessen:

```bash
docker compose exec api python -m app.cli set-password NAME
```

Fragt zweimal nach dem neuen Passwort.

```bash
docker compose exec api python -m app.cli purge-sessions
```

Meldet alle Geräte ab.

## Handy

Anmeldung gilt `SESSION_DAYS` Tage (30). Startbildschirm nur über HTTPS:

- iPhone, Safari: Teilen, «Zum Home-Bildschirm»
- Android, Chrome: Menü, «App installieren»

## Aus dem Handy-Browser speichern

Android, App installiert (siehe «Handy»): Teilen, «Rezepte».

iPhone, App «Kurzbefehle»:

1. «+», Name «Rezept speichern».
2. «i», «Im Teilen-Menü anzeigen» ein, Eingabetyp nur «URLs».
3. Aktion «URL codieren» mit «Kurzbefehl-Eingabe».
4. Aktion «URL öffnen»: `https://DOMAIN/#/import?url=`, dahinter das
   Ergebnis von Schritt 3.
5. Safari: Teilen, «Rezept speichern».

## Microsoft To Do

Einmal im [Entra admin center](https://entra.microsoft.com):

1. «App registrations», «New registration».
2. Kontotyp: persönliche Konten und Konten jeder Organisation.
3. Plattform «Mobile and desktop applications»; Redirect leer lassen,
   sonst `https://login.microsoftonline.com/common/oauth2/nativeclient`.
4. «Authentication», «Allow public client flows»: Yes.
5. «API permissions», «Microsoft Graph», «Delegated», `Tasks.ReadWrite`.

Kein Client Secret. «Application (client) ID» als `MS_CLIENT_ID` in
`.env`:

```bash
docker compose up -d api
```

```bash
docker compose exec api python -m app.cli todo-login
```

Zeigt Adresse und Code für die Anmeldung im Browser.

Die Einkaufsliste legt offene Einträge in der To-Do-Liste `TODO_LIST`
(`Einkauf`) an, vorhandene Titel nicht nochmals. Zutaten unter
`#/pantry` (Salz, Öl, …) kommen nicht auf die Einkaufsliste.

## Teilen

Je Rezept ein Link ohne Login auf die eigene Version mit Fotos;
Original, Notizen und Kochlog bleiben privat. «Link löschen» beendet
den Zugriff.

## Buchseite fotografieren

Im Import: Foto der Seite, Texterkennung (tesseract, Deutsch und
Englisch) füllt das Formular; Buch und Seite von Hand eintragen.

## Nährwerte

Pro Portion: kcal, Eiweiss, Kohlenhydrate, Fett. Im Formular; beim
Import übernommen, wenn die Seite sie liefert.

## Betrieb

Im Ordner `rezepte-app`:

```bash
docker compose ps
```

```bash
docker compose logs -f api
```

Logs von `api`; ohne Namen alle. Ctrl+C beendet.

```bash
git pull && docker compose up -d --build
```

Update; Daten bleiben, Migrationen laufen beim Start.

```bash
docker compose down
```

Stoppt. Nie `down -v`: löscht Datenbank und Fotos.

```bash
docker compose up -d
```

Startet; mit Name dahinter nur diesen Container.

## Backup

Täglich um `BACKUP_HOUR` Uhr (3, Zeitzone `TZ`) nach `./backups`:
`db-JJJJMMTT-HHMMSS.dump` und `media-JJJJMMTT-HHMMSS.tar.gz`. Löscht
Dateien älter als `BACKUP_KEEP_DAYS` Tage (14).

`./backups` regelmässig auf einen anderen Rechner kopieren:

```bash
rsync -av BENUTZER@SERVER:rezepte-app/backups/ ./rezepte-backups/
```

Sofort:

```bash
docker compose run --rm backup now
```

## Wiederherstellen

`DATUM` = Zeitstempel im Dateinamen, z. B. `20261029-030000`.

```bash
docker compose stop api
```

```bash
docker compose exec -T db pg_restore -U rezepte -d rezepte --clean --if-exists --no-owner < backups/db-DATUM.dump
```

Meldungen über nicht vorhandene Objekte sind normal.

```bash
docker compose run --rm --entrypoint tar -v "$PWD/backups:/backups" api -xzf /backups/media-DATUM.tar.gz -C /data
```

Entpackt die Fotos ins Volume.

```bash
docker compose up -d
```

## Umzug

1. Alt: `docker compose run --rm backup now`
2. `.env` und `backups/` kopieren
3. Neu: Installation, `.env` einsetzen, Wiederherstellen
4. NPM auf neue IP, alt `docker compose down`

## Entwicklung

```bash
docker compose -f compose.yaml -f compose.dev.yaml up --build
```

Code eingebunden, Auto-Reload, DB auf `localhost:5432`, API-Doku unter
`http://localhost:8080/api/docs`.

Tests:

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt && .venv/bin/pytest
```

## Fehlersuche

- Intern ja, NPM nein: Proxy Host prüfen (`http`, IP, 8080);
  `docker compose logs web`.
- Anmeldung intern geht nicht: `COOKIE_SECURE=true`, nur über HTTPS.
- Unterwegs kein Handshake in der WireGuard-App: in `zugang`
  `docker compose logs ddclient`; Port-Forwarding in myWingo prüfen.
- `rezepte.deinedomain.ch` nur im Heim-WLAN nicht gefunden: Router
  blockiert Namen auf interne Adressen (DNS-Rebind-Schutz); Tunnel
  auch zu Hause einschalten.
- Container `restarting`/`exited`: `docker compose logs NAME`.
- Passwort vergessen: `set-password`.
- «Zu viele Fehlversuche»: 15 Minuten warten. Fremde Versuche:
  `docker compose logs api | grep "auth failure"`.
- DB-Passwort ändern: zuerst in der DB,
  `docker compose exec db psql -U rezepte -c "ALTER USER rezepte PASSWORD 'NEU';"`,
  dann `.env`, dann `docker compose up -d`.
