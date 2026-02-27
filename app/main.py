"""
main.py — Job Aggregator (orchestrator)
Local: D:\\PORTFOLIO\\Job Aggregator\\app\\main.py

Cria a janela principal com duas abas:
  ⚡  Vagas     — busca e gestão de vagas (VagasTab)
  📄  Currículo — gerador de CV com rendercv (CvTab)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import customtkinter as ctk

from app.ui.shared import (
    COR_BG, COR_PANEL, COR_CARD, COR_CIANO, COR_TEXTO, COR_SUBTEXTO,
)
from app.ui.vagas_ui import VagasTab
from app.ui.cv_ui    import CvTab


class JobAggregator(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Job Aggregator")
        self.geometry("1440x860")
        self.minsize(1100, 700)
        self.configure(fg_color=COR_BG)
        self._construir_tabs()

    def _construir_tabs(self):
        tabs = ctk.CTkTabview(
            self,
            fg_color=COR_BG,
            segmented_button_fg_color=COR_PANEL,
            segmented_button_selected_color=COR_CIANO,
            segmented_button_selected_hover_color=COR_CIANO,
            segmented_button_unselected_color=COR_PANEL,
            segmented_button_unselected_hover_color=COR_CARD,
            text_color=COR_TEXTO,
        )
        tabs.pack(fill="both", expand=True, padx=0, pady=0)

        tabs.add("⚡  Vagas")
        tabs.add("📄  Currículo")

        VagasTab(tabs.tab("⚡  Vagas"))
        CvTab(tabs.tab("📄  Currículo"))


if __name__ == "__main__":
    app = JobAggregator()
    app.mainloop()
