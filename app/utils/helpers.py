"""
helpers.py
Funções utilitárias gerais do projeto.
Local do arquivo: D:\\PORTFOLIO\\Job Aggregator\\app\\utils\\helpers.py
"""

import re
from datetime import datetime, timedelta
from dateutil import parser as date_parser

# ─── Soft Skills (mercado brasileiro) ────────────────────────────────
# Cada entrada: (nome_canônico, [padrões em minúsculas para busca])
_SOFTSKILLS_BR = [
    ("Comunicação",                 ["comunicação eficaz", "boa comunicação", "comunicativo",
                                     "comunicativa", "habilidades de comunicação",
                                     "excelente comunicação", "comunicação clara"]),
    ("Trabalho em Equipe",          ["trabalho em equipe", "team player", "espírito de equipe",
                                     "trabalho colaborativo em equipe"]),
    ("Liderança",                   ["liderança", "gestão de equipes", "gestão de pessoas",
                                     "liderar equipes", "capacidade de liderança"]),
    ("Proatividade",                ["proatividade", "proativo", "proativa"]),
    ("Autonomia",                   ["autonomia", "autônomo", "autônoma", "trabalho autônomo"]),
    ("Iniciativa",                  ["iniciativa", "iniciativa própria", "tomada de iniciativa"]),
    ("Resolução de Problemas",      ["resolução de problemas", "problem solving",
                                     "solução de problemas", "análise e solução de problemas"]),
    ("Pensamento Crítico",          ["pensamento crítico", "raciocínio crítico",
                                     "análise crítica"]),
    ("Organização",                 ["organizado", "organizada", "habilidades organizacionais",
                                     "capacidade de organização"]),
    ("Gestão do Tempo",             ["gestão do tempo", "gerenciamento do tempo",
                                     "administração do tempo"]),
    ("Criatividade",                ["criatividade", "criativo", "criativa",
                                     "pensamento criativo"]),
    ("Inovação",                    ["inovação", "inovador", "inovadora",
                                     "mindset inovador", "perfil inovador"]),
    ("Flexibilidade",               ["flexibilidade", "flexível"]),
    ("Adaptabilidade",              ["adaptabilidade", "adaptável"]),
    ("Resiliência",                 ["resiliência", "resiliente"]),
    ("Empatia",                     ["empatia", "empático", "empática"]),
    ("Inteligência Emocional",      ["inteligência emocional"]),
    ("Relacionamento Interpessoal", ["relacionamento interpessoal", "habilidades interpessoais",
                                     "relacionamento com clientes", "relacionamento com stakeholders"]),
    ("Foco em Resultados",          ["foco em resultados", "orientado a resultados",
                                     "orientada a resultados", "orientação para resultados"]),
    ("Senso de Urgência",           ["senso de urgência"]),
    ("Aprendizado Contínuo",        ["aprendizado contínuo", "aprendizado rápido",
                                     "vontade de aprender", "disposição para aprender",
                                     "busca por conhecimento"]),
    ("Curiosidade",                 ["curiosidade intelectual", "perfil curioso",
                                     "mentalidade curiosa"]),
    ("Negociação",                  ["negociação", "capacidade de negociação",
                                     "habilidade de negociação"]),
    ("Dinamismo",                   ["dinamismo", "dinâmico", "dinâmica"]),
    ("Comprometimento",             ["comprometimento", "comprometido", "comprometida"]),
    ("Dedicação",                   ["dedicação", "dedicado", "dedicada"]),
    ("Responsabilidade",            ["senso de responsabilidade"]),
    ("Visão Estratégica",           ["visão estratégica", "pensamento estratégico"]),
    ("Colaboração",                 ["colaboração", "colaborativo", "colaborativa"]),
    ("Multitarefas",                ["multitarefas"]),
    ("Ética Profissional",          ["ética profissional", "conduta ética"]),
    ("Networking",                  ["networking"]),
    ("Coaching / Mentoria",         ["coaching", "mentoria"]),
    ("Gestão de Conflitos",         ["gestão de conflitos", "resolução de conflitos"]),
    ("Planejamento",                ["planejamento estratégico", "capacidade de planejamento"]),
    ("Criatividade na Solução",     ["solução criativa", "abordagem criativa"]),
]


