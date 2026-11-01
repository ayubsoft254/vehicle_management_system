# Deploying the multi-company platform on a new server

This guide sets up a **fresh** Ubuntu 24.04 server running the app in multi-company mode (`MULTI_TENANT=True`), from an empty server to a working control panel where you create companies.

- The control panel is at `https://<platform domain>/`.
- Each company gets its own address, `https://<company>.<platform domain>/`, and its own PostgreSQL schema.

To move an existing single-company database (Hoza or Taifa) onto the platform, follow [multi-company.md](multi-company.md) sections 4–6 instead of section 6 below.

---

## 0. Values used in this guide

Every command below uses these shell variables. Set them at the start of **each** SSH session, with your own values:

```bash
export DOMAIN=test.taifaassist.xyz                    # platform domain (control panel address)
export APP_DIR=/home/$USER/vehicle_management_system  # where the code is cloned
export OWNER_EMAIL=you@example.com                    # platform owner login + Let's Encrypt contact
```

Companies will be at `https://<name>.$DOMAIN`, for example `https://acme.test.taifaassist.xyz`.

---

## 1. DNS

At the DNS provider for the domain, create two records pointing at the server's public IP:

| Type | Name | Value |
|---|---|---|
| A | `test.taifaassist.xyz` (the platform domain) | server IP |
| A | `*.test.taifaassist.xyz` (every company under it) | server IP |

Check both records from the server. Each command must print the server IP:

```bash
dig +short $DOMAIN
dig +short anything.$DOMAIN
```

---

## 2. Server packages

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl dnsutils ca-certificates openssl \
    nginx docker.io docker-compose-v2 \
    certbot python3-certbot-nginx

sudo systemctl enable --now docker
sudo systemctl enable --now nginx

# Run docker without sudo (log out and back in afterwards, or run `newgrp docker`)
sudo usermod -aG docker $USER
newgrp docker
```

Firewall, if UFW is enabled:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

---

## 3. Get the code (the `tenancy` branch)

```bash
cd /home/$USER
git clone https://github.com/ayubsoft254/vehicle_management_system.git
cd $APP_DIR
git checkout tenancy
git pull
```

---

## 4. `.env`

```bash
cd $APP_DIR
cp .env.example .env

# Generate the two secrets and print them
echo "SECRET_KEY=$(openssl rand -base64 48 | tr -d '\n=+/')"
echo "FIELD_ENCRYPTION_KEY=$(openssl rand -base64 32 | tr '+/' '-_')"

nano .env
```

Set at least the following in `.env`. Paste in the two generated values, and replace each `change-…` placeholder with a real password:

```ini
SECRET_KEY=<generated above>
FIELD_ENCRYPTION_KEY=<generated above>
DEBUG=False

DB_NAME=vms_db
DB_USER=vms_user
DB_PASSWORD=change-this-strong-password
DATABASE_URL=postgresql://vms_user:change-this-strong-password@db:5432/vms_db
REDIS_URL=redis://redis:6379/0

# New company admins receive their sign-in link by email, so this must work
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-gmail@gmail.com
EMAIL_HOST_PASSWORD=your-gmail-app-password
DEFAULT_FROM_EMAIL=your-gmail@gmail.com

# Multi-company mode
MULTI_TENANT=True
PLATFORM_DOMAIN=test.taifaassist.xyz
PLATFORM_NAME=VMS Platform
PLATFORM_SCHEME=https
```

> **Keep `FIELD_ENCRYPTION_KEY` safe and never change it.** It encrypts every company's saved M-Pesa keys. If it is lost or changed, those keys can't be read.
>
> **Don't copy another server's M-Pesa keys or `.env` here.** On a test server, leave the `MPESA_*` values empty, and never press *Register Callbacks* with a live paybill.

---

## 5. Folders and permissions (static and media)

nginx runs on the host as `www-data` and serves `/static/` and `/media/` straight from the project folder. The app container runs as `appuser` (UID 1000) and writes into those folders. Both users need access.

**Ubuntu 24.04 creates home folders as `750`, so nginx can't enter them.** That makes every static file return **403 Forbidden**. The usual sign is that the currency pickers become plain single-choice boxes instead of tick-box lists.

```bash
cd $APP_DIR
mkdir -p src/static_collected src/media

# 1. The container (UID 1000) must be able to write collected static files and uploads
sudo chown -R 1000:1000 src/static_collected src/media

# 2. nginx (www-data) must be able to pass through every folder on the way...
sudo chmod o+x /home/$USER $APP_DIR $APP_DIR/src

