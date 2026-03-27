<div align="center">

# Job Aggregator

**Plataforma web de busca inteligente de vagas com IA + gerador de curriculo profissional**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Gemini](https://img.shields.io/badge/Gemini_2.0_Flash-AI-4285F4?style=flat-square&logo=google&logoColor=white)](https://aistudio.google.com/)
[![SQLite](https://img.shields.io/badge/DB-SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)](https://sqlite.org/)
[![License](https://img.shields.io/badge/License-MIT-22c55e?style=flat-square)](LICENSE)

*Projeto de portfolio — foco em automacao de recolocacao profissional na area fiscal, tributaria e contabil*

</div>

---

## Sobre

O **Job Aggregator** e uma aplicacao web que agrega vagas de multiplas fontes simultaneamente, usa IA para filtrar apenas as oportunidades relevantes ao seu perfil e gera curriculos profissionais em PDF — tudo rodando localmente, sem pagar por servicos externos.

Construido com Flask no backend e JavaScript vanilla no frontend, com uma interface dark estilo [Linear](https://linear.app) e atualizacoes em tempo real via Server-Sent Events.

---

## Funcionalidades

### Busca de Vagas com IA

- **Multi-fonte simultanea** — LinkedIn, Vagas.com e InfoJobs em paralelo com progresso ao vivo
- **Filtro Gemini AI** — cada vaga recebe score 0-10 de relevancia; vagas fora do perfil sao ocultadas automaticamente
- **Filtros dinamicos** — cargo, estado, modalidade (remoto / hibrido / presencial), fonte e status de candidatura
- **Match score** — compara automaticamente as skills da vaga com as do seu perfil cadastrado
- **Gestao de candidaturas** — Nova / Favorita / Aplicada / Ignorada com persistencia no banco

### Machine Learning Local

- Feedback manual ("Chamado!" / "Nao chamado") alimenta modelo probabilistico
- Calcula `probabilidade de aprovacao` por titulo, fonte e modalidade
- Atualiza todos os scores automaticamente apos cada feedback

### Gerador de Curriculo

- **Upload de CV** — suporte a `.pdf` e `.docx` com extracao automatica de texto
- **Parser PT-BR** — detecta secoes (experiencia, formacao, skills, contato) via heuristica
- **Correcao com IA** — botao envia YAML para o Gemini reformatar para a estrutura correta
- **6 temas profissionais:**

| Tema | Engine |
|------|--------|
| Executivo Azul | HTML + CSS + Chrome headless |
| Elegante Brasileiro | HTML + CSS + Chrome headless |
| Compacto Academico | HTML + CSS + Chrome headless |
| Moderno Conectado | HTML + CSS + Chrome headless |
| Classico Profissional | rendercv (Typst) |
| Engenharia & Tecnologia | rendercv (Typst) |

---

## Stack Tecnica

| Camada | Tecnologia |
|--------|-----------|
| Backend | Python 3.11 + Flask 3.1 |
| Frontend | HTML / CSS / JS vanilla — sem framework, sem build step |
| Banco de dados | SQLite |
| IA | Google Gemini 2.0 Flash (`google-genai` SDK v1.68+) |
| Scraping | requests + BeautifulSoup4 + fake-useragent |
| CV parsing | pdfplumber + python-docx + PyYAML |
| CV render | rendercv (Typst) + Edge/Chrome headless |
| Streaming | Server-Sent Events (SSE) — progresso em tempo real |

---

## Arquitetura

```
POST /api/buscar
  └── thread de fundo
        ├── LinkedIn / Vagas.com / InfoJobs scrapers (paralelo)
        ├── calcular_match_score() com perfil do usuario
        ├── INSERT vagas — duplicatas ignoradas por UNIQUE(link)
        └── Gemini pontua relevancia em lotes de 50
             └── SSE broadcast ao cliente (progresso em tempo real)

app/
├── database.py          # SQLite — vagas, feedbacks, perfil, historico
├── ai/gemini.py         # Filtro de relevancia Gemini (score 0-10)
├── scrapers/            # linkedin, vagas_com, infojobs
├── cv/                  # extractor, parser, renderer, html_renderer
└── utils/helpers.py     # match score, normalizacao de skills

web/
├── server.py            # Flask: 16 rotas REST + SSE
├── templates/index.html # SPA shell
└── static/              # style.css (design tokens) + app.js (SPA)
```

---

## Como Executar

**Requisitos:** Python 3.11+, Git

```bash
# Clonar
git clone https://github.com/CaetanoCOC/job-aggregator.git
cd job-aggregator

# Criar e ativar venv
python -m venv emprego
emprego\Scripts\activate        # Windows
# source emprego/bin/activate   # Linux / macOS

# Instalar dependencias
pip install flask google-genai requests beautifulsoup4 lxml fake-useragent \
            pdfplumber python-docx pyyaml python-dateutil "rendercv[full]"

# Iniciar servidor
python web/server.py

# Abrir no navegador
# http://localhost:5007
```

**Configurar Gemini AI (opcional — plano gratuito suficiente):**
1. Obter chave em [aistudio.google.com](https://aistudio.google.com)
2. Clicar no icone ⚙ na toolbar de vagas
3. Colar a chave e clicar em **Salvar** — filtro IA sera habilitado

---

## Design

Interface baseada no design system do **Linear** — dark mode com accent indigo.

```
Fundo:      #08090a
Surface:    #111213
Accent:     #5e6ad2  (indigo)
AI:         #c084fc  (roxo)

Tipografia: Inter (corpo) · Space Grotesk (titulos) · JetBrains Mono (dados)
```

Atualizacoes ao vivo via SSE sem polling — o frontend recebe eventos `progress`, `fonte_ok`, `ai_scoring`, `ai_done` e `done` durante o scraping.

---

## API Routes

| Metodo | Rota | Descricao |
|--------|------|-----------|
| GET | `/api/vagas` | Listar vagas com filtros |
| PUT | `/api/vagas/<id>/status` | Atualizar status candidatura |
| POST | `/api/vagas/<id>/feedback` | Feedback ML (chamado / nao chamado) |
| GET | `/api/skills` | Skills do usuario |
| POST | `/api/buscar` | Disparar scraping |
| GET | `/api/buscar/stream` | SSE — progresso em tempo real |
| GET | `/api/stats` | Estatisticas gerais |
| POST | `/api/cv/extrair` | Upload .pdf/.docx → YAML |
| POST | `/api/cv/normalizar-ia` | Corrigir YAML com Gemini |
| POST | `/api/cv/gerar` | Gerar PDF do curriculo |

---

## Contexto

Desenvolvido para automatizar a busca de recolocacao profissional com foco em **cargos fiscais, tributarios e contabeis** no mercado brasileiro. A ferramenta roda inteiramente local — sem SaaS, sem assinatura — usando apenas a API gratuita do Gemini para o filtro inteligente.

---

<div align="center">

**Caetano** — [github.com/CaetanoCOC](https://github.com/CaetanoCOC)

Flask · Gemini AI · SQLite · Vanilla JS

</div>
