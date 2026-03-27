"""
web/server.py — Flask backend para o Job Aggregator Web
Porta: 5007 (livre por padrão)
"""
import io
import json
import queue
import threading
import sys
import os
import tempfile
from pathlib import Path

# Força UTF-8 no stdout/stderr para evitar UnicodeEncodeError no Windows (cp1252)
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Garante que o root do projeto está no sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from flask import Flask, request, jsonify, render_template, Response, stream_with_context

from app.database import (
    criar_banco, inserir_vaga, buscar_vagas,
    atualizar_status, registrar_feedback,
    salvar_skill, deletar_skill, buscar_skills_usuario,
    salvar_historico, stats_gerais, get_connection,
)
from app.utils.helpers import normalizar_skills, calcular_match_score

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.config["TEMPLATES_AUTO_RELOAD"] = True

@app.after_request
def no_cache(response):
    if request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

criar_banco()

# ── Config persistente (API keys, etc.) ───────────────────────────────────────
_CONFIG_PATH = os.path.join(ROOT, "config.json")


def _load_config() -> dict:
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_config(data: dict):
    cfg = _load_config()
    cfg.update(data)
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ── Estado global de scraping ──────────────────────────────────────────────────
_scraping_lock  = threading.Lock()
_scraping_active = False
_scraping_queues: list[queue.Queue] = []   # um por cliente SSE conectado


def _broadcast(event: str, data: dict):
    """Envia um evento SSE para todos os clientes conectados."""
    msg = f"event: {event}\ndata: {json.dumps(data)}\n\n"
    dead = []
    for q in _scraping_queues:
        try:
            q.put_nowait(msg)
        except queue.Full:
            dead.append(q)
    for q in dead:
        _scraping_queues.remove(q)


# ── Utilitários ───────────────────────────────────────────────────────────────

def _skills_usuario() -> list[str]:
    return [r["skill"] for r in buscar_skills_usuario()]


def _vaga_to_dict(v) -> dict:
    """Converte Row do sqlite3 para dict serializável."""
    d = dict(v)
    if isinstance(d.get("skills"), str):
        try:
            d["skills"] = json.loads(d["skills"])
        except Exception:
            d["skills"] = []
    d["prob_pct"] = int((d.get("prob_aprovacao") or 0) * 100)
    return d


# ── Rotas principais ──────────────────────────────────────────────────────────

import time as _time
_BUILD_VERSION = str(int(_time.time()))

@app.route("/")
def index():
    return render_template("index.html", version=_BUILD_VERSION)


# ── API: Vagas ────────────────────────────────────────────────────────────────

@app.route("/api/vagas")
def api_vagas():
    cargo       = request.args.get("cargo", "").strip()
    status      = request.args.get("status", "")
    resultado   = request.args.get("resultado", "")
    estado      = request.args.get("estado", "")
    modalidade  = request.args.get("modalidade", "")
    ai_filtrar  = request.args.get("ai_filtrar", "0") == "1"  # filtra por ai_score

    vagas_raw = buscar_vagas(cargo=cargo, status=status, resultado=resultado)
    skills_u  = _skills_usuario()

    vagas = []
    for v in vagas_raw:
        loc       = (v.get("localizacao") or v.get("estado") or "").lower()
        mod       = (v.get("modalidade") or "").lower()
        is_remoto = "remot" in mod or "remot" in loc

        if estado and estado not in ("Todos", ""):
            if not is_remoto and estado.lower() not in loc and estado not in (v.get("estado") or ""):
                continue

        if modalidade and modalidade not in ("Todas", ""):
            if modalidade.lower() not in mod:
                continue

        d = _vaga_to_dict(v)
        d["match_score"] = calcular_match_score(d.get("skills", []), skills_u)

        # Filtro Gemini: oculta vagas abaixo do limiar quando ativo
        if ai_filtrar:
            from app.ai.gemini import LIMIAR_RELEVANCIA
            ai_score = d.get("ai_score", -1)
            if ai_score != -1 and ai_score < LIMIAR_RELEVANCIA:
                continue

        vagas.append(d)

    # Mais recentes primeiro
    vagas.sort(key=lambda v: v.get("data_coleta") or "", reverse=True)

    return jsonify(vagas)


