# Sambot production server

## Domains
- **Primary:** https://sambot.aktechsolutions.tech/
- Legacy (still works if DNS kept): https://sambot.immigrationhorizons.com/

## VPS
- IP: `169.58.250.40`
- Portal: systemd `axealgo-portal` → `127.0.0.1:8701`
- Bot: systemd `axealgo-bot` → `127.0.0.1:8700`
- App root: `/home/botops/axealgo`

## Cloudflare DNS (required for aktech domain)
Point `sambot.aktechsolutions.tech` at this VPS:

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| A | sambot | 169.58.250.40 | Proxied (orange) or DNS only |

After DNS updates, issue SSL on the server:
```bash
sudo certbot --nginx -d sambot.aktechsolutions.tech
```

If Cloudflare is proxied, set SSL mode to **Full** (or Full Strict after certbot).

## Env
`/home/botops/axealgo/portal/.env` must include:
```
SITE_URL=https://sambot.aktechsolutions.tech
ALLOWED_HOSTS=sambot.aktechsolutions.tech,...
CSRF_TRUSTED_ORIGINS=https://sambot.aktechsolutions.tech,...
FORCE_HTTPS=true
```
