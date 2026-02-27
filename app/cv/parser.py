"""
parser.py — Converte texto livre de CV em YAML compatível com rendercv.

O parser usa heurísticas com regex para identificar seções em PT-BR e EN.
As chaves de seção no YAML gerado são em português (Resumo, Experiência, etc.).
O YAML gerado é um ponto de partida editável — não precisa ser perfeito.
"""

import re
import yaml


# Mapeamento de headers comuns → chave PT-BR da seção
# A ordem importa: padrões mais específicos primeiro.
_SECOES_REGEX = [
    (r"experi[eê]ncias?\s*(profissionais?|adicionais?)?|experience|hist[oó]rico profissional", "Experiência"),
    (r"forma[cç][aã]o|educa[cç][aã]o|education|acad[eê]mico", "Formação"),
    (r"habilidades|compet[eê]ncias|skills|conhecimentos|tecnologia", "Habilidades"),
    (r"resumo|perfil|objetivo|sobre mim|summary|profile", "Resumo"),
    (r"certifica[cç][oõ]es?|cursos|certifications", "Certificações"),
    (r"idiomas?|languages|l[íi]nguas?", "Idiomas"),
    (r"projetos?|projects|portf[oó]lio", "Projetos"),
    (r"premia[cç][oõ]es?|reconhecimentos?|awards", "Premiações"),
]

# Prefixos de bullet comuns em PDFs
_BULLET_RE = re.compile(r'^[•·►▸▷\-\*]\s*')


def texto_para_yaml(texto: str) -> str:
    """Converte texto livre de CV em YAML rendercv editável."""
    dados = _extrair_estrutura(texto)
    return yaml.dump(
        {"cv": dados, "design": {"theme": "classic"}},
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )


# ── Normalização ──────────────────────────────────────────────────────────────

def _normalizar_texto(texto: str) -> str:
    """
    Corrige caracteres unicode problemáticos vindos de PDFs e outros artefatos.
    - Substitui variantes de hífen por hífen simples (-)
    - Corrige e-mails com espaço no meio: 'cae tanosql@...' → 'caetanosql@...'
    """
    subs = {
        '\u2011': '-',   # non-breaking hyphen
        '\u2010': '-',   # hyphen
        '\u00ad': '',    # soft hyphen (remove)
        '\u2019': "'",   # right single quotation mark
        '\u201c': '"',   # left double quotation mark
        '\u201d': '"',   # right double quotation mark
        '\u2022': '•',   # bullet
        '\u00b7': '·',   # middle dot
    }
    for ch, rep in subs.items():
        texto = texto.replace(ch, rep)

    # Corrige e-mail com palavra quebrada pelo PDF na MESMA linha: "cae tanosql@" → "caetanosql@"
    # Usa [ \t]+ em vez de \s+ para NÃO cruzar quebras de linha
    texto = re.sub(
        r'(\w{2,})[ \t]+(\w{2,}@[\w.\-]+\.[a-z]{2,})',
        r'\1\2',
        texto,
        flags=re.I,
    )
    return texto


# ── Extração principal ────────────────────────────────────────────────────────

def _normalizar_telefone(raw: str) -> str:
    """
    Converte o telefone bruto para E.164 (+5511999999999).
    Retorna string vazia se não for um número válido.
    """
    try:
        import phonenumbers
        parsed = phonenumbers.parse(raw, "BR")
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164)
    except Exception:
        pass
    return ""


def _extrair_estrutura(texto: str) -> dict:
    texto    = _normalizar_texto(texto)
    linhas   = [l for l in texto.splitlines() if l.strip()]

    nome     = _detectar_nome(linhas)
    email    = _regex_find(r"[\w.+\-]+@[\w.\-]+\.[a-z]{2,}", texto)
    tel_raw  = _regex_find(r"[\+\(]?[\d][\d\s\-\(\)\.]{7,20}[\d]", texto)
    telefone = _normalizar_telefone(tel_raw) if tel_raw else ""
    linkedin = _regex_find(r"linkedin\.com/in/[\w\-]+", texto)
    github   = _regex_find(r"github\.com/[\w\-]+", texto)

    contatos = {}
    if email:
        contatos["email"] = email
    if telefone:
        contatos["phone"] = telefone
    if linkedin:
        contatos["social_networks"] = [
            {"network": "LinkedIn", "username": linkedin.split("/in/")[-1]}
        ]
    if github:
        redes = contatos.get("social_networks", [])
        redes.append({"network": "GitHub", "username": github.split("github.com/")[-1]})
        contatos["social_networks"] = redes

    secoes = _segmentar_secoes(linhas)

    estrutura = {"name": nome or "Seu Nome"}
    estrutura.update(contatos)
    estrutura["sections"] = secoes
    return estrutura


