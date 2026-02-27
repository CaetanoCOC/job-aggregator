"""
vagas_com.py — Scraper do Vagas.com via BeautifulSoup
Local: D:\\PORTFOLIO\\Job Aggregator\\app\\scrapers\\vagas_com.py
"""

from datetime import datetime
from app.scrapers.base_scraper import BaseScraper


class VagasComScraper(BaseScraper):
    nome_fonte  = "vagas.com"
    url_base    = "https://www.vagas.com.br"
    MAX_PAGINAS = 4

    # Mapeamento estado → slug para URL
    _ESTADO_SLUG = {
        "SP": "sao-paulo", "RJ": "rio-de-janeiro", "MG": "minas-gerais",
        "RS": "rio-grande-do-sul", "PR": "parana", "SC": "santa-catarina",
        "BA": "bahia", "PE": "pernambuco", "CE": "ceara",
        "GO": "goias", "DF": "distrito-federal", "AM": "amazonas",
    }

    def buscar(self, cargo: str, localizacao: str = "", skills: list = None) -> list:
        skills    = skills or []
        coletadas = []

        cargo_slug   = cargo.strip().lower().replace(" ", "-")
        estado_slug  = self._ESTADO_SLUG.get(localizacao, "")

        if estado_slug:
            url_busca = f"{self.url_base}/vagas-de-{cargo_slug}-em-{estado_slug}"
        else:
            url_busca = f"{self.url_base}/vagas-de-{cargo_slug}"

        print(f"[Vagas.com] URL base: {url_busca}")

        for pagina in range(1, self.MAX_PAGINAS + 1):
            url = url_busca if pagina == 1 else f"{url_busca}?pagina={pagina}"

            soup = self._soup(url)
            if not soup:
                print(f"[Vagas.com] ✗ Sem resposta página {pagina}")
                break

            # ── Seletores reais do Vagas.com ─────────────────────────
            # O site usa <li class="vaga"> como container principal
            cards = soup.select("li.vaga")

            if not cards:
                print(f"[Vagas.com] Sem cards na página {pagina}, tentando seletor alternativo...")
                cards = soup.select("[class*='vaga-item']") or \
                        soup.select("article.vaga") or \
                        soup.select(".vagas-lista > li")

            if not cards:
                print(f"[Vagas.com] Nenhum card encontrado. Encerrando.")
                break

            print(f"[Vagas.com] Página {pagina}: {len(cards)} cards encontrados")

            ok = 0
            for card in cards:
                v = self._parsear_card(card, skills)
                if v:
                    coletadas.append(v)
                    ok += 1

            print(f"[Vagas.com] Página {pagina}: {ok}/{len(cards)} parseados com sucesso")

            if len(cards) < 5:
                break

            self._esperar(1.5, 2.5)

        print(f"[Vagas.com] Total: {len(coletadas)} vagas")
        return coletadas

    def _parsear_card(self, card, skills_usuario: list) -> dict | None:
        try:
            # ── Título + Link ────────────────────────────────────────
            # Vagas.com: <a class="link-detalhes-vaga" href="/vaga/...">
            titulo_el = (
                card.select_one("a.link-detalhes-vaga") or
                card.select_one("h2 > a") or
                card.select_one("h3 > a") or
                card.select_one("a[href*='/vaga/']")
            )
            if not titulo_el:
                return None

            titulo = self._limpar_texto(titulo_el.get_text())
            if not titulo:
                return None

            href = titulo_el.get("href", "").strip()
            if not href:
                return None
            if href.startswith("/"):
                link = f"{self.url_base}{href}"
            elif href.startswith("http"):
                link = href
            else:
                return None

            # Remove parâmetros de tracking
            if "?" in link:
                link = link.split("?")[0]

            # ── Empresa ──────────────────────────────────────────────
            empresa_el = (
                card.select_one("span.emprVaga") or
                card.select_one(".empresa-nome") or
                card.select_one("[class*='empresa']") or
                card.select_one("span.local")
            )
            empresa = self._limpar_texto(empresa_el.get_text()) if empresa_el else ""

            # ── Localização ──────────────────────────────────────────
            local_el = (
                card.select_one("span.local") or
                card.select_one("[class*='local']") or
                card.select_one(".cidade-estado")
            )
            # Se usou o mesmo elemento para empresa, pula
            localizacao = ""
            if local_el and local_el != empresa_el:
                localizacao = self._limpar_texto(local_el.get_text())

            # ── Descrição ─────────────────────────────────────────────
            desc_el = (
                card.select_one(".detalhes-vaga") or
                card.select_one("[class*='descricao']") or
                card.select_one("p")
            )
            descricao = self._limpar_texto(desc_el.get_text()) if desc_el else ""

            # ── Salário ───────────────────────────────────────────────
            sal_el = (
                card.select_one("[class*='salario']") or
                card.select_one(".salario")
            )
            salario = self._limpar_texto(sal_el.get_text()) if sal_el else ""

            texto_completo = titulo + " " + descricao
            modalidade  = self._detectar_modalidade(texto_completo)
            skills_enc  = self._extrair_skills(texto_completo, skills_usuario)
            softskills  = self._extrair_softskills(texto_completo)
            descricao_f = self._enriquecer_descricao(descricao[:800], softskills)

            return self._vaga_padrao(
                titulo=titulo,
                empresa=empresa,
                localizacao=localizacao,
                modalidade=modalidade,
                salario=salario,
                descricao=descricao_f,
                skills=skills_enc,
                link=link,
                data_pub=datetime.now().strftime("%Y-%m-%d"),
            )

        except Exception as e:
            print(f"[Vagas.com] ✗ Erro ao parsear card: {e}")
            return None


if __name__ == "__main__":
    s = VagasComScraper()
    vagas = s.buscar("Analista de Dados", "SP", ["Python", "SQL"])
    for v in vagas[:3]:
        print(f"\n  {v['titulo']} | {v['empresa']}")
        print(f"  Link: {v['link']}")
        print(f"  Local: {v['localizacao']}")