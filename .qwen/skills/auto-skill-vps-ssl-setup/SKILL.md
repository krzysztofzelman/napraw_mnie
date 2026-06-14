---
name: vps-ssl-setup
description: Set up SSL certificate + nginx configuration for a domain on a VPS via GitHub Actions CI/CD workflow, handling certbot, nginx config installation, and Docker hostname gotchas
source: auto-skill
extracted_at: '2026-06-14T11:19:46.106Z'
---

# VPS SSL Setup via GitHub Actions CI/CD

Use when you need to set up an SSL certificate (Let's Encrypt) and configure nginx for a new domain on a VPS, where the only access is via CI/CD (GitHub Actions) and you cannot SSH manually. Also applies when adding HTTPS for a new domain post-rebrand.

## The challenge

Setting up SSL on a VPS entirely through a CI/CD pipeline (no interactive SSH) is tricky because:

1. **certbot can prompt interactively** — in a non-interactive SSH session (e.g., `appleboy/ssh-action`), certbot may ask "Keep existing certificate?" and throw `EOFError`
2. **nginx runs on the host, not in Docker** — its `proxy_pass` must use `127.0.0.1:<PORT>` (host-accessible port), not the Docker internal service name (`app:8000`)
3. **Port 443 can't listen without a cert, but certbot needs nginx not to be running on port 80** — chicken-and-egg problem
4. **The workflow must be idempotent** — safe to run multiple times (cert already exists vs. first run)

## Prerequisites

- GitHub repository with GitHub Actions enabled
- VPS accessible via SSH (configured secrets: `VPS_HOST`, `VPS_USER`, `VPS_PORT`, `VPS_SSH_KEY`)
- Domain DNS pointing to the VPS IP address
- The app is already running via Docker Compose on the VPS
- nginx is installed on the VPS host (not inside Docker)

## Process

### 1. Create the setup-ssl workflow file

Create `.github/workflows/setup-ssl.yml`:

```yaml
name: Setup SSL on VPS

on:
  workflow_dispatch:

jobs:
  setup-ssl:
    runs-on: ubuntu-latest
    steps:
      - name: Setup SSL + nginx
        uses: appleboy/ssh-action@v1.2.2
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          port: ${{ secrets.VPS_PORT }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            set -e
            DOMAIN="your-domain.com"
            echo "=== 1. Create certbot directory ==="
            mkdir -p /var/www/certbot

            echo "=== 2. Stop nginx for certbot standalone ==="
            nginx -s stop 2>/dev/null || true
            sleep 1

            echo "=== 3. Get SSL certificate (standalone mode) ==="
            certbot certonly --standalone --preferred-challenges http --non-interactive \
              --email admin@your-domain.com --agree-tos --no-eff-email \
              -d "$DOMAIN" 2>&1

            echo "=== 4. Install nginx config ==="
            cp /path/to/repo/nginx.conf /etc/nginx/sites-available/$DOMAIN
            ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/$DOMAIN

            echo "=== 5. Test nginx config ==="
            nginx -t

            echo "=== 6. Start nginx ==="
            nginx

            echo "=== 7. Update SITE_URL in .env if needed ==="
            cd /path/to/repo
            if grep -q "SITE_URL" .env.production; then
              sed -i "s|SITE_URL=.*|SITE_URL=https://$DOMAIN|" .env.production
            else
              echo "SITE_URL=https://$DOMAIN" >> .env.production
            fi

            echo "=== 8. Restart app containers ==="
            docker compose down --timeout 10 2>/dev/null || true
            docker compose up -d

            echo "=== 9. Verify ==="
            curl -sf https://$DOMAIN/health && echo " - app OK" || echo " - app NOT OK"
```

### 2. Prepare nginx.conf for host-level nginx

The nginx config must use `127.0.0.1:<HOST_PORT>` (not the Docker internal service name) because nginx runs directly on the VPS host. Check `docker-compose.yml` for the port mapping (e.g., `127.0.0.1:8002:8000`).

```nginx
# HTTP — redirect to HTTPS
server {
    listen 80;
    server_name your-domain.com;
    server_tokens off;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS
server {
    listen 443 ssl;
    server_name your-domain.com;
    server_tokens off;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    location / {
        proxy_pass http://127.0.0.1:<HOST_PORT>;  # NOT app:8000
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    location /static/ {
        proxy_pass http://127.0.0.1:<HOST_PORT>;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 3. Trigger and verify

```bash
# Push the workflow file and nginx.conf to GitHub
git add .github/workflows/setup-ssl.yml nginx.conf
git commit -m "Add SSL setup workflow"
git push origin master

# Trigger the workflow
gh workflow run setup-ssl.yml

# Wait and check status
gh run list --workflow="setup-ssl.yml"

# Verify HTTPS works
curl -s https://your-domain.com/health
```

## Common failure modes and fixes

### Failure Mode 1: certbot interactive prompt (EOFError)

**Error in logs:**
```
Select the appropriate number [1-2] then [enter] (press 'c' to cancel):
An unexpected error occurred: EOFError
```

**Cause:** Certbot already has a valid certificate for this domain and asks "Keep existing or renew?" — it expects interactive input.

**Fix:** Add `--non-interactive` flag. This tells certbot to keep the existing certificate silently if it isn't due for renewal:
```bash
certbot certonly --standalone --non-interactive --agree-tos --no-eff-email -d "$DOMAIN"
```

### Failure Mode 2: nginx cannot resolve upstream "app" (Docker hostname)

**Error:**
```
nginx: [emerg] host not found in upstream "app" in /etc/nginx/sites-enabled/domain.com:29
```

**Cause:** `proxy_pass http://app:8000` uses `app` which is a Docker Compose service name — only resolvable inside the Docker network. nginx runs on the VPS host directly, not inside Docker.

**Fix:** Use the host-accessible port (`127.0.0.1:<HOST_PORT>`). Find the port mapping in `docker-compose.yml`:
```yaml
ports:
  - "127.0.0.1:8002:8000"  # HOST:CONTAINER
```
Then use `proxy_pass http://127.0.0.1:8002;` in nginx.conf.

### Failure Mode 3: certbot webroot mode serves wrong site

**Error in LE validation:** Let's Encrypt checks `http://domain.com/.well-known/acme-challenge/TOKEN` but gets the HTML of a completely different website (e.g., a portfolio site also running on port 80).

**Cause:** The VPS has another nginx server block (default or another domain) that catches requests before the certbot webroot location can serve the challenge file. This happens especially when nginx has a `default_server` or a `server_name _` catch-all block for a different project.

**Fix:** Use `--standalone` mode instead of `--webroot`. This stops nginx, starts certbot's own temporary HTTP server on port 80, completes the ACME challenge, then you restart nginx afterward.

```bash
nginx -s stop
certbot certonly --standalone --preferred-challenges http --non-interactive \
  --email admin@domain.com --agree-tos -d "$DOMAIN"
# Then install nginx config and restart
```

### Failure Mode 4: Old SSL cert paths in nginx.conf

**Error:** nginx -t fails or HTTPS serves the wrong content.

**Cause:** The nginx.conf file references the old domain's SSL cert paths (e.g., `/etc/letsencrypt/live/old-domain.com/...`).

**Fix:** Ensure the nginx.conf has the correct domain in:
- `server_name` directive
- `ssl_certificate` and `ssl_certificate_key` paths (they include the domain name)
- The `return 301 https://$host$request_uri` (uses `$host` dynamically, not hardcoded domain)

### Failure Mode 5: certbot needs packages installed

**Error:**
```
-bash: certbot: command not found
```

**Fix:** Install certbot on first run (add to the workflow before the certbot call):
```bash
apt-get update && apt-get install -y certbot python3-certbot-nginx 2>/dev/null || true
```

## Design decisions

### Why appleboy/ssh-action instead of a self-hosted runner?

- **No setup required** — the action uses SSH to the VPS directly, no runner installation
- **Works with any VPS** — no need to install GitHub Actions runner software
- **Secrets stay in GitHub** — SSH key never leaves the GitHub secrets store
- **Transient** — the runner is ephemeral, no persistent agent on the VPS

### Why standalone mode over webroot?

| Aspect | webroot | standalone |
|--------|---------|------------|
| Requires nginx running | Yes (serving from a known dir) | No (takes port 80) |
| Works with multiple server blocks | Only if the correct `server_name` block is active | Always works |
| Needs configuration | Must add `location /.well-known/` to nginx config | None (zero-config) |
| Service interruption | None (nginx stays up) | Brief (nginx stops for ~5s) |
| Complexity | Low if nginx is well-configured | Lower |

Use **standalone** when:
- The VPS has multiple websites/domains
- certbot webroot validation fails due to wrong server block answering
- You don't know the exact nginx site configuration state

Use **webroot** when:
- nginx is well-configured with only one site
- You want zero downtime
- The webroot directory is accessible from the correct server block

### Why keep nginx on the host and not inside Docker?

- **Simpler SSL management** — certbot runs on the host, writes certs to `/etc/letsencrypt/`
- **Separation of concerns** — nginx is a reverse proxy, not an application concern
- **No Dockerfile changes** — the app image doesn't need nginx
- **Cert renewal** — systemd timers/cron handle renewal without touching containers

## When to use this skill

- Setting up HTTPS for a new domain on a VPS
- After renaming/re branding a project (new domain needs SSL)
- Migrating a domain from one VPS project to another
- Setting up a CI/CD pipeline for SSL that's fully automated (no manual SSH)