# 3. ...and read the files
sudo chmod -R o+rX $APP_DIR/src/static_collected $APP_DIR/src/media
```

`o+x` on a folder only lets other users *pass through* it. They can't list or read anything else in your home folder.

Run step 3 again after section 6, once the static files have been collected.

---

## 6. Start the app

```bash
cd $APP_DIR
docker compose up -d --build
docker compose logs -f web      # wait for "Booting worker", then press Ctrl+C
```

On start, the `web` container:
- creates the platform schema (in this mode `migrate` covers the platform and every company);
- collects the static files;
- creates the cache table.

Then do the one-time platform setup:

```bash
# Register the control-panel address and create the platform owner.
# The password is printed ONCE, so copy it now.
docker compose exec web python manage.py setup_platform --owner-email $OWNER_EMAIL

# Re-apply read permission now that the static files exist
sudo chmod -R o+rX $APP_DIR/src/static_collected $APP_DIR/src/media
```

Check that all five containers are `Up` or `healthy`: `db`, `redis`, `web`, `celery_worker` and `celery_beat`.

```bash
docker compose ps
curl -s -o /dev/null -w "%{http_code}\n" -H "Host: $DOMAIN" http://127.0.0.1:3333/health/   # 200
```

> If you add periodic tasks later (Django admin → Periodic tasks), run
> `docker compose exec web python manage.py wrap_periodic_tasks`
> so that each task runs once per company instead of only on the platform.

---

## 7. HTTPS certificate (certbot)

The certificate must cover the platform domain **and** each company address under it. Choose **one** option.

First, create the folder Let's Encrypt uses for its HTTP check:

```bash
sudo mkdir -p /var/www/certbot
```

### Option A: wildcard certificate with Cloudflare DNS (recommended if the domain is on Cloudflare)

One certificate covers every company, present and future, and renews automatically.

```bash
sudo apt install -y python3-certbot-dns-cloudflare

# Cloudflare dashboard → My Profile → API Tokens → "Edit zone DNS" template, limited to this zone
sudo mkdir -p /root/.secrets
sudo bash -c 'echo "dns_cloudflare_api_token = PASTE_TOKEN_HERE" > /root/.secrets/cloudflare.ini'
sudo chmod 600 /root/.secrets/cloudflare.ini

sudo certbot certonly --dns-cloudflare \
    --dns-cloudflare-credentials /root/.secrets/cloudflare.ini \
    --dns-cloudflare-propagation-seconds 30 \
    -m $OWNER_EMAIL --agree-tos --no-eff-email \
    --cert-name $DOMAIN -d $DOMAIN -d "*.$DOMAIN"
```

Other DNS providers have similar plugins, for example `python3-certbot-dns-digitalocean` and `python3-certbot-dns-route53`. List them with `apt search certbot-dns`.

### Option B: wildcard certificate, manual DNS record (any DNS provider)

```bash
sudo certbot certonly --manual --preferred-challenges dns \
    -m $OWNER_EMAIL --agree-tos --no-eff-email \
    --cert-name $DOMAIN -d $DOMAIN -d "*.$DOMAIN"
```

certbot asks you to create a TXT record named `_acme-challenge.<domain>`. Create it at your DNS provider, wait a minute, and check it from a second terminal:

```bash
dig +short TXT _acme-challenge.$DOMAIN
```

Then press Enter in certbot. **This certificate does not renew by itself.** Repeat this command every ~80 days.

### Option C: one certificate listing each company (no DNS access needed)

This option uses HTTP checks only. Every time you create a company, add its address to the certificate.

Do sections 8 and 9 first, so nginx is answering on port 80, then run:

```bash
# First time: the platform address only
sudo certbot certonly --webroot -w /var/www/certbot \
    -m $OWNER_EMAIL --agree-tos --no-eff-email \
    --cert-name $DOMAIN -d $DOMAIN

# After creating each company, re-run with the FULL list of addresses (--expand adds them)
sudo certbot certonly --webroot -w /var/www/certbot --expand \
    --cert-name $DOMAIN -d $DOMAIN -d acme.$DOMAIN -d globex.$DOMAIN
sudo systemctl reload nginx
```

For option C, keep the HTTPS server block (section 8) commented out until the first certificate has been issued.

### Check renewal (all options)

```bash
sudo certbot certificates
sudo certbot renew --dry-run
sudo systemctl list-timers | grep certbot
# Reload nginx after every renewal so it picks up the new certificate
echo -e '#!/bin/sh\nsystemctl reload nginx' | sudo tee /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
```

---

## 8. nginx

The app picks the company from the web address, so nginx must pass the real `Host` through. Write the site config. It uses the `$DOMAIN` and `$APP_DIR` you set in section 0:

```bash
sudo tee /etc/nginx/sites-available/vms-platform > /dev/null <<EOF
# HTTP: Let's Encrypt checks, everything else to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN *.$DOMAIN;

    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 301 https://\$host\$request_uri; }
}

