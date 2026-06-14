---
name: codebase-rename
description: Systematically find and replace a brand name, identifier, or phrase across an entire codebase with categorization of what to change vs keep
source: auto-skill
extracted_at: '2026-06-14T10:37:26.842Z'
---

# Codebase-Wide Rename (Brand/Term Replacement)

Use when the user wants to rename a brand, project name, term, or identifier across the entire codebase — find every occurrence, categorize, and replace systematically.

## Process

### 0. Establish a naming convention table first

Before making any changes, determine how the name should appear in different contexts. Create a mapping table:

| Context | Convention | Example (Napraw Mnie) |
|---------|-----------|----------------------|
| Display/brand name | Capitalised, may include spaces | `Napraw Mnie` |
| Python identifiers, loggers | `snake_case` | `napraw_mnie` |
| Docker container/volume names | `kebab-case` | `napraw-mnie` |
| Domain / email addresses | `lowercased` no spaces | `naprawmnie.pl` |
| Prometheus metric names | `snake_case_*` | `napraw_mnie_*` |
| SMS sender name | CamelCase (SMSAPI format) | `NaprawMnie` |
| SMTP From header | Brand <email> | `Napraw Mnie <noreply@naprawmnie.pl>` |
| GitHub repo name | `snake_case` | `napraw_mnie` |
| VPS directory | `snake_case` | `/root/napraw_mnie` |
| Database name | `snake_case` | `napraw_mnie` |
| PostgreSQL user | `snake_case` | `napraw_mnie` |
| SQLite file name | `snake_case` | `napraw_mnie.db` |

Document this table for consistent replacement — one name may produce 5+ different slug forms across different systems.

### 1. Comprehensive search with case/diacritic variants

Search across all source file types with a regex that catches case variants and special characters:

```bash
# For a Polish brand name "Rezerwuj": catch rezerwuj, Rezerwuj, rezerwój, etc.
grep -ri "rezerw[uój]" --include='*.{py,js,css,html,sh,yml,yaml,conf,sql,md,txt}' .

# For an English name: use case-insensitive search
grep -ri "OldBrand" --include='*.{py,js,css,html,sh,yml,yaml,conf,sql,md,txt}' .
```

Key considerations for the regex:
- Include accented/diacritic variants if the language has them (e.g., Polish `ó` → `[uó]`)
- Search both the source code directory and the templates/static directories separately if the first pass misses some file types
- Check all directories: `app/`, `scripts/`, `migrations/`, `tests/`, `.github/`

### 2. Categorize every match into buckets

| Bucket | Action | Examples |
|--------|--------|---------|
| **Application-level references** | Change | DB names, container names, volume names, internal comments, script variables, env var defaults, test fixture names |
| **Infrastructure references** | Keep as-is | DNS domain name, SSL cert paths, GitHub repo URL, nginx server_name, SSH host |
| **Generic UI text** | Keep if meaningful | "Rezerwuj termin" = Polish "Book appointment" (action button, not brand) |
| **Historical archives** | Consider keeping | SQL migration comments referencing old DB file names, changelog entries |

Read each matching file to understand context before deciding its bucket.

### 3. Edit files systematically

Use `edit` tool per file, replacing one occurrence type at a time:

```python
# Pattern: read first, then edit
read_file("path/to/file.ext")
edit("path/to/file.ext", old_string="old_value", new_string="new_value")
```

For files with many occurrences of the same pattern, you can use `edit` with the same replacement applied to all matching lines within that file.

### 4. Handle file renames

When a script or config file itself has the old name:

```bash
# Git-based rename preserves history
git mv scripts/monitor_oldname.sh scripts/monitor_newname.sh
# Or on Windows:
move "scripts\monitor_oldname.sh" "scripts\monitor_newname.sh"
git add scripts/monitor_newname.sh
git rm scripts/monitor_oldname.sh
```

### 5. Update deployment references

After updating application-level names (e.g., container names, volume names, DB credentials), also update:
- `.github/workflows/deploy.yml` — VPS directory paths
- `scripts/deploy.sh` — repo directory on VPS, nginx config paths
- Any monitoring/healthcheck scripts that reference old container names

