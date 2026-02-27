"""
diagnostico.py — Limpa cache e testa cada scraper isoladamente
Local: D:\\PORTFOLIO\\Job Aggregator\\diagnostico.py

Como rodar:
  & "D:\PORTFOLIO\Job Aggregator\emprego\python.exe" "D:\PORTFOLIO\Job Aggregator\diagnostico.py"
"""

import sys
import os
import shutil
import requests
from bs4 import BeautifulSoup

BASE = r"D:\PORTFOLIO\Job Aggregator"

# ── 1. Limpa TODOS os __pycache__ ────────────────────────────────────
print("=" * 60)
print("PASSO 1 — Limpando __pycache__")
print("=" * 60)
for root, dirs, files in os.walk(BASE):
    for d in dirs:
        if d == "__pycache__":
            path = os.path.join(root, d)
            shutil.rmtree(path)
            print(f"  ✓ Removido: {path}")
    for f in files:
        if f.endswith(".pyc"):
            path = os.path.join(root, f)
            os.remove(path)
            print(f"  ✓ Removido: {path}")
print("  Cache limpo!\n")

# ── 2. Confirma versões dos arquivos ─────────────────────────────────
print("=" * 60)
print("PASSO 2 — Verificando arquivos")
print("=" * 60)
arquivos = [
    r"app\scrapers\gupy.py",
    r"app\scrapers\catho.py",
    r"app\scrapers\infojobs.py",
    r"app\scrapers\vagas_com.py",
]
for arq in arquivos:
    caminho = os.path.join(BASE, arq)
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            linha1 = f.readline().strip()
            linha2 = f.readline().strip()
        print(f"  ✓ {arq}")
        print(f"    → {linha1}")
        print(f"    → {linha2}")
    else:
        print(f"  ✗ FALTANDO: {arq}")
print()

# ── 3. Testa URLs diretamente ─────────────────────────────────────────
print("=" * 60)
print("PASSO 3 — Testando URLs de cada site")
print("=" * 60)

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def testar(nome, url, params=None, espera_json=False):
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        print(f"\n  [{nome}] Status: {r.status_code} | URL final: {r.url[:80]}")
        if r.status_code == 200:
            if espera_json:
                try:
                    data = r.json()
                    chaves = list(data.keys()) if isinstance(data, dict) else f"lista[{len(data)}]"
                    print(f"    → JSON OK | chaves: {chaves}")
                    if isinstance(data, dict):
                        for k in ["data", "offers", "results", "jobs"]:
                            if k in data:
                                print(f"    → '{k}': {len(data[k])} itens")
                    return True
                except Exception as e:
                    print(f"    → Não é JSON: {e}")
                    print(f"    → Conteúdo: {r.text[:200]}")
                    return False
            else:
                soup = BeautifulSoup(r.text, "html.parser")
                title = soup.find("title")
                print(f"    → Título: {title.get_text() if title else 'sem título'}")
                # Conta links de vagas
                links = [a for a in soup.find_all("a", href=True)
                         if "/vaga" in a["href"] or "/job" in a["href"]]
                print(f"    → Links de vaga encontrados: {len(links)}")
                if links:
                    print(f"    → Exemplo: {links[0].get_text()[:50]} → {links[0]['href'][:60]}")
                return len(links) > 0
        else:
            print(f"    → ERRO: {r.status_code}")
            return False
    except Exception as e:
        print(f"  [{nome}] EXCEÇÃO: {e}")
        return False

# ── Gupy API ─────────────────────────────────────────────────────────
print("\n--- GUPY ---")
ok = testar("Gupy API",
            "https://portal.api.gupy.io/api/v1/jobs",
            params={"jobName": "Analista de Dados", "limit": 5},
            espera_json=True)
if ok:
    r = requests.get("https://portal.api.gupy.io/api/v1/jobs",
                     params={"jobName": "Analista de Dados", "limit": 3},
                     headers=HEADERS, timeout=15)
    jobs = r.json().get("data", [])
    for j in jobs[:2]:
        nome  = j.get("name", "")
        url_j = j.get("jobUrl", "")
        cp    = j.get("careerPageName", "")
        jid   = j.get("id", "")
        estado = j.get("state", "")
        print(f"    • {nome[:40]} | estado='{estado}' | url='{url_j[:50]}'")
        print(f"      career='{cp}' | id='{jid}'")

# ── InfoJobs ─────────────────────────────────────────────────────────
print("\n--- INFOJOBS ---")
# Testa API JSON interna
testar("InfoJobs API JSON",
       "https://www.infojobs.com.br/api/v1/search/offer",
       params={"keyword": "Analista", "page": 1, "maxResults": 5},
       espera_json=True)

# Testa diferentes formatos de URL HTML
for url_ij in [
    "https://www.infojobs.com.br/empregos.aspx?q=Analista&l=sao-paulo-sp",
    "https://www.infojobs.com.br/candidatos/busca-de-vagas.jsf?q=Analista",
    "https://www.infojobs.com.br/vagas-de-emprego.aspx?q=Analista",
]:
    testar("InfoJobs HTML", url_ij)

# ── Catho ─────────────────────────────────────────────────────────────
print("\n--- CATHO ---")
for url_c, p in [
    ("https://www.catho.com.br/vagas/", {"q": "Analista de Dados", "l": "sao-paulo"}),
    ("https://www.catho.com.br/vagas/", {"q": "Analista de Dados", "l": "sao-paulo", "page": 1}),
    ("https://www.catho.com.br/vagas/", {"q": "Analista", "page": 1}),
]:
    testar("Catho", url_c, params=p)

print("\n" + "=" * 60)
print("Diagnóstico concluído!")
print("=" * 60)