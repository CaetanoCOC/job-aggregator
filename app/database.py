"""
database.py
Banco SQLite com sistema de feedback e aprendizado.
Local: D:\\PORTFOLIO\\Job Aggregator\\app\\database.py
"""

import sqlite3
import json
import os
import re
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "jobs.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def criar_banco():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS vagas (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo               TEXT    NOT NULL,
            empresa              TEXT    DEFAULT '',
            localizacao          TEXT    DEFAULT '',
            estado               TEXT    DEFAULT '',
            modalidade           TEXT    DEFAULT '',
            salario              TEXT    DEFAULT '',
            descricao            TEXT    DEFAULT '',
            skills               TEXT    DEFAULT '[]',
            link                 TEXT    UNIQUE,
            fonte                TEXT    DEFAULT '',
            data_pub             TEXT    DEFAULT '',
            data_coleta          TEXT    DEFAULT '',
            status               TEXT    DEFAULT 'nova',
            resultado_entrevista TEXT    DEFAULT 'pendente',
            data_feedback        TEXT    DEFAULT '',
            match_score          INTEGER DEFAULT 0,
            prob_aprovacao       REAL    DEFAULT 0.0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS feedbacks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            vaga_id     INTEGER REFERENCES vagas(id),
            titulo_norm TEXT,
            skills_json TEXT,
            fonte       TEXT,
            estado      TEXT,
            modalidade  TEXT,
            chamado     INTEGER,
            data        TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS perfil_usuario (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            skill   TEXT UNIQUE,
            nivel   TEXT DEFAULT 'intermediario'
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS historico_buscas (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            cargo       TEXT,
            skills      TEXT,
            estado      TEXT,
            fontes      TEXT,
            total_vagas INTEGER,
            data_busca  TEXT
        )
    """)

    conn.commit()
    conn.close()
    print(f"[DB] Banco OK -> {DB_PATH}")


# ─── VAGAS ────────────────────────────────────────────────────────────

def inserir_vaga(vaga: dict) -> bool:
    conn = get_connection()
    c = conn.cursor()
    try:
        skills_json = json.dumps(vaga.get("skills", []), ensure_ascii=False)
        estado = vaga.get("estado", "") or _extrair_estado(vaga.get("localizacao", ""))
        c.execute("""
            INSERT INTO vagas
                (titulo, empresa, localizacao, estado, modalidade, salario,
                 descricao, skills, link, fonte, data_pub, data_coleta, match_score)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            vaga.get("titulo", ""),
            vaga.get("empresa", ""),
            vaga.get("localizacao", ""),
            estado,
            vaga.get("modalidade", ""),
            vaga.get("salario", ""),
            vaga.get("descricao", ""),
            skills_json,
            vaga.get("link", ""),
            vaga.get("fonte", ""),
            vaga.get("data_pub", ""),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            vaga.get("match_score", 0),
        ))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def buscar_vagas(cargo: str = "", skills: list = None, estado: str = "",
                 modalidade: str = "", fonte: str = "", status: str = "",
                 resultado: str = "", limite: int = 500) -> list:
    conn = get_connection()
    c = conn.cursor()
    q = "SELECT * FROM vagas WHERE 1=1"
    p = []

    if cargo:
        q += " AND LOWER(titulo) LIKE ?"
        p.append(f"%{cargo.lower()}%")
    if estado and estado not in ("Todos", ""):
        q += " AND estado = ?"
        p.append(estado)
    if modalidade and modalidade not in ("Todas", ""):
        q += " AND LOWER(modalidade) LIKE ?"
        p.append(f"%{modalidade.lower()}%")
    if fonte and fonte not in ("Todas", ""):
        q += " AND fonte = ?"
        p.append(fonte)
    if status and status not in ("Todos", ""):
        q += " AND status = ?"
        p.append(status)
    if resultado and resultado not in ("Todos", ""):
        q += " AND resultado_entrevista = ?"
        p.append(resultado)
    if skills:
        for sk in skills:
            if sk.strip():
                q += " AND LOWER(skills) LIKE ?"
                p.append(f"%{sk.lower()}%")

    q += " ORDER BY prob_aprovacao DESC, match_score DESC, data_coleta DESC LIMIT ?"
    p.append(limite)

    c.execute(q, p)
    rows = c.fetchall()
    conn.close()

    result = []
    for row in rows:
        d = dict(row)
        try:
            d["skills"] = json.loads(d["skills"]) if d["skills"] else []
        except Exception:
            d["skills"] = []
        result.append(d)
    return result


