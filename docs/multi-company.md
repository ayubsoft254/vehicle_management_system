# Multi-company platform: setup and switch-over runbook

The app can run in two modes, chosen by `MULTI_TENANT` in `.env`:

| | `MULTI_TENANT=False` (default) | `MULTI_TENANT=True` |
|---|---|---|
| Companies | one | many, each in its own PostgreSQL schema |
| Database | SQLite or PostgreSQL | PostgreSQL only |
| Company chosen by | — | the web address of the request |
| Control panel | — | `https://<PLATFORM_DOMAIN>/` (platform owners) |

Everything a company configures itself (name, logo, colours, currency, M-Pesa, bank accounts, letterhead, agreement terms) is in **Settings → Company & Branding** inside that company, in both modes.

After the switch-over below, creating a company is a form in the control panel. The only steps that still need server or DNS access are the one-time wildcard DNS and certificate, and DNS/certificates for any custom domain.

---

## 1. Before you start

1. **Company Settings (Phase A) must already be live on every stack being moved** (Hoza and Taifa), so each database already has its own company profile. Check: open Settings → Company & Branding on each site and confirm the details are right.
2. `FIELD_ENCRYPTION_KEY` is set in `.env`, and the same value is used everywhere the database is used. Saved M-Pesa secrets can't be read without it.
3. Fresh backups of every database **and** the `media/` folder.
4. Pick the platform domain, e.g. `vmsplatform.co.ke`. New companies get `<name>.vmsplatform.co.ke`.

## 2. DNS and HTTPS (one time)

