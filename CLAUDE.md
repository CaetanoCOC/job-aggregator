# CLAUDE.md

Guia de referência para o Claude Code neste repositório.

**GitHub:** https://github.com/CaetanoCOC/job-aggregator

---

## Web App (v3 — Flask)

```bash
# Iniciar servidor web (porta 5007)
"D:\PORTFOLIO\Job Aggregator\emprego\python.exe" web/server.py
# Abre em: http://localhost:5007
```

**Stack web:** Flask 3.1 + HTML/CSS/JS puro (sem build step)
**Design:** Linear dark (indigo accent) + Space Grotesk headers + JetBrains Mono para dados
**SSE:** `/api/buscar/stream` — eventos em tempo real durante scraping

### Estrutura web/
```
web/
├── server.py          # Flask: rotas REST + SSE + Gemini AI
├── templates/
│   └── index.html     # Shell SPA — NUNCA usar caracteres Unicode especiais (✦ etc) no HTML
└── static/
    ├── style.css      # Design tokens Linear/SpaceX + componentes
    └── app.js         # SPA vanilla JS (sem framework)
```

### API Routes
| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/vagas` | Listar vagas (filtros: cargo, status, estado, modalidade, ai_filtrar) |
| PUT | `/api/vagas/<id>/status` | Atualizar status candidatura |
| POST | `/api/vagas/<id>/feedback` | Registrar feedback ML |
| GET | `/api/skills` | Skills do usuário |
| POST | `/api/skills` | Adicionar skill |
| DELETE | `/api/skills/<skill>` | Remover skill |
| GET | `/api/stats` | Estatísticas gerais |
| POST | `/api/buscar` | Disparar scraping (background thread) |
| GET | `/api/buscar/stream` | SSE — eventos progress/fonte_ok/ai_scoring/ai_done/done/error |
| GET | `/api/config` | Ler config (retorna gemini_configurado, gemini_key_preview) |
| POST | `/api/config` | Salvar config (gemini_api_key) |
| POST | `/api/ai/testar` | Testar chave Gemini (aceita api_key no body) |
| POST | `/api/cv/extrair` | Upload .pdf/.docx → YAML |
| POST | `/api/cv/normalizar-ia` | Corrigir estrutura YAML com Gemini |
| POST | `/api/cv/gerar` | Gerar PDF do currículo |

---

## Gemini AI

**SDK:** `google-genai` v1.68+ (novo SDK — NÃO usar `google-generativeai`, está deprecado)
**Modelos (fallback em ordem):** `gemini-2.0-flash-lite` → `gemini-2.0-flash` → `gemini-1.5-flash`
**Config persistida em:** `config.json` na raiz do projeto

> **ATENÇÃO:** `gemini-1.5-flash` retorna 404 no SDK v1beta atual — está na lista de fallback mas raramente funciona. Prioridade real é `gemini-2.0-flash-lite` e `gemini-2.0-flash`.

### Funcionalidades
1. **Filtro de vagas** — após scraping, pontua cada vaga 0–10 por relevância ao cargo buscado
   - Score salvo em `vagas.ai_score` (REAL, default -1 = não pontuada)
   - `ai_filtrar=1` no GET `/api/vagas` oculta vagas com score < 4
   - Lotes de 50 vagas por chamada (batch prompting)
2. **Corrigir YAML** — botão "Corrigir com IA" no editor de currículo
   - Reformata qualquer YAML para estrutura exata do rendercv
   - Tenta cada modelo em ordem; 429 = continue pro próximo (quota separada por modelo)
   - Quota diária reset: 04:00 horário de Brasília (meia-noite Pacific)

### Arquivos
```
app/ai/
├── __init__.py
└── gemini.py    # pontuar_vagas(), _pontuar_lote(), LIMIAR_RELEVANCIA=4, TAMANHO_LOTE=50
```

### SSE Events (Gemini)
- `ai_scoring` → `{total}` — iniciando avaliação
- `ai_done`    → `{total_analisadas, irrelevantes}` — concluído
- `ai_erro`    → `{error}` — falha na API

---

## Comandos Essenciais

```bash
# Iniciar servidor web
"D:\PORTFOLIO\Job Aggregator\emprego\python.exe" web/server.py

