"""
infojobs.py — Scraper do InfoJobs Brasil
Local: D:\\PORTFOLIO\\Job Aggregator\\app\\scrapers\\infojobs.py

DIAGNÓSTICO CONFIRMOU:
  ✓ /empregos-em-sao-paulo.aspx → 200 OK, 56 links de vaga
  ✗ /api/v1/search/offer → 404
  ✗ ?q=cargo → ignorado, redireciona para genérico

Estratégia: 
  1. Tenta URL no formato /vagas-de-emprego-{cargo}-em-{cidade}.aspx
  2. Fallback: /empregos-em-{cidade}.aspx e filtra por cargo no título
  3. Cada link é no formato /vaga-de-xxx-em-cidade__ID.aspx
"""

import urllib.parse
from datetime import datetime
from app.scrapers.base_scraper import BaseScraper


class InfoJobsScraper(BaseScraper):
    nome_fonte   = "infojobs"
    url_base     = "https://www.infojobs.com.br"
    MAX_PAGINAS  = 4

    _ESTADO_SLUG = {
        "SP": "sao-paulo",       "RJ": "rio-de-janeiro",
        "MG": "belo-horizonte",  "RS": "porto-alegre",
        "PR": "curitiba",        "SC": "florianopolis",
        "BA": "salvador",        "PE": "recife",
        "CE": "fortaleza",       "GO": "goiania",
        "DF": "brasilia",        "AM": "manaus",
    }

    def buscar(self, cargo: str, localizacao: str = "", skills: list = None) -> list:
        skills      = skills or []
        coletadas   = []
        cidade_slug = self._ESTADO_SLUG.get(localizacao, "sao-paulo")
        cargo_slug  = cargo.strip().lower().replace(" ", "-")

        # Lista de URLs para tentar (da mais específica para a mais genérica)
        urls_tentar = [
            # Formato: /vagas-de-emprego-{cargo}-em-{cidade}.aspx
            f"{self.url_base}/vagas-de-emprego-{cargo_slug}-em-{cidade_slug}.aspx",
            # Formato: /vagas-de-{cargo}-em-{cidade}.aspx
            f"{self.url_base}/vagas-de-{cargo_slug}-em-{cidade_slug}.aspx",
            # Formato: /empregos-{cargo}-em-{cidade}.aspx
            f"{self.url_base}/empregos-{cargo_slug}-em-{cidade_slug}.aspx",
            # Fallback geral da cidade (confirmado no diagnóstico: 56 links)
            f"{self.url_base}/empregos-em-{cidade_slug}.aspx",
        ]

        for url_base_busca in urls_tentar:
            print(f"[InfoJobs] Tentando: {url_base_busca}")
            soup = self._soup(url_base_busca)
            if not soup:
                print(f"[InfoJobs]   ✗ Sem resposta")
                continue

            # Verifica se a URL teve redirect para genérico (sem cargo)
            links_vaga = self._extrair_links_vaga(soup)
            if not links_vaga:
                print(f"[InfoJobs]   ✗ Sem links de vaga")
                continue

            print(f"[InfoJobs]   ✓ {len(links_vaga)} links encontrados em {url_base_busca}")

            # Filtra links que tenham o cargo no texto/URL
            palavras_cargo = cargo.lower().split()
            links_filtrados = []
            for titulo_texto, href in links_vaga:
                titulo_lower = titulo_texto.lower()
                url_lower    = href.lower()
                # Aceita se QUALQUER palavra do cargo estiver no título ou URL
                if any(p in titulo_lower or p in url_lower for p in palavras_cargo):
                    links_filtrados.append((titulo_texto, href))

            # Se muitos match, usa filtrados; senão usa todos (url genérica)
            usar = links_filtrados if len(links_filtrados) >= 3 else links_vaga
            print(f"[InfoJobs]   → Usando {len(usar)} links "
                  f"({'filtrados por cargo' if usar is links_filtrados else 'todos'})")

            for titulo_texto, href in usar[:30]:  # máximo 30 por página
                link = (f"{self.url_base}{href}"
                        if href.startswith("/") else href)
                titulo = self._limpar_texto(titulo_texto)
                if not titulo:
                    continue

                # Extrai localização do próprio href
                # Formato: /vaga-de-xxx-em-sao-paulo__123456.aspx
                loc = ""
                if "-em-" in href:
                    partes = href.split("-em-")[-1]
                    loc    = partes.split("__")[0].replace("-", " ").title()

                softskills = self._extrair_softskills(titulo)
                v = self._vaga_padrao(
                    titulo=titulo,
                    empresa="",
                    localizacao=loc or localizacao,
                    modalidade=self._detectar_modalidade(titulo),
                    salario="",
                    descricao=self._enriquecer_descricao("", softskills),
                    skills=self._extrair_skills(titulo, skills),
                    link=link,
                    data_pub=datetime.now().strftime("%Y-%m-%d"),
                )
                coletadas.append(v)

            # Se achou resultado, não tenta mais URLs
            if coletadas:
                break

            self._esperar(1.0, 2.0)

        print(f"[InfoJobs] ✔ Total: {len(coletadas)} vagas")
        return coletadas

    def _extrair_links_vaga(self, soup) -> list[tuple[str, str]]:
        """
        Extrai (titulo, href) de links que apontam para vagas.
        Formato InfoJobs: /vaga-de-xxx__ID.aspx
        """
        resultado = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Filtra apenas links de vaga real
            if ("vaga-de-" in href or "/vaga/" in href) and ".aspx" in href:
                titulo = self._limpar_texto(a.get_text())
                if titulo and len(titulo) > 3:
                    resultado.append((titulo, href))
        return resultado