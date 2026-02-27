"""
html_renderer.py — Gerador de currículo em HTML+CSS com conversão para PDF.

Formatos disponíveis:
  executivo_azul    — Clássico com acento azul (baseado no modelo 1)
  elegante_br       — Elegante brasileiro centralizado (baseado no modelo 2)
  compacto_academico — Layout compacto para CVs técnicos/acadêmicos
  moderno_conectado — Design moderno com links clicáveis (e-mail, LinkedIn, GitHub)

Conversão HTML → PDF:
  1. Microsoft Edge headless (--print-to-pdf)
  2. Google Chrome headless
  3. weasyprint (se instalado)
  4. xhtml2pdf/pisa (se instalado)
  5. Fallback: abre HTML no navegador → Ctrl+P → Salvar como PDF
"""

import os
import shutil
import subprocess
import tempfile
import webbrowser

import yaml
from pathlib import Path


# ── Localização do browser ────────────────────────────────────────────────────

def _encontrar_browser() -> str:
    """Retorna caminho para Edge ou Chrome instalado no sistema."""
    # Registro do Windows (mais confiável)
    exe = _edge_via_registro()
    if exe:
        return exe
    candidatos = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for p in candidatos:
        if os.path.exists(p):
            return p
    for nome in ("msedge", "chrome", "chromium-browser", "chromium"):
        found = shutil.which(nome)
        if found:
            return found
    return ""


def _edge_via_registro() -> str:
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe",
        )
        path, _ = winreg.QueryValueEx(key, "")
        winreg.CloseKey(key)
        return path if os.path.exists(path) else ""
    except Exception:
        return ""


# ── HTML → PDF ────────────────────────────────────────────────────────────────

def html_para_pdf(html_content: str, destino: str) -> str:
    """
    Converte HTML em PDF usando o melhor método disponível.
    Retorna o caminho do PDF gerado. Lança RuntimeError se tudo falhar.
    """
    browser = _encontrar_browser()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path  = Path(tmp)
        html_path = tmp_path / "curriculo.html"
        html_path.write_text(html_content, encoding="utf-8")
        pdf_path  = tmp_path / "curriculo.pdf"
        html_url  = "file:///" + str(html_path).replace("\\", "/")

        # ── Tentativa 1: Edge / Chrome headless ──────────────────────────
        if browser:
            for headless in ("--headless=new", "--headless"):
                try:
                    subprocess.run(
                        [
                            browser, headless, "--disable-gpu",
                            f"--print-to-pdf={pdf_path}",
                            "--no-pdf-header-footer",       # Chrome/Edge ≥ 112
                            "--print-to-pdf-no-header",     # versões mais antigas
                            "--no-first-run",
                            "--no-default-browser-check",
                            html_url,
                        ],
                        capture_output=True,
                        timeout=60,
                    )
                    if pdf_path.exists() and pdf_path.stat().st_size > 500:
                        shutil.copy(str(pdf_path), destino)
                        return destino
                    pdf_path.unlink(missing_ok=True)
                except Exception:
                    continue

        # ── Tentativa 2: weasyprint ───────────────────────────────────────
        try:
            from weasyprint import HTML  # type: ignore
            HTML(string=html_content).write_pdf(destino)
            return destino
        except ImportError:
            pass
        except Exception:
            pass

        # ── Tentativa 3: xhtml2pdf (pisa) ─────────────────────────────────
        try:
            from xhtml2pdf import pisa  # type: ignore
            with open(destino, "wb") as f:
                result = pisa.CreatePDF(html_content.encode("utf-8"), dest=f)
            if not result.err:
                return destino
        except ImportError:
            pass
        except Exception:
            pass

    # ── Fallback: salva HTML e abre no navegador ──────────────────────────
    html_destino = str(Path(destino).with_suffix(".html"))
    Path(html_destino).write_text(html_content, encoding="utf-8")
    webbrowser.open("file:///" + html_destino.replace("\\", "/"))
    raise RuntimeError(
        f"Currículo salvo como HTML em:\n{html_destino}\n\n"
        "Aberto no navegador. Use Ctrl+P → 'Salvar como PDF' para exportar o PDF."
    )