@app.route("/api/vagas/<int:vaga_id>/status", methods=["PUT"])
def api_set_status(vaga_id):
    status = request.json.get("status")
    atualizar_status(vaga_id, status)
    return jsonify({"ok": True})


@app.route("/api/vagas/<int:vaga_id>/feedback", methods=["POST"])
def api_feedback(vaga_id):
    chamado = request.json.get("chamado")
    contratado = request.json.get("contratado", False)

    if contratado:
        conn = get_connection()
        conn.execute(
            "UPDATE vagas SET resultado_entrevista='contratado', status='aplicada' WHERE id=?",
            (vaga_id,)
        )
        conn.commit()
        conn.close()
        registrar_feedback(vaga_id, True)
        return jsonify({"ok": True, "resultado": "contratado"})

    registrar_feedback(vaga_id, chamado)
    return jsonify({"ok": True, "resultado": "chamado" if chamado else "nao_chamado"})


# ── API: Config / Gemini ─────────────────────────────────────────────────────

@app.route("/api/config")
def api_config_get():
    cfg = _load_config()
    # Nunca devolve a chave completa — apenas se está configurada
    key = cfg.get("gemini_api_key", "")
    return jsonify({
        "gemini_configurado": bool(key),
        "gemini_key_preview": f"...{key[-6:]}" if key else "",
    })


@app.route("/api/config", methods=["POST"])
def api_config_set():
    data = request.json or {}
    if "gemini_api_key" in data:
        _save_config({"gemini_api_key": data["gemini_api_key"].strip()})
    return jsonify({"ok": True})


@app.route("/api/ai/testar", methods=["POST"])
def api_ai_testar():
    """Testa a chave do Gemini. Aceita chave no body ou usa a salva."""
    data = request.json or {}
    key = data.get("api_key", "").strip()
    if not key:
        cfg = _load_config()
        key = cfg.get("gemini_api_key", "")
    if not key:
        return jsonify({"ok": False, "mensagem": "Chave não configurada"}), 400
    try:
        from google import genai
        client = genai.Client(api_key=key)
        r = client.models.generate_content(model="gemini-1.5-flash", contents="Responda apenas: OK")
        return jsonify({"ok": True, "mensagem": f"Conexão OK — {r.text.strip()[:30]}"})
    except Exception as e:
        return jsonify({"ok": False, "mensagem": str(e)[:200]}), 400


# ── API: Skills ───────────────────────────────────────────────────────────────

@app.route("/api/skills")
def api_skills():
    return jsonify(_skills_usuario())


@app.route("/api/skills", methods=["POST"])
def api_add_skill():
    raw = request.json.get("skill", "")
    for sk in normalizar_skills(raw):
        if sk:
            salvar_skill(sk)
    return jsonify(_skills_usuario())


@app.route("/api/skills/<path:skill>", methods=["DELETE"])
def api_del_skill(skill):
    deletar_skill(skill)
    return jsonify(_skills_usuario())


# ── API: Stats ────────────────────────────────────────────────────────────────

@app.route("/api/stats")
def api_stats():
    return jsonify(stats_gerais())


# ── API: Scraping (SSE) ───────────────────────────────────────────────────────

@app.route("/api/buscar/stream")
def api_buscar_stream():
    """SSE endpoint — o cliente se conecta aqui para receber eventos de scraping."""
    q = queue.Queue(maxsize=200)
    _scraping_queues.append(q)

    def generate():
        try:
            # keepalive inicial
            yield ": keepalive\n\n"
            while True:
                try:
                    msg = q.get(timeout=30)
                    yield msg
                    if '"done"' in msg or '"error"' in msg:
                        break
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            if q in _scraping_queues:
                _scraping_queues.remove(q)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@app.route("/api/buscar", methods=["POST"])
def api_buscar():
    global _scraping_active

    with _scraping_lock:
        if _scraping_active:
            return jsonify({"ok": False, "error": "Scraping já em andamento"}), 409
        _scraping_active = True

    body  = request.json or {}
    cargo = body.get("cargo", "").strip()
    if not cargo:
        _scraping_active = False
        return jsonify({"ok": False, "error": "Cargo obrigatório"}), 400

    estado = body.get("estado", "")
    fonte  = body.get("fonte", "")

    thread = threading.Thread(
        target=_run_scrapers,
        args=(cargo, estado, fonte),
        daemon=True
    )
    thread.start()
    return jsonify({"ok": True})


