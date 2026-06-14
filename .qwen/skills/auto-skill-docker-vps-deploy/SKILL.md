---
name: docker-vps-deploy
description: Deploy code changes to a VPS running Docker Compose — rebuild containers, handle database migrations when .dockerignore blocks migration files
source: auto-skill
extracted_at: '2026-06-14T10:24:41.608Z'
---

# Deploy to Docker VPS with Database Migrations

Use when the user wants to push code changes to a production VPS running Docker Compose, including database schema migrations that cannot go through the normal Docker build because `.dockerignore` excludes the `migrations/` directory.

## The challenge

A common pattern: the Dockerfile builds a production image, and `.dockerignore` excludes `migrations/`, `scripts/`, and other development artifacts. This means SQL migration files or helper scripts are **not present** inside the running container — so you cannot simply `docker exec` to run a migration.

Solution: write a self-contained Python migration script that connects directly to the database container, copy it into the application container via `docker cp`, and execute it.

## Prerequisites

- SSH access to the VPS (host, port, password or key)
- The project uses Docker Compose with a database container (PostgreSQL or similar)
- The application container has the database driver installed (e.g., `psycopg2` for PostgreSQL, `sqlite3` for SQLite — these are often in the app's `requirements.txt`)
- Code changes are already committed and pushed to the remote git repository

## Process

### 1. Push code to git

```bash
git add -A
git commit -m "Description of changes"
git push
```

### 2. SSH into the VPS and update the code

```bash
ssh -p <PORT> root@<HOST>
cd /path/to/project
git pull
```

### 3. Rebuild and restart containers

```bash
docker compose down
docker compose up -d --build
```

Wait for containers to become healthy:

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}'
```

### 4. Check if migration file is accessible inside the container

```bash
docker exec <app-container-name> ls migrations/
```

If the file is missing (likely, due to `.dockerignore`), proceed to step 5.

### 5. Create a self-contained Python migration script

Write a Python script that:

- Connects to the database directly (using the container's internal hostname, e.g., `host="db"` for the sibling container)
- Checks which columns/tables already exist using `information_schema.columns` (PostgreSQL) or `PRAGMA table_info` (SQLite)
- Only adds missing columns — making the script **idempotent** and safe to run multiple times
- Creates indexes with `IF NOT EXISTS`

**PostgreSQL template:**

```python
"""Run database migration inside Docker container."""
import psycopg2

conn = psycopg2.connect(
    host="db",                          # Docker Compose service name
    dbname="<dbname>",
    user="<dbuser>",
    password="<dbpassword>",
)
c = conn.cursor()

# Discover existing columns
c.execute(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_name='<table>' AND table_schema='public'"
)
cols = [row[0] for row in c.fetchall()]
print("Existing columns:", cols)

# Define new columns: {name: "TYPE DEFAULT value"}
columns = {
    "new_col_1": "TEXT DEFAULT ''",
    "new_col_2": "INTEGER DEFAULT 0",
    "new_col_3": "VARCHAR(20) DEFAULT 'pending'",
}

for col, dtype in columns.items():
    if col not in cols:
        c.execute(f"ALTER TABLE <table> ADD COLUMN {col} {dtype}")
        print(f"  + Added: {col}")
    else:
        print(f"  - Exists: {col}")