# ── Dispatcher ────────────────────────────────────────────────────────────────

def gerar_pdf_formato(tema: str, yaml_content: str, destino: str) -> str:
    """Gera PDF de formato customizado a partir do conteúdo YAML."""
    dados = yaml.safe_load(yaml_content)
    cv    = dados.get("cv", {}) if isinstance(dados, dict) else {}

    if tema == "executivo_azul":
        html = _template_executivo_azul(cv)
    elif tema == "elegante_br":
        html = _template_elegante_br(cv)
    elif tema == "compacto_academico":
        html = _template_compacto_academico(cv)
    elif tema == "moderno_conectado":
        html = _template_moderno_conectado(cv)
    else:
        raise ValueError(f"Tema HTML desconhecido: {tema}")

    return html_para_pdf(html, destino)


# ── Helpers compartilhados ────────────────────────────────────────────────────

_ORDEM_SECOES = [
    "Resumo", "Experiência", "Formação", "Projetos",
    "Certificações", "Habilidades", "Idiomas", "Premiações",
]

_LABELS_AZUL = {
    "Resumo":        "Resumo Profissional",
    "Experiência":   "Experiência Profissional",
    "Formação":      "Formação Acadêmica",
    "Habilidades":   "Habilidades & Tecnologias",
    "Certificações": "Certificações",
    "Idiomas":       "Idiomas",
    "Projetos":      "Projetos",
    "Premiações":    "Premiações",
}

_LABELS_BR = {
    "Resumo":        "Perfil",
    "Experiência":   "Experiência Profissional",
    "Formação":      "Formação",
    "Habilidades":   "Competências",
    "Certificações": "Certificações",
    "Idiomas":       "Idiomas",
    "Projetos":      "Projetos",
    "Premiações":    "Premiações",
}


def _campos_entrada(item: dict) -> tuple:
    title      = item.get("institution") or item.get("company") or item.get("name", "")
    position   = item.get("position") or item.get("degree") or item.get("area", "")
    start      = str(item.get("start_date", ""))
    end        = str(item.get("end_date", "presente"))
    location   = item.get("location", "")
    highlights = item.get("highlights") or []
    return title, position, start, end, location, highlights


def _bullets_html(highlights: list) -> str:
    if not highlights:
        return ""
    itens = "".join(f"<li>{h}</li>" for h in highlights)
    return f"<ul>{itens}</ul>"


def _skills_lista(items: list) -> list:
    """
    Extrai lista plana de skills de diferentes formatos de entrada.

    Formatos suportados:
      - str puro                          → split por vírgula
      - {"bullet": "..."}                 → item direto (sem split)
      - {"label": "Python (pandas...)",   → label como item direto (details vazio)
         "details": ""}
      - {"label": "Tecnologias",          → split de details por vírgula
         "details": "Python, SQL, Excel"}
    """
    _GENERICOS = {"tecnologias", "skills", "habilidades", "competências",
                  "conhecimentos", "ferramentas"}
    skills = []
    for item in items:
        if isinstance(item, str):
            for s in item.split(","):
                s = s.strip()
                if s:
                    skills.append(s)
        elif isinstance(item, dict):
            if "bullet" in item:
                skills.append(item["bullet"])
            else:
                details = item.get("details", "")
                label   = item.get("label", "")
                if details:
                    if label.lower().strip() in _GENERICOS:
                        # Label genérico: divide details por vírgula
                        for s in details.split(","):
                            s = s.strip()
                            if s:
                                skills.append(s)
                    else:
                        # Label específico com details: usa como um único item
                        skills.append(f"{label}: {details}")
                elif label:
                    # Sem details: usa label inteiro como item (ex: "Python (pandas, NumPy)")
                    skills.append(label)
    return skills


def _rede_social(cv: dict, network: str) -> str:
    for s in cv.get("social_networks", []):
        if s.get("network", "").lower() == network.lower():
            return s.get("username", "")
    return ""