def _run_scrapers(cargo: str, estado: str, fonte_filtro: str):
    global _scraping_active

    from app.scrapers.linkedin  import LinkedInScraper
    from app.scrapers.vagas_com import VagasComScraper
    from app.scrapers.infojobs  import InfoJobsScraper

    todos = {
        "linkedin":  LinkedInScraper(),
        "vagas.com": VagasComScraper(),
        "infojobs":  InfoJobsScraper(),
    }
    scrapers = ([todos[fonte_filtro]] if fonte_filtro in todos else list(todos.values()))
    skills_u = _skills_usuario()
    total_novas = 0

    try:
        for scraper in scrapers:
            _broadcast("progress", {
                "fonte": scraper.nome_fonte,
                "msg": f"Buscando em {scraper.nome_fonte}…",
                "total": total_novas,
            })

            try:
                vagas = scraper.buscar(cargo=cargo, localizacao=estado, skills=skills_u)
                novas_fonte = 0

                for v in vagas:
                    lk = (v.get("link") or "").strip()
                    if lk and not lk.startswith("http"):
                        v["link"] = "https://" + lk
                    v["match_score"] = calcular_match_score(v.get("skills", []), skills_u)
                    if inserir_vaga(v):
                        novas_fonte += 1
                        total_novas += 1

                _broadcast("fonte_ok", {
                    "fonte": scraper.nome_fonte,
                    "coletadas": len(vagas),
                    "novas": novas_fonte,
                    "total": total_novas,
                })

            except Exception as e:
                _broadcast("fonte_erro", {
                    "fonte": scraper.nome_fonte,
                    "error": str(e),
                })

        salvar_historico(cargo, skills_u, estado,
                         [s.nome_fonte for s in scrapers], total_novas)

        # ── Filtro Gemini (se chave configurada) ─────────────────────────
        cfg = _load_config()
        api_key = cfg.get("gemini_api_key", "")
        if api_key and total_novas > 0:
            _broadcast("ai_scoring", {"total": total_novas})
            try:
                from app.ai.gemini import pontuar_vagas, LIMIAR_RELEVANCIA
                conn = get_connection()
                # Busca apenas as vagas inseridas nesta sessão (ai_score = -1)
                rows = conn.execute(
                    "SELECT id, titulo, descricao FROM vagas WHERE ai_score = -1 LIMIT 500"
                ).fetchall()
                conn.close()

                if rows:
                    vagas_para_pontuar = [dict(r) for r in rows]
                    scores = pontuar_vagas(cargo, vagas_para_pontuar, api_key)

                    # Salva os scores no banco
                    conn = get_connection()
                    for vid, score in scores.items():
                        conn.execute(
                            "UPDATE vagas SET ai_score = ? WHERE id = ?", (score, vid)
                        )
                    conn.commit()
                    conn.close()

                    irrelevantes = sum(1 for s in scores.values() if s < LIMIAR_RELEVANCIA)
                    _broadcast("ai_done", {
                        "total_analisadas": len(scores),
                        "irrelevantes": irrelevantes,
                        "msg": f"Gemini: {len(scores)-irrelevantes} relevantes, {irrelevantes} filtradas",
                    })
            except Exception as e:
                _broadcast("ai_erro", {"error": f"Gemini: {str(e)[:120]}"})

        _broadcast("done", {"total": total_novas, "cargo": cargo})

    except Exception as e:
        _broadcast("error", {"error": str(e)})
    finally:
        _scraping_active = False


# ── API: Currículo ────────────────────────────────────────────────────────────

_CV_ALLOWED = {".pdf", ".docx"}


