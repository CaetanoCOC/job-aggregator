"""
cv_ui.py — Classe CvTab: aba de geração de currículo com rendercv.

Layout (2 painéis side-by-side):
  LEFT  (340px fixo) — upload, tema, botões de ação, log de status
  RIGHT (flex)       — editor YAML + botões Gerar PDF / Abrir PDF
"""

import os
import threading
import webbrowser

import customtkinter as ctk
from tkinter import filedialog, messagebox

from app.ui.shared import (
    COR_BG, COR_PANEL, COR_CARD, COR_BORDA, COR_SECAO,
    COR_AZUL, COR_AZUL_H, COR_CIANO, COR_VERDE, COR_VERDE_H,
    COR_VERMELHO, COR_VERMELHO_H, COR_AMARELO,
    COR_TEXTO, COR_SUBTEXTO,
)

# Mapeamento: nome exibido → ID interno do tema
_TEMAS_MAP: dict[str, str] = {
    "Executivo Azul":      "executivo_azul",
    "Elegante Brasileiro": "elegante_br",
    "Compacto Acadêmico":  "compacto_academico",
    "Moderno Conectado":   "moderno_conectado",
}
_TEMAS_DISPLAY = list(_TEMAS_MAP.keys())
_TEMAS_HTML    = {"executivo_azul", "elegante_br", "compacto_academico", "moderno_conectado"}

_YAML_PLACEHOLDER = """\
# Selecione um arquivo .pdf ou .docx e clique em
# "Extrair e Converter" para gerar o YAML automaticamente.
#
# Você também pode escrever ou colar o YAML aqui diretamente.
# Exemplo mínimo:
#
# cv:
#   name: Seu Nome
#   email: seuemail@exemplo.com
#   phone: "+55 11 99999-9999"
#   sections:
#     Resumo:
#       - "Profissional com experiência em..."
#     Experiência:
#       - bullet: "Empresa XYZ — Cargo — 2020–2024"
#     Habilidades:
#       - label: Python (pandas, NumPy)
#         details: ""
#     Formação:
#       - bullet: "Universidade — Curso (2020–2024)"
#     Idiomas:
#       - label: Inglês
#         details: Avançado
#
# design:
#   theme: classic
"""


