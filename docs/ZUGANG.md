# Zugriff von unterwegs – eingerichteter Stand

Stand 15.11.2026. Anleitung zum Aufbau: README, «Zugriff von
unterwegs». Keine Passwörter oder Tokens in dieser Datei; sie liegen im
Passwort-Manager.

## Kurzfassung für Fachleute

- Zugang nur per WireGuard (wg-easy 15.5.0) im LXC `zugang`
  (Debian 13, unprivilegiert, nesting+keyctl, `192.168.0.210/24`,
  GW `192.168.0.254`). Kernelmodul `wireguard` auf dem PVE-Host per
  `/etc/modules-load.d/wireguard.conf`.
- Router Wingo Internet-Box: einzige Weiterleitung UDP 51820 →
  `192.168.0.210`. Damit eigene öffentliche IPv4 statt geteilter.
- Client-Config: AllowedIPs `192.168.0.210/32` (Split-Tunnel nur zu
  `zugang`), DNS `9.9.9.9`, kein IPv6 im Tunnel.
- Endpoint `vpn.hus-digital.ch`: Infomaniak-DynDNS, A-Record,
  aktualisiert von ddclient (linuxserver v4.0.0-ls238,
  `protocol=infomaniak`, nur IPv4).
- `rezepte.hus-digital.ch`: statischer A-Record → `192.168.0.210`
  (privat, nur im Tunnel/LAN erreichbar).
- TLS: Nginx Proxy Manager 2.17.0 in `zugang`, Let's-Encrypt-Zertifikat
  ECDSA P-256 per DNS-01 (Infomaniak-API-Token, Scopes `domain:read`,
  `domain:write`, `dns:read`, `dns:write`). Proxy Host →
  `http://192.168.0.211:8080` (LXC `rezepte`, statisch).
- Admin-Oberflächen nur intern: NPM `:81`, wg-easy `:51821`.
- Konfiguration: `/root/zugang/compose.yaml`,
  `/root/zugang/ddclient/ddclient.conf` (chmod 600).
- Fallstricke: DynDNS-Passwort mit Sonderzeichen → HTTP 302;
  Token nur mit Scope «domain» → 403 auf `/2/zones`; Wingo-Box liefert
  für `rezepte.…` evtl. NXDOMAIN (Negativ-Cache oder Rebind-Schutz).

## Was eingerichtet ist

| Wo | Was |
| --- | --- |
| Infomaniak | Domain `hus-digital.ch` |
| Infomaniak, DNS-Zone | A `rezepte` → `192.168.0.210` |
| Infomaniak, Dynamic DNS | `vpn.hus-digital.ch`, Benutzer `rezepte-dyndns` |
| Infomaniak, API-Token | `npm-zertifikate-rezepte-app` |
| Proxmox-Host | WireGuard-Modul, Datei `/etc/modules-load.d/wireguard.conf` |
| Proxmox | Vorlage `debian-13-standard` heruntergeladen |
| Proxmox | Container `zugang`, `192.168.0.210` |
| Proxmox | Container `rezepte`: Adresse fest `192.168.0.211` statt DHCP |
| zugang | Docker; Ordner `/root/zugang` mit wg-easy, NPM, ddclient |
| myWingo | Port-Forwarding UDP 51820 → `zugang` |
| wg-easy | Admin-Benutzer; Allowed IPs `192.168.0.210/32`; DNS `9.9.9.9` |
| NPM | Admin-Benutzer; Zertifikat und Proxy Host `rezepte.hus-digital.ch` |
| Handy | App WireGuard mit Tunnel aus dem QR-Code |

## Offen

- [ ] Wingo-Box löst `rezepte.hus-digital.ch` auf (nach 1 h prüfen,
      sonst Rebind-Schutz)
- [ ] Test unterwegs: Handshake, App mit Schloss
- [ ] Schritt 10: `COOKIE_SECURE=true` in `.env` von `rezepte`
- [ ] App unter `http://192.168.0.211:8080` erreichbar (nach Wechsel)
- [ ] In NPM fehlgeschlagene Zertifikatseinträge löschen
- [ ] Alten Infomaniak-Token (nur «domain») löschen
- [ ] Proxmox-Host `192.168.0.41` liegt im DHCP-Bereich
      (`.10`–`.200`); später ausserhalb legen

## Rückgängig machen

In dieser Reihenfolge; danach ist der Zustand wie vorher.

1. **Handy:** In der WireGuard-App den Tunnel löschen, App
   deinstallieren.
2. **rezepte:** War Schritt 10 gemacht, in `/root/rezepte-app/.env`
   `COOKIE_SECURE=false` setzen, dann `docker compose up -d api`. Die
   App ist wieder unter `http://192.168.0.211:8080` erreichbar.
3. **myWingo:** Port-Forwarding-Regel UDP 51820 löschen. Der Anschluss
   fällt auf die geteilte Adresse zurück.
4. **Proxmox, zugang:** Container auswählen, «Shutdown», dann «More»,
   «Remove» (Haken bei «Purge»). Damit sind wg-easy, NPM, ddclient,
   Zertifikate und alle Schlüssel weg.
5. **Proxmox-Host**, Shell:
   `rm /etc/modules-load.d/wireguard.conf`. Das Modul ist nach dem
   nächsten Neustart nicht mehr geladen.
6. **Proxmox, Vorlage** (optional): `local`, «CT Templates»,
   `debian-13-standard` löschen.
7. **Infomaniak:** API-Token löschen; Dynamic DNS `vpn` mit Benutzer
   löschen; DNS-Eintrag A `rezepte` löschen. Domain bei Bedarf nicht
   verlängern.
8. **rezepte, Adresse** (optional): «Network», `net0`, IPv4 wieder
   «DHCP». Die Box vergibt dann wieder eine Adresse.
