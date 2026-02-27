"""
extractor.py — Extrai texto puro de arquivos .pdf ou .docx.

Estratégia para PDF (da mais precisa para fallback):
  1. Análise de caracteres individuais (page.chars) com detecção de
     espaços por gap entre bounding-boxes → resolve palavras coladas
  2. extract_words() com agrupamento por posição
  3. extract_text() simples
O melhor resultado é escolhido por heurística (menos palavras longas/coladas).
Pós-processamento: separação de camelCase e limpeza de espaços.
"""

import re


# ── Entrada pública ───────────────────────────────────────────────────────────

def extrair_texto(caminho: str) -> str:
    """Extrai texto puro de .pdf ou .docx."""
    lower = caminho.lower()
    if lower.endswith(".pdf"):
        return _de_pdf(caminho)
    elif lower.endswith(".docx"):
        return _de_docx(caminho)
    raise ValueError(f"Formato não suportado: {caminho}")


# ── PDF ───────────────────────────────────────────────────────────────────────

def _de_pdf(caminho: str) -> str:
    import pdfplumber

    with pdfplumber.open(caminho) as pdf:
        partes = []
        for page in pdf.pages:
            txt = _melhor_texto(page)
            if txt.strip():
                partes.append(txt)

            # Captura texto de tabelas que as outras estratégias ignoram
            for tabela in page.extract_tables():
                for linha in tabela:
                    celulas = [c.strip() for c in linha if c and c.strip()]
                    if celulas:
                        partes.append(" | ".join(celulas))

    texto = "\n".join(partes)
    texto = _pos_processar(texto)

    # Remove linhas duplicadas (artefato de sobreposição na extração)
    vistas: set = set()
    linhas_unicas = []
    for linha in texto.splitlines():
        l = linha.strip()
        if l and l not in vistas:
            vistas.add(l)
            linhas_unicas.append(l)

    return "\n".join(linhas_unicas)


def _melhor_texto(page) -> str:
    """
    Tenta três estratégias e escolhe a que produz menos palavras coladas.
    """
    candidatos: dict[str, str] = {}

    # 1 — Nível de caractere (mais preciso para espaçamento)
    if page.chars:
        t = _chars_para_texto(page.chars)
        if t.strip():
            candidatos["chars"] = t

    # 2 — extract_words com agrupamento posicional
    palavras = page.extract_words(x_tolerance=3, y_tolerance=3,
                                  keep_blank_chars=False)
    if palavras:
        t = _palavras_para_linhas(palavras)
        if t.strip():
            candidatos["words"] = t

    # 3 — extract_text com x_tolerance mínimo (insere mais espaços)
    t = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
    if t.strip():
        candidatos["text"] = t

    if not candidatos:
        return ""

    # Escolhe o candidato com menor proporção de palavras muito longas.
    # Emails e URLs são excluídos da penalidade (são legitimamente longos).
    def _eh_url_email(p: str) -> bool:
        return "@" in p or "://" in p or (p.count(".") >= 2 and len(p) > 10)

    def _score(txt: str) -> float:
        tokens = [p for p in txt.split() if len(p) > 1]
        if not tokens:
            return -1.0
        longas = sum(1 for p in tokens if len(p) > 18 and not _eh_url_email(p))
        return -(longas / len(tokens))   # menos negativo = melhor

    return max(candidatos.values(), key=_score)


def _chars_para_texto(chars: list) -> str:
    """
    Reconstrói texto a partir dos caracteres individuais do PDF.
    Detecta espaços comparando o gap entre bounding-boxes de caracteres
    consecutivos: gap ≥ 25 % da largura do caractere anterior → espaço.
    """
    # Filtra chars sem texto e deduplica posições exatas
    vistos: set = set()
    filtrados = []
    for c in chars:
        txt = c.get("text", "")
        if not txt:
            continue
        chave = (round(c["x0"], 1), round(c["top"], 1))
        if chave not in vistos:
            vistos.add(chave)
            filtrados.append(c)

    if not filtrados:
        return ""

    filtrados.sort(key=lambda c: (round(c["top"], 1), c["x0"]))

    # Agrupa em linhas (tolerância vertical de 4 pt)
    linhas: list[list] = [[filtrados[0]]]
    for c in filtrados[1:]:
        if abs(c["top"] - linhas[-1][-1]["top"]) > 4:
            linhas.append([])
        linhas[-1].append(c)

    resultado = []
    for linha in linhas:
        linha.sort(key=lambda c: c["x0"])
        texto = ""
        for i, c in enumerate(linha):
            if i > 0:
                prev     = linha[i - 1]
                gap      = c["x0"] - prev["x1"]
                char_w   = max(prev["x1"] - prev["x0"], 1.0)
                # Hífens e travessões são estreitos: usar threshold maior para
                # evitar espaços falsos em palavras compostas (e-mail, 92085-6714)
                threshold = 1.0 if prev.get("text", "") in ("-", "\u2010", "\u2011") else 0.25
                if gap >= char_w * threshold:
                    texto += " "
            texto += c.get("text", "")
        if texto.strip():
            resultado.append(texto)

    return "\n".join(resultado)


def _palavras_para_linhas(palavras: list) -> str:
    """
    Reconstrói texto com quebras de linha corretas a partir da lista
    de palavras do pdfplumber (agrupa por posição vertical, tolerância 4 pt).
    """
    if not palavras:
        return ""

    palavras = sorted(palavras, key=lambda w: (w["top"], w["x0"]))
    linhas: list[list] = [[palavras[0]]]

    for p in palavras[1:]:
        if abs(p["top"] - linhas[-1][-1]["top"]) > 4:
            linhas.append([])
        linhas[-1].append(p)

    resultado = []
    for linha in linhas:
        linha.sort(key=lambda w: w["x0"])
        resultado.append(" ".join(p["text"] for p in linha))

    return "\n".join(resultado)


def _pos_processar(texto: str) -> str:
    """
    Pós-processamento para corrigir concatenações comuns:
    - camelCase genuíno: pelaAudac → pela Audac
      Só separa quando há ≥3 letras antes E ≥3 letras minúsculas após a maiúscula,
      para evitar quebrar termos legítimos como NumPy, MySQL, GitHub, LinkedIn.
    - Travessão/meia-risca sem espaço após: "Audac –Telemarketing" → "Audac – Telemarketing"
    """
    # Espaço após travessão/meia-risca quando imediatamente seguido por caractere não-espaço
    texto = re.sub(r'([–—])([^\s–—])', r'\1 \2', texto)

    # Ao menos 3 letras minúsculas antes + Maiúscula + ao menos 3 letras minúsculas depois
    texto = re.sub(
        r'([a-záéíóúàâêîôûãõçœ]{3,})([A-ZÁÉÍÓÚÀÂÊÎÔÛÃÕÇ][a-záéíóúàâêîôûãõçœ]{3,})',
        r'\1 \2',
        texto,
    )
    return texto


# ── DOCX ──────────────────────────────────────────────────────────────────────

def _de_docx(caminho: str) -> str:
    from docx import Document
    doc = Document(caminho)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
