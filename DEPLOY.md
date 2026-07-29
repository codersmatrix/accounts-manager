# Deploy Accounts Manager

## Option A — Heroku (recommended)

Heroku works well with this Flask app. Use **Postgres** (free/eco dyno + Essential-0 database or hobby tier depending on current Heroku plans).

### Prerequisites

- [Heroku account](https://signup.heroku.com/)
- [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli) installed
- [Git](https://git-scm.com/) installed

### Steps

1. **Unzip and enter the project**
   ```bash
   unzip accounts_app.zip
   cd accounts_app
   ```

2. **Initialize Git (if needed)**
   ```bash
   git init
   git add .
   git commit -m "Accounts Manager app"
   ```

3. **Create Heroku app**
   ```bash
   heroku login
   heroku create your-app-name   # e.g. my-accounts-manager
   ```

4. **Add Postgres**
   ```bash
   heroku addons:create heroku-postgresql:essential-0
   # or the current free/lowest tier available in your region
   ```
   This sets `DATABASE_URL` automatically.

5. **Set config vars (secrets & email)**
   ```bash
   heroku config:set SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"

   # Optional – email reminders
   heroku config:set MAIL_USERNAME="you@gmail.com"
   heroku config:set MAIL_PASSWORD="your-gmail-app-password"
   heroku config:set MAIL_DEFAULT_SENDER="you@gmail.com"
   # optional:
   # heroku config:set MAIL_SERVER=smtp.gmail.com
   # heroku config:set MAIL_PORT=587
   ```

6. **Deploy**
   ```bash
   git push heroku main
   # If your branch is master:
   # git push heroku master
   ```

7. **Open the app**
   ```bash
   heroku open
   ```

8. **Check logs if something fails**
   ```bash
   heroku logs --tail
   ```

### Local development after deploy changes

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py              # still uses SQLite locally when DATABASE_URL is unset
```

---

## Option B — Vercel (possible, but limited)

Vercel is built for serverless functions. A traditional Flask + SQLAlchemy + login session app has limitations:

| Issue | Impact |
|--------|--------|
| Ephemeral filesystem | SQLite is wiped on every deploy / cold start |
| Serverless | No long-lived process; cold starts; 10s–60s timeouts |
| Sessions / cookies | Work only if configured carefully |
| Database | You **must** use an external DB (e.g. Neon, Supabase, PlanetScale Postgres) |

### Minimal Vercel approach

1. Use an external Postgres (e.g. [Neon](https://neon.tech) free tier) and set `DATABASE_URL`.
2. Add `vercel.json`:
   ```json
   {
     "version": 2,
     "builds": [
       { "src": "app.py", "use": "@vercel/python" }
     ],
     "routes": [
       { "src": "/(.*)", "dest": "app.py" }
     ]
   }
   ```
3. Install Vercel CLI: `npm i -g vercel`
4. In project folder: `vercel` and follow prompts.
5. Set environment variables in Vercel dashboard: `SECRET_KEY`, `DATABASE_URL`, mail vars.

**Recommendation:** Prefer **Heroku** (or Render / Railway / Fly.io) for this app. Use Vercel only if you already rely on it and use external Postgres.

---

## Alternative free hosts (similar to Heroku)

- **[Render](https://render.com)** – Web Service + free Postgres; use the same `Procfile` / `gunicorn`
- **[Railway](https://railway.app)** – Connect GitHub repo; set env vars
- **[Fly.io](https://fly.io)** – `fly launch` with the same Dockerfile-free Python setup

On all of these: set `SECRET_KEY`, `DATABASE_URL` (or their Postgres addon), and optional mail variables.

---

## Docker

### Build & run (SQLite)

```bash
cd accounts_app
cp .env.example .env   # set SECRET_KEY
docker compose up --build
```

Open **http://localhost:8000**

Data is stored in the `app-data` volume (`/app/instance` in the container).

### Run with Postgres

```bash
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up --build
```

### Plain Docker (no Compose)

```bash
docker build -t accounts-manager .
docker run -d --name accounts \
  -p 8000:8000 \
  -e SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')" \
  -v accounts-data:/app/instance \
  accounts-manager
```

### Deploy image to a host / registry

```bash
docker build -t your-registry/accounts-manager:latest .
docker push your-registry/accounts-manager:latest
```

On the server, pull and run with the same env vars (`SECRET_KEY`, optional `DATABASE_URL`, `MAIL_*`).

### Notes

- Container runs as non-root user `appuser`
- Healthcheck probes `http://127.0.0.1:8000/`
- Gunicorn: 2 workers × 4 threads (tune via Dockerfile `CMD` if needed)

---

## Security (public deployment checklist)

1. **Set a strong `SECRET_KEY`** (required in production; min 32 characters).
2. **Serve only over HTTPS** and keep `SESSION_COOKIE_SECURE=true` / `FORCE_HTTPS=true`.
3. Prefer **Postgres** over SQLite for multi-user / durable storage.
4. Optionally set `ALLOW_REGISTRATION=false` after creating your account.
5. Configure SMTP with an **app password**, never your main mailbox password.
6. For multiple gunicorn workers, set `RATELIMIT_STORAGE_URI` to Redis so rate limits are shared.
7. Keep dependencies updated (`pip install -U -r requirements.txt`).

The app includes: CSRF protection, secure session cookies, rate-limited login/register,
security headers (CSP, HSTS, X-Frame-Options), IDOR-safe ownership checks, input validation,
and generic error pages (no stack traces).
