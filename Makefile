# ============================================================
# PflegeOS — Makefile
# Voraussetzung: Docker Desktop installiert und gestartet
# ============================================================

.PHONY: help up down build logs shell db-shell migrate seed superadmin reset prod-build

# Standard: Hilfe anzeigen
help:
	@echo ""
	@echo "  PflegeOS — verfügbare Befehle:"
	@echo ""
	@echo "  make up          — App + DB starten (Hot-Reload)"
	@echo "  make down        — Alles stoppen"
	@echo "  make build       — Images neu bauen"
	@echo "  make logs        — Live-Logs anzeigen"
	@echo "  make shell       — Bash-Shell im App-Container"
	@echo "  make db-shell    — psql im DB-Container"
	@echo "  make migrate     — flask db upgrade ausführen"
	@echo "  make seed        — Testdaten einspielen"
	@echo "  make superadmin  — Superadmin-Account anlegen"
	@echo "  make reset       — ALLE Daten löschen + neu starten"
	@echo ""

# Erste Einrichtung + Start
up:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "⚠  .env aus .env.example erstellt — bitte SECRET_KEY setzen!"; \
	fi
	docker compose up

# Im Hintergrund starten
up-d:
	@if [ ! -f .env ]; then cp .env.example .env; fi
	docker compose up -d

# Stoppen (Container bleiben erhalten)
down:
	docker compose down

# Images neu bauen
build:
	docker compose build --no-cache

# Live-Logs aller Services
logs:
	docker compose logs -f

# Nur App-Logs
logs-app:
	docker compose logs -f app

# Bash-Shell im laufenden App-Container
shell:
	docker compose exec app bash

# psql direkt im DB-Container
db-shell:
	docker compose exec db psql -U pflegeos -d pflegeos_db

# Nur Migrationen ausführen
migrate:
	docker compose exec app flask db upgrade

# Neue Migration erstellen (m=Beschreibung)
migration:
	docker compose exec app flask db migrate -m "$(m)"

# Testdaten einspielen
seed:
	docker compose exec app python seed.py

# Superadmin-Account anlegen
superadmin:
	docker compose exec app python seed_superadmin.py

# WARNUNG: löscht alle Volumes (DB + Uploads) und startet neu
reset:
	@echo "⚠  Alle Daten werden gelöscht! Weiter? [Ctrl+C zum Abbrechen]"
	@sleep 3
	docker compose down -v
	docker compose up

# Produktions-Build testen (kein Hot-Reload, Gunicorn)
prod-build:
	docker build -t pflegeos:prod .
	docker run --rm -p 5000:5000 \
		-e DATABASE_URL=postgresql+psycopg://pflegeos:pflegeos_passwort@host.docker.internal:5432/pflegeos_db \
		-e SECRET_KEY=test-secret \
		pflegeos:prod