def atualizar_status(vaga_id: int, status: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE vagas SET status=? WHERE id=?", (status, vaga_id))
    conn.commit()
    conn.close()


def registrar_feedback(vaga_id: int, chamado: bool):
    """Registra se foi chamado para entrevista e dispara recálculo."""
    conn = get_connection()
    c = conn.cursor()

    resultado = "chamado" if chamado else "nao_chamado"
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Quando chamado=True, garante que status='aplicada' (você só é chamado se aplicou)
    if chamado:
        c.execute(
            "UPDATE vagas SET resultado_entrevista=?, data_feedback=?, status='aplicada' WHERE id=?",
            (resultado, agora, vaga_id))
    else:
        c.execute("UPDATE vagas SET resultado_entrevista=?, data_feedback=? WHERE id=?",
                  (resultado, agora, vaga_id))

    c.execute("SELECT titulo, skills, fonte, estado, modalidade FROM vagas WHERE id=?", (vaga_id,))
    row = c.fetchone()
    if row:
        c.execute("""
            INSERT INTO feedbacks (vaga_id, titulo_norm, skills_json, fonte, estado, modalidade, chamado, data)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            vaga_id,
            _normalizar_titulo(row["titulo"]),
            row["skills"],
            row["fonte"],
            row["estado"],
            row["modalidade"],
            1 if chamado else 0,
            agora
        ))

    conn.commit()
    conn.close()
    _recalcular_probabilidades()


def _recalcular_probabilidades():
    """Recalcula prob_aprovacao para todas as vagas usando feedbacks históricos."""
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT AVG(chamado) FROM feedbacks")
    row = c.fetchone()
    taxa_global = row[0] if row[0] is not None else 0.5

    c.execute("SELECT titulo_norm, AVG(chamado) as t, COUNT(*) as n FROM feedbacks GROUP BY titulo_norm")
    taxa_titulo = {r["titulo_norm"]: (r["t"], r["n"]) for r in c.fetchall()}

    c.execute("SELECT fonte, AVG(chamado) as t FROM feedbacks GROUP BY fonte")
    taxa_fonte = {r["fonte"]: r["t"] for r in c.fetchall()}

    c.execute("SELECT modalidade, AVG(chamado) as t FROM feedbacks GROUP BY modalidade")
    taxa_modal = {r["modalidade"]: r["t"] for r in c.fetchall()}

    c.execute("SELECT id, titulo, fonte, modalidade FROM vagas")
    for v in c.fetchall():
        titulo_n = _normalizar_titulo(v["titulo"])
        t_t, n_t = taxa_titulo.get(titulo_n, (taxa_global, 0))
        t_f = taxa_fonte.get(v["fonte"], taxa_global)
        t_m = taxa_modal.get(v["modalidade"], taxa_global)

        peso = min(n_t / 5.0, 1.0)
        prob = (
            t_t * peso * 0.5 +
            t_f * 0.25 +
            t_m * 0.25 +
            taxa_global * (1 - peso) * 0.5
        )
        prob = round(min(max(prob, 0.0), 1.0), 4)
        conn.execute("UPDATE vagas SET prob_aprovacao=? WHERE id=?", (prob, v["id"]))

    conn.commit()
    conn.close()


# ─── PERFIL ───────────────────────────────────────────────────────────

def salvar_skill(skill: str, nivel: str = "intermediario"):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO perfil_usuario (skill, nivel) VALUES (?,?)",
              (skill.strip(), nivel))
    conn.commit()
    conn.close()


def deletar_skill(skill: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM perfil_usuario WHERE skill=?", (skill,))
    conn.commit()
    conn.close()


def buscar_skills_usuario() -> list:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT skill, nivel FROM perfil_usuario ORDER BY skill")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── HISTÓRICO ────────────────────────────────────────────────────────

def salvar_historico(cargo, skills, estado, fontes, total):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO historico_buscas (cargo, skills, estado, fontes, total_vagas, data_busca)
        VALUES (?,?,?,?,?,?)
    """, (cargo, json.dumps(skills), estado, json.dumps(fontes), total,
          datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()


# ─── ESTATÍSTICAS ─────────────────────────────────────────────────────

def stats_gerais() -> dict:
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM vagas")
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM vagas WHERE status='aplicada'")
    aplicadas = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM feedbacks WHERE chamado=1")
    chamados = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM feedbacks")
    total_fb = c.fetchone()[0]

    c.execute("SELECT fonte, COUNT(*) as n FROM vagas GROUP BY fonte ORDER BY n DESC")
    por_fonte = {r["fonte"]: r["n"] for r in c.fetchall()}

    conn.close()
    taxa = round(chamados / total_fb * 100, 1) if total_fb else 0.0
    return {
        "total_vagas": total,
        "aplicadas": aplicadas,
        "chamados": chamados,
        "total_feedbacks": total_fb,
        "taxa_entrevista": taxa,
        "por_fonte": por_fonte,
    }


# ─── HELPERS ─────────────────────────────────────────────────────────

_ESTADOS_BR = {
    "são paulo": "SP", "sao paulo": "SP", " sp": "SP",
    "rio de janeiro": "RJ", " rj": "RJ",
    "minas gerais": "MG", " mg": "MG",
    "bahia": "BA", " ba": "BA",
    "paraná": "PR", "parana": "PR", " pr": "PR",
    "rio grande do sul": "RS", " rs": "RS",
    "santa catarina": "SC", " sc": "SC",
    "pernambuco": "PE", " pe": "PE",
    "ceará": "CE", "ceara": "CE", " ce": "CE",
    "goiás": "GO", "goias": "GO", " go": "GO",
    "distrito federal": "DF", "brasília": "DF", "brasilia": "DF", " df": "DF",
    "amazonas": "AM", " am": "AM",
    "remoto": "Remoto", "home office": "Remoto", "remote": "Remoto",
}


def _extrair_estado(localizacao: str) -> str:
    if not localizacao:
        return ""
    loc = " " + localizacao.lower()
    for chave, sigla in _ESTADOS_BR.items():
        if chave in loc:
            return sigla
    partes = re.split(r"[\s,\-]+", localizacao)
    for p in reversed(partes):
        p2 = p.strip().upper()
        if len(p2) == 2 and p2.isalpha():
            return p2
    return ""


def _normalizar_titulo(titulo: str) -> str:
    t = titulo.lower().strip()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t)
    for nivel in ["junior", "júnior", "pleno", "sênior", "senior", "sr", "jr", "i", "ii", "iii"]:
        t = re.sub(rf"\b{nivel}\b", "", t)
    return t.strip()


if __name__ == "__main__":
    criar_banco()
    print(stats_gerais())