"""
renderer.py — Gera PDF profissional via rendercv (subprocess) ou HTML+CSS.

Fluxo (temas rendercv padrão):
  1. Salva o YAML em diretório temporário
  2. Chama `python -m rendercv render cv.yaml --output-folder-name <tmp>`
  3. Copia o PDF gerado para o destino informado
  4. Retorna o caminho do PDF copiado

Fluxo (temas HTML customizados):
  1. Delega para app.cv.html_renderer.gerar_pdf_formato()
  2. Converte HTML+CSS via Edge/Chrome headless → PDF
"""

import subprocess
import shutil
import tempfile
from pathlib import Path

PYTHON = r"D:\PORTFOLIO\Job Aggregator\emprego\python.exe"

# Temas que usam HTML+CSS em vez de rendercv
_TEMAS_HTML = {"executivo_azul", "elegante_br", "compacto_academico", "moderno_conectado"}


def gerar_pdf(yaml_content: str, destino: str, tema_id: str = "") -> str:
    """
    Recebe o conteúdo YAML como string e salva o PDF em `destino`.
    Retorna o caminho do PDF gerado.
    Lança RuntimeError se a geração falhar.

    Para temas HTML customizados (executivo_azul, elegante_br), usa
    html_renderer em vez do rendercv.
    """
    if tema_id in _TEMAS_HTML:
        from app.cv.html_renderer import gerar_pdf_formato
        return gerar_pdf_formato(tema_id, yaml_content, destino)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path  = Path(tmp)
        yaml_path = tmp_path / "cv.yaml"
        yaml_path.write_text(yaml_content, encoding="utf-8")

        resultado = subprocess.run(
            [PYTHON, "-m", "rendercv", "render", str(yaml_path),
             "--output-folder-name", str(tmp_path / "saida")],
            capture_output=True,
            text=True,
            timeout=180,
        )

        if resultado.returncode != 0:
            raise RuntimeError(
                resultado.stderr or resultado.stdout or "Erro desconhecido no rendercv"
            )

        pdfs = list(tmp_path.glob("**/*.pdf"))
        if not pdfs:
            raise FileNotFoundError(
                "rendercv executou sem erros mas não gerou nenhum PDF.\n"
                + resultado.stdout
            )

        shutil.copy(str(pdfs[0]), destino)
        return destino