# ── Formato 1: Executivo Azul ─────────────────────────────────────────────────
# Inspirado no modelo clássico com acento azul (modelo.png)

def _template_executivo_azul(cv: dict) -> str:
    nome     = cv.get("name", "Seu Nome")
    email    = cv.get("email", "")
    phone    = cv.get("phone", "")
    loc      = cv.get("location", "")
    website  = cv.get("website", "")
    linkedin = _rede_social(cv, "LinkedIn")
    github   = _rede_social(cv, "GitHub")

    contatos = []
    if loc:      contatos.append(f"📍 {loc}")
    if phone:    contatos.append(f"📞 {phone}")
    if email:    contatos.append(f"✉ {email}")
    if website:  contatos.append(f"🌐 {website}")
    if linkedin: contatos.append(f"LinkedIn: {linkedin}")
    if github:   contatos.append(f"GitHub: {github}")
    contato_html = " &nbsp;·&nbsp; ".join(contatos)

    secoes      = cv.get("sections", {})
    secoes_html = ""

    for key in _ORDEM_SECOES + [k for k in secoes if k not in _ORDEM_SECOES]:
        if key not in secoes:
            continue
        label = _LABELS_AZUL.get(key, key.replace("_", " ").title())
        items = secoes[key]
        corpo = ""
        tem_li = False

        for item in items:
            if isinstance(item, str):
                corpo += f'<p class="summary-p">{item}</p>'
            elif isinstance(item, dict):
                if "bullet" in item:
                    corpo += f'<li>{item["bullet"]}</li>'
                    tem_li = True
                elif "label" in item and "details" in item:
                    if key == "Habilidades":
                        if item["details"]:
                            corpo += (
                                f'<li><strong>{item["label"]}:</strong>'
                                f' {item["details"]}</li>'
                            )
                        else:
                            corpo += f'<li>{item["label"]}</li>'
                        tem_li = True
                    else:
                        corpo += (
                            f'<div class="oneline">'
                            f'<strong>{item["label"]}:</strong>'
                            f' {item["details"]}</div>'
                        )
                else:
                    t, pos, start, end, loc_e, hi = _campos_entrada(item)
                    date_str = f"{start} – {end}" if start else (end if end != "presente" else "")
                    loc_date = " &nbsp;|&nbsp; ".join(filter(None, [loc_e, date_str]))

                    left = ""
                    if t and pos:   left = f"<strong>{t}</strong>, <em>{pos}</em>"
                    elif t:         left = f"<strong>{t}</strong>"
                    elif pos:       left = f"<em>{pos}</em>"

                    corpo += (
                        f'<div class="entry">'
                        f'<div class="entry-header">'
                        f'<span class="entry-left">{left}</span>'
                        f'<span class="entry-right">{loc_date}</span>'
                        f'</div>'
                        f'{_bullets_html(hi)}'
                        f'</div>'
                    )

        if tem_li:
            corpo = f"<ul>{corpo}</ul>"

        secoes_html += (
            f'<section>'
            f'<h2 class="sec-title">{label}</h2>'
            f'<div class="sec-body">{corpo}</div>'
            f'</section>'
        )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: 'Segoe UI', Calibri, Arial, sans-serif;
  font-size: 10.5pt;
  color: #1a1a1a;
  background: #fff;
  padding: 36px 48px;
  max-width: 820px;
  margin: 0 auto;
}}
.header {{
  text-align: center;
  margin-bottom: 16px;
}}
.name {{
  font-size: 22pt;
  font-weight: 700;
  color: #1a5fa8;
  letter-spacing: 1px;
}}
.contact {{
  font-size: 8.5pt;
  color: #444;
  margin-top: 6px;
}}
section {{
  margin-top: 14px;
}}
.sec-title {{
  font-size: 10.5pt;
  font-weight: 700;
  color: #1a5fa8;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  border-bottom: 1.5px solid #1a5fa8;
  padding-bottom: 2px;
  margin-bottom: 8px;
}}
.sec-body {{
  padding: 0 2px;
}}
.summary-p {{
  line-height: 1.55;
  text-align: justify;
  margin-bottom: 4px;
}}
.entry {{
  margin-bottom: 9px;
}}
.entry-header {{
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 4px;
}}
.entry-left {{
  flex: 1;
}}
.entry-right {{
  font-size: 8.5pt;
  color: #555;
  text-align: right;
  white-space: nowrap;
}}
ul {{
  padding-left: 18px;
  margin: 4px 0 6px;
  list-style: disc;
}}
li {{
  margin-bottom: 2px;
  line-height: 1.4;
}}
.oneline {{
  margin-bottom: 4px;
}}
@page {{ margin: 1.8cm; }}
@media print {{
  body {{ padding: 0; }}
}}
</style>
</head>
<body>
<div class="header">
  <div class="name">{nome}</div>
  <div class="contact">{contato_html}</div>
