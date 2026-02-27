<div align="center">

# ⚡ Job Aggregator

**Agregador de vagas e gerador de currículo — tudo em um app desktop**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![CustomTkinter](https://img.shields.io/badge/UI-CustomTkinter-1f538d?style=flat-square)](https://github.com/TomSchimansky/CustomTkinter)
[![SQLite](https://img.shields.io/badge/DB-SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)](https://sqlite.org/)
[![License](https://img.shields.io/badge/License-MIT-22c55e?style=flat-square)](LICENSE)

</div>

---

## Sobre o projeto

O **Job Aggregator** é um aplicativo desktop que centraliza a busca de vagas em múltiplos portais brasileiros e internacionais, com filtros inteligentes, rastreamento de candidaturas e geração de currículo em PDF — tudo sem abrir o navegador.

Construído com Python puro e uma interface dark moderna via CustomTkinter.

---

## Funcionalidades

### ⚡ Aba de Vagas

- **Busca multi-fonte simultânea** — LinkedIn, Vagas.com e InfoJobs em paralelo
- **Filtros em tempo real** — cargo, estado, modalidade (remoto/híbrido/presencial), status
- **Match score automático** — compara skills da vaga com seu perfil cadastrado (0–100%)
- **Gestão de candidaturas** — marque vagas como favorita, aplicada, rejeitada etc.
- **Sistema de feedback ML** — aprova/rejeita vagas para ajustar probabilidade de aprovação via fórmula Bayesiana
- **Histórico e estatísticas** — painel com total de vagas, candidaturas e aprovações

### 📄 Aba de Currículo

- **Upload de CV existente** — suporte a `.pdf` e `.docx`
- **Parser inteligente** — extrai seções (experiência, formação, skills, contato) com heurística PT-BR
- **6 temas disponíveis:**

| Tema | Engine |
|------|--------|
| Clássico Profissional | rendercv |
| Engenharia & Tecnologia | rendercv |
| CV Moderno | rendercv |
| Compacto Acadêmico | rendercv |
| Executivo Azul ✦ | HTML+CSS |
| Elegante Brasileiro ✦ | HTML+CSS |

- **Exportação em PDF** via rendercv (Typst) ou browser headless (Edge/Chrome)

---

## Stack

| Camada | Tecnologia |
|--------|-----------|
| UI | CustomTkinter (dark theme) |
| Scraping | requests + BeautifulSoup4 |
| Banco de dados | SQLite |
| CV parsing | pdfplumber + python-docx |
| CV geração | rendercv + HTML/CSS headless |

---

## Instalação

### Pré-requisitos

- Python 3.10+
- Git

### Passos

```bash
# Clone o repositório
git clone https://github.com/CaetanoCOC/job-aggregator.git
cd job-aggregator

# Crie e ative o ambiente virtual
python -m venv emprego
emprego\Scripts\activate      # Windows
# source emprego/bin/activate   # Linux/macOS

# Instale as dependências
pip install customtkinter requests beautifulsoup4 lxml fake-useragent python-dateutil
pip install pdfplumber python-docx pyyaml
pip install "rendercv[full]"

# Execute
python -m app.main
```

---

## Estrutura do projeto

```
job-aggregator/
├── app/
│   ├── main.py               # Entry point — JobAggregator(CTk)
│   ├── database.py           # Toda a lógica SQLite (4 tabelas)
│   ├── scrapers/
│   │   ├── base_scraper.py   # ABC com _get(), _soup(), _vaga_padrao()
│   │   ├── linkedin.py       # LinkedIn Guest API
│   │   ├── vagas_com.py      # Vagas.com HTML scraping
│   │   └── infojobs.py       # InfoJobs HTML scraping
│   ├── ui/
│   │   ├── shared.py         # Constantes de cor + listas globais
│   │   ├── vagas_ui.py       # VagasTab — busca, filtros, feedback
│   │   └── cv_ui.py          # CvTab — upload, parse, exportar PDF
│   ├── cv/
│   │   ├── extractor.py      # Extração de texto (.pdf / .docx)
│   │   ├── parser.py         # Texto → dict estruturado → YAML
│   │   ├── renderer.py       # Roteador rendercv / HTML
│   │   └── html_renderer.py  # Templates HTML+CSS → PDF headless
│   └── utils/
│       └── helpers.py        # Match score, normalização de skills
├── diagnostico.py            # Testa todos os scrapers isoladamente
├── CLAUDE.md                 # Instruções para Claude Code
└── README.md
```

---

## Como funciona o scraping

```
Usuário define: cargo + estado + site
        ↓
_iniciar_scraping() → thread background
        ↓
scraper.buscar(cargo, localização, skills)  ← cada fonte em paralelo
        ↓
inserir_vaga()  →  SQLite (UNIQUE em link, duplicatas ignoradas)
        ↓
_aplicar_filtros()  →  repopula tabela com filtros ativos
```

---

## Diagnóstico

```bash
# Testa todos os scrapers e exibe resultados
python diagnostico.py

# Testa um scraper isolado
python -m app.scrapers.linkedin
python -m app.scrapers.vagas_com
```

---

## Contribuindo

Pull requests são bem-vindos. Para mudanças maiores, abra uma issue primeiro para discutir o que você gostaria de alterar.

---

<div align="center">

Feito com Python · CustomTkinter · SQLite

</div>
