"""
base_scraper.py
Classe base abstrata que todos os scrapers devem herdar.
Local do arquivo: D:\\PORTFOLIO\\Job Aggregator\\app\\scrapers\\base_scraper.py
"""

import requests
from abc import ABC, abstractmethod
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from datetime import datetime
import time
import random

from app.utils.helpers import extrair_softskills


class BaseScraper(ABC):
    """
    Classe base para todos os scrapers de emprego.
    
    Para criar um novo scraper, herde esta classe e implemente:
        - nome_fonte  → str com o nome do site (ex: "gupy", "linkedin")
        - url_base    → str com a URL raiz do site
        - buscar()    → método principal que retorna lista de vagas
    """

    nome_fonte: str = ""
    url_base: str = ""

    def __init__(self):
        self.ua = UserAgent()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.ua.random})
        self.vagas_encontradas: list = []

    # ─────────────────────────────────────────────
    #  MÉTODO PRINCIPAL — deve ser implementado
    # ─────────────────────────────────────────────

    @abstractmethod
    def buscar(self, cargo: str, localizacao: str = "",
               skills: list = None) -> list:
        """
        Realiza a busca de vagas no site.

        Parâmetros:
            cargo       → título da vaga (ex: "Analista de Dados")
            localizacao → cidade/estado (ex: "São Paulo")
            skills      → lista de habilidades (ex: ["Python", "SQL"])

        Retorna:
            Lista de dicts no formato padrão (veja _vaga_padrao)
        """
        pass

    # ─────────────────────────────────────────────
    #  FORMATO PADRÃO DE VAGA
    # ─────────────────────────────────────────────

    def _vaga_padrao(self,
                     titulo: str = "",
                     empresa: str = "",
                     localizacao: str = "",
                     modalidade: str = "",
                     salario: str = "",
                     descricao: str = "",
                     skills: list = None,
                     link: str = "",
                     data_pub: str = "") -> dict:
        """
        Retorna um dicionário no formato padrão de vaga.
        Use este método em todos os scrapers para garantir consistência.
        """
        return {
            "titulo": titulo.strip(),
            "empresa": empresa.strip(),
            "localizacao": localizacao.strip(),
            "modalidade": modalidade.strip().lower(),   # remoto/hibrido/presencial
            "salario": salario.strip(),
            "descricao": descricao.strip(),
            "skills": skills or [],
            "link": link.strip(),
            "fonte": self.nome_fonte,
            "data_pub": data_pub or datetime.now().strftime("%Y-%m-%d"),
        }

    # ─────────────────────────────────────────────
    #  UTILITÁRIOS HTTP
    # ─────────────────────────────────────────────

    def _get(self, url: str, params: dict = None,
             timeout: int = 15) -> requests.Response | None:
        """GET com tratamento de erro e user-agent rotativo."""
        try:
            self.session.headers.update({"User-Agent": self.ua.random})
            response = self.session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            print(f"[{self.nome_fonte}] Erro ao acessar {url}: {e}")
            return None

    def _soup(self, url: str, params: dict = None) -> BeautifulSoup | None:
        """Retorna BeautifulSoup da página ou None em caso de erro."""
        response = self._get(url, params)
        if response:
            return BeautifulSoup(response.text, "lxml")
        return None

    def _esperar(self, min_seg: float = 1.0, max_seg: float = 3.0):
        """Pausa aleatória para evitar bloqueio."""
        tempo = random.uniform(min_seg, max_seg)
        time.sleep(tempo)

    # ─────────────────────────────────────────────
    #  UTILITÁRIOS DE TEXTO
    # ─────────────────────────────────────────────

    def _extrair_skills(self, texto: str, skills_busca: list) -> list:
        """
        Verifica quais skills da busca aparecem no texto da vaga.
        Útil para popular o campo skills de cada vaga encontrada.
        """
        texto_lower = texto.lower()
        encontradas = []
        for skill in skills_busca:
            if skill.lower() in texto_lower:
                encontradas.append(skill)
        return encontradas

    def _extrair_softskills(self, texto: str) -> list:
        """Detecta soft skills comportamentais no texto da vaga."""
        return extrair_softskills(texto)

    def _enriquecer_descricao(self, descricao: str, softskills: list) -> str:
        """
        Appende as soft skills detectadas à descrição da vaga.
        Retorna a descrição original se não houver soft skills.
        """
        if not softskills:
            return descricao
        bloco = "🧠 Soft Skills: " + " • ".join(softskills)
        return (descricao.strip() + "\n\n" + bloco).strip()

    def _detectar_modalidade(self, texto: str) -> str:
        """Detecta se a vaga é remota, híbrida ou presencial pelo texto."""
        texto_lower = texto.lower()
        if any(p in texto_lower for p in ["100% remoto", "home office", "trabalho remoto", "remote"]):
            return "remoto"
        elif any(p in texto_lower for p in ["híbrido", "hibrido", "hybrid"]):
            return "hibrido"
        elif any(p in texto_lower for p in ["presencial", "on-site", "onsite"]):
            return "presencial"
        return ""

    def _limpar_texto(self, texto: str) -> str:
        """Remove espaços extras e caracteres indesejados."""
        if not texto:
            return ""
        return " ".join(texto.split()).strip()

    # ─────────────────────────────────────────────
    #  REPR
    # ─────────────────────────────────────────────

    def __repr__(self):
        return f"<Scraper: {self.nome_fonte} | {self.url_base}>"