def _detectar_nome(linhas: list) -> str:
    """Heurística: primeira linha não vazia que não parece e-mail/tel/URL."""
    for linha in linhas[:5]:
        l = linha.strip()
        if not l:
            continue
        if re.search(r"[@://]|curriculum|resum[eé]|cv\b", l, re.I):
            continue
        if re.match(r"^[\+\d\(\)\-\s]{7,}$", l):
            continue
        return l
    return ""


def _regex_find(pattern: str, texto: str) -> str:
    m = re.search(pattern, texto, re.I)
    return m.group(0) if m else ""


# ── Segmentação de seções ─────────────────────────────────────────────────────

def _e_header_secao(linha: str) -> str | None:
    """
    Retorna a chave PT-BR da seção se a linha for um cabeçalho de seção,
    ou None caso contrário.

    Aceita:
      - Match exato:              "Resumo"
      - Header com sufixo curto:  "Resumo Profissional", "Competências Técnicas"
      - Header com separador:     "Habilidades:"
    Rejeita linhas longas (> 60 chars) ou com 7+ palavras (provavelmente conteúdo).
    """
    l = linha.strip()
    if not l or len(l) > 60 or len(l.split()) > 6:
        return None
    # Não é header se começa com bullet ou parêntese (é conteúdo)
    if _BULLET_RE.match(l) or l.startswith('('):
        return None
    for padrao, chave in _SECOES_REGEX:
        if (re.fullmatch(padrao, l, re.I)
                or re.match(rf"^({padrao})\s*[:：]?\s*$", l, re.I)
                or re.match(rf"^({padrao})\b", l, re.I)):
            return chave
    return None


def _segmentar_secoes(linhas: list) -> dict:
    """
    Divide as linhas do CV pelos headers detectados.
    Retorna dict {chave_PT: [items]}.
    Seções duplicadas (ex: Objetivo + Resumo → ambos Resumo) são mescladas.
    """
    breaks = []
    for i, linha in enumerate(linhas):
        chave = _e_header_secao(linha)
        if chave:
            breaks.append((i, chave))

    if not breaks:
        return {"Resumo": [" ".join(linhas[:10])]}

    secoes: dict = {}

    for idx_break, (start, chave) in enumerate(breaks):
        end      = breaks[idx_break + 1][0] if idx_break + 1 < len(breaks) else len(linhas)
        bloco_raw = [l.strip() for l in linhas[start + 1:end] if l.strip()]
        if not bloco_raw:
            continue

        bloco = _juntar_continuacoes(bloco_raw)
        novos = _processar_bloco(chave, bloco)

        # Mescla se chave já existe (ex: Objetivo + Resumo Profissional → Resumo)
        if chave in secoes:
            secoes[chave].extend(novos)
        else:
            secoes[chave] = novos

    return secoes


def _juntar_continuacoes(linhas: list) -> list:
    """
    Junta linhas de continuação de bullet multi-linha.
    Regra: se a linha anterior não termina com pontuação de fim de frase
    (.  !  ?) e a linha atual não começa com bullet, é continuação.
    """
    _FIM_FRASE = re.compile(r'[.!?]\s*$')
    resultado = []
    for linha in linhas:
        eh_bullet = bool(_BULLET_RE.match(linha))
        if not eh_bullet and resultado:
            anterior = resultado[-1]
            if not _FIM_FRASE.search(anterior):
                resultado[-1] = anterior.rstrip() + ' ' + linha
                continue
        resultado.append(linha)
    return resultado


def _processar_bloco(chave: str, bloco: list) -> list:
    """Converte as linhas de um bloco no formato correto para a chave."""

    if chave == "Resumo":
        texto = " ".join(
            _BULLET_RE.sub('', l) for l in bloco
        ).strip()
        return [texto]

    if chave == "Habilidades":
        items = []
        for linha in bloco:
            limpo = _BULLET_RE.sub('', linha).strip()
            if limpo:
                items.append({"label": limpo, "details": ""})
        if not items:
            tudo = ", ".join(bloco)
            items = [{"label": "Tecnologias", "details": tudo}]
        return items

    if chave == "Idiomas":
        items = []
        for linha in bloco:
            limpo  = _BULLET_RE.sub('', linha).strip()
            partes = re.split(r"\s*[–\-:]\s*", limpo, maxsplit=1)
            if len(partes) == 2:
                items.append({"label": partes[0].strip(), "details": partes[1].strip()})
            else:
                items.append({"label": limpo, "details": "Fluente"})
        return items

    # Experiência / Formação / Projetos / Certificações / Premiações
    return [
        {"bullet": _BULLET_RE.sub('', l).strip()}
        for l in bloco
        if _BULLET_RE.sub('', l).strip()
    ]