# Testar um scraper isolado
"D:\PORTFOLIO\Job Aggregator\emprego\python.exe" -m app.scrapers.linkedin
"D:\PORTFOLIO\Job Aggregator\emprego\python.exe" -m app.scrapers.vagas_com
"D:\PORTFOLIO\Job Aggregator\emprego\python.exe" -m app.scrapers.infojobs

# Matar processos acumulados nas portas 5007-5010 (Windows)
"D:\PORTFOLIO\Job Aggregator\emprego\python.exe" -c "
import subprocess
r = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
pids = set()
for line in r.stdout.splitlines():
    if any(f':{p} ' in line for p in ['5007','5008','5009','5010']):
        try: pids.add(int(line.split()[-1]))
        except: pass
pids.discard(0)
for pid in pids:
    subprocess.run(['taskkill', '/F', '/PID', str(pid)], capture_output=True)
print('Killed:', pids)
"
```

**Python:** `emprego/python.exe` (venv conda-style em `emprego/`, Python 3.11)

---

## Estrutura de Arquivos

```
app/
├── main.py                  # (legado CustomTkinter — não usado na versão web)
├── database.py              # Toda a lógica SQLite (4 tabelas)
├── ai/
│   ├── __init__.py
│   └── gemini.py            # Filtro de relevância via Gemini 2.0 Flash
├── scrapers/
│   ├── base_scraper.py      # ABC com _get(), _soup(), _vaga_padrao(), _extrair_skills()
│   ├── linkedin.py          # Guest API (HTML cards, sem auth)
│   ├── vagas_com.py         # HTML scraping (BS4)
│   └── infojobs.py          # HTML scraping (BS4) com estratégia de URL fallback
├── cv/
│   ├── extractor.py         # Extrai texto de .pdf (pdfplumber) e .docx (python-docx)
│   ├── parser.py            # texto → dict estruturado → YAML rendercv
│   ├── renderer.py          # Roteador: rendercv subprocess ou html_renderer
│   └── html_renderer.py     # Templates HTML/CSS → PDF via Edge/Chrome headless
└── utils/
    └── helpers.py           # calcular_match_score, normalizar_skills, extrair_softskills…

config.json                  # API keys (gemini_api_key) — no .gitignore, não commitar
diagnostico.py               # Script standalone de diagnóstico dos scrapers
```

---

## Arquitetura e Fluxo de Dados

### 1. Busca de Vagas (Web)

```
Modal Buscar (cargo + estado + fonte) → POST /api/buscar
  └─ _run_scrapers() [thread de fundo]
       ├─ LinkedInScraper.buscar()
       ├─ VagasComScraper.buscar()
       └─ InfoJobsScraper.buscar()
            ↓ lista de dicts
       calcular_match_score(skills_vaga, skills_usuario)
       inserir_vaga()  ← ignora duplicatas (UNIQUE em link)
       _broadcast(fonte_ok / fonte_erro)
       ↓ se gemini_api_key configurada:
       pontuar_vagas() → UPDATE vagas.ai_score
       _broadcast(ai_scoring / ai_done / ai_erro)
       _broadcast(done)
```

SSE conectado via `GET /api/buscar/stream` — um `queue.Queue` por cliente conectado.

### 2. Feedback / ML

```
Usuário: "Chamado!" ou "Não chamado"
  └─ registrar_feedback(vaga_id, chamado)
       ├─ INSERT em feedbacks
       └─ _recalcular_probabilidades()
            ├─ 50% peso — titulo_norm (com confidence weighting)
            ├─ 25% peso — fonte
            ├─ 25% peso — modalidade
            └─ fallback → média global
            → UPDATE vagas.prob_aprovacao
```

### 3. Geração de Currículo

```
Upload .pdf / .docx → POST /api/cv/extrair
  └─ extrair_texto() → texto_para_yaml() → YAML no editor

[opcional] POST /api/cv/normalizar-ia
  └─ Gemini reformata YAML para estrutura rendercv correta

POST /api/cv/gerar (yaml_content + tema_id)
  └─ _normalizar_yaml_cv() → valida cv.sections
       ├─ tema HTML? → html_renderer.gerar_pdf_formato() → Edge/Chrome → PDF
       └─ rendercv?  → subprocess rendercv render → PDF