</div>
{secoes_html}
</body>
</html>"""


# ── Formato 2: Elegante Brasileiro ───────────────────────────────────────────
# Inspirado no CV elegante PT-BR com nome centralizado em maiúsculas (modelo2.png)

def _template_elegante_br(cv: dict) -> str:
    nome  = cv.get("name", "Seu Nome").upper()
    email = cv.get("email", "")
    phone = cv.get("phone", "")
    loc   = cv.get("location", "")

    secoes = cv.get("sections", {})

    # Inferir cargo da primeira entrada de experiência
    cargo = ""
    if "Experiência" in secoes and secoes["Experiência"]:
        first = secoes["Experiência"][0]
        if isinstance(first, dict):
            cargo = first.get("position") or first.get("degree") or ""

    # Cabeçalho
    header_html = f'<div class="name">{nome}</div>'
    if cargo:
        header_html += f'<div class="cargo">{cargo}</div>'
    if loc:
        header_html += f'<div class="loc">{loc}</div>'

    # Linha de contatos
    contato_html = ""
    if phone or email:
        left  = f'<span class="c-left">{phone}</span>' if phone else ""
        right = f'<span class="c-right">{email}</span>' if email else ""
        contato_html = f'<div class="c-row">{left}{right}</div>'

    secoes_html = ""

    for key in _ORDEM_SECOES + [k for k in secoes if k not in _ORDEM_SECOES]:
        if key not in secoes:
            continue
        label = _LABELS_BR.get(key, key.replace("_", " ").title())
        items = secoes[key]
        corpo = ""

        if key == "Habilidades":
            skills = _skills_lista(items)
            cells  = ""
            for s in skills:
                cells += (
                    f'<div class="sk-row">'
                    f'<span class="sk-name">{s}</span>'
                    f'<span class="sk-fill"></span>'
                    f'<span class="sk-level">Especialista</span>'
                    f'</div>'
                )
            corpo = f'<div class="skills-grid">{cells}</div>'
        else:
            tem_li = False
            for item in items:
                if isinstance(item, str):
                    corpo += f'<p class="profile-p">{item}</p>'
                elif isinstance(item, dict):
                    if "bullet" in item:
                        corpo += f'<li>{item["bullet"]}</li>'
                        tem_li = True
                    elif "label" in item and "details" in item:
                        corpo += (
                            f'<div class="oneline">'
                            f'❖ <strong>{item["label"]}</strong>'
                            f' — {item["details"]}</div>'
                        )
                    else:
                        t, pos, start, end, loc_e, hi = _campos_entrada(item)
                        date_str = f"{start} – {end}" if start else ""

                        titulo = ""
                        if t and pos:   titulo = f"<strong>{pos}, {t}</strong>"
                        elif t:         titulo = f"<strong>{t}</strong>"
                        elif pos:       titulo = f"<strong>{pos}</strong>"

                        corpo += (
                            f'<div class="entry">'
                            f'<div class="entry-header">'
                            f'<span class="entry-titulo">❖ {titulo}</span>'
                            f'<span class="entry-date">{date_str}</span>'
                            f'</div>'
                        )
                        if loc_e:
                            corpo += f'<div class="entry-loc">{loc_e}</div>'
                        corpo += _bullets_html(hi)
                        corpo += '</div>'

            if tem_li:
                corpo = f"<ul>{corpo}</ul>"

        secoes_html += (
            f'<section>'
            f'<h2 class="sec-title">{label.upper()}</h2>'
            f'<div class="sec-body">{corpo}</div>'
            f'</section>'
        )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: 'Georgia', 'Times New Roman', serif;
  font-size: 10.5pt;
  color: #111;
  background: #fff;
  padding: 36px 48px;
  max-width: 820px;
  margin: 0 auto;
}}
.header {{
  text-align: center;
  padding-bottom: 10px;
  border-bottom: 2px solid #1a1a1a;
}}
.name {{
  font-family: 'Segoe UI', Arial, sans-serif;
  font-size: 20pt;
  font-weight: 700;
  letter-spacing: 3px;
  color: #111;
}}
.cargo {{
  font-size: 10.5pt;
  font-style: italic;
  color: #444;
  margin-top: 4px;
}}
.loc {{
  font-size: 8.5pt;
  color: #666;
  margin-top: 3px;
}}
.c-row {{
  display: flex;
  justify-content: space-between;
  font-size: 9pt;
  padding: 6px 2px;
  border-bottom: 1px solid #ccc;
  margin-bottom: 4px;
}}
section {{
  margin-top: 14px;
}}
.sec-title {{
  font-family: 'Segoe UI', Arial, sans-serif;
  font-size: 9.5pt;
  font-weight: 700;
  text-align: center;
  letter-spacing: 2px;
  padding: 4px 0;
  background: #f2f2f2;
  border-top: 1px solid #bbb;
  border-bottom: 1px solid #bbb;
  margin-bottom: 8px;
}}
.sec-body {{
  padding: 0 4px;
}}
.profile-p {{
  text-align: justify;
  line-height: 1.55;
  margin-bottom: 5px;
}}
.entry {{
  margin-bottom: 10px;
}}
.entry-header {{
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}}
.entry-titulo {{
  flex: 1;
}}
.entry-date {{
  font-size: 8.5pt;
  color: #555;
  white-space: nowrap;
}}
.entry-loc {{
  font-size: 8.5pt;
  color: #666;
  font-style: italic;
  padding-left: 16px;
  margin-top: 2px;
}}
ul {{
  padding-left: 20px;
  margin: 4px 0 6px;
  list-style: disc;
}}
li {{
  margin-bottom: 2px;
  line-height: 1.4;
}}
.oneline {{
  margin-bottom: 4px;
}}
/* Skills em grade de 2 colunas com pontinhos */
.skills-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 5px 24px;
}}
.sk-row {{
  display: flex;
  align-items: baseline;
  font-size: 9.5pt;
}}
.sk-name {{
  white-space: nowrap;
}}
.sk-fill {{
  flex: 1;
  border-bottom: 1px dotted #aaa;
  margin: 0 6px;
  height: 0;
  position: relative;
  top: -4px;
}}
.sk-level {{
  font-style: italic;
  white-space: nowrap;
  font-size: 9pt;
}}
@page {{ margin: 1.8cm; }}
@media print {{
  body {{ padding: 0; }}
}}
</style>
</head>
<body>
<div class="header">
  {header_html}
</div>
{contato_html}
{secoes_html}
</body>
</html>"""


