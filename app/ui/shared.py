"""
shared.py — Constantes de cor, listas e configuração do CustomTkinter.
Importado por vagas_ui.py e cv_ui.py para manter consistência visual.
"""

import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Paleta Deep Space ────────────────────────────────────────────────
COR_BG         = "#07090f"
COR_PANEL      = "#0c1018"
COR_CARD       = "#111720"
COR_SURFACE    = "#19222e"
COR_BORDA      = "#1e2a3c"
COR_SECAO      = "#060810"

# Ação / destaque
COR_AZUL       = "#2563eb"
COR_AZUL_H     = "#5b8ef5"
COR_CIANO      = "#22d3ee"
COR_VERDE      = "#16a34a"
COR_VERDE_H    = "#22c55e"
COR_VERMELHO   = "#dc2626"
COR_VERMELHO_H = "#ef4444"
COR_AMARELO    = "#ca8a04"

# Texto
COR_TEXTO      = "#f0f4ff"
COR_SUBTEXTO   = "#7b92b0"
COR_SEL        = "#163060"

# Listas usadas na UI
FONTES_SITES   = ["Todas", "linkedin", "vagas.com", "infojobs"]
ESTADOS        = ["Todos", "SP", "RJ", "MG", "RS", "PR", "SC",
                  "BA", "PE", "CE", "GO", "DF", "AM", "Remoto"]
MODALIDADES    = ["Todas", "remoto", "hibrido", "presencial"]
STATUS_LISTA   = ["Todos", "nova", "favorita", "aplicada", "ignorada"]
RESULTADO_LISTA= ["Todos", "pendente", "chamado", "nao_chamado", "contratado"]