**DNS** (at the platform domain's DNS provider):

```
vmsplatform.co.ke      A   <server IP>
*.vmsplatform.co.ke    A   <server IP>
```

**Wildcard certificate.** Let's Encrypt needs a DNS challenge for wildcards. Use your DNS provider's certbot plugin, e.g. Cloudflare:

```
sudo certbot certonly --dns-cloudflare --dns-cloudflare-credentials /root/cf.ini \
     -d vmsplatform.co.ke -d '*.vmsplatform.co.ke'
```

Without a plugin you can use `--manual --preferred-challenges dns`, but then renewals are manual every 90 days. A plugin is strongly recommended.

**nginx.** Copy the existing HTTPS `server { … }` block and change three lines. Keep the `/static/`, `/media/` and `location /` proxy sections as they are:

```
server_name vmsplatform.co.ke *.vmsplatform.co.ke;
ssl_certificate     /etc/letsencrypt/live/vmsplatform.co.ke/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/vmsplatform.co.ke/privkey.pem;
```

- `proxy_set_header Host $host;` **must** stay, because the app picks the company from the Host header.
- Don't enable Django's `USE_X_FORWARDED_HOST`. The current config sends `X-Forwarded-Host $server_name`, which under a wildcard `server_name` is the pattern, not the real host.
- Keep the existing `hozacars.com` and `taifaassist.xyz` server blocks. Point their `proxy_pass` at the same app container.

**Custom domain for a company** (repeat per domain):
1. In the control panel, open the company, then add the address under *Web addresses*.
2. The company points the domain's DNS (CNAME or A) at the server.
3. Issue a certificate, e.g. `sudo certbot --nginx -d portal.acme.co.ke`, and add a server block for it (same proxy settings).
4. In that company's Settings → Payments, update the M-Pesa callback URLs to the new address and register them with Safaricom. **Daraja registers URLs once per shortcode, so get them right before registering.**

## 3. `.env` for multi-company mode

```
MULTI_TENANT=True
PLATFORM_DOMAIN=vmsplatform.co.ke
PLATFORM_NAME=VMS Platform
PLATFORM_SCHEME=https
DATABASE_URL=postgresql://…           # unchanged
FIELD_ENCRYPTION_KEY=…                # unchanged
```

`ALLOWED_HOSTS` is not used in this mode. Any address that isn't registered to a company gets a 404 before any app code runs.

## 4. Rehearse on a copy first

Do sections 5 and 6 on a **restored copy of the production database**, on a staging server or a local PostgreSQL, before touching production. The same steps were rehearsed during development on a synthetic copy. The checklist at the end of section 5 must pass on your copy too.

## 5. Moving Hoza (data stays in place)

Downtime: about 10 minutes. Times assume one app container plus a Celery worker and beat.

```bash
# 0. Maintenance window: stop the app, worker and beat (keep the db running)
docker-compose stop web celery celery-beat

# 1. Backups
pg_dump -Fc "$DATABASE_URL" > hoza-before-tenancy.dump
tar czf media-before-tenancy.tgz media/
# Keep the beat schedule to restore later
pg_dump --data-only -t 'django_celery_beat_*' "$DATABASE_URL" > beat-schedule.sql

# 2. Hoza's tables move into their own schema; an empty "public" becomes the platform
psql "$DATABASE_URL" -c 'ALTER SCHEMA public RENAME TO hoza; CREATE SCHEMA public;'

# 3. Deploy the new code with MULTI_TENANT=True (section 3), but don't start the app
#    containers until step 2 is done: their entrypoint runs `migrate`, which in
#    this mode migrates the platform schema and every registered company. Then:
python manage.py migrate_schemas --shared
psql "$DATABASE_URL" -c 'SET search_path TO public' -f beat-schedule.sql
python manage.py wrap_periodic_tasks            # periodic jobs now run once per company
python manage.py setup_platform --owner-email you@example.com   # prints a password once
python manage.py register_company --schema hoza --name "HOZA INVESTMENT (K) LIMITED" \
       --domain hozacars.com --domain www.hozacars.com
python manage.py migrate_schemas --schema=hoza  # should report nothing (or only no-op) to apply

# 4. Uploaded files move under media/hoza/ (uploads are now kept per company)
mkdir -p media/hoza && find media -mindepth 1 -maxdepth 1 ! -name hoza -exec mv {} media/hoza/ \;

# 5. Start everything
docker-compose up -d
```

**Checklist (also run on the rehearsal copy):**
- [ ] `https://hozacars.com` loads, an existing user can log in, and the dashboard and payments show the usual figures.
- [ ] A receipt PDF, a sales agreement PDF and a client statement download correctly, with the letterhead.
- [ ] Vehicle photos and documents open, which confirms the media move.
- [ ] Settings → Company & Branding shows Hoza's details, and Payments still shows the server M-Pesa values.
- [ ] An M-Pesa C2B test payment to 4320049 appears in the Paybill Tracker.
- [ ] `https://<PLATFORM_DOMAIN>/` shows the control panel and lists Hoza.
- [ ] A made-up address such as `https://nobody.<PLATFORM_DOMAIN>/` returns 404.

**Rollback (before customers use the new setup):**
```bash
docker-compose stop web celery celery-beat
psql "$DATABASE_URL" -c 'ALTER SCHEMA public RENAME TO platform_unused; ALTER SCHEMA hoza RENAME TO public;'
mv media/hoza/* media/ && rmdir media/hoza
# set MULTI_TENANT=False and redeploy the previous image
docker-compose up -d
```

## 6. Moving Taifa onto the same server

Taifa currently runs its own stack and database. Its data is copied into a schema called `taifa`. Until you are ready, Taifa can stay on its own stack.

```bash
# On Taifa's server
pg_dump -Fc "$TAIFA_DATABASE_URL" > taifa.dump
tar czf taifa-media.tgz media/

# On the platform server: restore into a scratch DB, rename the schema, copy it across
createdb taifa_tmp && pg_restore -d taifa_tmp taifa.dump
psql taifa_tmp -c 'ALTER SCHEMA public RENAME TO taifa;'
pg_dump -Fc -n taifa taifa_tmp > taifa-schema.dump
pg_restore -d "$DATABASE_URL" taifa-schema.dump
dropdb taifa_tmp

python manage.py register_company --schema taifa --name "Taifa Assist" --domain taifaassist.xyz
python manage.py migrate_schemas --schema=taifa
mkdir -p media/taifa && tar xzf taifa-media.tgz -C media/taifa --strip-components=1
```

> **M-Pesa warning.** On its own stack, Taifa read its M-Pesa keys from its own `.env`, so its profile has *Use the server's M-Pesa settings* switched on. On the shared server, that `.env` is Hoza's. **Before Taifa takes payments on the shared server**, sign in to Taifa, open Settings → Company & Branding → Payments, enter Taifa's paybill, keys and callback URLs, untick *Use the server's M-Pesa settings for blank fields*, and save. The option can only be switched off there, never back on.
> Taifa's callback URLs already registered with Safaricom point at `taifaassist.xyz`, which still routes to Taifa, so they keep working.

Then point `taifaassist.xyz` DNS at the platform server, and add its nginx server block and certificate (section 2).

## 7. Creating a new company (no server access needed)

Control panel → **New company**: enter the name, sub-address, country and first admin's email. Setup runs in the background (about 1–2 minutes) with progress shown on the page. It:

- creates the company's schema and runs all migrations;
- sets up roles and permissions;
- applies the country's currency, time zone and number formats, and generic agreement terms;
- creates a starter bank-account channel;
- creates the admin user and emails them a set-password link.

If the email doesn't arrive, use **Re-send admin sign-in link**. If setup fails, the error is shown on the page, and **Retry setup** is safe to run again. Without a Celery worker, setup runs inside the web process instead. You can also run it by hand: `python manage.py provision_company <schema>`.

**Support access:** *Open as company* signs you in to that company as its admin. The link is valid for 2 minutes and works only for that company, and the sign-in is recorded in both the platform's audit log and the company's own.

**Suspend** locks the company's users out with a "temporarily unavailable" page. M-Pesa callbacks are still accepted, so customer payments aren't lost.

## 8. Local development

- `MULTI_TENANT=False` keeps working on SQLite as before.
- Multi-company mode needs PostgreSQL. Run the compose `db` service, or any local PostgreSQL, with:
  ```
  DATABASE_URL=postgresql://vms_user:vms_password@localhost:5432/vms_db
  MULTI_TENANT=True
  PLATFORM_DOMAIN=platform.localhost
  PLATFORM_SCHEME=http
  ```
  `*.localhost` resolves to your machine in modern browsers, so `http://platform.localhost:8000/` is the panel and `http://acme.platform.localhost:8000/` is a company.

## 9. Known limitations

- **Files in `/media/` are served straight by nginx**, so anyone who knows a file's exact URL can download it from any host. This is the same as today. Restricting it per company would need nginx to map host → schema, or signed URLs.
- **Payroll statutory deductions** (PAYE, NHIF, NSSF) are implemented for Kenya only. Companies in other countries enter tax, pension and insurance as manual employee deductions.
- **Each company has its own users.** Someone who works for two companies needs an account in each.