# ── Formato 3: Compacto Acadêmico ─────────────────────────────────────────────
# Layout compacto, ideal para CVs acadêmicos e técnicos com muito conteúdo.
# Headers com linha horizontal, fonte menor, margens reduzidas.

def _template_compacto_academico(cv: dict) -> str:
    nome     = cv.get("name", "Seu Nome")
    email    = cv.get("email", "")
    phone    = cv.get("phone", "")
    loc      = cv.get("location", "")
    website  = cv.get("website", "")
    linkedin = _rede_social(cv, "LinkedIn")
    github   = _rede_social(cv, "GitHub")

    contatos = []
    if loc:      contatos.append(loc)
    if phone:    contatos.append(phone)
    if email:    contatos.append(email)
    if website:  contatos.append(website)
    if linkedin: contatos.append(f"LinkedIn: {linkedin}")
    if github:   contatos.append(f"GitHub: {github}")
    contato_html = " · ".join(contatos)

    _LABELS_CA = {
        "Resumo":        "Resumo",
        "Experiência":   "Experiência Profissional",
        "Formação":      "Formação Acadêmica",
        "Habilidades":   "Habilidades Técnicas",
        "Certificações": "Certificações e Cursos",
        "Idiomas":       "Idiomas",
        "Projetos":      "Projetos",
        "Premiações":    "Premiações",
    }

    secoes      = cv.get("sections", {})
    secoes_html = ""

    for key in _ORDEM_SECOES + [k for k in secoes if k not in _ORDEM_SECOES]:
        if key not in secoes:
            continue
        label = _LABELS_CA.get(key, key)
        items = secoes[key]
        corpo = ""
        tem_li = False

        if key == "Habilidades":
            skills = _skills_lista(items)
            colunas = ""
            for i in range(0, len(skills), 2):
                par = skills[i:i+2]
                colunas += "<tr>" + "".join(f"<td>▸ {s}</td>" for s in par) + "</tr>"
            corpo = f'<table class="sk-table"><tbody>{colunas}</tbody></table>'
        else:
            for item in items:
                if isinstance(item, str):
                    corpo += f'<p class="resumo-p">{item}</p>'
                elif isinstance(item, dict):
                    if "bullet" in item:
                        corpo += f'<li>{item["bullet"]}</li>'
                        tem_li = True
                    elif "label" in item and "details" in item:
                        if item["details"]:
                            corpo += f'<div class="oneline"><strong>{item["label"]}:</strong> {item["details"]}</div>'
                        else:
                            corpo += f'<div class="oneline">▸ {item["label"]}</div>'
                    else:
                        t, pos, start, end, loc_e, hi = _campos_entrada(item)
                        date_str = f"{start} – {end}" if start else ""
                        loc_date = "  ·  ".join(filter(None, [loc_e, date_str]))

                        left = ""
                        if t and pos:   left = f"<strong>{t}</strong> — <em>{pos}</em>"
                        elif t:         left = f"<strong>{t}</strong>"
                        elif pos:       left = f"<em>{pos}</em>"

                        corpo += (
                            f'<div class="entry">'
                            f'<div class="entry-header">'
                            f'<span class="entry-left">{left}</span>'
                            f'<span class="entry-right">{loc_date}</span>'
                            f'</div>'
                            f'{_bullets_html(hi)}'
                            f'</div>'
                        )
            if tem_li:
                corpo = f"<ul>{corpo}</ul>"

        secoes_html += (
            f'<section>'
            f'<h2 class="sec-title">{label}</h2>'
            f'<div class="sec-body">{corpo}</div>'
            f'</section>'
        )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: 'Segoe UI', Calibri, Arial, sans-serif;
  font-size: 9.5pt;
  color: #111;
  background: #fff;
  padding: 28px 40px;
  max-width: 820px;
  margin: 0 auto;
}}
.header {{
  text-align: center;
  margin-bottom: 8px;
}}
.name {{
  font-size: 16pt;
  font-weight: 700;
  color: #1a1a2e;
  letter-spacing: 0.5px;
}}
.contact {{
  font-size: 8pt;
  color: #444;
  margin-top: 4px;
}}
.header-line {{
  border: none;
  border-top: 2px solid #1a1a2e;
  margin: 6px 0 0;
}}
section {{
  margin-top: 10px;
}}
.sec-title {{
  font-size: 9pt;
  font-weight: 700;
  color: #1a1a2e;
  text-transform: uppercase;
  letter-spacing: 1px;
  border-bottom: 1px solid #1a1a2e;
  padding-bottom: 1px;
  margin-bottom: 5px;
}}
.sec-body {{
  padding: 0 2px;
}}
.resumo-p {{
  line-height: 1.45;
  text-align: justify;
  margin-bottom: 3px;
  font-size: 9pt;
}}
.entry {{
  margin-bottom: 6px;
}}
.entry-header {{
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 4px;
}}
.entry-left {{
  flex: 1;
  font-size: 9.5pt;
}}
.entry-right {{
  font-size: 8pt;
  color: #555;
  white-space: nowrap;
}}
ul {{
  padding-left: 16px;
  margin: 2px 0 4px;
  list-style: disc;
}}
li {{
  margin-bottom: 1px;
  line-height: 1.35;
  font-size: 9pt;
}}
.oneline {{
  margin-bottom: 3px;
  font-size: 9pt;
}}
.sk-table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 9pt;
}}
.sk-table td {{
  padding: 1px 8px 1px 0;
  width: 50%;
  vertical-align: top;
}}
@page {{ margin: 1.5cm; }}
@media print {{
  body {{ padding: 0; }}
}}
</style>
</head>
<body>
<div class="header">
  <div class="name">{nome}</div>
  <div class="contact">{contato_html}</div>
  <hr class="header-line">