```

---

## Banco de Dados (`jobs.db`)

SQLite na raiz do projeto.

| Tabela | Colunas-chave | Notas |
|---|---|---|
| `vagas` | `link UNIQUE`, `skills` (JSON), `prob_aprovacao` (REAL 0–1), `match_score` (INT 0–100), `ai_score` (REAL default -1) | `status`: nova/favorita/aplicada/ignorada |
| `feedbacks` | `titulo_norm`, `chamado` (0/1), `fonte`, `modalidade` | Base do ML |
| `perfil_usuario` | `skill UNIQUE`, `nivel` | Skills do usuário |
| `historico_buscas` | `cargo`, `fontes` (JSON), `total_vagas` | Log de buscas |

- `ai_score = -1` → vaga ainda não avaliada pelo Gemini
- `ai_score < 4` → irrelevante (oculta quando filtro IA ativo)

---

## UI Web (SPA)

**Paleta Linear Dark** em `style.css` (variáveis CSS):
- Fundo: `--bg: #08090a`, Surface: `--surface: #111213`, Border: `--border`
- Indigo: `--indigo: #5e6ad2`, Verde: `--green`, Roxo: `#c084fc` (AI)
- Fontes: Inter (corpo), Space Grotesk (títulos), JetBrains Mono (dados/código)

**Tabs no header:**
- `Vagas` → toolbar com filtros + feed de cards + painel de detalhe
- `Currículo` → upload zone + seletor de tema + editor YAML + log

**Toolbar de Vagas (da esquerda para direita):**
1. Pills de status (Todas / Nova / Favorita / Aplicada / Ignorada)
2. Select de Estado
3. Pills de modalidade (Todas / Remoto / Híbrido / Presencial)
4. Botões de fonte (LinkedIn / Vagas.com / InfoJobs)
5. **✦ Filtro IA** + **⚙** — ativar filtro Gemini + configurar API key
6. **Buscar Vagas** (margin-left: auto — sempre à direita)

**Editor YAML (aba Currículo):**
- Botão **✦ Corrigir com IA** — envia YAML para Gemini reformatar
- Botões Limpar e Copiar

---

## Temas de Currículo

| Display | tema_id | Engine |
|---|---|---|
| Executivo Azul | `executivo_azul` | HTML + Edge headless |
| Elegante Brasileiro | `elegante_br` | HTML + Edge headless |
| Compacto Acadêmico | `compacto_academico` | HTML + Edge headless |
| Moderno Conectado | `moderno_conectado` | HTML + Edge headless |
| Clássico Profissional | `classic` | rendercv (Typst) |
| Engenharia & Tecnologia | `engineeringresumes` | rendercv (Typst) |

Fallback de PDF: weasyprint → xhtml2pdf → abre HTML no browser

---

## Pacotes-chave (venv `emprego/`)

| Categoria | Pacotes |
|---|---|
| Web | `flask` 3.1 |
| AI | `google-genai` 1.68+ (NÃO usar `google-generativeai` — deprecado) |
| Scraping | `requests`, `beautifulsoup4`, `lxml`, `fake-useragent` |
| CV parsing | `pdfplumber`, `python-docx`, `pyyaml` |
| CV render | `rendercv[full]` (Typst), `weasyprint`, `xhtml2pdf` (fallbacks) |
| Utilitários | `python-dateutil`, `phonenumbers` |

---

## Problemas Conhecidos

- `rendercv --help` falha (bug click/typer), mas `rendercv render` funciona normalmente
- `diagnostico.py` referencia scrapers removidos (gupy, catho, emprego.com.br) — ignorar
- `renderer.py` tem caminho hardcoded: `D:\PORTFOLIO\Job Aggregator\emprego\python.exe`
- Múltiplos processos se acumulam nas portas 5007–5010 se o servidor não for fechado corretamente — usar o script de kill acima antes de reiniciar
- Caracteres Unicode especiais (✦ U+2726 etc.) no `index.html` causam conflito com encoding Windows cp1252 no processo Flask — usar entidades HTML (`&#10022;`) ou evitar esses caracteres no template
- Gemini free tier: 1500 req/dia · 15 RPM — erro 429 = quota esgotada; reset às 04:00 horário de Brasília (meia-noite Pacific). Criar nova chave/conta NÃO resolve se a quota diária foi atingida — é por projeto/IP
- `gemini-1.5-flash` retorna 404 no SDK `google-genai` v1beta atual — modelos funcionais: `gemini-2.0-flash-lite`, `gemini-2.0-flash`
- Modal de config Gemini tem dois botões separados: **Testar** (não salva) e **Salvar** — usuário precisa clicar Salvar para persistir nova chave
