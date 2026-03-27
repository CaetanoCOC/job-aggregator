"""
app/ai/gemini.py — Filtro de relevância de vagas via Gemini 2.0 Flash (free tier).

Plano gratuito: 1500 req/dia · 15 req/min · 1M tokens/min
Estratégia: batch de até 50 títulos por chamada → pouquíssimas requests.

Retorna scores 0–10 por vaga:
  0–3  → irrelevante (não exibe)
  4–6  → relacionado mas não exato
  7–10 → exatamente o que foi pedido
"""

import json
import re
import time

from google import genai
from google.genai import types

# Score mínimo para a vaga aparecer quando filtro AI está ativo
LIMIAR_RELEVANCIA = 4
TAMANHO_LOTE = 50  # vagas por chamada à API


def pontuar_vagas(cargo_buscado: str, vagas: list[dict], api_key: str) -> dict[int, float]:
    """
    Recebe lista de vagas (com 'id', 'titulo', 'descricao') e o cargo buscado.
    Retorna dict {vaga_id: score_0_a_10}.
    Vagas sem resposta da API recebem score 5.0 (neutro).
    """
    if not api_key or not vagas:
        return {}

    client = genai.Client(api_key=api_key)
    scores: dict[int, float] = {}

    for i in range(0, len(vagas), TAMANHO_LOTE):
        lote = vagas[i: i + TAMANHO_LOTE]
        scores.update(_pontuar_lote(client, cargo_buscado, lote))
        if i + TAMANHO_LOTE < len(vagas):
            time.sleep(1)  # respeita 15 RPM do free tier

    return scores


def _pontuar_lote(client, cargo_buscado: str, lote: list[dict]) -> dict[int, float]:
    """Pontua um lote de vagas em uma única chamada."""

    linhas = []
    for v in lote:
        titulo = (v.get("titulo") or "").strip()
        desc   = (v.get("descricao") or "")[:120].strip().replace("\n", " ")
        linhas.append(f'{v["id"]}. {titulo} — {desc}')

    prompt = f"""Você é um assistente de triagem de vagas de emprego no Brasil.

Cargo buscado: "{cargo_buscado}"

Avalie a relevância de cada vaga abaixo de 0 a 10:
- 0 a 3  → completamente irrelevante (outra área, outro cargo)
- 4 a 6  → relacionado, mas não é exatamente o cargo buscado
- 7 a 10 → exatamente o cargo buscado ou variação muito similar

Vagas:
{chr(10).join(linhas)}

Responda APENAS com um objeto JSON no formato:
{{"<id>": <score>, "<id>": <score>, ...}}
Sem explicações. Sem texto fora do JSON."""

    try:
        _MODELS = ["gemini-2.0-flash-lite", "gemini-2.0-flash"]
        response = None
        for _model in _MODELS:
            try:
                response = client.models.generate_content(model=_model, contents=prompt)
                break
            except Exception as _me:
                _err = str(_me)
                if "429" in _err or "RESOURCE_EXHAUSTED" in _err or "quota" in _err.lower():
                    continue
                raise
        if response is None:
            raise RuntimeError("Quota esgotada em todos os modelos Gemini")

        texto = response.text.strip()

        # Extrai o JSON mesmo se vier com markdown (```json ... ```)
        match = re.search(r'\{[^{}]+\}', texto, re.DOTALL)
        if not match:
            raise ValueError("JSON não encontrado na resposta")

        dados = json.loads(match.group())
        return {int(k): float(v) for k, v in dados.items()}

    except Exception as e:
        print(f"[Gemini] Erro no lote: {e}")
        # Fallback: score neutro para não bloquear vagas por falha da API
        return {v["id"]: 5.0 for v in lote}