</div>
{secoes_html}
</body>
</html>"""


# ── Formato 4: Moderno Conectado ──────────────────────────────────────────────
# Design moderno com cabeçalho escuro e links clicáveis (e-mail, LinkedIn, GitHub).
# Os links são hipelinks reais no PDF — clicáveis em qualquer leitor de PDF.

_LABELS_MC = {
    "Resumo":        "Resumo Profissional",
    "Experiência":   "Experiência Profissional",
    "Formação":      "Formação Acadêmica",
    "Habilidades":   "Habilidades & Tecnologias",
    "Certificações": "Certificações",
    "Idiomas":       "Idiomas",
    "Projetos":      "Projetos",
    "Premiações":    "Premiações",
}


def _template_moderno_conectado(cv: dict) -> str:
    nome     = cv.get("name", "Seu Nome")
    email    = cv.get("email", "")
    phone    = cv.get("phone", "")
    loc      = cv.get("location", "")
    website  = cv.get("website", "")
    linkedin = _rede_social(cv, "LinkedIn")
    github   = _rede_social(cv, "GitHub")

    # Monta itens de contato com links clicáveis onde aplicável
    contatos = []
    if loc:
        contatos.append(f'<span class="ci">&#128205; {loc}</span>')
    if phone:
        tel_href = "tel:" + phone.replace(" ", "")
        contatos.append(f'<a class="ci" href="{tel_href}">&#128222; {phone}</a>')
    if email:
        contatos.append(f'<a class="ci" href="mailto:{email}">&#9993; {email}</a>')
    if website:
        url = website if website.startswith("http") else f"https://{website}"
        contatos.append(f'<a class="ci" href="{url}">&#127758; {website}</a>')
    if linkedin:
        url = f"https://linkedin.com/in/{linkedin}"
        contatos.append(f'<a class="ci" href="{url}">in&nbsp;{linkedin}</a>')
    if github:
        url = f"https://github.com/{github}"
        contatos.append(f'<a class="ci" href="{url}">&#9883;&nbsp;{github}</a>')

    contato_html = '<span class="sep"> | </span>'.join(contatos)

    secoes      = cv.get("sections", {})
    secoes_html = ""

    for key in _ORDEM_SECOES + [k for k in secoes if k not in _ORDEM_SECOES]:
        if key not in secoes:
            continue
        label = _LABELS_MC.get(key, key.replace("_", " ").title())
        items = secoes[key]
        corpo = ""
        tem_li = False

        if key == "Habilidades":
            skills = _skills_lista(items)
            tags   = "".join(f'<span class="tag">{s}</span>' for s in skills)
            corpo  = f'<div class="tags">{tags}</div>'
        else:
            for item in items:
                if isinstance(item, str):
                    corpo += f'<p class="summary-p">{item}</p>'
                elif isinstance(item, dict):
                    if "bullet" in item:
                        corpo += f'<li>{item["bullet"]}</li>'
                        tem_li = True
                    elif "label" in item and "details" in item:
                        if item["details"]:
                            corpo += (
                                f'<div class="oneline">'
                                f'<strong>{item["label"]}:</strong> {item["details"]}'
                                f'</div>'
                            )
                        else:
                            corpo += f'<div class="oneline">&#9656; {item["label"]}</div>'
                    else:
                        t, pos, start, end, loc_e, hi = _campos_entrada(item)
                        date_str = f"{start} – {end}" if start else (end if end != "presente" else "")
                        loc_date = " &nbsp;·&nbsp; ".join(filter(None, [loc_e, date_str]))

                        left = ""
                        if t and pos:   left = f"<strong>{t}</strong> — <em>{pos}</em>"
                        elif t:         left = f"<strong>{t}</strong>"
                        elif pos:       left = f"<em>{pos}</em>"

                        corpo += (
                            f'<div class="entry">'
                            f'<div class="entry-header">'
                            f'<span class="entry-left">{left}</span>'
                            f'<span class="entry-right">{loc_date}</span>'
                            f'</div>'
                            f'{_bullets_html(hi)}'
                            f'</div>'
                        )
            if tem_li:
                corpo = f"<ul>{corpo}</ul>"

        secoes_html += (
            f'<section>'
            f'<h2 class="sec-title"><span class="sec-bar"></span>{label}</h2>'
            f'<div class="sec-body">{corpo}</div>'
            f'</section>'
        )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: 'Segoe UI', Calibri, Arial, sans-serif;
  font-size: 10pt;
  color: #1a1a1a;
  background: #fff;
  max-width: 820px;
  margin: 0 auto;
}}
/* ── Cabeçalho escuro ── */
.header-top {{
  background: #1e293b;
  color: #fff;
  text-align: center;
  padding: 22px 48px 14px;
}}
.name {{
  font-size: 22pt;
  font-weight: 700;
  letter-spacing: 1px;
  color: #fff;
}}
.subtitle {{
  font-size: 10pt;
  color: #94a3b8;
  margin-top: 4px;
  font-style: italic;
}}
/* ── Barra de contatos ── */
.contact-bar {{
  background: #0f172a;
  padding: 8px 32px;
  text-align: center;
  font-size: 8.5pt;
  flex-wrap: wrap;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 0;
}}
.contact-bar a.ci,
.contact-bar span.ci {{
  color: #7dd3fc;
  text-decoration: none;
  white-space: nowrap;
}}
.contact-bar a.ci:hover {{
  text-decoration: underline;
}}
.contact-bar .sep {{
  color: #475569;
  margin: 0 6px;
}}
/* ── Corpo ── */
.body-content {{
  padding: 18px 44px 24px;
}}
section {{
  margin-top: 14px;
}}
.sec-title {{
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 9.5pt;
  font-weight: 700;
  color: #0f4c81;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  margin-bottom: 7px;
}}
.sec-bar {{
  display: inline-block;
  width: 4px;
  height: 14px;
  background: #0f4c81;
  border-radius: 2px;
  flex-shrink: 0;
}}
.sec-body {{
  padding-left: 12px;
  border-left: 1px solid #e2e8f0;
}}
.summary-p {{
  line-height: 1.55;
  text-align: justify;
  margin-bottom: 4px;
}}
.entry {{
  margin-bottom: 9px;
}}
.entry-header {{
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 4px;
}}
.entry-left {{
  flex: 1;
}}
.entry-right {{
  font-size: 8.5pt;
  color: #64748b;
  white-space: nowrap;
}}
ul {{
  padding-left: 18px;
  margin: 4px 0 4px;
  list-style: disc;
}}
li {{
  margin-bottom: 2px;
  line-height: 1.4;
}}
.oneline {{
  margin-bottom: 4px;
}}
/* ── Tags de skills ── */
.tags {{
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}}
.tag {{
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 8.5pt;
  white-space: nowrap;
}}
/* ── Links no PDF ── */
a {{
  color: inherit;
  text-decoration: none;
}}
@page {{ margin: 0; }}
@media print {{
  body {{ margin: 0; }}
  a {{ color: #7dd3fc; }}
}}
</style>
</head>
<body>
<div class="header-top">
  <div class="name">{nome}</div>
</div>
<div class="contact-bar">{contato_html}</div>
<div class="body-content">
{secoes_html}
</div>
</body>
</html>"""