def normalizar_cargo(cargo: str) -> str:
    """
    Normaliza o título do cargo para busca.
    Ex: '  Analista  de  Dados ' → 'analista de dados'
    """
    return " ".join(cargo.strip().lower().split())


def normalizar_skills(skills_str: str) -> list:
    """
    Converte string de skills em lista limpa.
    Ex: 'Python, SQL, Excel' → ['Python', 'SQL', 'Excel']
    """
    if not skills_str:
        return []
    return [s.strip() for s in re.split(r"[,;|\n]", skills_str) if s.strip()]


def calcular_match_score(skills_vaga: list, skills_usuario: list) -> int:
    """
    Calcula o % de match entre as skills da vaga e do usuário.
    Retorna inteiro de 0 a 100.
    """
    if not skills_vaga or not skills_usuario:
        return 0
    vaga_lower = [s.lower() for s in skills_vaga]
    usuario_lower = [s.lower() for s in skills_usuario]
    matches = sum(1 for s in usuario_lower if s in vaga_lower)
    return int((matches / len(skills_vaga)) * 100)


def formatar_data_relativa(data_str: str) -> str:
    """
    Converte string de data em formato relativo legível.
    Ex: '2024-01-15' → 'há 3 dias'
    """
    if not data_str:
        return "Data desconhecida"
    try:
        data = date_parser.parse(data_str)
        agora = datetime.now()
        diff = agora - data

        if diff.days == 0:
            return "Hoje"
        elif diff.days == 1:
            return "Ontem"
        elif diff.days < 7:
            return f"há {diff.days} dias"
        elif diff.days < 30:
            semanas = diff.days // 7
            return f"há {semanas} semana{'s' if semanas > 1 else ''}"
        elif diff.days < 365:
            meses = diff.days // 30
            return f"há {meses} mês/meses"
        else:
            return data.strftime("%d/%m/%Y")
    except Exception:
        return data_str


def truncar_texto(texto: str, limite: int = 200) -> str:
    """Trunca texto longo adicionando reticências."""
    if not texto or len(texto) <= limite:
        return texto or ""
    return texto[:limite].rsplit(" ", 1)[0] + "..."


def detectar_modalidade_texto(texto: str) -> str:
    """Detecta modalidade de trabalho pelo texto da vaga."""
    texto_lower = texto.lower()
    if any(p in texto_lower for p in ["100% remoto", "home office", "totalmente remoto", "remote"]):
        return "remoto"
    elif any(p in texto_lower for p in ["híbrido", "hibrido", "hybrid"]):
        return "hibrido"
    elif any(p in texto_lower for p in ["presencial", "on-site"]):
        return "presencial"
    return "não informado"


def formatar_salario(salario: str) -> str:
    """Padroniza exibição do salário."""
    if not salario or salario.strip() == "":
        return "Não informado"
    return salario.strip()


def extrair_softskills(texto: str) -> list:
    """
    Detecta soft skills mencionadas no texto de uma vaga.
    Retorna lista de nomes canônicos únicos, ex: ['Liderança', 'Proatividade'].
    A busca é case-insensitive e sem distinção de acentos redundantes.
    """
    if not texto:
        return []
    texto_lower = texto.lower()
    encontradas = []
    for canonical, padroes in _SOFTSKILLS_BR:
        if any(p in texto_lower for p in padroes):
            encontradas.append(canonical)
    return encontradas


# Teste rápido
if __name__ == "__main__":
    print(normalizar_skills("Python, SQL, Excel, Power BI"))
    print(calcular_match_score(["Python", "SQL", "Excel"], ["Python", "Excel"]))
    print(formatar_data_relativa("2024-01-01"))
    print(truncar_texto("Este é um texto muito longo que precisa ser truncado para caber na interface.", 40))
    print(extrair_softskills("Buscamos profissional proativo, com boa comunicação e foco em resultados."))