### 6. Verify no stragglers

After all edits, re-run the search:

```bash
grep -ri "old_name" --include='*.{py,js,css,html,sh,yml,yaml,conf,sql,md,txt}' .
```

Confirm every remaining match is in the **keep-as-is** bucket. Document why each one stays.

### 7. Rename the GitHub repository

After all file edits are done, rename the remote repository so the URL matches the new brand:

```bash
# Check gh CLI is available and authenticated
gh auth status

# Rename the repo (the --yes flag skips interactive confirmation)
gh repo rename <new-name> --yes

# This automatically updates the local "origin" remote URL
git remote -v  # verify
```

The `gh repo rename` command handles both the GitHub-side rename and the local remote URL update in one step.

### 8. Commit with structured message

Use a multi-line commit message that:
- Summarizes what was renamed
- Lists every category of file changed
- Explicitly documents what was NOT changed and why

```
Usuń wszystkie ślady '<OldBrand>' z kodu — pełna zmiana na <NewBrand>

- docker-compose.yml: nazwy kontenerów, bazy, użytkownika, woluminu
- scripts/: wszystkie skrypty (vps-init, test_login, migrate, deploy)
- tests/: testowa baza danych
- migrations/: komentarze SQL
- static/: komentarze w JS/CSS
- monitor_old.sh → monitor_new.sh
- .github/workflows/: VPS ścieżki

Pozostawiono: domena (rzeczywista), repo GitHub (rzeczywista),
tekst UI '<action_text>' (polski przycisk akcji, nie brand)
```

### 9. Push and verify

```bash
git push origin master
git ls-remote origin  # verify reachable at new URL
```

### 10. Example: brand rename with multiple slug forms

When renaming a project, the same name often needs different forms for different systems:

| System | Old Value | New Value | File(s) affected |
|--------|-----------|-----------|-----------------|
| FastAPI app title | `ServiceHub` | `Napraw Mnie` | `main.py` |
| Python loggers | `servicehub` | `napraw_mnie` | All `.py` files |
| Docker container | `servicehub-app` | `napraw-mnie-app` | `docker-compose.yml` |
| Docker volume | `servicehub_pgdata` | `napraw_mnie_pgdata` | `docker-compose.yml` |
| DB name | `servicehub` | `napraw_mnie` | `docker-compose.yml`, scripts |
| SQLite file | `servicehub.db` | `napraw_mnie.db` | config, scripts |
| Prometheus metrics | `servicehub_*` | `napraw_mnie_*` | `metrics.py`, README |
| SMS sender | `ServiceHub` | `NaprawMnie` | `.env`, config |
| SMTP from | `ServiceHub <...>` | `Napraw Mnie <...>` | `.env`, config, email |
| Admin email | `admin@servicehub.app` | `admin@naprawmnie.pl` | `.env`, tests, scripts |
| GitHub repo | `krzysztofzelman/servicehub` | `krzysztofzelman/napraw_mnie` | gh rename + remote |
| VPS directory | `/root/servicehub` | `/root/napraw_mnie` | deploy scripts, workflows |
| Monitoring script | `monitor_servicehub.sh` | `monitor_napraw_mnie.sh` | File rename |
| Migration file | `002_servicehub_columns.sql` | `002_napraw_mnie_columns.sql` | File rename |

**Priority order for editing:** Core Python code → Templates → Config/environment → Scripts → Tests → Migrations → Docs → Git/GitHub. This ensures the most critical files (that could break at runtime) are handled first.

### 11. Use the todo list to track progress across sessions

For a rename touching 30+ files, use the `todo_write` task list to track completion. Group files by category (e.g., "Core Python", "Templates", "Tests", "Scripts", "Migrations", "Docs", "Git") and mark them off one by one. This is especially useful if the rename spans multiple conversation turns due to context limits.

### 12. Handle VPS/CI migration AFTER the rebrand

The GitHub rename and remote update are just the first step. The deployment workflow on the VPS will break in predictable ways. Fix them proactively:

#### 12.1 Deploy workflow must handle old-directory migration

The `.github/workflows/deploy.yml` will fail because it tries `cd /root/<new_name>` but the VPS still has the old directory. Add a migration block at the top:

```yaml
script: |
  if [ ! -d /root/<new_name> ]; then
    if [ -d /root/<old_name> ]; then
      cp /root/<old_name>/.env.production /root/ 2>/dev/null || true
      rm -rf /root/<old_name>
    fi
    git clone git@github.com:<user>/<new_name>.git /root/<new_name>
    if [ -f /root/.env.production ]; then
      mv /root/.env.production /root/<new_name>/.env.production
    fi
  fi
```

#### 12.2 Always use SSH git URL (not HTTPS) for the clone

The VPS has SSH keys configured for GitHub. Using HTTPS will fail with `could not read Username for 'https://github.com'`:

```yaml
# Correct — uses SSH keys already on the VPS
git clone git@github.com:<user>/<new_name>.git /root/<new_name>

# Wrong — will fail in non-interactive SSH
git clone https://github.com/<user>/<new_name>.git /root/<new_name>
```

#### 12.3 Generate `.env.production` with a fallback if migration fails

The first deployment run that migrates the directory may delete the old `.env.production` before the clone succeeds (e.g., HTTPS auth failure). Add a fallback that creates a minimal `.env.production` with a generated `SECRET_KEY`:

```yaml
if [ ! -f .env.production ]; then
  echo "DATABASE_URL=sqlite:///./data/<new_name>.db" > .env.production
  echo "SECRET_KEY=change-this..." >> .env.production
  echo "SITE_URL=https://<domain>" >> .env.production
  echo "SMS_SENDER=<NewBrand>" >> .env.production
  # ... other required vars ...
  NEW_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -base64 32)
  sed -i "s/SECRET_KEY=.*/SECRET_KEY=$NEW_KEY/" .env.production
  echo "Warning: .env.production utworzony z domyslnymi wartosciami - uzupelnij klucze API!"
fi
```

**Important:** Use `echo "KEY=VALUE" > file` and `echo "KEY=VALUE" >> file` instead of heredocs (`<< 'EOF'`). Heredocs inside YAML multi-line strings (the `|` block scalar) break YAML syntax.

#### 12.4 Kill the old container blocking the port

After a rebrand, the old container (e.g., `servicehub-app` from the previous project) may still be running and occupying the application port. `docker compose down` only affects containers defined in the current `docker-compose.yml`, not containers from the old project with different names. Add aggressive cleanup:

```yaml
# Find and kill any Docker container publishing on your port
docker ps -q --filter publish=<PORT> | xargs -r docker rm -f 2>/dev/null || true
# Also kill any non-Docker process on the port
fuser -k <PORT>/tcp 2>/dev/null || true
# Then stop the new project's containers (if any started by a previous failed run)
docker compose down --timeout 10 2>/dev/null || true
```

The two commands (`docker ps --filter publish=` and `fuser`) between them catch every possible port occupant: the old project's container, the new project's half-started container from a failed run, or a rogue process started manually.

#### 12.5 Update nginx config and certbot for new domain

If the domain also changed (e.g., `rezerwuj.kzelman.pl` → `napraw.kzelman.pl`), update `nginx.conf` (server_name AND ssl_certificate paths) and the deploy script's `DOMAIN` variable. The nginx-init.conf is used by the initial setup script for the ACME challenge — update it too.

After DNS is pointed to the VPS, run on the VPS:
```bash
certbot certonly --webroot -w /var/www/certbot --email admin@example.com --agree-tos -d napraw.kzelman.pl
nginx -t && nginx -s reload
```

## What NOT to change

- **Actual domain names** — changing these would break DNS; keep them even if they contain the old brand
- **GitHub repository URLs** — the repo name on GitHub is the actual name
- **SSL certificate paths** — match the actual domain
- **Generic UI action text** — "Rezerwuj termin" means "Book appointment" in Polish; it's a verb, not a brand name
- **Historical migration files** — their SQL comments may reference old names but they're archive artifacts

## When to use this

- User says "change all occurrences of X to Y in the code"
- User says "I don't want any traces of OldName in the code"
- Completing a rebranding where the main refactoring is done but the old name still appears in configs, scripts, comments, and file names