# Add indexes
c.execute("CREATE INDEX IF NOT EXISTS idx_<table>_<col> ON <table>(<col>)")
conn.commit()
conn.close()
print("Migration complete!")
```

### 6. Copy script to the VPS

```bash
# From local machine
scp -P <PORT> /path/to/local/migration_script.py root@<HOST>:/tmp/
```

### 7. Copy script into the Docker container

```bash
ssh -p <PORT> root@<HOST> "docker cp /tmp/migration_script.py <app-container-name>:/tmp/"
```

### 8. Execute the migration inside the container

```bash
ssh -p <PORT> root@<HOST> "docker exec <app-container-name> python3 /tmp/migration_script.py"
```

### 9. Verify the migration

Check that the new columns were added:

```bash
ssh -p <PORT> root@<HOST> "docker exec <app-container-name> python3 -c \"
import psycopg2
conn = psycopg2.connect(host='db', dbname='<dbname>', user='<dbuser>', password='<dbpassword>')
c = conn.cursor()
c.execute(\"SELECT column_name FROM information_schema.columns WHERE table_name='<table>'\")
for row in c.fetchall(): print(row[0])
\""
```

### 10. Clean up (optional)

Remove the script from the container and VPS:

```bash
ssh -p <PORT> root@<HOST> "docker exec <app-container-name> rm /tmp/migration_script.py && rm /tmp/migration_script.py"
```

## Alternative: mount migrations as a volume

If you need to run migrations regularly, a more permanent solution is to modify `docker-compose.yml` to mount the `migrations/` directory as a bind volume:

```yaml
services:
  app:
    volumes:
      - ./migrations:/app/migrations:ro
```

Then migrations can be run directly:

```bash
docker exec <app-container-name> psql -U <dbuser> -d <dbname> -f migrations/002_something.sql
```

## Key invariants

- **Idempotency**: The migration script must check what already exists before adding — it should be safe to run multiple times.
- **Password handling**: Database passwords are often environment variables. Look for `${DB_PASSWORD:-default}` patterns in `docker-compose.yml` and `.env.production` files. Use the default or read from the env file.
- **Container hostnames**: Inside Docker Compose, containers can reach each other by service name (e.g., `db`, not `localhost` or `127.0.0.1`).
- **.dockerignore awareness**: Always check the project's `.dockerignore` before relying on any file being inside the container.
- **Connection strings**: The `DATABASE_URL` environment variable in the running container tells you exactly how the app connects — match those credentials in your migration script.

---

## Appendix: Deploying a Renamed/Rebranded Project via CI/CD

When a full project rename (codebase, Docker names, GitHub repo) happens, the VPS deploy workflow will break in multiple predictable ways. This appendix documents every failure mode and fix encountered during a real rebrand.

### The scenario

- Old project name: `servicehub` (Docker: `servicehub-app`, repo: `krzysztofzelman/servicehub`, VPS dir: `/root/servicehub`)
- New project name: `napraw_mnie` (Docker: `napraw-mnie-app`, repo: `krzysztofzelman/napraw_mnie`, VPS dir: `/root/napraw_mnie`)
- Deploy via: GitHub Actions using `appleboy/ssh-action`
- The VPS has old containers running, old `.env.production`, old repo directory

### Failure mode 1: VPS directory doesn't exist

**Error:**
```
bash: line 1: cd: /root/napraw_mnie: No such file or directory
```

**Fix:** Make the workflow self-healing — check if the new directory exists; if not, migrate from the old one:

```yaml
script: |
  if [ ! -d /root/napraw_mnie ]; then
    if [ -d /root/servicehub ]; then
      cp /root/servicehub/.env.production /root/ 2>/dev/null || true
      rm -rf /root/servicehub
    fi
    git clone <SSH-URL> /root/napraw_mnie
    if [ -f /root/.env.production ]; then
      mv /root/.env.production /root/napraw_mnie/.env.production
    fi
  fi
```

**Why this works:** The old repo is removed atomically before cloning the new one. The `.env.production` (containing production secrets) is preserved via a temp copy.

### Failure mode 2: HTTPS clone requires auth

**Error:**
```
Cloning into '/root/napraw_mnie'...
fatal: could not read Username for 'https://github.com': No such device or address
```

**Fix:** Use SSH URL (`git@github.com:user/repo.git`) instead of HTTPS. The VPS should have SSH keys registered with GitHub (they already do if the old repo was cloned via SSH).

```yaml
git clone git@github.com:krzysztofzelman/napraw_mnie.git /root/napraw_mnie
```

### Failure mode 3: Missing .env.production after migration

**Error:**
```
env file /root/napraw_mnie/.env.production not found: stat /root/napraw_mnie/.env.production: no such file or directory
```

**Cause:** If the migration logic (step 1) ran but the old repo was already deleted by a previous failed attempt, `.env.production` is lost.

**Fix:** Add a fallback that generates a minimal `.env.production` if it's missing:

```yaml
if [ ! -f .env.production ]; then
  echo "DATABASE_URL=sqlite:///./data/napraw_mnie.db" > .env.production
  echo "SECRET_KEY=change-this-to-a-long-random-secret-key-for-production" >> .env.production
  echo "SITE_URL=https://yourdomain.com" >> .env.production
  # ... remaining env vars ...
  NEW_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
  sed -i "s/SECRET_KEY=.*/SECRET_KEY=$NEW_KEY/" .env.production
  echo "Warning: .env.production created with defaults - update API keys!"
fi
```

**Warning:** This generates a **development-only** config. The user must manually restore real secrets (Stripe, SMS, SMTP) after the first successful deploy.

### Failure mode 4: YAML syntax error from heredoc

**Error:**
```
Invalid workflow file: .github/workflows/deploy.yml#L35
You have an error in your yaml syntax on line 35
```

**Cause:** GitHub Actions YAML files do not support shell heredocs (`cat << 'EOF' > file`) inside the `script:` field. The newlines and special characters break YAML parsing.

**Fix:** Never use heredocs in YAML `script:` blocks. Use `echo` for each line:
```yaml
# BAD — YAML breakage:
script: |
  cat > .env.production << 'EOF'
  KEY=value
  EOF

# GOOD — works in YAML:
script: |
  echo "KEY=value" > .env.production
  echo "KEY2=value2" >> .env.production
```

### Failure mode 5: Port already allocated (old containers persist)

**Error:**
```
Bind for 127.0.0.1:8002 failed: port is already allocated
```

**Cause:** The old project's containers (e.g., `servicehub-app`) are still running on the same port. `docker compose down` only affects containers defined in the current compose file — it does NOT stop containers from a different project name.

**Fix:** Kill anything using the port before starting:
```yaml
# Kill any Docker container publishing port 8002
docker ps -q --filter publish=8002 | xargs -r docker rm -f 2>/dev/null || true
# Kill any non-Docker process on port 8002
fuser -k 8002/tcp 2>/dev/null || true
# Then the normal compose down
docker compose down --timeout 10 2>/dev/null || true
```

**Why `fuser -k`:** It targets the specific port regardless of process type (Docker, nginx, manual Python process). It's idempotent — if nothing is using the port, it silently exits.

### The final robust deploy workflow template

Combining all fixes into a single GitHub Actions workflow:

```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1.2.2
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          port: ${{ secrets.VPS_PORT }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            # 1. Clone/migrate repo (handles project rename)
            if [ ! -d /root/NEW_PROJECT ]; then
              if [ -d /root/OLD_PROJECT ]; then
                cp /root/OLD_PROJECT/.env.production /root/ 2>/dev/null || true
                rm -rf /root/OLD_PROJECT
              fi
              git clone git@github.com:USER/NEW_PROJECT.git /root/NEW_PROJECT
              if [ -f /root/.env.production ]; then
                mv /root/.env.production /root/NEW_PROJECT/.env.production
              fi
            fi

            cd /root/NEW_PROJECT

            # 2. Generate .env.production if missing (first deploy or failed migration)
            if [ ! -f .env.production ]; then
              cat /dev/null > .env.production
              echo "DATABASE_URL=sqlite:///./data/NEW_PROJECT.db" >> .env.production
              echo "SECRET_KEY=change-this-to-a-long-random-secret-key-for-production" >> .env.production
              # ... add all required vars via echo ...
              NEW_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
              sed -i "s/SECRET_KEY=.*/SECRET_KEY=$NEW_KEY/" .env.production
              echo "Warning: .env.production created with defaults - update secrets!"
            fi

            git pull origin master

            # 3. Free the port (handles old project containers + stray processes)
            docker ps -q --filter publish=8002 | xargs -r docker rm -f 2>/dev/null || true
            fuser -k 8002/tcp 2>/dev/null || true
            docker compose down --timeout 10 2>/dev/null || true

            # 4. Build and deploy
            docker compose build app
            docker compose up -d app
```

### When this appendix applies

Use this approach whenever:
- A project has been rebranded/renamed (code + Docker + GitHub repo)
- The old project was already deployed to a VPS
- The CI/CD deploy workflow (GitHub Actions or similar) needs to survive the migration
- You cannot manually SSH into the VPS to set things up
