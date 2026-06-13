#!/bin/bash
# Skrypt inicjalizujący wdrożenie Rezerwuj na VPS
# Uruchom: bash scripts/deploy.sh
set -e

DOMAIN="rezerwuj.kzelman.pl"
REPO_DIR="/root/rezerwuj"
EMAIL="krzysztof@zelman.pl"

echo "=== Krok 1: Klonowanie repozytorium ==="
if [ -d "$REPO_DIR" ]; then
    cd $REPO_DIR && git pull
else
    git clone https://github.com/krzysztofzelman/rezerwuj.git $REPO_DIR
    cd $REPO_DIR
fi

echo "=== Krok 2: Konfiguracja .env.production ==="
if [ ! -f "$REPO_DIR/.env.production" ]; then
    cp .env.production .env.production
fi

# Generuj SECRET_KEY jeśli placeholder
CURRENT_KEY=$(grep SECRET_KEY .env.production | cut -d= -f2)
if [ "$CURRENT_KEY" = "change-this-to-a-long-random-secret-key-for-production" ] || [ -z "$CURRENT_KEY" ]; then
    NEW_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    sed -i "s/SECRET_KEY=.*/SECRET_KEY=$NEW_KEY/" .env.production
    echo "✅ SECRET_KEY wygenerowany"
fi

echo "=== Krok 3: Uruchomienie tymczasowego nginx (HTTP) ==="
cp nginx-init.conf nginx.conf
docker compose up -d nginx
sleep 3

echo "=== Krok 4: Pobranie certyfikatu SSL ==="
docker compose run --rm certbot certonly --webroot \
    --webroot-path=/var/www/certbot \
    --email $EMAIL \
    --agree-tos \
    --no-eff-email \
    -d $DOMAIN

echo "=== Krok 5: Generowanie konfiguracji SSL dla nginx ==="
docker compose run --rm certbot \
    sh -c "mkdir -p /etc/letsencrypt && certbot certificates 2>/dev/null; \
           cp /etc/letsencrypt/options-ssl-nginx.conf /etc/letsencrypt/ 2>/dev/null || true"

echo "=== Krok 6: Uruchomienie pełnego stosu ==="
# Przywróć właściwy nginx.conf z gita
git checkout nginx.conf
docker compose down
docker compose up -d

echo "=== Krok 7: Sprawdzenie statusu ==="
docker compose ps

echo ""
echo "✅ Wdrożenie zakończone!"
echo "🔗 https://$DOMAIN"