class CvTab:
    def __init__(self, parent: ctk.CTkFrame):
        self.parent = parent
        self._arquivo_cv: str  = ""
        self._pdf_gerado: str  = ""
        self._gerando: bool    = False

        self.parent.grid_columnconfigure(0, weight=0)
        self.parent.grid_columnconfigure(1, weight=1)
        self.parent.grid_rowconfigure(0, weight=1)

        self._construir_ui()

    # ══════════════════════════════════════════════════════════════════
    #  CONSTRUÇÃO DA UI
    # ══════════════════════════════════════════════════════════════════

    def _construir_ui(self):
        self._build_left_panel()
        self._build_right_panel()

    def _build_left_panel(self):
        left = ctk.CTkFrame(self.parent, fg_color=COR_PANEL, corner_radius=0,
                            width=340)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_propagate(False)
        left.grid_columnconfigure(0, weight=1)

        # Borda direita separadora
        ctk.CTkFrame(left, fg_color=COR_BORDA, width=1,
                     corner_radius=0).place(relx=1.0, rely=0, relheight=1,
                                            anchor="ne")

        # ── Logo / título da aba ───────────────────────────────────────
        logo_card = ctk.CTkFrame(left, fg_color=COR_CARD, corner_radius=8,
                                 border_color=COR_BORDA, border_width=1)
        logo_card.grid(row=0, column=0, padx=12, pady=(14, 6), sticky="ew")
        ctk.CTkFrame(logo_card, fg_color=COR_CIANO, height=2,
                     corner_radius=8).pack(fill="x")
        inner = ctk.CTkFrame(logo_card, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=(6, 6))
        ctk.CTkLabel(inner, text="📄",
                     font=ctk.CTkFont("Segoe UI", 16),
                     text_color=COR_CIANO).pack(side="left")
        ctk.CTkLabel(inner, text="  Gerador de Currículo",
                     font=ctk.CTkFont("Segoe UI", 14, "bold"),
                     text_color=COR_TEXTO).pack(side="left")

        # ── Separador ─────────────────────────────────────────────────
        self._sep(left, 1)

        # ── Seção: Arquivo ─────────────────────────────────────────────
        self._bloco_titulo(left, "📁  ARQUIVO DO CURRÍCULO", 2)

        self._lbl(left, "Arquivo selecionado:", 3)
        self.lbl_arquivo = ctk.CTkLabel(
            left, text="Nenhum arquivo selecionado",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=COR_SUBTEXTO, anchor="w", wraplength=300)
        self.lbl_arquivo.grid(row=4, column=0, padx=14, pady=(0, 4), sticky="ew")

        ctk.CTkButton(
            left, text="📂  Selecionar Arquivo (.pdf / .docx)",
            fg_color=COR_AZUL, hover_color=COR_AZUL_H,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            height=34, command=self._selecionar_arquivo
        ).grid(row=5, column=0, padx=12, pady=(0, 6), sticky="ew")

        self._sep(left, 6)

        # ── Seção: Tema ────────────────────────────────────────────────
        self._bloco_titulo(left, "🎨  TEMA RENDERCV", 7)

        self._lbl(left, "Tema visual do PDF:", 8)
        self.combo_tema = ctk.CTkComboBox(
            left, values=_TEMAS_DISPLAY,
            fg_color=COR_CARD, border_color=COR_BORDA, button_color=COR_AZUL,
            text_color=COR_TEXTO, dropdown_fg_color=COR_CARD, height=32)
        self.combo_tema.set("Executivo Azul")
        self.combo_tema.grid(row=9, column=0, padx=12, pady=(0, 6), sticky="ew")

        self._sep(left, 10)

        # ── Botão principal ────────────────────────────────────────────
        self._bloco_titulo(left, "⚡  AÇÕES", 11)

        self.btn_extrair = ctk.CTkButton(
            left, text="⚡  Extrair e Converter para YAML",
            fg_color=COR_VERDE, hover_color=COR_VERDE_H,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            height=38, command=self._extrair_e_converter
        )
        self.btn_extrair.grid(row=12, column=0, padx=12, pady=(0, 6), sticky="ew")

        ctk.CTkButton(
            left, text="💾  Salvar YAML em disco",
            fg_color=COR_AZUL, hover_color=COR_AZUL_H,
            font=ctk.CTkFont("Segoe UI", 11),
            height=34, command=self._salvar_yaml
        ).grid(row=13, column=0, padx=12, pady=(0, 4), sticky="ew")

        self._sep(left, 14)

        # ── Log de status ──────────────────────────────────────────────
        self._bloco_titulo(left, "📋  STATUS", 15)

        self.txt_log = ctk.CTkTextbox(
            left, height=140, fg_color=COR_CARD,
            border_color=COR_BORDA, border_width=1,
            text_color=COR_SUBTEXTO,
            font=ctk.CTkFont("Consolas", 10), wrap="word")
        self.txt_log.grid(row=16, column=0, padx=12, pady=(0, 12), sticky="ew")
        self.txt_log.configure(state="disabled")
        self._log("Pronto. Selecione um arquivo para começar.")

    def _build_right_panel(self):
        right = ctk.CTkFrame(self.parent, fg_color=COR_BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(1, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        # ── Topbar ────────────────────────────────────────────────────
        topo = ctk.CTkFrame(right, fg_color=COR_PANEL, corner_radius=10, height=54)
        topo.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 0))
        topo.grid_columnconfigure(1, weight=1)
        topo.grid_propagate(False)
        ctk.CTkFrame(topo, fg_color=COR_CIANO, height=2,
                     corner_radius=10).grid(row=0, column=0, columnspan=3,
                                            sticky="new")
        ctk.CTkLabel(topo, text="📝  Editor YAML",
                     font=ctk.CTkFont("Segoe UI", 13, "bold"),
                     text_color=COR_TEXTO
                     ).grid(row=0, column=0, padx=18, sticky="ns")
        ctk.CTkLabel(topo,
                     text="Edite o YAML gerado antes de gerar o PDF",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=COR_SUBTEXTO
                     ).grid(row=0, column=1, padx=6, sticky="w")

        # ── Editor YAML ────────────────────────────────────────────────
        editor_frame = ctk.CTkFrame(right, fg_color=COR_PANEL, corner_radius=10)
        editor_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=10)
        editor_frame.grid_columnconfigure(0, weight=1)
        editor_frame.grid_rowconfigure(0, weight=1)

        self.editor_yaml = ctk.CTkTextbox(
            editor_frame,
            fg_color=COR_CARD, border_color=COR_BORDA, border_width=1,
            text_color=COR_TEXTO,
            font=ctk.CTkFont("Consolas", 11),
            wrap="none")
        self.editor_yaml.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.editor_yaml.insert("0.0", _YAML_PLACEHOLDER)

        # ── Botões de geração ──────────────────────────────────────────
        btn_frame = ctk.CTkFrame(right, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)
        btn_frame.grid_columnconfigure(2, weight=0)

        self.btn_gerar = ctk.CTkButton(
            btn_frame, text="🖨  Gerar PDF",
            fg_color=COR_VERDE, hover_color=COR_VERDE_H,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            height=40, command=self._gerar_pdf
        )
        self.btn_gerar.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        self.btn_abrir = ctk.CTkButton(
            btn_frame, text="📂  Abrir PDF",
            fg_color=COR_AZUL, hover_color=COR_AZUL_H,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            height=40, command=self._abrir_pdf,
            state="disabled"
        )
        self.btn_abrir.grid(row=0, column=1, padx=(0, 6), sticky="ew")

        self.lbl_pdf_status = ctk.CTkLabel(
            btn_frame, text="",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=COR_SUBTEXTO, anchor="w")
        self.lbl_pdf_status.grid(row=0, column=2, padx=(6, 0), sticky="w")

    # ══════════════════════════════════════════════════════════════════
    #  AÇÕES
    # ══════════════════════════════════════════════════════════════════

    def _selecionar_arquivo(self):
        caminho = filedialog.askopenfilename(
            title="Selecionar currículo",
            filetypes=[
                ("Documentos", "*.pdf *.docx"),
                ("PDF", "*.pdf"),
                ("Word", "*.docx"),
                ("Todos", "*.*"),
            ]
        )
        if caminho:
            self._arquivo_cv = caminho
            nome = os.path.basename(caminho)
            self.lbl_arquivo.configure(text=nome, text_color=COR_TEXTO)
            self._log(f"Arquivo selecionado: {nome}")

    def _extrair_e_converter(self):
        if not self._arquivo_cv:
            messagebox.showwarning(
                "Arquivo necessário",
                "Selecione um arquivo .pdf ou .docx antes de converter.")
            return

        self.btn_extrair.configure(state="disabled", text="⏳  Convertendo...")
        self._log("Extraindo texto do arquivo...")

        def _tarefa():
            try:
                from app.cv.extractor import extrair_texto
                from app.cv.parser    import texto_para_yaml

                texto = extrair_texto(self._arquivo_cv)
                self.parent.after(0, lambda: self._log(
                    f"Texto extraído: {len(texto)} caracteres."))

                yaml_str = texto_para_yaml(texto)

                # Atualiza o tema no YAML apenas para temas rendercv padrão
                tema_display = self.combo_tema.get()
                tema_id = _TEMAS_MAP.get(tema_display, "classic")
                if tema_id not in _TEMAS_HTML:
                    yaml_str = yaml_str.replace("theme: classic",
                                                f"theme: {tema_id}")

                self.parent.after(0, lambda: self._preencher_editor(yaml_str))
                self.parent.after(0, lambda: self._log(
                    "YAML gerado! Revise e edite antes de gerar o PDF."))

            except Exception as e:
                self.parent.after(0, lambda: self._log(f"Erro: {e}"))
                self.parent.after(0, lambda: messagebox.showerror(
                    "Erro na extração", str(e)))
            finally:
                self.parent.after(0, lambda: self.btn_extrair.configure(
                    state="normal", text="⚡  Extrair e Converter para YAML"))

        threading.Thread(target=_tarefa, daemon=True).start()

    def _preencher_editor(self, conteudo: str):
        self.editor_yaml.configure(state="normal")
        self.editor_yaml.delete("0.0", "end")
        self.editor_yaml.insert("0.0", conteudo)

    def _gerar_pdf(self):
        if self._gerando:
            return

        yaml_content = self.editor_yaml.get("0.0", "end").strip()
        if not yaml_content or yaml_content.startswith("#"):
            messagebox.showwarning(
                "YAML vazio",
                "Gere ou escreva o YAML no editor antes de gerar o PDF.")
            return

        destino = filedialog.asksaveasfilename(
            title="Salvar PDF como",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile="curriculo.pdf",
        )
        if not destino:
            return

        tema_display = self.combo_tema.get()
        tema_id      = _TEMAS_MAP.get(tema_display, "classic")
        eh_html      = tema_id in _TEMAS_HTML
        msg_inicio   = (
            f"Gerando PDF com formato '{tema_display}'..."
            if eh_html else
            "Iniciando rendercv (pode demorar ~30s)..."
        )

        self._gerando = True
        self.btn_gerar.configure(state="disabled", text="⏳  Gerando PDF...")
        self.btn_abrir.configure(state="disabled")
        self.lbl_pdf_status.configure(text="", text_color=COR_SUBTEXTO)
        self._log(msg_inicio)

        def _tarefa():
            try:
                from app.cv.renderer import gerar_pdf
                caminho = gerar_pdf(yaml_content, destino, tema_id=tema_id)
                self._pdf_gerado = caminho
                self.parent.after(0, lambda: self._log(
                    f"PDF gerado com sucesso!\n{caminho}"))
                self.parent.after(0, lambda: self.btn_abrir.configure(
                    state="normal"))
                self.parent.after(0, lambda: self.lbl_pdf_status.configure(
                    text="✅ PDF gerado!", text_color=COR_VERDE_H))
            except RuntimeError as e:
                # RuntimeError do fallback HTML = HTML aberto no browser
                msg = str(e)
                self.parent.after(0, lambda: self._log(msg))
                self.parent.after(0, lambda: messagebox.showinfo(
                    "Currículo em HTML", msg))
                self.parent.after(0, lambda: self.lbl_pdf_status.configure(
                    text="⚠ Aberto no navegador", text_color=COR_AMARELO))
            except Exception as e:
                self.parent.after(0, lambda: self._log(f"Erro ao gerar PDF:\n{e}"))
                self.parent.after(0, lambda: messagebox.showerror(
                    "Erro ao gerar PDF", str(e)))
                self.parent.after(0, lambda: self.lbl_pdf_status.configure(
                    text="❌ Falhou", text_color=COR_VERMELHO_H))
            finally:
                self._gerando = False
                self.parent.after(0, lambda: self.btn_gerar.configure(
                    state="normal", text="🖨  Gerar PDF"))

        threading.Thread(target=_tarefa, daemon=True).start()

    def _abrir_pdf(self):
        if self._pdf_gerado and os.path.exists(self._pdf_gerado):
            webbrowser.open(self._pdf_gerado)
        else:
            messagebox.showinfo("PDF não encontrado",
                                "Gere o PDF primeiro ou verifique o caminho.")

    def _salvar_yaml(self):
        conteudo = self.editor_yaml.get("0.0", "end").strip()
        if not conteudo:
            messagebox.showwarning("Editor vazio", "Nada para salvar.")
            return

        caminho = filedialog.asksaveasfilename(
            title="Salvar YAML",
            defaultextension=".yaml",
            filetypes=[("YAML", "*.yaml *.yml"), ("Todos", "*.*")],
            initialfile="curriculo.yaml",
        )
        if caminho:
            with open(caminho, "w", encoding="utf-8") as f:
                f.write(conteudo)
            self._log(f"YAML salvo em: {os.path.basename(caminho)}")

    # ── Helpers UI ─────────────────────────────────────────────────────

    def _log(self, msg: str):
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", f"› {msg}\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def _sep(self, parent, row: int):
        ctk.CTkFrame(parent, fg_color=COR_BORDA, height=1
                     ).grid(row=row, column=0, sticky="ew", padx=12, pady=2)

    def _lbl(self, parent, texto: str, row: int):
        ctk.CTkLabel(parent, text=texto,
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=COR_TEXTO, anchor="w"
                     ).grid(row=row, column=0, padx=14, pady=(4, 1), sticky="ew")

    def _bloco_titulo(self, parent, texto: str, row: int):
        ctk.CTkLabel(parent,
                     text=f"▌  {texto}",
                     font=ctk.CTkFont("Segoe UI", 9, "bold"),
                     text_color=COR_CIANO,
                     fg_color=COR_SECAO,
                     corner_radius=4,
                     anchor="w"
                     ).grid(row=row, column=0, padx=10, pady=(4, 2), sticky="ew")
