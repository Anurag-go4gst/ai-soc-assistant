# Deployment

Docker Compose is the default local and runtime setup for this scaffold. Use `docker compose`, the Compose v2 Docker CLI plugin command.

## Current Production-Style Layout

- Public URL: `https://cisco-vai.vnudge.com`.
- Nginx site config path: `/etc/nginx/sites-available/ai-soc-assistant.conf`.
- Frontend static path: `/var/www/ai-soc-assistant/frontend/dist`.
- Backend local port: `127.0.0.1:8010`.
- Frontend dev port, if running: `127.0.0.1:3010`.
- Postgres local host port: `127.0.0.1:5434`.

Production access is intended to go through Nginx only. Docker service ports are bound to localhost so backend, frontend dev server, and Postgres are not directly exposed on public interfaces.

## Access Control

The site is publicly reachable through Nginx and protected by Basic Auth. Do not commit the real Basic Auth password to git. The backend and Postgres remain localhost-only.

## SSL Status

SSL is configured with Certbot for `cisco-vai.vnudge.com`. HTTP redirects to HTTPS.

Certbot renewal is handled by the existing `certbot.timer` systemd timer. `certbot renew --dry-run` succeeded for `cisco-vai.vnudge.com`.

## Rebuild Frontend And Reload Nginx

```bash
cd /var/www/ai-soc-assistant/frontend
npm install
npm run build

nginx -t
systemctl reload nginx
```

## Docker Restart

```bash
cd /var/www/ai-soc-assistant
docker compose up -d --build
```

## Verification Commands

```bash
dig +short cisco-vai.vnudge.com
curl -4 ifconfig.me
curl -s http://127.0.0.1:8010/health
ss -ltnp | grep -E '8010|3010|5434'
curl -I http://cisco-vai.vnudge.com
curl -I https://cisco-vai.vnudge.com
curl -I -u demo:'<password>' https://cisco-vai.vnudge.com
curl -s -u demo:'<password>' https://cisco-vai.vnudge.com/health
certbot renew --dry-run
```
