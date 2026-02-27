# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
# Activate venv first
emprego\Scripts\activate

# Run the app
python -m app.main

# Or via full path
"D:\PORTFOLIO\Job Aggregator\emprego\python.exe" -m app.main
```

## Diagnostics & Testing Scrapers

```bash
# Run full diagnostic (clears cache, tests all scraper URLs)
"D:\PORTFOLIO\Job Aggregator\emprego\python.exe" diagnostico.py

# Test a single scraper in isolation (each scraper has a __main__ block)
"D:\PORTFOLIO\Job Aggregator\emprego\python.exe" -m app.scrapers.linkedin
"D:\PORTFOLIO\Job Aggregator\emprego\python.exe" -m app.scrapers.vagas_com
```

## Architecture

**Entry point:** `app/main.py` — `JobAggregator(ctk.CTk)` class, self-contained GUI.

**Data flow:**
1. User sets cargo + estado + site in sidebar → clicks "Buscar na Web"
2. `_iniciar_scraping()` spawns a background thread calling `_run_scrapers()`
3. Each scraper returns a list of dicts via `scraper.buscar(cargo, localizacao, skills)`
4. `inserir_vaga()` stores each result in SQLite; duplicate links are silently ignored (`UNIQUE` constraint on `link`)
5. `_aplicar_filtros()` queries the DB and repopulates the table, runs in-memory state+modalidade filtering

**Scrapers** (`app/scrapers/`):
- All inherit `BaseScraper` (ABC) and must implement `buscar()`, set `nome_fonte` and `url_base`
- `BaseScraper` provides: `_get()` (HTTP with rotating user-agent), `_soup()` (BS4), `_vaga_padrao()` (standard dict), `_esperar()`, `_extrair_skills()`, `_detectar_modalidade()`

| File | Site | Method |
|------|------|--------|
| linkedin.py | LinkedIn | Guest API (HTML cards, sem auth) — `linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search` |
| vagas_com.py | Vagas.com | HTML scraping (BS4) |
| infojobs.py | InfoJobs | HTML scraping (BS4) |
| empregobr.py | Emprego.com.br | HTML scraping (BS4) |

**Database** (`app/database.py`):
- SQLite at project root `jobs.db`
- Tables: `vagas`, `feedbacks`, `perfil_usuario`, `historico_buscas`
- `prob_aprovacao` is recalculated after every feedback via a weighted Bayesian-style formula in `_recalcular_probabilidades()`

**Skills matching** (`app/utils/helpers.py`):
- `calcular_match_score(skills_vaga, skills_usuario)` → 0–100 int, computed at display time (not stored)
- Skills are stored as JSON arrays in `vagas.skills`

## Virtual Environment

Located at `emprego/` (conda-style layout with `Scripts/`, `Lib/`, `Library/`). Key packages: `customtkinter`, `requests`, `beautifulsoup4`, `lxml`, `fake-useragent`, `python-dateutil`.