# HTTPS: platform + every company
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name $DOMAIN *.$DOMAIN;

    ssl_certificate     /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    access_log /var/log/nginx/vms-platform.access.log;
    error_log  /var/log/nginx/vms-platform.error.log warn;

    add_header X-Frame-Options        "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy        "strict-origin-when-cross-origin" always;

    client_max_body_size 100M;
    proxy_read_timeout   120s;

    location /static/ {
        alias $APP_DIR/src/static_collected/;
        expires 30d;
        add_header Cache-Control "public, immutable";
        try_files \$uri =404;
    }

    location /media/ {
        alias $APP_DIR/src/media/;
        expires 7d;
        try_files \$uri =404;
    }

    location / {
        proxy_pass         http://127.0.0.1:3333;
        proxy_http_version 1.1;
        proxy_set_header   Host              \$host;
        proxy_set_header   X-Real-IP         \$remote_addr;
        proxy_set_header   X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_redirect     off;
    }
}
EOF
```

Notes:
- `proxy_set_header Host $host` is required, because it is how the app finds the company.
- **Don't** send `X-Forwarded-Host $server_name`, as the old single-site config did. With a wildcard `server_name`, that header contains the pattern (`*.domain`), not the real address.
- The `options-ssl-nginx.conf` and `ssl-dhparams.pem` files come from the `python3-certbot-nginx` package. If they are missing, create them:
  ```bash
  sudo curl -so /etc/letsencrypt/options-ssl-nginx.conf https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/src/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf
  sudo openssl dhparam -out /etc/letsencrypt/ssl-dhparams.pem 2048
  ```

Enable the site:

```bash
sudo ln -sf /etc/nginx/sites-available/vms-platform /etc/nginx/sites-enabled/vms-platform
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

---

## 9. Verify

```bash
# Static files are served (403 means section 5 permissions, 404 means the alias path or collectstatic)
curl -sI https://$DOMAIN/static/js/multi_currency.js | head -1        # HTTP/2 200

# nginx itself can read the file
sudo -u www-data stat $APP_DIR/src/static_collected/js/multi_currency.js

# Control panel
curl -s -o /dev/null -w "%{http_code}\n" https://$DOMAIN/              # 200 or 302

# Unknown company addresses are rejected
curl -s -o /dev/null -w "%{http_code}\n" https://nobody.$DOMAIN/       # 404
```

In the browser:
1. Open `https://<DOMAIN>/` and sign in as the platform owner with the password from section 6.
2. Click **New company**. Enter the name, the sub-address (for example `acme`), the country and the admin's email. Setup takes 1–2 minutes and shows its progress on the page.
3. The admin receives an email with a set-password link to `https://acme.<DOMAIN>/`. If it doesn't arrive, use **Re-send admin sign-in link**.
4. In the company, open **Settings → Company & Branding** and set the logo, colours, contacts, currencies, bank accounts and M-Pesa.
5. On the dashboard, the **Currency** picker should be a tick-box list. If it's a plain dropdown, the currency script isn't loading. Go back to the first check above.

Option C only: add each new company's address to the certificate (section 7C) before the company uses its site.

---

## 10. Updating to newer code

```bash
cd $APP_DIR
git pull
docker compose up -d --build                 # migrates every company + collects static
sudo chmod -R o+rX $APP_DIR/src/static_collected $APP_DIR/src/media
```

Then do a hard refresh (Ctrl+F5) in the browser, so it loads the new scripts.

---

## 11. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `/static/...` returns **403** | nginx can't enter the home folder (Ubuntu 24.04 `750`) | Section 5, steps 2–3 |
| `/static/...` returns **404** | wrong `alias` path in nginx, or static files not collected | `sudo grep -rn alias /etc/nginx/sites-enabled/`, then `docker compose exec web python manage.py collectstatic --noinput` |
| `PermissionError` during collectstatic | `static_collected` isn't owned by UID 1000 | `sudo chown -R 1000:1000 $APP_DIR/src/static_collected $APP_DIR/src/media` |
| Currency box only allows one currency | the static JS isn't loading | the two rows above |
| Company address shows nginx's default page or a certificate error | the wildcard DNS record or the certificate doesn't cover it | Sections 1 and 7 |
| Every company address returns 404 | `Host` isn't passed through, or `PLATFORM_DOMAIN` is wrong | Section 8 `proxy_set_header Host $host`; check `.env` |
| New company stuck on "Creating the company database" | `celery_worker` isn't running | `docker compose ps`, then `docker compose logs celery_worker` |
| Admin never received the email | SMTP settings | check `EMAIL_*` in `.env`, then use **Re-send admin sign-in link** |

Useful commands:

```bash
docker compose logs -f web
docker compose logs -f celery_worker
docker compose exec web python manage.py provision_company <schema>   # re-run a company's setup by hand
sudo tail -f /var/log/nginx/vms-platform.error.log
```

## Rolling back

This server is separate from Taifa Assist, so nothing here affects it. To return this server to single-company mode, set `MULTI_TENANT=False` in `.env`, check out `main`, and run `docker compose up -d --build` with a **fresh** database. A multi-company database can't be used in single-company mode.
