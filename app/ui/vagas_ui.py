"""
vagas_ui.py — Classe VagasTab: toda a interface da aba de vagas.
Extraído de app/main.py; o parent é o frame da aba do CTkTabview.
"""

import threading
import webbrowser
import tkinter as tk
import random

import customtkinter as ctk
from tkinter import messagebox, ttk

from app.database import (
    criar_banco, inserir_vaga, buscar_vagas,
    atualizar_status, registrar_feedback,
    salvar_skill, deletar_skill, buscar_skills_usuario,
    salvar_historico, stats_gerais,
)
from app.utils.helpers import normalizar_skills, calcular_match_score
from app.ui.shared import (
    COR_BG, COR_PANEL, COR_CARD, COR_SURFACE, COR_BORDA, COR_SECAO,
    COR_AZUL, COR_AZUL_H, COR_CIANO, COR_VERDE, COR_VERDE_H,
    COR_VERMELHO, COR_VERMELHO_H, COR_AMARELO,
    COR_TEXTO, COR_SUBTEXTO, COR_SEL,
    FONTES_SITES, ESTADOS, MODALIDADES, STATUS_LISTA, RESULTADO_LISTA,
)


class VagasTab:
    def __init__(self, parent: ctk.CTkFrame):
        self.parent = parent
        criar_banco()

        self._vagas_cache: list    = []
        self._skills_usuario: list = []
        self._busca_ativa: bool    = False
        self._novas_inseridas: int = 0

        self.parent.grid_columnconfigure(1, weight=1)
        self.parent.grid_rowconfigure(0, weight=1)

        self._carregar_skills_usuario()
        self._construir_ui()
        self._atualizar_stats()
        self._aplicar_filtros()

    # ══════════════════════════════════════════════════════════════════
    #  CONSTRUÇÃO DA UI
    # ══════════════════════════════════════════════════════════════════

    def _construir_ui(self):
        self._build_sidebar()
        self._build_main()

    # ── Sidebar ────────────────────────────────────────────────────────

    def _build_sidebar(self):
        outer = ctk.CTkFrame(self.parent, fg_color=COR_PANEL, corner_radius=0, width=292)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.grid_propagate(False)
        outer.grid_rowconfigure(0, weight=1)
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_columnconfigure(1, weight=0)

        sb = ctk.CTkScrollableFrame(
            outer, fg_color=COR_PANEL,
            scrollbar_button_color=COR_BORDA,
            scrollbar_button_hover_color=COR_CIANO,
            corner_radius=0)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_columnconfigure(0, weight=1)

        # Borda direita da sidebar (separador visual)
        ctk.CTkFrame(outer, fg_color=COR_BORDA, width=1,
                     corner_radius=0).grid(row=0, column=1, sticky="ns")

        row = [0]

        def nr(extra_before=0):
            row[0] += 1 + extra_before
            return row[0]

        # ── Logo em card ──────────────────────────────────────────────
        logo_card = ctk.CTkFrame(sb, fg_color=COR_CARD, corner_radius=8,
                                 border_color=COR_BORDA, border_width=1)
        logo_card.grid(row=nr(), column=0, padx=12, pady=(10, 4), sticky="ew")

        ctk.CTkFrame(logo_card, fg_color=COR_CIANO, height=2,
                     corner_radius=8).pack(fill="x")

        logo_inner = ctk.CTkFrame(logo_card, fg_color="transparent")
        logo_inner.pack(fill="x", padx=10, pady=(6, 6))
        ctk.CTkLabel(logo_inner, text="⚡",
                     font=ctk.CTkFont("Segoe UI", 16, "bold"),
                     text_color=COR_CIANO).pack(side="left")
        ctk.CTkLabel(logo_inner, text="  Job Aggregator",
                     font=ctk.CTkFont("Segoe UI", 15, "bold"),
                     text_color=COR_TEXTO).pack(side="left")

        self._sep(sb, nr())

        # ── BLOCO 1: BUSCAR NA WEB ─────────────────────────────────────
        self._bloco_titulo(sb, "🌐  BUSCAR NOVAS VAGAS", nr())

        self._lbl(sb, "🎯 Cargo", nr())
        self.entry_cargo = ctk.CTkEntry(
            sb, placeholder_text="ex: Analista de Dados",
            fg_color=COR_CARD, border_color=COR_BORDA,
            text_color=COR_TEXTO, height=32)
        self.entry_cargo.grid(row=nr(), column=0, padx=12, pady=(0, 4), sticky="ew")
        self.entry_cargo.bind("<Return>", lambda e: self._iniciar_scraping())

        self._lbl(sb, "📍 Estado", nr())
        self.combo_estado_web = ctk.CTkComboBox(
            sb, values=ESTADOS, fg_color=COR_CARD,
            border_color=COR_BORDA, button_color=COR_AZUL,
            text_color=COR_TEXTO, dropdown_fg_color=COR_CARD, height=32)
        self.combo_estado_web.set("Todos")
        self.combo_estado_web.grid(row=nr(), column=0, padx=12, pady=(0, 4), sticky="ew")

        self._lbl(sb, "🌐 Site", nr())
        self.combo_fonte = ctk.CTkComboBox(
            sb, values=FONTES_SITES, fg_color=COR_CARD,
            border_color=COR_BORDA, button_color=COR_AZUL,
            text_color=COR_TEXTO, dropdown_fg_color=COR_CARD, height=32)
        self.combo_fonte.set("Todas")
        self.combo_fonte.grid(row=nr(), column=0, padx=12, pady=(0, 4), sticky="ew")

        self._lbl(sb, "🏠 Modalidade", nr())
        self.combo_modal = ctk.CTkComboBox(
            sb, values=MODALIDADES, fg_color=COR_CARD,
            border_color=COR_BORDA, button_color=COR_AZUL,
            text_color=COR_TEXTO, dropdown_fg_color=COR_CARD, height=32)
        self.combo_modal.set("Todas")
        self.combo_modal.grid(row=nr(), column=0, padx=12, pady=(0, 6), sticky="ew")

        self.btn_web = ctk.CTkButton(
            sb, text="🌐  Buscar na Web",
            fg_color=COR_VERDE, hover_color=COR_VERDE_H,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            height=36, command=self._iniciar_scraping)
        self.btn_web.grid(row=nr(), column=0, padx=12, pady=(0, 6), sticky="ew")

        self._sep(sb, nr())

        # ── BLOCO 2: FILTRAR SALVOS ────────────────────────────────────
        self._bloco_titulo(sb, "🔍  FILTRAR SALVOS", nr())

        self._lbl(sb, "📋 Status Candidatura", nr())
        self.combo_status = ctk.CTkComboBox(
            sb, values=STATUS_LISTA, fg_color=COR_CARD,
            border_color=COR_BORDA, button_color=COR_AZUL,
            text_color=COR_TEXTO, dropdown_fg_color=COR_CARD, height=32)
        self.combo_status.set("Todos")
        self.combo_status.grid(row=nr(), column=0, padx=12, pady=(0, 4), sticky="ew")

        self._lbl(sb, "📊 Resultado Entrevista", nr())
        self.combo_resultado = ctk.CTkComboBox(
            sb, values=RESULTADO_LISTA, fg_color=COR_CARD,
            border_color=COR_BORDA, button_color=COR_AZUL,
            text_color=COR_TEXTO, dropdown_fg_color=COR_CARD, height=32)
        self.combo_resultado.set("Todos")
        self.combo_resultado.grid(row=nr(), column=0, padx=12, pady=(0, 6), sticky="ew")

        ctk.CTkButton(
            sb, text="🔍  Filtrar Resultados",
            fg_color=COR_AZUL, hover_color=COR_AZUL_H,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            height=36, command=self._aplicar_filtros
        ).grid(row=nr(), column=0, padx=12, pady=(0, 6), sticky="ew")

        self._sep(sb, nr())

        # ── BLOCO 3: MINHAS HABILIDADES ────────────────────────────────
        self._bloco_titulo(sb, "💡  MINHAS HABILIDADES", nr())

        frame_input = ctk.CTkFrame(sb, fg_color="transparent")
        frame_input.grid(row=nr(), column=0, padx=12, pady=(0, 4), sticky="ew")
        frame_input.grid_columnconfigure(0, weight=1)

        self.entry_skill = ctk.CTkEntry(
            frame_input, placeholder_text="Python, SQL, Excel...",
            fg_color=COR_CARD, border_color=COR_BORDA,
            text_color=COR_TEXTO, height=30)
        self.entry_skill.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.entry_skill.bind("<Return>", lambda e: self._add_skills())

        ctk.CTkButton(
            frame_input, text="+", width=30, height=30,
            fg_color=COR_AZUL, hover_color=COR_AZUL_H,
            font=ctk.CTkFont("Segoe UI", 15, "bold"),
            command=self._add_skills
        ).grid(row=0, column=1)

        self.frame_skills = ctk.CTkFrame(
            sb, fg_color=COR_CARD, corner_radius=6,
            border_color=COR_BORDA, border_width=1)
        self.frame_skills.grid(row=nr(), column=0, padx=12, pady=(0, 6), sticky="ew")
        self._render_skills()

        self._sep(sb, nr())

        # ── BLOCO 4: ESTATÍSTICAS ──────────────────────────────────────
        self._bloco_titulo(sb, "📊  ESTATÍSTICAS", nr())

        self.frame_stats = ctk.CTkFrame(sb, fg_color="transparent")
        self.frame_stats.grid(row=nr(), column=0, padx=12, pady=(0, 10), sticky="ew")
        self.frame_stats.grid_columnconfigure((0, 1), weight=1)
        self._render_stats()

    # ── Área principal ─────────────────────────────────────────────────

    def _build_main(self):
        main = ctk.CTkFrame(self.parent, fg_color=COR_BG)
        main.grid(row=0, column=1, sticky="nsew", padx=(1, 0))
        main.grid_columnconfigure(0, weight=3)
        main.grid_columnconfigure(1, weight=2)
        main.grid_rowconfigure(1, weight=1)

        # ── Canvas com efeito de fundo espacial (estrelas) ────────────
        self._canvas_bg = tk.Canvas(main, bg=COR_BG, highlightthickness=0)
        self._canvas_bg.place(x=0, y=0, relwidth=1, relheight=1)

        _rng = random.Random(1337)

        def _redesenhar_pontos(event):
            self._canvas_bg.delete("estrelas")
            w, h = event.width, event.height
            if w < 4 or h < 4:
                return
            _rng.seed(1337)
            for _ in range(130):
                x = _rng.randint(0, w)
                y = _rng.randint(0, h)
                b = _rng.randint(18, 32)
                cor = f"#{b:02x}{b:02x}{min(b + 10, 48):02x}"
                self._canvas_bg.create_rectangle(
                    x, y, x + 1, y + 1, fill=cor, outline="", tags="estrelas")
            for _ in range(45):
                x = _rng.randint(0, w)
                y = _rng.randint(0, h)
                b = _rng.randint(30, 55)
                cor = f"#{b:02x}{b:02x}{min(b + 14, 70):02x}"
                self._canvas_bg.create_oval(
                    x - 1, y - 1, x + 1, y + 1, fill=cor, outline="",
                    tags="estrelas")
            for _ in range(12):
                x = _rng.randint(0, w)
                y = _rng.randint(0, h)
                b = _rng.randint(55, 80)
                cor = f"#{b:02x}{b:02x}{min(b + 20, 100):02x}"
                self._canvas_bg.create_oval(
                    x - 1, y - 1, x + 2, y + 2, fill=cor, outline="",
                    tags="estrelas")

        main.bind("<Configure>", _redesenhar_pontos)

        # ── Topbar ────────────────────────────────────────────────────
        topo = ctk.CTkFrame(main, fg_color=COR_PANEL, corner_radius=10, height=54)
        topo.grid(row=0, column=0, columnspan=2, sticky="ew",
                  padx=12, pady=(12, 0))
        topo.grid_columnconfigure(1, weight=1)
        topo.grid_propagate(False)

        ctk.CTkFrame(topo, fg_color=COR_CIANO, height=2,
                     corner_radius=10).grid(row=0, column=0, columnspan=3,
                                            sticky="new", padx=0)

        left = ctk.CTkFrame(topo, fg_color="transparent")
        left.grid(row=0, column=0, padx=18, sticky="ns")
        ctk.CTkLabel(left, text="Vagas encontradas",
                     font=ctk.CTkFont("Segoe UI", 13, "bold"),
                     text_color=COR_TEXTO
                     ).pack(side="left", pady=16)
        self.lbl_contagem = ctk.CTkLabel(
            left, text="0 vagas",
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            text_color=COR_CIANO)
        self.lbl_contagem.pack(side="left", padx=(8, 0), pady=16)

        self.lbl_status = ctk.CTkLabel(
            topo, text="",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=COR_SUBTEXTO)
        self.lbl_status.grid(row=0, column=1, padx=10, sticky="w")

        pill = ctk.CTkFrame(topo, fg_color=COR_CARD, corner_radius=20)
        pill.grid(row=0, column=2, padx=16, pady=10, sticky="e")

        self.dot_status = ctk.CTkLabel(
            pill, text="●",
            font=ctk.CTkFont("Segoe UI", 13),
            text_color=COR_SUBTEXTO)
        self.dot_status.pack(side="left", padx=(10, 4), pady=5)

        self.lbl_indicator = ctk.CTkLabel(
            pill, text="Aguardando",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=COR_SUBTEXTO)
        self.lbl_indicator.pack(side="left", padx=(0, 12), pady=5)

        self.progress = ctk.CTkProgressBar(
            main, mode="indeterminate",
            fg_color=COR_BG,
            progress_color=COR_CIANO, height=2, corner_radius=0)
        self.progress.grid(row=0, column=0, columnspan=2,
                           sticky="sew", padx=12, pady=0)
        self.progress.set(0)

        # Tabela
        frame_tab = ctk.CTkFrame(main, fg_color=COR_PANEL, corner_radius=10)
        frame_tab.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=10)
        frame_tab.grid_rowconfigure(0, weight=1)
        frame_tab.grid_columnconfigure(0, weight=1)
        self._build_tabela(frame_tab)

        # Detalhe
        self.painel_det = ctk.CTkScrollableFrame(
            main, fg_color=COR_PANEL, corner_radius=10)
        self.painel_det.grid(row=1, column=1, sticky="nsew",
                             padx=(6, 12), pady=10)
        self._detalhe_vazio()

    def _build_tabela(self, parent):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("J.Treeview",
                        background=COR_CARD,
                        foreground=COR_TEXTO,
                        fieldbackground=COR_CARD,
                        rowheight=36,
                        borderwidth=0,
                        font=("Segoe UI", 11))

        style.configure("J.Treeview.Heading",
                        background=COR_SURFACE,
                        foreground=COR_TEXTO,
                        font=("Segoe UI", 10, "bold"),
                        relief="flat",
                        padding=(6, 8))

        style.map("J.Treeview",
                  background=[("selected", COR_SEL)],
                  foreground=[("selected", "#ffffff")])
        style.map("J.Treeview.Heading",
                  background=[("active", COR_BORDA)],
                  foreground=[("active", COR_TEXTO)])

        style.configure("J.Vertical.TScrollbar",
                        background=COR_CARD,
                        troughcolor=COR_PANEL,
                        borderwidth=0,
                        arrowsize=0,
                        width=6)
        style.map("J.Vertical.TScrollbar",
                  background=[("active", COR_BORDA)])

        cols = ("titulo", "empresa", "local", "site",
                "match", "prob", "status")
        self.tabela = ttk.Treeview(parent, columns=cols, show="headings",
                                   style="J.Treeview", selectmode="browse")
        heads = [
            ("titulo",  "Cargo / Vaga",  230),
            ("empresa", "Empresa",       145),
            ("local",   "Local",          80),
            ("site",    "Site",           85),
            ("match",   "Match %",        68),
            ("prob",    "Chance %",       68),
            ("status",  "Status",         85),
        ]
        for col, txt, w in heads:
            self.tabela.heading(col, text=txt, anchor="w")
            self.tabela.column(col, width=w, anchor="w", minwidth=40)

        vsb = ttk.Scrollbar(parent, orient="vertical",
                            command=self.tabela.yview,
                            style="J.Vertical.TScrollbar")
        self.tabela.configure(yscrollcommand=vsb.set)
        self.tabela.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        vsb.grid(row=0, column=1, sticky="ns", pady=8, padx=(0, 4))
        self.tabela.bind("<<TreeviewSelect>>", self._ao_selecionar)

        self.tabela.tag_configure("par",   background=COR_CARD)
        self.tabela.tag_configure("impar", background="#0d1420")

        self.tabela.tag_configure("nova",        foreground=COR_TEXTO)
        self.tabela.tag_configure("favorita",    foreground="#fbbf24")
        self.tabela.tag_configure("aplicada",    foreground=COR_VERDE_H)
        self.tabela.tag_configure("ignorada",    foreground="#4a5f78")
        self.tabela.tag_configure("chamado",     foreground=COR_VERDE_H)
        self.tabela.tag_configure("nao_chamado", foreground=COR_VERMELHO_H)
        self.tabela.tag_configure("contratado",  foreground="#a855f7")

    # ══════════════════════════════════════════════════════════════════
    #  PAINEL DETALHE
    # ══════════════════════════════════════════════════════════════════

    def _detalhe_vazio(self):
        for w in self.painel_det.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.painel_det,
                     text="← Selecione uma vaga\npara ver os detalhes",
                     font=ctk.CTkFont("Segoe UI", 14),
                     text_color=COR_SUBTEXTO, justify="center"
                     ).pack(expand=True, pady=80)

    def _render_detalhe(self, vaga: dict):
        for w in self.painel_det.winfo_children():
            w.destroy()
        pd = self.painel_det

        ctk.CTkLabel(pd, text=vaga["titulo"],
                     font=ctk.CTkFont("Segoe UI", 15, "bold"),
                     text_color=COR_TEXTO, wraplength=340, justify="left"
                     ).pack(anchor="w", padx=16, pady=(16, 2))
        ctk.CTkLabel(pd,
                     text=vaga.get("empresa") or "Empresa não informada",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=COR_AZUL_H).pack(anchor="w", padx=16)

        frame_b = ctk.CTkFrame(pd, fg_color="transparent")
        frame_b.pack(anchor="w", padx=16, pady=8, fill="x")
        for emoji, txt in [
            ("📍", vaga.get("localizacao") or "—"),
            ("🏠", vaga.get("modalidade") or "—"),
            ("💰", vaga.get("salario") or "Não informado"),
            ("🌐", vaga.get("fonte", "")),
        ]:
            f = ctk.CTkFrame(frame_b, fg_color=COR_BORDA, corner_radius=6)
            f.pack(side="left", padx=(0, 5), pady=2)
            ctk.CTkLabel(f, text=f"{emoji} {txt}",
                         font=ctk.CTkFont("Segoe UI", 10),
                         text_color=COR_SUBTEXTO).pack(padx=8, pady=3)

        frame_sc = ctk.CTkFrame(pd, fg_color=COR_CARD, corner_radius=8)
        frame_sc.pack(fill="x", padx=16, pady=(4, 8))
        frame_sc.grid_columnconfigure((0, 1), weight=1)
        match_pct = vaga.get("match_score", 0)
        prob_pct  = int(vaga.get("prob_aprovacao", 0) * 100)
        for col, (lbl, val, cor) in enumerate([
            ("🎯 Match Skills",     f"{match_pct}%", COR_AZUL_H),
            ("🤖 Chance Aprovação", f"{prob_pct}%",
             COR_VERDE_H if prob_pct >= 50 else COR_AMARELO),
        ]):
            ctk.CTkLabel(frame_sc, text=lbl,
                         font=ctk.CTkFont("Segoe UI", 10),
                         text_color=COR_SUBTEXTO
                         ).grid(row=0, column=col, padx=16, pady=(10, 2))
            ctk.CTkLabel(frame_sc, text=val,
                         font=ctk.CTkFont("Segoe UI", 24, "bold"),
                         text_color=cor
                         ).grid(row=1, column=col, padx=16, pady=(0, 10))

        pb = ctk.CTkProgressBar(pd, fg_color=COR_BORDA,
                                 progress_color=COR_AZUL, height=6, corner_radius=3)
        pb.pack(fill="x", padx=16, pady=(0, 8))
        pb.set(match_pct / 100)

        self._det_secao(pd, "🏷  Skills da vaga")
        frame_sk = ctk.CTkFrame(pd, fg_color="transparent")
        frame_sk.pack(fill="x", padx=16, pady=(0, 8))
        skills_usu = [s.lower() for s in self._skills_usuario]
        for sk in (vaga.get("skills") or ["—"]):
            cor = COR_VERDE if sk.lower() in skills_usu else COR_BORDA
            f = ctk.CTkFrame(frame_sk, fg_color=cor, corner_radius=5)
            f.pack(side="left", padx=(0, 5), pady=2)
            ctk.CTkLabel(f, text=sk, font=ctk.CTkFont("Segoe UI", 10),
                         text_color="#ffffff").pack(padx=7, pady=3)

        self._det_secao(pd, "📄 Descrição")
        tb = ctk.CTkTextbox(pd, height=150, fg_color=COR_CARD,
                             border_color=COR_BORDA, text_color=COR_SUBTEXTO,
                             font=ctk.CTkFont("Segoe UI", 11), wrap="word")
        tb.pack(fill="x", padx=16, pady=(0, 8))
        tb.insert("0.0", vaga.get("descricao") or "Sem descrição disponível.")
        tb.configure(state="disabled")

        link = (vaga.get("link") or "").strip()
        if link:
            lk = link if link.startswith("http") else "https://" + link
            ctk.CTkButton(pd, text="🔗  Abrir Vaga no Site",
                          fg_color=COR_AZUL, hover_color=COR_AZUL_H,
                          font=ctk.CTkFont("Segoe UI", 13, "bold"), height=40,
                          command=lambda l=lk: webbrowser.open(l)
                          ).pack(fill="x", padx=16, pady=(4, 2))
            url_curta = lk[:65] + ("…" if len(lk) > 65 else "")
            ctk.CTkLabel(pd, text=url_curta,
                         font=ctk.CTkFont("Segoe UI", 9),
                         text_color=COR_SUBTEXTO, wraplength=330, justify="left"
                         ).pack(anchor="w", padx=18, pady=(0, 8))

        self._det_secao(pd, "📋 Candidatura")
        frame_cand = ctk.CTkFrame(pd, fg_color="transparent")
        frame_cand.pack(fill="x", padx=16, pady=(0, 8))
        frame_cand.grid_columnconfigure((0, 1, 2, 3), weight=1)
        for col, (em, st, cor) in enumerate([
            ("⭐", "favorita", "#ca8a04"),
            ("✅", "aplicada", COR_VERDE),
            ("🚫", "ignorada", "#64748b"),
            ("🔄", "nova",     COR_AZUL),
        ]):
            ctk.CTkButton(frame_cand, text=f"{em}\n{st.capitalize()}",
                          fg_color=cor, hover_color=COR_CARD,
                          font=ctk.CTkFont("Segoe UI", 10, "bold"), height=40,
                          command=lambda s=st, v=vaga["id"]: self._set_status(v, s)
                          ).grid(row=0, column=col, padx=2, sticky="ew")

        self._det_secao(pd, "🤖 Sistema de Aprendizado")
        resultado = vaga.get("resultado_entrevista", "pendente")
        cor_res = {"chamado": COR_VERDE_H, "nao_chamado": COR_VERMELHO_H,
                   "contratado": "#a855f7", "pendente": COR_SUBTEXTO
                   }.get(resultado, COR_SUBTEXTO)
        ctk.CTkLabel(pd, text=f"Status: {resultado.replace('_', ' ').title()}",
                     font=ctk.CTkFont("Segoe UI", 11, "bold"),
                     text_color=cor_res).pack(anchor="w", padx=16, pady=(0, 4))
        ctk.CTkLabel(pd,
                     text="Marque o resultado — o sistema aprende\n"
                          "quais vagas têm maior chance pra você!",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=COR_SUBTEXTO, justify="left"
                     ).pack(anchor="w", padx=16, pady=(0, 8))

        frame_fb = ctk.CTkFrame(pd, fg_color="transparent")
        frame_fb.pack(fill="x", padx=16, pady=(0, 6))
        frame_fb.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(frame_fb, text="🟢  Fui Chamado!",
                      fg_color=COR_VERDE, hover_color=COR_VERDE_H,
                      font=ctk.CTkFont("Segoe UI", 12, "bold"), height=42,
                      command=lambda v=vaga["id"]: self._feedback(v, True)
                      ).grid(row=0, column=0, padx=(0, 4), sticky="ew")
        ctk.CTkButton(frame_fb, text="🔴  Não Chamado",
                      fg_color=COR_VERMELHO, hover_color=COR_VERMELHO_H,
                      font=ctk.CTkFont("Segoe UI", 12, "bold"), height=42,
                      command=lambda v=vaga["id"]: self._feedback(v, False)
                      ).grid(row=0, column=1, padx=(4, 0), sticky="ew")
        ctk.CTkButton(pd, text="🏆  Fui Contratado!",
                      fg_color="#7c3aed", hover_color="#9333ea",
                      font=ctk.CTkFont("Segoe UI", 12, "bold"), height=38,
                      command=lambda v=vaga["id"]: self._feedback_contratado(v)
                      ).pack(fill="x", padx=16, pady=(0, 20))

    # ══════════════════════════════════════════════════════════════════
    #  AÇÕES PRINCIPAIS
    # ══════════════════════════════════════════════════════════════════

    def _aplicar_filtros(self):
        cargo      = self.entry_cargo.get().strip()
        estado     = self.combo_estado_web.get()
        status     = self.combo_status.get()
        modalidade = self.combo_modal.get()
        resultado  = self.combo_resultado.get()

        vagas_raw = buscar_vagas(
            cargo=cargo,
            status=status,
            resultado=resultado,
        )

        vagas = []
        for v in vagas_raw:
            loc        = (v.get("localizacao") or v.get("estado") or "").lower()
            mod        = (v.get("modalidade") or "").lower()
            is_remoto  = "remot" in mod or "remot" in loc

            if estado and estado not in ("Todos", ""):
                if is_remoto:
                    pass
                elif estado.lower() in loc or estado in (v.get("estado") or ""):
                    pass
                else:
                    continue

            if modalidade and modalidade not in ("Todas", ""):
                if modalidade.lower() not in mod:
                    continue

            v["match_score"] = calcular_match_score(
                v.get("skills", []), self._skills_usuario)
            vagas.append(v)

        self._vagas_cache = vagas
        self._popular_tabela(vagas)
        self._atualizar_stats()

    def _popular_tabela(self, vagas: list):
        self.tabela.delete(*self.tabela.get_children())
        for idx, v in enumerate(vagas):
            resultado  = v.get("resultado_entrevista", "pendente")
            status     = v.get("status", "nova")
            tag_status = resultado if resultado in ("chamado", "nao_chamado", "contratado") \
                else status
            tag_zebra  = "par" if idx % 2 == 0 else "impar"
            local = v.get("estado") or v.get("localizacao", "")
            local = (local[:14] + "…") if len(local) > 16 else local
            self.tabela.insert("", "end",
                iid=str(v["id"]),
                values=(
                    v.get("titulo", ""),
                    v.get("empresa", ""),
                    local,
                    v.get("fonte", ""),
                    f"{v.get('match_score', 0)}%",
                    f"{int(v.get('prob_aprovacao', 0) * 100)}%",
                    status,
                ),
                tags=(tag_zebra, tag_status))
        n = len(vagas)
        self.lbl_contagem.configure(
            text=f"{n} vaga{'s' if n != 1 else ''}")

    def _ao_selecionar(self, event=None):
        sel = self.tabela.selection()
        if not sel:
            return
        vaga_id = int(sel[0])
        vaga = next((v for v in self._vagas_cache if v["id"] == vaga_id), None)
        if vaga:
            vaga["match_score"] = calcular_match_score(
                vaga.get("skills", []), self._skills_usuario)
            self._render_detalhe(vaga)

    def _set_status(self, vaga_id: int, status: str):
        atualizar_status(vaga_id, status)
        self._aplicar_filtros()
        vaga = next((v for v in self._vagas_cache if v["id"] == vaga_id), None)
        if vaga:
            vaga["status"] = status
            self._render_detalhe(vaga)

    def _feedback(self, vaga_id: int, chamado: bool):
        registrar_feedback(vaga_id, chamado)
        msg = "✅ Ótimo! Sistema anotou que você foi chamado!" if chamado \
              else "📊 Anotado. O sistema vai aprender com isso."
        self._set_status_msg(msg)
        self._aplicar_filtros()
        vaga = next((v for v in self._vagas_cache if v["id"] == vaga_id), None)
        if vaga:
            self._render_detalhe(vaga)

    def _feedback_contratado(self, vaga_id: int):
        from app.database import get_connection
        conn = get_connection()
        conn.execute(
            "UPDATE vagas SET resultado_entrevista='contratado',"
            " status='aplicada' WHERE id=?", (vaga_id,))
        conn.commit()
        conn.close()
        registrar_feedback(vaga_id, True)
        self._set_status_msg("🏆 Parabéns! Marcado como contratado!")
        self._aplicar_filtros()

    # ── Scraping ───────────────────────────────────────────────────────

    def _iniciar_scraping(self):
        if self._busca_ativa:
            return
        cargo = self.entry_cargo.get().strip()
        if not cargo:
            messagebox.showwarning("Campo obrigatório",
                                   "Preencha o cargo antes de buscar na web.")
            return

        self._busca_ativa     = True
        self._novas_inseridas = 0
        self.btn_web.configure(state="disabled", text="⏳  Buscando...")
        self.progress.start()
        self._set_indicator("buscando")
        self._set_status_msg("Preparando scrapers...")

        thread = threading.Thread(
            target=self._run_scrapers,
            args=(cargo,
                  self.combo_estado_web.get(),
                  self.combo_fonte.get()),
            daemon=True)
        thread.start()

    def _run_scrapers(self, cargo: str, estado: str, fonte_filtro: str):
        from app.scrapers.linkedin  import LinkedInScraper
        from app.scrapers.vagas_com import VagasComScraper
        from app.scrapers.infojobs  import InfoJobsScraper

        todos = {
            "linkedin":  LinkedInScraper(),
            "vagas.com": VagasComScraper(),
            "infojobs":  InfoJobsScraper(),
        }
        scrapers = ([todos[fonte_filtro]] if fonte_filtro in todos
                    else list(todos.values()))

        for scraper in scrapers:
            try:
                self.parent.after(0, lambda s=scraper.nome_fonte:
                                  self._set_status_msg(f"⏳ Buscando em {s}..."))
                vagas = scraper.buscar(
                    cargo=cargo,
                    localizacao=estado,
                    skills=self._skills_usuario)

                novas_fonte = 0
                for v in vagas:
                    lk = (v.get("link") or "").strip()
                    if lk and not lk.startswith("http"):
                        v["link"] = "https://" + lk
                    v["match_score"] = calcular_match_score(
                        v.get("skills", []), self._skills_usuario)
                    if inserir_vaga(v):
                        novas_fonte          += 1
                        self._novas_inseridas += 1

                print(f"[Main] {scraper.nome_fonte}: "
                      f"{len(vagas)} coletadas, {novas_fonte} novas")
                self.parent.after(0, self._aplicar_filtros)

            except Exception as e:
                print(f"[Main] ✗ Erro {scraper.nome_fonte}: {e}")
                import traceback; traceback.print_exc()

        salvar_historico(cargo, self._skills_usuario, estado,
                         [s.nome_fonte for s in scrapers],
                         self._novas_inseridas)
        self.parent.after(0, self._fim_scraping)

    def _fim_scraping(self):
        self._busca_ativa = False
        self.progress.stop()
        self.progress.set(0)
        self.btn_web.configure(state="normal", text="🌐  Buscar na Web")
        n = self._novas_inseridas
        self._set_status_msg(
            f"✅ {n} nova{'s' if n != 1 else ''} "
            f"vaga{'s' if n != 1 else ''} encontrada{'s' if n != 1 else ''}!")
        self._set_indicator("ok")
        self._aplicar_filtros()
        self.parent.after(6000, lambda: (
            self._set_status_msg(""), self._set_indicator("idle")))

    # ── Skills ─────────────────────────────────────────────────────────

    def _add_skills(self):
        raw = self.entry_skill.get().strip()
        if not raw:
            return
        for sk in normalizar_skills(raw):
            salvar_skill(sk)
        self.entry_skill.delete(0, "end")
        self._carregar_skills_usuario()
        self._render_skills()

    def _carregar_skills_usuario(self):
        self._skills_usuario = [r["skill"] for r in buscar_skills_usuario()]

    def _render_skills(self):
        for w in self.frame_skills.winfo_children():
            w.destroy()

        if not self._skills_usuario:
            ctk.CTkLabel(
                self.frame_skills,
                text="Nenhuma habilidade cadastrada.\nDigite acima e pressione +",
                font=ctk.CTkFont("Segoe UI", 10),
                text_color=COR_SUBTEXTO, justify="center"
            ).pack(padx=10, pady=12)
            return

        linhas = [self._skills_usuario[i:i + 3]
                  for i in range(0, len(self._skills_usuario), 3)]
        for linha in linhas:
            rf = ctk.CTkFrame(self.frame_skills, fg_color="transparent")
            rf.pack(fill="x", padx=6, pady=2)
            for sk in linha:
                tag = ctk.CTkFrame(rf, fg_color=COR_AZUL, corner_radius=5)
                tag.pack(side="left", padx=(0, 4))
                ctk.CTkLabel(tag, text=sk,
                             font=ctk.CTkFont("Segoe UI", 10, "bold"),
                             text_color="#ffffff"
                             ).pack(side="left", padx=(8, 2), pady=4)
                ctk.CTkButton(tag, text="×", width=18, height=18,
                              fg_color="transparent", hover_color="#1d4ed8",
                              text_color="#ffffff",
                              font=ctk.CTkFont("Segoe UI", 11, "bold"),
                              command=lambda s=sk: self._del_skill(s)
                              ).pack(side="left", padx=(0, 4))

        ctk.CTkFrame(self.frame_skills, fg_color="transparent", height=4).pack()

    def _del_skill(self, skill: str):
        deletar_skill(skill)
        self._carregar_skills_usuario()
        self._render_skills()

    # ── Stats ──────────────────────────────────────────────────────────

    def _atualizar_stats(self):
        for w in self.frame_stats.winfo_children():
            w.destroy()
        self._render_stats()

    def _render_stats(self):
        s = stats_gerais()
        dados = [
            ("Total Vagas",     str(s["total_vagas"]),      COR_CIANO),
            ("Aplicações",      str(s["aplicadas"]),        COR_VERDE_H),
            ("Entrevistas",     str(s["chamados"]),         "#c084fc"),
            ("Taxa Entrevista", f"{s['taxa_entrevista']}%", COR_AMARELO),
        ]
        for i, (lbl, val, cor) in enumerate(dados):
            r, c = divmod(i, 2)
            card = ctk.CTkFrame(self.frame_stats, fg_color=COR_CARD,
                                corner_radius=8, border_color=COR_BORDA,
                                border_width=1)
            card.grid(row=r, column=c, padx=3, pady=3, sticky="ew")
            ctk.CTkLabel(card, text=val,
                         font=ctk.CTkFont("Segoe UI", 22, "bold"),
                         text_color=cor).pack(pady=(10, 0))
            ctk.CTkLabel(card, text=lbl,
                         font=ctk.CTkFont("Segoe UI", 9),
                         text_color=COR_TEXTO).pack(pady=(0, 10))

    # ── Helpers UI ─────────────────────────────────────────────────────

    def _set_status_msg(self, msg: str):
        self.lbl_status.configure(text=msg)

    def _set_indicator(self, estado: str):
        cfg = {
            "idle":     ("●", "Aguardando",   COR_SUBTEXTO, COR_CARD),
            "buscando": ("◉", "Buscando...",  "#f59e0b",    "#292015"),
            "ok":       ("●", "Concluído",    COR_VERDE_H,  "#0f2a1a"),
            "erro":     ("●", "Erro na busca",COR_VERMELHO_H, "#2a0f0f"),
        }.get(estado, ("●", "Aguardando", COR_SUBTEXTO, COR_CARD))

        dot_txt, lbl_txt, cor, bg = cfg
        self.dot_status.configure(text=dot_txt, text_color=cor)
        self.lbl_indicator.configure(text=lbl_txt, text_color=cor)
        self.dot_status.master.configure(fg_color=bg)

    def _sep(self, parent, row: int):
        ctk.CTkFrame(parent, fg_color=COR_BORDA, height=1
                     ).grid(row=row, column=0, sticky="ew", padx=12, pady=2)

    def _lbl(self, parent, texto: str, row: int):
        ctk.CTkLabel(parent, text=texto,
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=COR_TEXTO, anchor="w"
                     ).grid(row=row, column=0, padx=14, pady=(4, 1), sticky="ew")

    def _bloco_titulo(self, parent, texto: str, row: int, subtexto: str = ""):
        ctk.CTkLabel(parent,
                     text=f"▌  {texto}",
                     font=ctk.CTkFont("Segoe UI", 9, "bold"),
                     text_color=COR_CIANO,
                     fg_color=COR_SECAO,
                     corner_radius=4,
                     anchor="w"
                     ).grid(row=row, column=0, padx=10, pady=(4, 2), sticky="ew")

    def _det_secao(self, parent, texto: str):
        ctk.CTkLabel(parent, text=texto,
                     font=ctk.CTkFont("Segoe UI", 11, "bold"),
                     text_color=COR_TEXTO
                     ).pack(anchor="w", padx=16, pady=(10, 4))
