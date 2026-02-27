"""
linkedin.py — Scraper do LinkedIn via API pública (guest, sem login)
Local: D:\\PORTFOLIO\\Job Aggregator\\app\\scrapers\\linkedin.py

A API guest retorna HTML com cards de vagas sem exigir autenticação.
URL: linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search
"""

from datetime import datetime
from bs4 import BeautifulSoup
from app.scrapers.base_scraper import BaseScraper


class LinkedInScraper(BaseScraper):
    nome_fonte  = "linkedin"
    url_base    = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    MAX_PAGINAS = 4

    _ESTADO_LOCATION = {
        "SP": "São Paulo, Brasil",
        "RJ": "Rio de Janeiro, Brasil",
        "MG": "Minas Gerais, Brasil",
        "RS": "Rio Grande do Sul, Brasil",
        "PR": "Paraná, Brasil",
        "SC": "Santa Catarina, Brasil",
        "BA": "Bahia, Brasil",
        "PE": "Pernambuco, Brasil",
        "CE": "Ceará, Brasil",
        "GO": "Goiás, Brasil",
        "DF": "Brasília, Brasil",
        "AM": "Amazonas, Brasil",
        "Remoto": "Brasil",
    }

    def buscar(self, cargo: str, localizacao: str = "", skills: list = None) -> list:
        skills   = skills or []
        coletadas = []

        location = self._ESTADO_LOCATION.get(localizacao, "Brasil")
        print(f"[LinkedIn] ▶ Buscando: '{cargo}' em '{location}'")

        for pagina in range(self.MAX_PAGINAS):
            params = {
                "keywords": cargo,
                "location": location,
                "start":    pagina * 25,
            }
            # Filtro remoto quando estado = Remoto
            if localizacao == "Remoto":
                params["f_WT"] = "2"

            resp = self._get(self.url_base, params=params)
            if not resp:
                print(f"[LinkedIn] ✗ Sem resposta offset {pagina * 25}")
                break

            soup  = BeautifulSoup(resp.text, "lxml")
            cards = soup.select("li")

            if not cards:
                print(f"[LinkedIn] Sem cards no offset {pagina * 25}, encerrando.")
                break

            print(f"[LinkedIn] Offset {pagina * 25}: {len(cards)} cards")

            ok = 0
            for card in cards:
                v = self._parsear_card(card, skills)
                if v:
                    coletadas.append(v)
                    ok += 1

            print(f"[LinkedIn] {ok}/{len(cards)} parseados")

            if len(cards) < 25:
                break

            self._esperar(1.5, 2.5)

        print(f"[LinkedIn] ✔ Total: {len(coletadas)} vagas")
        return coletadas

    def _parsear_card(self, card, skills_usuario: list) -> dict | None:
        try:
            link_el = card.select_one("a.base-card__full-link")
            if not link_el:
                return None

            titulo = self._limpar_texto(link_el.get_text())
            link   = link_el.get("href", "").strip()
            if not titulo or not link:
                return None

            # Remove parâmetros de tracking
            if "?" in link:
                link = link.split("?")[0]

            emp_el  = card.select_one("h4.base-search-card__subtitle")
            empresa = self._limpar_texto(emp_el.get_text()) if emp_el else ""

            loc_el     = card.select_one(".job-search-card__location")
            localizacao = self._limpar_texto(loc_el.get_text()) if loc_el else ""

            date_el  = card.select_one("time")
            data_pub = (date_el.get("datetime", "") or "")[:10] if date_el else ""
            if not data_pub:
                data_pub = datetime.now().strftime("%Y-%m-%d")

            texto_card  = titulo + " " + localizacao
            modalidade  = self._detectar_modalidade(texto_card)
            skills_enc  = self._extrair_skills(titulo, skills_usuario)
            softskills  = self._extrair_softskills(texto_card)

            return self._vaga_padrao(
                titulo=titulo,
                empresa=empresa,
                localizacao=localizacao,
                modalidade=modalidade,
                salario="",
                descricao=self._enriquecer_descricao("", softskills),
                skills=skills_enc,
                link=link,
                data_pub=data_pub,
            )
        except Exception as e:
            print(f"[LinkedIn] ✗ Erro parsear: {e}")
            return None


if __name__ == "__main__":
    s = LinkedInScraper()
    vagas = s.buscar("Analista de Dados", "SP", ["Python", "SQL"])
    for v in vagas[:3]:
        print(f"\n  {v['titulo']} | {v['empresa']}")
        print(f"  Link: {v['link']}")
        print(f"  Local: {v['localizacao']}")