@app.route("/api/cv/extrair", methods=["POST"])
def api_cv_extrair():
    if "file" not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    file = request.files["file"]
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _CV_ALLOWED:
        return jsonify({"error": f"Formato não suportado: {ext}. Use .pdf ou .docx"}), 400

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        from app.cv.extractor import extrair_texto
        from app.cv.parser import texto_para_yaml
        texto = extrair_texto(tmp_path)
        yaml_content = texto_para_yaml(texto)
        return jsonify({"yaml": yaml_content, "chars": len(texto)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def _normalizar_yaml_cv(yaml_content: str) -> str:
    """
    Garante que o YAML tenha 'cv:' como chave raiz.
    Renomeia chaves comuns em PT-BR (curriculo, curriculum, resume) para 'cv'.
    """
    import yaml as _yaml
    import re as _re

    # Renomeia chave raiz comum em PT-BR antes de parsear
    aliases = ("curriculo", "curriculum", "resume", "currículo")
    for alias in aliases:
        # Substitui apenas se for a primeira chave do documento (início de linha)
        yaml_content = _re.sub(
            rf"^{alias}\s*:", "cv:", yaml_content, count=1, flags=_re.MULTILINE | _re.IGNORECASE
        )

    # Valida que é YAML válido
    try:
        parsed = _yaml.safe_load(yaml_content)
    except _yaml.YAMLError as e:
        raise ValueError(f"YAML inválido: {e}")

    if not isinstance(parsed, dict):
        raise ValueError("O YAML precisa ser um mapeamento (chave: valor).")

    # Se não tem 'cv' mas tem outro mapeamento único, envolve com 'cv:'
    if "cv" not in parsed:
        # Último recurso: embrulha tudo sob cv:
        import yaml as _yaml2
        wrapped = {"cv": parsed}
        yaml_content = _yaml2.dump(wrapped, allow_unicode=True, sort_keys=False)

    return yaml_content


def _extrair_erro_rendercv(texto: str) -> str:
    """Extrai só as linhas de erro relevantes do output verboso do rendercv."""
    linhas = texto.splitlines()
    erros = []
    capturando = False
    for linha in linhas:
        if "Error Message" in linha or "error" in linha.lower() and "|" in linha:
            capturando = True
        if capturando and "|" in linha:
            parte = linha.split("|")
            if len(parte) >= 3:
                msg = parte[-2].strip()
                if msg and msg not in ("Error Message", "---"):
                    erros.append(msg)
        if capturando and linha.strip().startswith("+---") and erros:
            break
    return " | ".join(erros) if erros else texto[:400]


_ESTRUTURA_MINIMA = """
cv:
  name: Nome Completo
  email: email@exemplo.com
  phone: '+55 11 99999-9999'
  location: Cidade/UF — Brasil
  social_networks:
    - network: LinkedIn
      username: seu-perfil

  sections:

    Resumo:
      - Breve descrição profissional.

    Experiência:
      - company: Empresa
        position: Cargo
        date: Jan 2022 – presente
        highlights:
          - Responsabilidade principal

    Formação:
      - institution: Universidade
        area: Área de Estudo
        degree: Bacharelado
        date: 2019 – 2023

    Habilidades:
      - label: Linguagens
        details: Python, SQL
""".strip()


@app.route("/api/cv/normalizar-ia", methods=["POST"])
def api_cv_normalizar_ia():
    """Usa Gemini para reformatar YAML do usuário na estrutura correta do rendercv."""
    cfg = _load_config()
    api_key = cfg.get("gemini_api_key", "")
    if not api_key:
        return jsonify({"error": "Gemini não configurado. Clique em ⚙ para adicionar a API key."}), 400

    data = request.json or {}
    yaml_bruto = data.get("yaml_content", "").strip()
    if not yaml_bruto:
        return jsonify({"error": "YAML vazio"}), 400

    prompt = f"""Você é um especialista em formatação de currículos em YAML para o sistema rendercv.

Abaixo está a ESTRUTURA OBRIGATÓRIA que o YAML deve seguir (com indentação de 2 espaços):

{_ESTRUTURA_MINIMA}

Regras importantes:
- A chave raiz DEVE ser "cv:" (não "curriculo:", "resume:", etc.)
- Indentação: exatamente 2 espaços (nunca tabs)
- Seções ficam dentro de "cv.sections:"
- Nomes de seções são livres (em português está OK: "Experiência", "Formação", etc.)
- Entradas de experiência têm: company, position, date, highlights (lista)
- Entradas de formação têm: institution, area, degree, date
- Entradas de habilidades têm: label, details
- Entradas de texto simples (Resumo, Objetivo) são strings diretas na lista
- Preserve TODO o conteúdo original (nomes, datas, empresas, descrições)
- Apenas reorganize/corrija a estrutura e indentação

YAML a ser corrigido:
{yaml_bruto}

Responda APENAS com o YAML corrigido, sem explicações, sem markdown (sem ```yaml)."""

    # Tenta modelos em ordem — fallback automático se um falhar
    _MODELS = ["gemini-2.0-flash-lite", "gemini-2.0-flash", "gemini-1.5-flash"]

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
    except Exception as e:
        return jsonify({"error": f"Erro ao conectar ao Gemini: {str(e)[:120]}"}), 500

    quota_esgotada = False
    last_error = ""
    for model_id in _MODELS:
        try:
            response = client.models.generate_content(model=model_id, contents=prompt)
            yaml_corrigido = response.text.strip()

            # Remove blocos de markdown se o modelo insistir
            if yaml_corrigido.startswith("```"):
                yaml_corrigido = "\n".join(
                    l for l in yaml_corrigido.splitlines()
                    if not l.strip().startswith("```")
                ).strip()

            # Valida que é YAML válido antes de devolver
            import yaml as _yaml
            _yaml.safe_load(yaml_corrigido)

            return jsonify({"yaml": yaml_corrigido, "modelo": model_id})

        except Exception as e:
            err = str(e)
            print(f"[Gemini normalizar-ia] {model_id} -> {err[:300]}")
            if "429" in err or "RESOURCE_EXHAUSTED" in err or "quota" in err.lower():
                quota_esgotada = True
                continue  # tenta o próximo modelo (quota separada por modelo)
            elif "404" in err or "not found" in err.lower():
                last_error = f"Modelo {model_id} indisponível."
                continue  # tenta o próximo modelo
            else:
                last_error = err[:200]
                break

    if quota_esgotada and not last_error:
        last_error = "Quota esgotada em todos os modelos Gemini. Aguarde alguns minutos e tente novamente."
    elif quota_esgotada:
        last_error = "Quota esgotada em todos os modelos Gemini. Aguarde alguns minutos e tente novamente."

    return jsonify({"error": last_error}), 500


@app.route("/api/cv/gerar", methods=["POST"])
def api_cv_gerar():
    data = request.json or {}
    yaml_content = data.get("yaml_content", "").strip()
    tema_id = data.get("tema_id", "classic")

    if not yaml_content:
        return jsonify({"error": "YAML vazio"}), 400

    # Normaliza estrutura (renomeia curriculo: → cv:, valida)
    try:
        yaml_content = _normalizar_yaml_cv(yaml_content)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    # Valida que cv.sections existe e tem conteúdo
    try:
        import yaml as _yaml
        parsed = _yaml.safe_load(yaml_content)
        cv_node = parsed.get("cv", {}) if isinstance(parsed, dict) else {}
        sections = cv_node.get("sections", {})
        if not sections:
            return jsonify({
                "error": "O YAML não tem 'sections:' com conteúdo. "
                         "Adicione pelo menos uma seção (Experiência, Habilidades, etc.) "
                         "dentro de cv.sections:"
            }), 400
    except Exception:
        pass  # Deixa o rendercv reportar o erro

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        destino = tmp.name

    try:
        from app.cv.renderer import gerar_pdf
        gerar_pdf(yaml_content, destino, tema_id)
        with open(destino, "rb") as f:
            pdf_bytes = f.read()
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": "attachment; filename=curriculo.pdf"},
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            os.unlink(destino)
        except Exception:
            pass


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import socket

    def porta_livre(p):
        s = socket.socket()
        try:
            s.bind(("", p))
            return True
        except OSError:
            return False
        finally:
            s.close()

    porta = next((p for p in [5007, 5008, 5009] if porta_livre(p)), 5010)
    print(f"\n  Job Aggregator Web  ->  http://localhost:{porta}\n")
    app.run(host="0.0.0.0", port=porta, debug=False, threaded=True)
