import tkinter as tk
from tkinter import messagebox, ttk, scrolledtext, simpledialog
import sqlite3
import hashlib
import datetime

# --- Configuração do Banco de Dados ---
DB_NAME = "kondu_interactive_v2.db" # Novo nome
CURRENT_USER_INFO = None 

# --- Conexão com Banco de Dados ---
conn_global = sqlite3.connect(DB_NAME)
cursor_global = conn_global.cursor()

def criar_tabelas():
    # Tabela usuarios com todos os campos
    cursor_global.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_completo TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL,
            telefone TEXT,
            endereco_completo TEXT,
            cep TEXT,
            nome_condominio TEXT NOT NULL,
            apartamento TEXT NOT NULL,
            perfil TEXT NOT NULL, 
            data_cadastro TEXT NOT NULL,
            bitkondu_saldo INTEGER DEFAULT 0
        )
    """)
    # Outras tabelas (mural_avisos, bitkondu_transacoes, financeiro, manutencoes, reservas_ambientes)
    
    cursor_global.execute("""
        CREATE TABLE IF NOT EXISTS mural_avisos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_usuario_autor INTEGER NOT NULL,
            mensagem TEXT NOT NULL,
            data_postagem TEXT NOT NULL,
            FOREIGN KEY(id_usuario_autor) REFERENCES usuarios(id) ON DELETE CASCADE
        )
    """)
    cursor_global.execute("""
        CREATE TABLE IF NOT EXISTS bitkondu_transacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_usuario INTEGER NOT NULL,
            acao TEXT NOT NULL, 
            quantidade INTEGER NOT NULL, 
            datahora TEXT NOT NULL,
            FOREIGN KEY(id_usuario) REFERENCES usuarios(id) ON DELETE CASCADE
        )
    """)
    cursor_global.execute("""
        CREATE TABLE IF NOT EXISTS financeiro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_usuario_responsavel INTEGER, 
            id_usuario_destino INTEGER, 
            id_usuario_pagador INTEGER, -- NOVO: Para morador registrar pagamento
            tipo_registro TEXT NOT NULL DEFAULT 'COBRANCA', -- COBRANCA, PAGAMENTO_COMPROVANTE
            descricao TEXT NOT NULL,
            valor REAL NOT NULL,
            data_lancamento TEXT NOT NULL,
            data_vencimento TEXT,
            data_pagamento_comprovante TEXT, -- NOVO
            pago INTEGER DEFAULT 0, 
            status_comprovante TEXT, -- APROVADO, PENDENTE, REJEITADO (para pagamentos)
            FOREIGN KEY(id_usuario_responsavel) REFERENCES usuarios(id) ON DELETE SET NULL,
            FOREIGN KEY(id_usuario_destino) REFERENCES usuarios(id) ON DELETE CASCADE,
            FOREIGN KEY(id_usuario_pagador) REFERENCES usuarios(id) ON DELETE SET NULL
        )
    """)
    cursor_global.execute("""
        CREATE TABLE IF NOT EXISTS manutencoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_usuario_registro INTEGER, 
            tipo TEXT NOT NULL, 
            descricao TEXT NOT NULL,
            local TEXT NOT NULL,
            data_agendada TEXT,
            data_conclusao TEXT,
            status TEXT DEFAULT 'Pendente', 
            FOREIGN KEY(id_usuario_registro) REFERENCES usuarios(id) ON DELETE SET NULL
        )
    """)
    cursor_global.execute("""
        CREATE TABLE IF NOT EXISTS reservas_ambientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_usuario_reserva INTEGER NOT NULL,
            ambiente TEXT NOT NULL,
            data_reserva TEXT NOT NULL,
            horario_inicio TEXT NOT NULL,
            horario_fim TEXT,
            status TEXT DEFAULT 'Confirmada', 
            FOREIGN KEY(id_usuario_reserva) REFERENCES usuarios(id) ON DELETE CASCADE
        )
    """)
    conn_global.commit()

# --- Funções de Hash ---
def hash_senha(senha): return hashlib.sha256(senha.encode()).hexdigest()
def verificar_senha(h, s): return h == hash_senha(s)

# --- Funções BitKondu  ---
def registrar_transacao_bitkondu(id_usuario, acao, quantidade, parent_window=None):
    global CURRENT_USER_INFO, app_instance
    datahora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cursor_global.execute(
            "INSERT INTO bitkondu_transacoes (id_usuario, acao, quantidade, datahora) VALUES (?, ?, ?, ?)",
            (id_usuario, acao, quantidade, datahora)
        )
        cursor_global.execute(
            "UPDATE usuarios SET bitkondu_saldo = bitkondu_saldo + ? WHERE id = ?",
            (quantidade, id_usuario)
        )
        conn_global.commit()
        print(f"BitKondu: {quantidade} BK para usuário ID {id_usuario} por '{acao}'.")
        
        if CURRENT_USER_INFO and CURRENT_USER_INFO['id'] == id_usuario:
            CURRENT_USER_INFO['bitkondu_saldo'] += quantidade
            if app_instance and hasattr(app_instance, 'update_user_info_display_live'):
                app_instance.update_user_info_display_live()
        return True
    except sqlite3.Error as e:
        conn_global.rollback()
        msg = f"Erro ao registrar transação BitKondu: {e}"
        print(msg)
        if parent_window: messagebox.showerror("Erro BitKondu", msg, parent=parent_window)
        return False

# --- Variáveis Globais para Widgets ---
app_instance = None
# Aba Perfil & Mural
text_mural_display = None
entry_novo_aviso = None
listbox_adm_usuarios = None
usuarios_list_data_admin = []
# Aba Financeiro
listbox_financeiro_registros = None # inclui cobranças e pagamentos
financeiro_registros_data = []
combo_financeiro_destino_user_admin = None # Para admin registrar cobrança
entry_financeiro_descricao_admin = None
entry_financeiro_valor_admin = None
entry_financeiro_data_venc_admin = None
entry_financeiro_descricao_morador = None # Para morador registrar pagamento
entry_financeiro_valor_morador = None
# Aba Manutenção
listbox_manutencoes_registradas = None
manutencoes_data = []
# Aba Reservas
listbox_reservas_registradas = None
reservas_data = []
# Aba Gerenciar BitKondu
combo_bitkondu_manage_user_admin = None # Admin seleciona usuário
entry_bitkondu_manage_quantidade = None
entry_bitkondu_manage_acao = None
listbox_bitkondu_historico_geral = None # Para admin ver todas as transações

# --- Funções do Mural de Avisos  ---
def carregar_avisos_mural():
    
    if text_mural_display and text_mural_display.winfo_exists():
        text_mural_display.config(state=tk.NORMAL)
        text_mural_display.delete(1.0, tk.END)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.mensagem, m.data_postagem, u.nome_completo
            FROM mural_avisos m JOIN usuarios u ON m.id_usuario_autor = u.id
            ORDER BY m.data_postagem DESC LIMIT 10
        """)
        avisos = cursor.fetchall()
        conn.close()
        if avisos:
            for aviso_data in avisos:
                try:
                    dt_obj = datetime.datetime.strptime(aviso_data[1], "%Y-%m-%d %H:%M:%S")
                    data_formatada = dt_obj.strftime("%d/%m %H:%M")
                except ValueError: data_formatada = aviso_data[1]
                text_mural_display.insert(tk.END, f"[{data_formatada}] {aviso_data[2]}: {aviso_data[0]}\n---\n")
        else:
            text_mural_display.insert(tk.END, "Nenhum aviso no mural.\n")
        text_mural_display.config(state=tk.DISABLED)

def postar_novo_aviso(parent_window):
    
    global CURRENT_USER_INFO, entry_novo_aviso
    if not (CURRENT_USER_INFO and CURRENT_USER_INFO['perfil'] == 'admin' and entry_novo_aviso): return
    mensagem = entry_novo_aviso.get("1.0", tk.END).strip()
    if not mensagem: messagebox.showwarning("Atenção", "Digite uma mensagem.", parent=parent_window); return
    data_atual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cursor_global.execute("INSERT INTO mural_avisos (id_usuario_autor, mensagem, data_postagem) VALUES (?, ?, ?)",
                       (CURRENT_USER_INFO['id'], mensagem, data_atual))
        conn_global.commit()
        entry_novo_aviso.delete("1.0", tk.END); carregar_avisos_mural()
    except sqlite3.Error as e: conn_global.rollback(); messagebox.showerror("Erro DB", f"Postar aviso falhou: {e}", parent=parent_window)

def excluir_ultimo_aviso(parent_window):
    
    if not (CURRENT_USER_INFO and CURRENT_USER_INFO['perfil'] == 'admin'): return
    try:
        cursor_global.execute("SELECT id FROM mural_avisos ORDER BY data_postagem DESC LIMIT 1")
        aviso_recente = cursor_global.fetchone()
        if aviso_recente:
            if messagebox.askyesno("Confirmação", "Excluir o aviso mais recente?", parent=parent_window):
                cursor_global.execute("DELETE FROM mural_avisos WHERE id = ?", (aviso_recente[0],))
                conn_global.commit(); carregar_avisos_mural()
        else: messagebox.showinfo("Info", "Nenhum aviso para excluir.", parent=parent_window)
    except sqlite3.Error as e: conn_global.rollback(); messagebox.showerror("Erro DB", f"Excluir aviso falhou: {e}", parent=parent_window)


# --- Classe da Aplicação Principal ---
class KonduApp:
    def __init__(self, root_tk):
        global app_instance
        app_instance = self
        self.root = root_tk
        self.root.withdraw() 
        self.current_toplevel = None
        self.notebook = None

        self.entries_meu_perfil_all = {} # Unificado para todos os campos editáveis do perfil
        self.label_bitkondu_saldo_widget = None 
        self.admin_edit_user_entries = {} 
        self.current_editing_user_id_admin = None

        self.mostrar_tela_login()

    def _setup_toplevel_window(self, title, geometry):
        
        if self.current_toplevel and self.current_toplevel.winfo_exists():
            self.current_toplevel.destroy()
        self.current_toplevel = tk.Toplevel(self.root)
        self.current_toplevel.title(title)
        self.current_toplevel.protocol("WM_DELETE_WINDOW", self.on_close_main_window)
        self.current_toplevel.update_idletasks()
        try: w_req, h_req = map(int, geometry.split('x'))
        except ValueError: w_req, h_req = 800, 600 
        sw, sh = self.current_toplevel.winfo_screenwidth(), self.current_toplevel.winfo_screenheight()
        x, y = (sw - w_req) // 2, (sh - h_req) // 2
        self.current_toplevel.geometry(f"{w_req}x{h_req}+{x}+{y}")
        return self.current_toplevel
    
    def on_close_main_window(self):
        
        if messagebox.askokcancel("Sair", "Deseja realmente sair do Kondu?"): self.root.quit()

    def mostrar_tela_login(self):
        
        login_window = self._setup_toplevel_window("Kondu Interativo - Login", "380x220")
        frame_login = ttk.Frame(login_window, padding="20"); frame_login.pack(expand=True, fill=tk.BOTH)
        ttk.Label(frame_login, text="Email:").grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)
        self.entry_email_login = ttk.Entry(frame_login, width=30); self.entry_email_login.grid(row=0, column=1, pady=5, padx=5, sticky=tk.EW); self.entry_email_login.focus()
        ttk.Label(frame_login, text="Senha:").grid(row=1, column=0, sticky=tk.W, pady=5, padx=5)
        self.entry_senha_login = ttk.Entry(frame_login, width=30, show="*"); self.entry_senha_login.grid(row=1, column=1, pady=5, padx=5, sticky=tk.EW)
        frame_login.columnconfigure(1, weight=1)
        btn_entrar = ttk.Button(frame_login, text="Entrar", command=self.processar_login); btn_entrar.grid(row=2, column=0, columnspan=2, pady=(15,5))
        login_window.bind('<Return>', lambda event: btn_entrar.invoke())
        btn_ir_cadastro = ttk.Button(frame_login, text="Não tem conta? Cadastre-se", command=self.mostrar_tela_cadastro); btn_ir_cadastro.grid(row=3, column=0, columnspan=2, pady=5)
        login_window.lift()

    def processar_login(self):
        
        global CURRENT_USER_INFO
        email = self.entry_email_login.get().strip(); senha = self.entry_senha_login.get()
        if not email or not senha: messagebox.showerror("Erro", "Email e senha são obrigatórios.", parent=self.current_toplevel); return
        conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
        cursor.execute("""SELECT id, nome_completo, email, senha_hash, perfil, telefone, 
                                 endereco_completo, cep, nome_condominio, apartamento, bitkondu_saldo 
                          FROM usuarios WHERE email = ?""", (email,))
        usuario_db = cursor.fetchone(); conn.close()
        if usuario_db and verificar_senha(usuario_db[3], senha):
            CURRENT_USER_INFO = dict(zip(["id", "nome_completo", "email", "senha_hash_db", "perfil", "telefone", "endereco_completo", "cep", "nome_condominio", "apartamento", "bitkondu_saldo"], usuario_db))
            del CURRENT_USER_INFO["senha_hash_db"] # Não precisa manter o hash em memória
            self.mostrar_tela_principal_com_abas()
        else: messagebox.showerror("Erro", "Email ou senha incorretos.", parent=self.current_toplevel)


    def mostrar_tela_cadastro(self):
        
        cadastro_toplevel = tk.Toplevel(self.current_toplevel); cadastro_toplevel.title("Kondu - Cadastro Novo Usuário"); cadastro_toplevel.geometry("450x450"); cadastro_toplevel.grab_set(); cadastro_toplevel.focus_set()
        frame_form = ttk.Frame(cadastro_toplevel, padding="15"); frame_form.pack(expand=True, fill=tk.BOTH)
        campos_info = [("Nome Completo*", "nome_completo"), ("Email*", "email"), ("Senha*", "senha"), ("Confirmar Senha*", "confirmar_senha"), ("Telefone", "telefone"), ("Endereço Completo", "endereco_completo"), ("CEP", "cep"), ("Nome do Condomínio*", "nome_condominio"), ("Apartamento*", "apartamento")]
        self.entries_cadastro_novo = {}
        for i, (label_text, key) in enumerate(campos_info):
            ttk.Label(frame_form, text=label_text).grid(row=i, column=0, sticky=tk.W, pady=3, padx=5)
            entry = ttk.Entry(frame_form, width=35); 
            if "senha" in key: entry.config(show="*")
            entry.grid(row=i, column=1, pady=3, padx=5, sticky=tk.EW); self.entries_cadastro_novo[key] = entry
        frame_form.columnconfigure(1, weight=1)
        btn_cadastrar_user = ttk.Button(frame_form, text="Cadastrar", command=lambda: self.processar_cadastro_novo_usuario(cadastro_toplevel)); btn_cadastrar_user.grid(row=len(campos_info), column=0, columnspan=2, pady=15)
        ttk.Button(frame_form, text="Voltar para Login", command=cadastro_toplevel.destroy).grid(row=len(campos_info)+1, column=0, columnspan=2)
        cadastro_toplevel.update_idletasks(); w, h = cadastro_toplevel.winfo_width(), cadastro_toplevel.winfo_height(); sw, sh = cadastro_toplevel.winfo_screenwidth(), cadastro_toplevel.winfo_screenheight(); x, y = (sw - w) // 2, (sh - h) // 2; cadastro_toplevel.geometry(f"{w}x{h}+{x}+{y}")


    def processar_cadastro_novo_usuario(self, janela_atual):
        
        dados = {key: entry.get().strip() for key, entry in self.entries_cadastro_novo.items()}
        obrigatorios = ["nome_completo", "email", "senha", "confirmar_senha", "nome_condominio", "apartamento"]
        for campo in obrigatorios:
            if not dados[campo]: messagebox.showerror("Erro", f"Campo '{campo.replace('_', ' ').title()}' obrigatório.", parent=janela_atual); return
        if dados["senha"] != dados["confirmar_senha"]: messagebox.showerror("Erro", "As senhas não coincidem.", parent=janela_atual); return
        if len(dados["senha"]) < 4: messagebox.showwarning("Atenção", "Senha: mínimo 4 caracteres.", parent=janela_atual); return
        senha_hashed = hash_senha(dados["senha"]); data_atual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn_check = sqlite3.connect(DB_NAME); cursor_check = conn_check.cursor(); cursor_check.execute("SELECT COUNT(*) FROM usuarios"); is_first_user = (cursor_check.fetchone()[0] == 0); conn_check.close()
        perfil_novo_usuario = 'admin' if is_first_user else 'morador'; bitkondu_inicial = 1
        try:
            cursor_global.execute("""
                INSERT INTO usuarios (nome_completo, email, senha_hash, telefone, endereco_completo, cep, nome_condominio, apartamento, perfil, data_cadastro, bitkondu_saldo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (dados["nome_completo"], dados["email"], senha_hashed, dados["telefone"], dados["endereco_completo"], dados["cep"], dados["nome_condominio"], dados["apartamento"], perfil_novo_usuario, data_atual, 0))
            id_novo_usuario = cursor_global.lastrowid; conn_global.commit()
            registrar_transacao_bitkondu(id_novo_usuario, "Cadastro Inicial", bitkondu_inicial, janela_atual)
            messagebox.showinfo("Sucesso", f"Usuário '{dados['nome_completo']}' cadastrado como '{perfil_novo_usuario}' com {bitkondu_inicial} BitKondu!\nFaça o login.", parent=janela_atual)
            janela_atual.destroy()
        except sqlite3.IntegrityError: conn_global.rollback(); messagebox.showerror("Erro", "Email já cadastrado.", parent=janela_atual)
        except sqlite3.Error as e: conn_global.rollback(); messagebox.showerror("Erro DB", f"Erro ao cadastrar: {e}", parent=janela_atual)


    def mostrar_tela_principal_com_abas(self):
        # ... (Declarações de widgets globais) ...
        global text_mural_display, entry_novo_aviso, listbox_adm_usuarios 
        global listbox_financeiro_registros, combo_financeiro_destino_user_admin, entry_financeiro_descricao_admin, entry_financeiro_valor_admin, entry_financeiro_data_venc_admin
        global entry_financeiro_descricao_morador, entry_financeiro_valor_morador 
        global listbox_manutencoes_registradas, listbox_reservas_registradas
        global combo_bitkondu_manage_user_admin, entry_bitkondu_manage_quantidade, entry_bitkondu_manage_acao, listbox_bitkondu_historico_geral

        main_window = self._setup_toplevel_window(f"Kondu ({CURRENT_USER_INFO['nome_completo']})", "950x750") # Maior
        self.notebook = ttk.Notebook(main_window)
        self.notebook.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        self._criar_aba_perfil_mural(self.notebook)
        self._criar_aba_financeiro(self.notebook)
        self._criar_aba_manutencoes(self.notebook)
        self._criar_aba_reservas(self.notebook)
        self._criar_aba_gerenciar_bitkondu(self.notebook) 

        ttk.Button(main_window, text="Logout", command=self.logout).pack(pady=10, side=tk.BOTTOM)
        main_window.lift()
        
        # Carregar dados para comboboxes e listas após UI estar pronta
        if CURRENT_USER_INFO['perfil'] == 'admin':
            self.carregar_usuarios_para_combobox_geral(combo_financeiro_destino_user_admin, "Selecione Morador Destino")
            self.carregar_usuarios_para_combobox_geral(combo_bitkondu_manage_user_admin, "Selecione Usuário")
        self.atualizar_lista_financeiro_display()
        self.atualizar_lista_manutencoes_display()
        self.atualizar_lista_reservas_display()
        self.atualizar_lista_bitkondu_historico_geral_display() # Para a nova aba de gerenciamento


    def _criar_aba_perfil_mural(self, notebook_pai):
        global text_mural_display, entry_novo_aviso, listbox_adm_usuarios
        aba_perfil = ttk.Frame(notebook_pai); notebook_pai.add(aba_perfil, text="Meu Perfil & Mural")
        main_frame_aba = ttk.Frame(aba_perfil, padding=10); main_frame_aba.pack(fill=tk.BOTH, expand=True)
        main_frame_aba.columnconfigure(0, weight=1) 
        if CURRENT_USER_INFO['perfil'] == 'admin': main_frame_aba.columnconfigure(1, weight=1) 

        col_esquerda_frame = ttk.Frame(main_frame_aba); col_esquerda_frame.grid(row=0, column=0, sticky="nsew", padx=(0,10))
        frame_dados_user = ttk.LabelFrame(col_esquerda_frame, text="Meus Dados", padding=10); frame_dados_user.pack(fill=tk.X, pady=(0,10))
        
        self.entries_meu_perfil_all.clear()
        # Campos do perfil tornam-se todos editáveis (exceto email e perfil)
        campos_perfil_editaveis = [
            ("Nome Completo:", "nome_completo"), ("Telefone:", "telefone"),
            ("Endereço Completo:", "endereco_completo"), ("CEP:", "cep"),
            ("Nome do Condomínio:", "nome_condominio"), ("Apartamento:", "apartamento")
        ]
        row_idx = 0
        for label_text, key in campos_perfil_editaveis:
            ttk.Label(frame_dados_user, text=label_text).grid(row=row_idx, column=0, sticky=tk.W, pady=2)
            entry = ttk.Entry(frame_dados_user, width=40)
            entry.insert(0, str(CURRENT_USER_INFO.get(key, '')))
            entry.grid(row=row_idx, column=1, sticky=tk.EW, pady=2)
            self.entries_meu_perfil_all[key] = entry
            row_idx += 1
        
        # Email e Perfil (não editáveis pelo usuário)
        ttk.Label(frame_dados_user, text="Email:").grid(row=row_idx, column=0, sticky=tk.W, pady=2)
        ttk.Label(frame_dados_user, text=CURRENT_USER_INFO['email']).grid(row=row_idx, column=1, sticky=tk.W, pady=2)
        row_idx += 1
        ttk.Label(frame_dados_user, text="Perfil:").grid(row=row_idx, column=0, sticky=tk.W, pady=2)
        ttk.Label(frame_dados_user, text=CURRENT_USER_INFO['perfil'].title()).grid(row=row_idx, column=1, sticky=tk.W, pady=2)
        row_idx += 1
        
        ttk.Label(frame_dados_user, text="BitKondus:").grid(row=row_idx, column=0, sticky=tk.W, pady=2)
        self.label_bitkondu_saldo_widget = ttk.Label(frame_dados_user, text=str(CURRENT_USER_INFO['bitkondu_saldo']))
        self.label_bitkondu_saldo_widget.grid(row=row_idx, column=1, sticky=tk.W, pady=2)
        row_idx += 1
        frame_dados_user.columnconfigure(1, weight=1)

        btn_salvar_meus_dados = ttk.Button(frame_dados_user, text="Salvar Minhas Alterações", command=self.salvar_meus_dados_perfil_completo)
        btn_salvar_meus_dados.grid(row=row_idx, column=0, columnspan=2, pady=10); row_idx +=1
        btn_alterar_minha_senha = ttk.Button(frame_dados_user, text="Alterar Minha Senha", command=self.alterar_minha_senha_dialog)
        btn_alterar_minha_senha.grid(row=row_idx, column=0, columnspan=2, pady=5)

        # Mural (código igual)
        frame_mural = ttk.LabelFrame(col_esquerda_frame, text="Mural de Avisos", padding=10); frame_mural.pack(fill=tk.BOTH, expand=True, pady=(10,0))
        text_mural_display = scrolledtext.ScrolledText(frame_mural, wrap=tk.WORD, height=8, state=tk.DISABLED); text_mural_display.pack(fill=tk.BOTH, expand=True, pady=(0,5))
        carregar_avisos_mural()
        if CURRENT_USER_INFO['perfil'] == 'admin':
            frame_postar_aviso = ttk.Frame(frame_mural); frame_postar_aviso.pack(fill=tk.X, pady=5)
            entry_novo_aviso = tk.Text(frame_postar_aviso, height=3, width=30); entry_novo_aviso.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5))
            ttk.Button(frame_postar_aviso, text="Postar Aviso", command=lambda: postar_novo_aviso(self.current_toplevel)).pack(side=tk.LEFT)
            ttk.Button(frame_mural, text="Excluir Último Aviso", command=lambda: excluir_ultimo_aviso(self.current_toplevel)).pack(pady=3, side=tk.BOTTOM)

        # Gestão de Usuários (Admin) - código igual
        if CURRENT_USER_INFO['perfil'] == 'admin':
            col_direita_frame = ttk.LabelFrame(main_frame_aba, text="Gerenciar Usuários (Admin)", padding=10); col_direita_frame.grid(row=0, column=1, sticky="nsew", rowspan=2) 
            btn_admin_add_user = ttk.Button(col_direita_frame, text="Adicionar Novo Usuário", command=self.admin_mostrar_janela_add_usuario_pelo_admin); btn_admin_add_user.pack(pady=5, fill=tk.X)
            listbox_adm_usuarios = tk.Listbox(col_direita_frame, height=10); listbox_adm_usuarios.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=5, padx=(0,5))
            scroll_adm = ttk.Scrollbar(col_direita_frame, orient="vertical", command=listbox_adm_usuarios.yview); scroll_adm.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
            listbox_adm_usuarios.config(yscrollcommand=scroll_adm.set)
            botoes_adm_frame = ttk.Frame(col_direita_frame); botoes_adm_frame.pack(fill=tk.X, pady=5)
            ttk.Button(botoes_adm_frame, text="Editar Sel.", command=self.admin_editar_usuario_selecionado).pack(side=tk.LEFT, expand=True, padx=2)
            ttk.Button(botoes_adm_frame, text="Excluir Sel.", command=self.admin_excluir_usuario_selecionado).pack(side=tk.LEFT, expand=True, padx=2)
            self.admin_atualizar_lista_usuarios_display()


    def update_user_info_display_live(self):
        if not CURRENT_USER_INFO: return
        # Atualiza todos os campos editáveis na aba "Meu Perfil"
        for key, entry_widget in self.entries_meu_perfil_all.items():
            if entry_widget and entry_widget.winfo_exists():
                entry_widget.delete(0, tk.END)
                entry_widget.insert(0, str(CURRENT_USER_INFO.get(key, '')))
        
        if self.label_bitkondu_saldo_widget and self.label_bitkondu_saldo_widget.winfo_exists():
            self.label_bitkondu_saldo_widget.config(text=str(CURRENT_USER_INFO.get('bitkondu_saldo', '0')))
        
        # Atualiza também o saldo na aba de Gerenciar BitKondu
        if hasattr(self, 'label_meu_saldo_bitkondu_gerenciar') and \
           self.label_meu_saldo_bitkondu_gerenciar and self.label_meu_saldo_bitkondu_gerenciar.winfo_exists():
            self.label_meu_saldo_bitkondu_gerenciar.config(text=f"Meu Saldo Atual: {CURRENT_USER_INFO['bitkondu_saldo']} BitKondus")


    def salvar_meus_dados_perfil_completo(self):
        if not CURRENT_USER_INFO or not self.entries_meu_perfil_all: return
        
        novos_dados_perfil = {}
        campos_obrigatorios_perfil = ["nome_completo", "nome_condominio", "apartamento"] # Email não é editável aqui
        
        for key, entry_widget in self.entries_meu_perfil_all.items():
            valor = entry_widget.get().strip()
            if key in campos_obrigatorios_perfil and not valor:
                messagebox.showwarning("Atenção", f"O campo '{key.replace('_',' ').title()}' não pode ser vazio.", parent=self.current_toplevel)
                return
            novos_dados_perfil[key] = valor
        
        # Não permite alterar email ou perfil aqui
        # novos_dados_perfil['email'] = CURRENT_USER_INFO['email']
        # novos_dados_perfil['perfil'] = CURRENT_USER_INFO['perfil']

        try:
            update_fields = []
            update_values = []
            for key, value in novos_dados_perfil.items():
                update_fields.append(f"{key} = ?")
                update_values.append(value)
            
            if not update_fields: # Nada para atualizar
                messagebox.showinfo("Info", "Nenhum dado alterado.", parent=self.current_toplevel)
                return

            set_clause = ", ".join(update_fields)
            update_values.append(CURRENT_USER_INFO['id'])
            
            cursor_global.execute(f"UPDATE usuarios SET {set_clause} WHERE id = ?", tuple(update_values))
            conn_global.commit()
            
            for key, value in novos_dados_perfil.items():
                CURRENT_USER_INFO[key] = value # Atualiza o dict global
            
            messagebox.showinfo("Sucesso", "Seus dados de perfil foram atualizados!", parent=self.current_toplevel)
            self.update_user_info_display_live() 
            # Atualiza o título da janela principal se o nome mudou
            if 'nome_completo' in novos_dados_perfil and self.current_toplevel:
                 self.current_toplevel.title(f"Kondu ({CURRENT_USER_INFO['nome_completo']})")
        except sqlite3.Error as e:
            conn_global.rollback()
            messagebox.showerror("Erro DB", f"Não foi possível atualizar seus dados: {e}", parent=self.current_toplevel)


    def alterar_minha_senha_dialog(self):
        
        if not CURRENT_USER_INFO: return; parent_win = self.current_toplevel
        senha_atual_digitada = simpledialog.askstring("Alterar Senha", "Senha ATUAL:", show='*', parent=parent_win)
        if not senha_atual_digitada: return
        cursor_global.execute("SELECT senha_hash FROM usuarios WHERE id = ?", (CURRENT_USER_INFO['id'],))
        user_db_data = cursor_global.fetchone()
        if not user_db_data or not verificar_senha(user_db_data[0], senha_atual_digitada): messagebox.showerror("Erro", "Senha atual incorreta.", parent=parent_win); return
        nova_senha = simpledialog.askstring("Alterar Senha", "NOVA senha:", show='*', parent=parent_win)
        if not nova_senha: return
        if len(nova_senha) < 4: messagebox.showwarning("Atenção", "Nova senha: mínimo 4 caracteres.", parent=parent_win); return
        confirm_nova_senha = simpledialog.askstring("Alterar Senha", "CONFIRME nova senha:", show='*', parent=parent_win)
        if nova_senha != confirm_nova_senha: messagebox.showerror("Erro", "Novas senhas não coincidem.", parent=parent_win); return
        nova_senha_hash = hash_senha(nova_senha)
        try:
            cursor_global.execute("UPDATE usuarios SET senha_hash = ? WHERE id = ?", (nova_senha_hash, CURRENT_USER_INFO['id']))
            conn_global.commit(); messagebox.showinfo("Sucesso", "Senha alterada!", parent=parent_win)
        except sqlite3.Error as e: conn_global.rollback(); messagebox.showerror("Erro DB", f"Falha ao alterar senha: {e}", parent=parent_win)

    # --- Métodos de Admin para Gerenciar Usuários (na Aba Perfil/Mural) ---
    # (admin_mostrar_janela_add_usuario_pelo_admin, admin_processar_add_usuario_pelo_admin, 
    #  admin_atualizar_lista_usuarios_display, admin_excluir_usuario_selecionado,
    #  admin_editar_usuario_selecionado, admin_processar_salvar_edicao_de_usuario,
    #  admin_alterar_senha_outro_usuario_dialog 
    #  já incluem os campos de endereço/cep e lidam com BitKondu no cadastro)
    def admin_mostrar_janela_add_usuario_pelo_admin(self):
        
        add_user_win = tk.Toplevel(self.current_toplevel); add_user_win.title("Admin - Adicionar Usuário"); add_user_win.geometry("450x480"); add_user_win.grab_set(); add_user_win.focus_set()
        frame_form = ttk.Frame(add_user_win, padding="15"); frame_form.pack(expand=True, fill=tk.BOTH)
        campos_info_admin_add = [("Nome Completo*", "nome_completo"), ("Email*", "email"), ("Senha Inicial*", "senha_inicial"), ("Telefone", "telefone"), ("Endereço Completo", "endereco_completo"), ("CEP", "cep"), ("Nome do Condomínio*", "nome_condominio"), ("Apartamento*", "apartamento"), ("Perfil*", "perfil")]
        self.entries_admin_add_user = {}
        for i, (label_text, key) in enumerate(campos_info_admin_add):
            ttk.Label(frame_form, text=label_text).grid(row=i, column=0, sticky=tk.W, pady=3, padx=5)
            if key == "perfil": entry = ttk.Combobox(frame_form, values=['morador', 'admin'], state="readonly", width=33); entry.set('morador')
            else: entry = ttk.Entry(frame_form, width=35); 
            if "senha" in key: entry.config(show="*")
            entry.grid(row=i, column=1, pady=3, padx=5, sticky=tk.EW); self.entries_admin_add_user[key] = entry
        frame_form.columnconfigure(1, weight=1)
        btn_final_add = ttk.Button(frame_form, text="Adicionar Usuário", command=lambda: self.admin_processar_add_usuario_pelo_admin(add_user_win)); btn_final_add.grid(row=len(campos_info_admin_add), column=0, columnspan=2, pady=15)
        ttk.Button(frame_form, text="Cancelar", command=add_user_win.destroy).grid(row=len(campos_info_admin_add)+1, column=0, columnspan=2)
        add_user_win.update_idletasks(); w, h = add_user_win.winfo_width(), add_user_win.winfo_height(); sw, sh = add_user_win.winfo_screenwidth(), add_user_win.winfo_screenheight(); x, y = (sw - w) // 2, (sh - h) // 2; add_user_win.geometry(f"{w}x{h}+{x}+{y}")

    def admin_processar_add_usuario_pelo_admin(self, parent_window):
        
        dados = {key: entry.get().strip() for key, entry in self.entries_admin_add_user.items()}
        obrigatorios = ["nome_completo", "email", "senha_inicial", "nome_condominio", "apartamento", "perfil"]
        for campo in obrigatorios:
            if not dados[campo]: messagebox.showerror("Erro", f"Campo '{campo.replace('_', ' ').title()}' obrigatório.", parent=parent_window); return
        if dados["perfil"] not in ['admin', 'morador']: messagebox.showerror("Erro", "Perfil inválido.", parent=parent_window); return
        if len(dados["senha_inicial"]) < 4: messagebox.showwarning("Atenção", "Senha inicial: mínimo 4 caracteres.", parent=parent_window); return
        senha_hashed = hash_senha(dados["senha_inicial"]); data_atual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"); bitkondu_admin_add = 1
        try:
            cursor_global.execute("""INSERT INTO usuarios (nome_completo, email, senha_hash, telefone, endereco_completo, cep, nome_condominio, apartamento, perfil, data_cadastro, bitkondu_saldo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (dados["nome_completo"], dados["email"], senha_hashed, dados["telefone"], dados["endereco_completo"], dados["cep"], dados["nome_condominio"], dados["apartamento"], dados["perfil"], data_atual, 0))
            id_novo_usuario = cursor_global.lastrowid; conn_global.commit()
            registrar_transacao_bitkondu(id_novo_usuario, "Cadastro (via Admin)", bitkondu_admin_add, parent_window)
            messagebox.showinfo("Sucesso", "Usuário adicionado!", parent=parent_window); parent_window.destroy(); self.admin_atualizar_lista_usuarios_display()
        except sqlite3.IntegrityError: conn_global.rollback(); messagebox.showerror("Erro", "Email já cadastrado.", parent=parent_window)
        except sqlite3.Error as e: conn_global.rollback(); messagebox.showerror("Erro DB", f"Falha ao adicionar: {e}", parent=parent_window)

    def admin_atualizar_lista_usuarios_display(self):
        
        global listbox_adm_usuarios, usuarios_list_data_admin
        if not (listbox_adm_usuarios and listbox_adm_usuarios.winfo_exists()): return
        usuarios_list_data_admin.clear(); listbox_adm_usuarios.delete(0, tk.END)
        cursor_global.execute("""SELECT id, nome_completo, email, perfil, apartamento, nome_condominio, telefone, endereco_completo, cep FROM usuarios ORDER BY nome_completo ASC""")
        for u_data in cursor_global.fetchall():
            display_text = f"{u_data[1]} (Apt {u_data[4]}, {u_data[5]}) - {u_data[2]} [{u_data[3]}]"
            usuarios_list_data_admin.append(dict(zip(["id", "nome_completo", "email", "perfil", "apartamento", "nome_condominio", "telefone", "endereco_completo", "cep"], u_data)))
            listbox_adm_usuarios.insert(tk.END, display_text)

    def admin_excluir_usuario_selecionado(self):
        
        global listbox_adm_usuarios, usuarios_list_data_admin
        sel_idx_tuple = listbox_adm_usuarios.curselection()
        if not sel_idx_tuple: messagebox.showwarning("Atenção", "Selecione um usuário.", parent=self.current_toplevel); return
        user_data_dict = usuarios_list_data_admin[sel_idx_tuple[0]]; user_id_to_delete = user_data_dict['id']
        if user_id_to_delete == CURRENT_USER_INFO['id']: messagebox.showerror("Erro", "Não pode se auto-excluir.", parent=self.current_toplevel); return
        if user_data_dict['perfil'] == 'admin':
            cursor_global.execute("SELECT COUNT(*) FROM usuarios WHERE perfil='admin'"); num_admins = cursor_global.fetchone()[0]
            if num_admins <= 1: messagebox.showerror("Erro", "Não pode excluir o único admin.", parent=self.current_toplevel); return
        if messagebox.askyesno("Confirmação", f"Excluir '{user_data_dict['nome_completo']}'?", parent=self.current_toplevel):
            try:
                cursor_global.execute("DELETE FROM usuarios WHERE id = ?", (user_id_to_delete,)); conn_global.commit()
                messagebox.showinfo("Sucesso", "Usuário excluído.", parent=self.current_toplevel); self.admin_atualizar_lista_usuarios_display(); carregar_avisos_mural()
            except sqlite3.Error as e: conn_global.rollback(); messagebox.showerror("Erro DB", f"Falha ao excluir: {e}", parent=self.current_toplevel)

    def admin_editar_usuario_selecionado(self):
        
        global listbox_adm_usuarios, usuarios_list_data_admin
        sel_idx_tuple = listbox_adm_usuarios.curselection();
        if not sel_idx_tuple: messagebox.showwarning("Atenção", "Selecione um usuário.", parent=self.current_toplevel); return
        user_data_to_edit_from_list = usuarios_list_data_admin[sel_idx_tuple[0]]; self.current_editing_user_id_admin = user_data_to_edit_from_list['id']
        edit_win = tk.Toplevel(self.current_toplevel); edit_win.title(f"Admin - Editar: {user_data_to_edit_from_list['nome_completo']}"); edit_win.geometry("450x450"); edit_win.grab_set(); edit_win.focus_set()
        frame_edit = ttk.Frame(edit_win, padding="15"); frame_edit.pack(expand=True, fill=tk.BOTH)
        self.admin_edit_user_entries.clear()
        campos_para_edicao_admin = [("Nome*", "nome_completo", user_data_to_edit_from_list['nome_completo']), ("Email*", "email", user_data_to_edit_from_list['email']), ("Telefone", "telefone", user_data_to_edit_from_list.get('telefone', '')), ("Endereço", "endereco_completo", user_data_to_edit_from_list.get('endereco_completo', '')), ("CEP", "cep", user_data_to_edit_from_list.get('cep', '')), ("Condomínio*", "nome_condominio", user_data_to_edit_from_list['nome_condominio']), ("Apartamento*", "apartamento", user_data_to_edit_from_list['apartamento']), ("Perfil*", "perfil", user_data_to_edit_from_list['perfil'])]
        row_idx = 0
        for label_text, key, current_value in campos_para_edicao_admin:
            ttk.Label(frame_edit, text=label_text).grid(row=row_idx, column=0, sticky=tk.W, pady=3, padx=5)
            if key == "perfil": entry_widget = ttk.Combobox(frame_edit, values=['morador', 'admin'], state="readonly", width=33); entry_widget.set(current_value)
            else: entry_widget = ttk.Entry(frame_edit, width=35); entry_widget.insert(0, current_value or "")
            entry_widget.grid(row=row_idx, column=1, pady=3, padx=5, sticky=tk.EW); self.admin_edit_user_entries[key] = entry_widget; row_idx += 1
        frame_edit.columnconfigure(1, weight=1)
        btn_admin_alt_senha_outro = ttk.Button(frame_edit, text="Admin: Alterar Senha Deste Usuário", command=lambda: self.admin_alterar_senha_outro_usuario_dialog(self.current_editing_user_id_admin, edit_win)); btn_admin_alt_senha_outro.grid(row=row_idx, column=0, columnspan=2, pady=(10,5)); row_idx += 1
        btn_salvar_edicao = ttk.Button(frame_edit, text="Salvar Alterações", command=lambda: self.admin_processar_salvar_edicao_de_usuario(edit_win)); btn_salvar_edicao.grid(row=row_idx, column=0, columnspan=2, pady=8); row_idx += 1
        ttk.Button(frame_edit, text="Cancelar", command=edit_win.destroy).grid(row=row_idx, column=0, columnspan=2)
        edit_win.update_idletasks(); w, h = edit_win.winfo_width(), edit_win.winfo_height(); sw, sh = edit_win.winfo_screenwidth(), edit_win.winfo_screenheight(); x, y = (sw - w) // 2, (sh - h) // 2; edit_win.geometry(f"{w}x{h}+{x}+{y}")

    def admin_processar_salvar_edicao_de_usuario(self, parent_window):
        
        if not self.current_editing_user_id_admin: return
        dados_editados = {key: entry.get().strip() for key, entry in self.admin_edit_user_entries.items()}
        obrigatorios_edicao = ["nome_completo", "email", "nome_condominio", "apartamento", "perfil"]
        for campo in obrigatorios_edicao:
            if not dados_editados[campo]: messagebox.showerror("Erro", f"Campo '{campo.replace('_',' ').title()}' obrigatório.", parent=parent_window); return
        if dados_editados["perfil"] == 'morador': 
            cursor_global.execute("SELECT perfil FROM usuarios WHERE id=?", (self.current_editing_user_id_admin,)); perfil_atual_db_editado = cursor_global.fetchone()
            if perfil_atual_db_editado and perfil_atual_db_editado[0] == 'admin':
                cursor_global.execute("SELECT COUNT(*) FROM usuarios WHERE perfil='admin'"); num_admins = cursor_global.fetchone()[0]
                if num_admins <= 1: messagebox.showerror("Erro", "Não pode rebaixar o único admin.", parent=parent_window); return
        try:
            cursor_global.execute("""UPDATE usuarios SET nome_completo=?, email=?, telefone=?, endereco_completo=?, cep=?, nome_condominio=?, apartamento=?, perfil=? WHERE id=?""", (dados_editados["nome_completo"], dados_editados["email"], dados_editados["telefone"], dados_editados["endereco_completo"], dados_editados["cep"], dados_editados["nome_condominio"], dados_editados["apartamento"], dados_editados["perfil"], self.current_editing_user_id_admin)); conn_global.commit()
            messagebox.showinfo("Sucesso", "Dados atualizados!", parent=parent_window); parent_window.destroy(); self.admin_atualizar_lista_usuarios_display()
            if self.current_editing_user_id_admin == CURRENT_USER_INFO['id']:
                for key_edited, val_edited in dados_editados.items():
                    if key_edited in CURRENT_USER_INFO: CURRENT_USER_INFO[key_edited] = val_edited
                self.update_user_info_display_live()
                if CURRENT_USER_INFO['perfil'] != dados_editados['perfil']: self.logout(show_login_after=False); self.mostrar_tela_principal_com_abas()
        except sqlite3.IntegrityError: conn_global.rollback(); messagebox.showerror("Erro", "Email já em uso.", parent=parent_window)
        except sqlite3.Error as e: conn_global.rollback(); messagebox.showerror("Erro DB", f"Falha ao salvar: {e}", parent=parent_window)
        finally: self.current_editing_user_id_admin = None; self.admin_edit_user_entries.clear()

    def admin_alterar_senha_outro_usuario_dialog(self, id_usuario_alvo, parent_window):
        
        nova_senha_admin_input = simpledialog.askstring("Admin - Alterar Senha", f"Nova senha para ID {id_usuario_alvo}:", show='*', parent=parent_window)
        if not nova_senha_admin_input: return
        if len(nova_senha_admin_input) < 4: messagebox.showwarning("Atenção", "Nova senha: mínimo 4 caracteres.", parent=parent_window); return
        confirm_nova_senha_admin = simpledialog.askstring("Admin - Alterar Senha", "Confirme NOVA senha:", show='*', parent=parent_window)
        if nova_senha_admin_input != confirm_nova_senha_admin: messagebox.showerror("Erro", "Novas senhas não coincidem.", parent=parent_window); return
        nova_senha_hash_admin = hash_senha(nova_senha_admin_input)
        try:
            cursor_global.execute("UPDATE usuarios SET senha_hash = ? WHERE id = ?", (nova_senha_hash_admin, id_usuario_alvo)); conn_global.commit()
            messagebox.showinfo("Sucesso", f"Senha do usuário ID {id_usuario_alvo} alterada!", parent=parent_window)
        except sqlite3.Error as e: conn_global.rollback(); messagebox.showerror("Erro DB", f"Falha ao alterar senha: {e}", parent=parent_window)


    # --- Métodos da Aba Financeiro ---
    def _criar_aba_financeiro(self, notebook_pai):
        global listbox_financeiro_registros, combo_financeiro_destino_user_admin, entry_financeiro_descricao_admin
        global entry_financeiro_valor_admin, entry_financeiro_data_venc_admin
        global entry_financeiro_descricao_morador, entry_financeiro_valor_morador

        aba_financeiro = ttk.Frame(notebook_pai); notebook_pai.add(aba_financeiro, text="Financeiro")
        main_frame_fin = ttk.Frame(aba_financeiro, padding=10); main_frame_fin.pack(fill=tk.BOTH, expand=True)

        if CURRENT_USER_INFO['perfil'] == 'admin':
            frame_registrar_cob_admin = ttk.LabelFrame(main_frame_fin, text="Admin: Registrar Nova Cobrança", padding=10)
            frame_registrar_cob_admin.pack(fill=tk.X, pady=5)
            ttk.Label(frame_registrar_cob_admin, text="Destino:").grid(row=0, column=0, padx=5, pady=3, sticky=tk.W)
            combo_financeiro_destino_user_admin = ttk.Combobox(frame_registrar_cob_admin, width=30, state="readonly")
            combo_financeiro_destino_user_admin.grid(row=0, column=1, padx=5, pady=3, sticky=tk.EW)
            ttk.Label(frame_registrar_cob_admin, text="Descrição:").grid(row=1, column=0, padx=5, pady=3, sticky=tk.W)
            entry_financeiro_descricao_admin = ttk.Entry(frame_registrar_cob_admin, width=40)
            entry_financeiro_descricao_admin.grid(row=1, column=1, padx=5, pady=3, sticky=tk.EW)
            ttk.Label(frame_registrar_cob_admin, text="Valor (R$):").grid(row=2, column=0, padx=5, pady=3, sticky=tk.W)
            entry_financeiro_valor_admin = ttk.Entry(frame_registrar_cob_admin, width=15)
            entry_financeiro_valor_admin.grid(row=2, column=1, padx=5, pady=3, sticky=tk.W)
            ttk.Label(frame_registrar_cob_admin, text="Vencimento (DD/MM/AAAA):").grid(row=3, column=0, padx=5, pady=3, sticky=tk.W)
            entry_financeiro_data_venc_admin = ttk.Entry(frame_registrar_cob_admin, width=15)
            entry_financeiro_data_venc_admin.grid(row=3, column=1, padx=5, pady=3, sticky=tk.W)
            frame_registrar_cob_admin.columnconfigure(1, weight=1)
            btn_registrar_cob_admin = ttk.Button(frame_registrar_cob_admin, text="Registrar Cobrança", command=self.registrar_cobranca_financeira_admin)
            btn_registrar_cob_admin.grid(row=4, column=0, columnspan=2, pady=10)
        
        # Seção para Morador registrar comprovante de pagamento
        frame_registrar_pag_morador = ttk.LabelFrame(main_frame_fin, text="Registrar Comprovante de Pagamento", padding=10)
        frame_registrar_pag_morador.pack(fill=tk.X, pady=5)
        ttk.Label(frame_registrar_pag_morador, text="Descrição do Pagamento:").grid(row=0, column=0, padx=5, pady=3, sticky=tk.W)
        entry_financeiro_descricao_morador = ttk.Entry(frame_registrar_pag_morador, width=40)
        entry_financeiro_descricao_morador.grid(row=0, column=1, padx=5, pady=3, sticky=tk.EW)
        ttk.Label(frame_registrar_pag_morador, text="Valor Pago (R$):").grid(row=1, column=0, padx=5, pady=3, sticky=tk.W)
        entry_financeiro_valor_morador = ttk.Entry(frame_registrar_pag_morador, width=15)
        entry_financeiro_valor_morador.grid(row=1, column=1, padx=5, pady=3, sticky=tk.W)
        frame_registrar_pag_morador.columnconfigure(1, weight=1)
        btn_registrar_pag_morador = ttk.Button(frame_registrar_pag_morador, text="Registrar Pagamento", command=self.registrar_pagamento_financeiro_morador)
        btn_registrar_pag_morador.grid(row=2, column=0, columnspan=2, pady=10)


        frame_lista_registros_fin = ttk.LabelFrame(main_frame_fin, text="Histórico Financeiro", padding=10)
        frame_lista_registros_fin.pack(fill=tk.BOTH, expand=True, pady=5)
        listbox_financeiro_registros = tk.Listbox(frame_lista_registros_fin, height=10)
        listbox_financeiro_registros.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))
        scroll_cob = ttk.Scrollbar(frame_lista_registros_fin, orient="vertical", command=listbox_financeiro_registros.yview)
        scroll_cob.pack(side=tk.RIGHT, fill=tk.Y)
        listbox_financeiro_registros.config(yscrollcommand=scroll_cob.set)
        
        if CURRENT_USER_INFO['perfil'] == 'admin':
            botoes_lista_fin_frame = ttk.Frame(frame_lista_registros_fin)
            botoes_lista_fin_frame.pack(fill=tk.X, pady=5, side=tk.BOTTOM)
            ttk.Button(botoes_lista_fin_frame, text="Gerenciar Status", command=self.admin_gerenciar_status_financeiro).pack(side=tk.LEFT, padx=2) # Para aprovar/rejeitar pagamentos ou marcar cobrança como paga
            ttk.Button(botoes_lista_fin_frame, text="Excluir Registro", command=self.excluir_registro_financeiro_selecionado).pack(side=tk.LEFT, padx=2)

    def carregar_usuarios_para_combobox_geral(self, combobox_widget, default_text="Selecione"):
        if not (combobox_widget and combobox_widget.winfo_exists()): return
        
        cursor_global.execute("SELECT id, nome_completo, apartamento FROM usuarios ORDER BY nome_completo")
        usuarios = cursor_global.fetchall()
        
        # Guardar o mapeamento no próprio widget ou na instância da app se precisar acessar o ID depois
        if not hasattr(self, 'combobox_user_maps'): self.combobox_user_maps = {}
        current_map_key = id(combobox_widget) # Usa o ID do widget como chave única
        self.combobox_user_maps[current_map_key] = {}
        
        display_list = [default_text]
        if usuarios:
            for u_id, nome, apt in usuarios:
                display = f"{nome} (Apt: {apt})"
                display_list.append(display)
                self.combobox_user_maps[current_map_key][display] = u_id # Mapeia display string para ID
            combobox_widget['values'] = display_list
            combobox_widget.set(default_text)
        else:
            combobox_widget['values'] = ["Nenhum usuário cadastrado"]
            combobox_widget.set("Nenhum usuário cadastrado")

    def registrar_cobranca_financeira_admin(self):
        global CURRENT_USER_INFO, combo_financeiro_destino_user_admin, entry_financeiro_descricao_admin
        global entry_financeiro_valor_admin, entry_financeiro_data_venc_admin

        if CURRENT_USER_INFO['perfil'] != 'admin': messagebox.showerror("Acesso Negado", "Apenas admins.", parent=self.current_toplevel); return

        selected_display_user = combo_financeiro_destino_user_admin.get()
        map_key = id(combo_financeiro_destino_user_admin)
        id_usuario_destino = self.combobox_user_maps[map_key].get(selected_display_user)

        if not id_usuario_destino: messagebox.showwarning("Atenção", "Selecione um usuário de destino.", parent=self.current_toplevel); return
        
        descricao = entry_financeiro_descricao_admin.get().strip()
        valor_str = entry_financeiro_valor_admin.get().strip().replace(",",".")
        data_venc = entry_financeiro_data_venc_admin.get().strip()

        if not all([descricao, valor_str]): messagebox.showwarning("Atenção", "Descrição e Valor obrigatórios.", parent=self.current_toplevel); return
        try: valor = float(valor_str); assert valor > 0
        except: messagebox.showwarning("Atenção", "Valor inválido.", parent=self.current_toplevel); return
        if data_venc and not (len(data_venc) == 10 and data_venc[2] == '/' and data_venc[5] == '/'): messagebox.showwarning("Atenção", "Data venc. DD/MM/AAAA.", parent=self.current_toplevel); return

        data_lancamento = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            cursor_global.execute("""
                INSERT INTO financeiro (id_usuario_responsavel, id_usuario_destino, tipo_registro, descricao, valor, data_lancamento, data_vencimento, pago)
                VALUES (?, ?, 'COBRANCA', ?, ?, ?, ?, 0)
            """, (CURRENT_USER_INFO['id'], id_usuario_destino, descricao, valor, data_lancamento, data_venc or None))
            conn_global.commit()
            registrar_transacao_bitkondu(CURRENT_USER_INFO['id'], "Registro de Cobrança", 1, self.current_toplevel)
            messagebox.showinfo("Sucesso", "Cobrança registrada!", parent=self.current_toplevel)
            entry_financeiro_descricao_admin.delete(0, tk.END); entry_financeiro_valor_admin.delete(0, tk.END); entry_financeiro_data_venc_admin.delete(0, tk.END)
            self.atualizar_lista_financeiro_display()
        except sqlite3.Error as e: conn_global.rollback(); messagebox.showerror("Erro DB", f"Falha: {e}", parent=self.current_toplevel)

    def registrar_pagamento_financeiro_morador(self):
        global CURRENT_USER_INFO, entry_financeiro_descricao_morador, entry_financeiro_valor_morador
        
        descricao = entry_financeiro_descricao_morador.get().strip()
        valor_str = entry_financeiro_valor_morador.get().strip().replace(",",".")

        if not all([descricao, valor_str]): messagebox.showwarning("Atenção", "Descrição e Valor do pagamento são obrigatórios.", parent=self.current_toplevel); return
        try: valor = float(valor_str); assert valor > 0
        except: messagebox.showwarning("Atenção", "Valor do pagamento inválido.", parent=self.current_toplevel); return

        data_pagamento = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            cursor_global.execute("""
                INSERT INTO financeiro (id_usuario_pagador, tipo_registro, descricao, valor, data_lancamento, data_pagamento_comprovante, status_comprovante)
                VALUES (?, 'PAGAMENTO_COMPROVANTE', ?, ?, ?, ?, 'PENDENTE')
            """, (CURRENT_USER_INFO['id'], descricao, valor, data_pagamento, data_pagamento)) # data_lancamento = data_pagamento_comprovante
            conn_global.commit()
            # Morador ganha BitKondu por registrar comprovante
            registrar_transacao_bitkondu(CURRENT_USER_INFO['id'], "Registro Comprovante Pag.", 1, self.current_toplevel)
            messagebox.showinfo("Sucesso", "Comprovante de pagamento registrado! Aguardando aprovação do admin.", parent=self.current_toplevel)
            entry_financeiro_descricao_morador.delete(0, tk.END); entry_financeiro_valor_morador.delete(0, tk.END)
            self.atualizar_lista_financeiro_display()
        except sqlite3.Error as e: conn_global.rollback(); messagebox.showerror("Erro DB", f"Falha ao registrar pagamento: {e}", parent=self.current_toplevel)

    def atualizar_lista_financeiro_display(self):
        global listbox_financeiro_registros, financeiro_registros_data
        if not (listbox_financeiro_registros and listbox_financeiro_registros.winfo_exists()): return

        listbox_financeiro_registros.delete(0, tk.END); financeiro_registros_data.clear()
        
        # Admin vê tudo, morador vê suas cobranças e seus pagamentos
        query = """
            SELECT f.id, f.tipo_registro, f.descricao, f.valor, f.data_vencimento, f.data_pagamento_comprovante, 
                   f.pago, f.status_comprovante, u_dest.nome_completo AS nome_destino, u_pag.nome_completo AS nome_pagador
            FROM financeiro f
            LEFT JOIN usuarios u_dest ON f.id_usuario_destino = u_dest.id
            LEFT JOIN usuarios u_pag ON f.id_usuario_pagador = u_pag.id
        """
        params = []
        if CURRENT_USER_INFO['perfil'] == 'morador':
            query += " WHERE f.id_usuario_destino = ? OR f.id_usuario_pagador = ?"
            params.extend([CURRENT_USER_INFO['id'], CURRENT_USER_INFO['id']])
        query += " ORDER BY f.data_lancamento DESC"
        
        cursor_global.execute(query, params)
        for row in cursor_global.fetchall():
            reg_id, tipo, desc, val, data_venc, data_pag_comp, pago_cob, status_comp, nome_dest, nome_pag = row
            
            display_text = f"ID:{reg_id} [{tipo}] {desc} - R${val:.2f} - "
            if tipo == 'COBRANCA':
                status_str = "PAGO" if pago_cob == 1 else "PENDENTE"
                display_text += f"Para: {nome_dest or 'N/A'} - Venc: {data_venc or 'N/A'} - [{status_str}]"
            elif tipo == 'PAGAMENTO_COMPROVANTE':
                display_text += f"Por: {nome_pag or 'N/A'} - Data: {data_pag_comp.split(' ')[0]} - [{status_comp or 'N/A'}]"
            
            listbox_financeiro_registros.insert(tk.END, display_text)
            financeiro_registros_data.append({'id': reg_id, 'tipo': tipo, 'pago_cobranca': pago_cob, 'status_comprovante': status_comp, 'descricao': desc})

    def admin_gerenciar_status_financeiro(self):
        global listbox_financeiro_registros, financeiro_registros_data
        if CURRENT_USER_INFO['perfil'] != 'admin': return

        sel_idx_tuple = listbox_financeiro_registros.curselection()
        if not sel_idx_tuple: messagebox.showwarning("Atenção", "Selecione um registro.", parent=self.current_toplevel); return
        
        selected_data = financeiro_registros_data[sel_idx_tuple[0]]
        reg_id = selected_data['id']
        tipo_reg = selected_data['tipo']

        if tipo_reg == 'COBRANCA':
            novo_status_pago = 1 if selected_data['pago_cobranca'] == 0 else 0
            status_texto = "PAGA" if novo_status_pago == 1 else "PENDENTE"
            if messagebox.askyesno("Admin", f"Marcar cobrança ID {reg_id} como {status_texto}?", parent=self.current_toplevel):
                try:
                    cursor_global.execute("UPDATE financeiro SET pago = ? WHERE id = ?", (novo_status_pago, reg_id))
                    conn_global.commit(); messagebox.showinfo("Sucesso", "Status da cobrança alterado.", parent=self.current_toplevel)
                    self.atualizar_lista_financeiro_display()
                except sqlite3.Error as e: conn_global.rollback(); messagebox.showerror("Erro DB", f"Falha: {e}", parent=self.current_toplevel)
        
        elif tipo_reg == 'PAGAMENTO_COMPROVANTE':
            novo_status_comp = simpledialog.askstring("Admin", f"Novo status para comprovante ID {reg_id} (APROVADO, REJEITADO, PENDENTE):", parent=self.current_toplevel)
            if novo_status_comp and novo_status_comp.upper() in ['APROVADO', 'REJEITADO', 'PENDENTE']:
                try:
                    cursor_global.execute("UPDATE financeiro SET status_comprovante = ? WHERE id = ?", (novo_status_comp.upper(), reg_id))
                    conn_global.commit(); messagebox.showinfo("Sucesso", "Status do comprovante alterado.", parent=self.current_toplevel)
                    self.atualizar_lista_financeiro_display()
                except sqlite3.Error as e: conn_global.rollback(); messagebox.showerror("Erro DB", f"Falha: {e}", parent=self.current_toplevel)
            elif novo_status_comp: # Se digitou algo, mas inválido
                messagebox.showwarning("Atenção", "Status inválido.", parent=self.current_toplevel)


    def excluir_registro_financeiro_selecionado(self):
        
        global listbox_financeiro_registros, financeiro_registros_data
        if CURRENT_USER_INFO['perfil'] != 'admin': return
        sel_idx_tuple = listbox_financeiro_registros.curselection()
        if not sel_idx_tuple: messagebox.showwarning("Atenção", "Selecione um registro.", parent=self.current_toplevel); return
        reg_id_para_excluir = financeiro_registros_data[sel_idx_tuple[0]]['id']
        desc_reg = financeiro_registros_data[sel_idx_tuple[0]]['descricao']
        if messagebox.askyesno("Confirmação", f"Excluir registro '{desc_reg}' (ID: {reg_id_para_excluir})?", parent=self.current_toplevel):
            try:
                cursor_global.execute("DELETE FROM financeiro WHERE id = ?", (reg_id_para_excluir,)); conn_global.commit()
                messagebox.showinfo("Sucesso", "Registro excluído.", parent=self.current_toplevel); self.atualizar_lista_financeiro_display()
            except sqlite3.Error as e: conn_global.rollback(); messagebox.showerror("Erro DB", f"Falha: {e}", parent=self.current_toplevel)


    # --- Métodos da Aba Manutenção ---
    def _criar_aba_manutencoes(self, notebook_pai):
         
        global listbox_manutencoes_registradas
        aba_manutencoes = ttk.Frame(notebook_pai); notebook_pai.add(aba_manutencoes, text="Manutenções")
        main_frame_man = ttk.Frame(aba_manutencoes, padding=10); main_frame_man.pack(fill=tk.BOTH, expand=True)

        frame_reg_man = ttk.LabelFrame(main_frame_man, text="Registrar/Solicitar Manutenção", padding=10)
        frame_reg_man.pack(fill=tk.X, pady=5)
        ttk.Label(frame_reg_man, text="Tipo:").grid(row=0, column=0, sticky=tk.W)
        self.manut_tipo_var = tk.StringVar(value="Corretiva") # Default para solicitação de morador
        ttk.OptionMenu(frame_reg_man, self.manut_tipo_var, "Corretiva", "Corretiva", "Preventiva").grid(row=0, column=1, sticky=tk.EW)
        ttk.Label(frame_reg_man, text="Descrição:").grid(row=1, column=0, sticky=tk.W)
        self.manut_desc_entry = ttk.Entry(frame_reg_man, width=40); self.manut_desc_entry.grid(row=1, column=1, sticky=tk.EW)
        ttk.Label(frame_reg_man, text="Local:").grid(row=2, column=0, sticky=tk.W)
        self.manut_local_entry = ttk.Entry(frame_reg_man, width=40); self.manut_local_entry.grid(row=2, column=1, sticky=tk.EW)
        if CURRENT_USER_INFO['perfil'] == 'admin': # Admin pode agendar data
            ttk.Label(frame_reg_man, text="Data Agendada (Admin - DD/MM/AAAA):").grid(row=3, column=0, sticky=tk.W)
            self.manut_data_agendada_admin_entry = ttk.Entry(frame_reg_man, width=15); self.manut_data_agendada_admin_entry.grid(row=3, column=1, sticky=tk.W)
        frame_reg_man.columnconfigure(1, weight=1)
        btn_text_manut = "Registrar Manutenção" if CURRENT_USER_INFO['perfil'] == 'admin' else "Solicitar Manutenção"
        ttk.Button(frame_reg_man, text=btn_text_manut, command=self.registrar_ou_solicitar_manutencao).grid(row=4, column=0, columnspan=2, pady=10)

        frame_lista_man = ttk.LabelFrame(main_frame_man, text="Histórico de Manutenções", padding=10); frame_lista_man.pack(fill=tk.BOTH, expand=True, pady=5)
        listbox_manutencoes_registradas = tk.Listbox(frame_lista_man, height=10); listbox_manutencoes_registradas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))
        scroll_man = ttk.Scrollbar(frame_lista_man, orient="vertical", command=listbox_manutencoes_registradas.yview); scroll_man.pack(side=tk.RIGHT, fill=tk.Y)
        listbox_manutencoes_registradas.config(yscrollcommand=scroll_man.set)
        if CURRENT_USER_INFO['perfil'] == 'admin':
            btn_gerenciar_manut = ttk.Button(frame_lista_man, text="Gerenciar Status Manut.", command=self.admin_gerenciar_status_manutencao)
            btn_gerenciar_manut.pack(pady=5, side=tk.BOTTOM)
        self.atualizar_lista_manutencoes_display()


    def registrar_ou_solicitar_manutencao(self):
        tipo = self.manut_tipo_var.get()
        descricao = self.manut_desc_entry.get().strip()
        local = self.manut_local_entry.get().strip()
        data_agendada = None
        if CURRENT_USER_INFO['perfil'] == 'admin' and hasattr(self, 'manut_data_agendada_admin_entry'):
            data_agendada = self.manut_data_agendada_admin_entry.get().strip()

        if not all([tipo, descricao, local]): messagebox.showwarning("Atenção", "Tipo, Descrição e Local obrigatórios.", parent=self.current_toplevel); return
        
        status_inicial = "Solicitada" if CURRENT_USER_INFO['perfil'] == 'morador' else "Pendente" # Admin já registra como pendente para execução
        id_usuario_registro = CURRENT_USER_INFO['id']
        try:
            cursor_global.execute("""
                INSERT INTO manutencoes (id_usuario_registro, tipo, descricao, local, data_agendada, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (id_usuario_registro, tipo, descricao, local, data_agendada or None, status_inicial))
            conn_global.commit()
            acao_bk = "Solicitação de Manutenção" if CURRENT_USER_INFO['perfil'] == 'morador' else "Registro de Manutenção"
            registrar_transacao_bitkondu(id_usuario_registro, acao_bk, 1, self.current_toplevel)
            messagebox.showinfo("Sucesso", f"Manutenção {status_inicial.lower()} com sucesso!", parent=self.current_toplevel)
            self.manut_desc_entry.delete(0, tk.END); self.manut_local_entry.delete(0, tk.END)
            if CURRENT_USER_INFO['perfil'] == 'admin' and hasattr(self, 'manut_data_agendada_admin_entry'): self.manut_data_agendada_admin_entry.delete(0, tk.END)
            self.atualizar_lista_manutencoes_display()
        except sqlite3.Error as e: conn_global.rollback(); messagebox.showerror("Erro DB", f"Falha: {e}", parent=self.current_toplevel)

    def atualizar_lista_manutencoes_display(self):
        
        global listbox_manutencoes_registradas, manutencoes_data
        if not (listbox_manutencoes_registradas and listbox_manutencoes_registradas.winfo_exists()): return
        listbox_manutencoes_registradas.delete(0, tk.END); manutencoes_data.clear()
        # Admin vê todas, morador vê as que ele registrou/solicitou
        query = """ SELECT m.id, m.tipo, m.descricao, m.local, m.data_agendada, m.status, u.nome_completo
                    FROM manutencoes m LEFT JOIN usuarios u ON m.id_usuario_registro = u.id """
        params = []
        if CURRENT_USER_INFO['perfil'] == 'morador':
            query += " WHERE m.id_usuario_registro = ?"
            params.append(CURRENT_USER_INFO['id'])
        query += " ORDER BY m.id DESC"
        cursor_global.execute(query, params)
        for row in cursor_global.fetchall():
            man_id, tipo, desc, local, data_ag, status, nome_reg = row
            display = f"ID:{man_id} [{tipo}] {desc} - Local: {local} - Ag.: {data_ag or 'N/A'} - Status: {status} (Por: {nome_reg or 'Sistema'})"
            listbox_manutencoes_registradas.insert(tk.END, display)
            manutencoes_data.append({'id': man_id, 'status_atual': status})

    def admin_gerenciar_status_manutencao(self):
        global listbox_manutencoes_registradas, manutencoes_data
        if CURRENT_USER_INFO['perfil'] != 'admin': return
        sel_idx_tuple = listbox_manutencoes_registradas.curselection()
        if not sel_idx_tuple: messagebox.showwarning("Atenção", "Selecione uma manutenção.", parent=self.current_toplevel); return
        
        selected_man = manutencoes_data[sel_idx_tuple[0]]
        man_id = selected_man['id']
        
        novos_status_validos = ['Pendente', 'Em Andamento', 'Concluída', 'Cancelada']
        novo_status = simpledialog.askstring("Admin - Status Manutenção", f"Novo status para Manutenção ID {man_id} ({', '.join(novos_status_validos)}):", parent=self.current_toplevel)

        if novo_status and novo_status.strip().title() in novos_status_validos: # .title() para capitalizar
            status_final = novo_status.strip().title()
            data_conclusao_str = None
            if status_final == 'Concluída':
                data_conclusao_str = datetime.datetime.now().strftime("%Y-%m-%d") # Data atual como conclusão
            
            try:
                cursor_global.execute("UPDATE manutencoes SET status = ?, data_conclusao = ? WHERE id = ?", (status_final, data_conclusao_str, man_id))
                conn_global.commit(); messagebox.showinfo("Sucesso", "Status da manutenção atualizado.", parent=self.current_toplevel)
                self.atualizar_lista_manutencoes_display()
            except sqlite3.Error as e: conn_global.rollback(); messagebox.showerror("Erro DB", f"Falha: {e}", parent=self.current_toplevel)
        elif novo_status: # Digitou algo, mas inválido
            messagebox.showwarning("Atenção", "Status inválido.", parent=self.current_toplevel)


    # --- Métodos da Aba Reservas ---
    def _criar_aba_reservas(self, notebook_pai):
       
        global listbox_reservas_registradas
        aba_reservas = ttk.Frame(notebook_pai); notebook_pai.add(aba_reservas, text="Reservas de Ambientes")
        main_frame_res = ttk.Frame(aba_reservas, padding=10); main_frame_res.pack(fill=tk.BOTH, expand=True)
        frame_reg_res = ttk.LabelFrame(main_frame_res, text="Nova Reserva", padding=10); frame_reg_res.pack(fill=tk.X, pady=5)
        ttk.Label(frame_reg_res, text="Ambiente:").grid(row=0, column=0, sticky=tk.W)
        self.reserva_ambiente_entry = ttk.Entry(frame_reg_res, width=30); self.reserva_ambiente_entry.grid(row=0, column=1, sticky=tk.EW)
        ttk.Label(frame_reg_res, text="Data (DD/MM/AAAA):").grid(row=1, column=0, sticky=tk.W)
        self.reserva_data_entry = ttk.Entry(frame_reg_res, width=15); self.reserva_data_entry.grid(row=1, column=1, sticky=tk.W)
        ttk.Label(frame_reg_res, text="Horário Início (HH:MM):").grid(row=2, column=0, sticky=tk.W)
        self.reserva_horario_entry = ttk.Entry(frame_reg_res, width=10); self.reserva_horario_entry.grid(row=2, column=1, sticky=tk.W)
        frame_reg_res.columnconfigure(1, weight=1)
        ttk.Button(frame_reg_res, text="Registrar Reserva", command=self.registrar_reserva).grid(row=3,column=0, columnspan=2, pady=10)
        frame_lista_res = ttk.LabelFrame(main_frame_res, text="Minhas Reservas / Todas (Admin)", padding=10); frame_lista_res.pack(fill=tk.BOTH, expand=True, pady=5)
        listbox_reservas_registradas = tk.Listbox(frame_lista_res, height=10); listbox_reservas_registradas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))
        scroll_res = ttk.Scrollbar(frame_lista_res, orient="vertical", command=listbox_reservas_registradas.yview); scroll_res.pack(side=tk.RIGHT, fill=tk.Y)
        listbox_reservas_registradas.config(yscrollcommand=scroll_res.set)
        if CURRENT_USER_INFO['perfil'] == 'admin': # Admin pode cancelar reservas
             btn_cancelar_reserva_admin = ttk.Button(frame_lista_res, text="Cancelar Reserva Sel. (Admin)", command=self.admin_cancelar_reserva_selecionada)
             btn_cancelar_reserva_admin.pack(pady=5, side=tk.BOTTOM)
        self.atualizar_lista_reservas_display()

    def registrar_reserva(self):
        
        ambiente = self.reserva_ambiente_entry.get().strip(); data_reserva = self.reserva_data_entry.get().strip(); horario_inicio = self.reserva_horario_entry.get().strip()
        if not all([ambiente, data_reserva, horario_inicio]): messagebox.showwarning("Atenção", "Ambiente, Data e Horário obrigatórios.", parent=self.current_toplevel); return
        id_usuario_reserva = CURRENT_USER_INFO['id']
        try:
            cursor_global.execute("""INSERT INTO reservas_ambientes (id_usuario_reserva, ambiente, data_reserva, horario_inicio, status) VALUES (?, ?, ?, ?, 'Confirmada')""", (id_usuario_reserva, ambiente, data_reserva, horario_inicio)); conn_global.commit()
            registrar_transacao_bitkondu(id_usuario_reserva, "Reserva de Ambiente", 1, self.current_toplevel)
            messagebox.showinfo("Sucesso", "Reserva registrada!", parent=self.current_toplevel)
            self.reserva_ambiente_entry.delete(0, tk.END); self.reserva_data_entry.delete(0, tk.END); self.reserva_horario_entry.delete(0, tk.END)
            self.atualizar_lista_reservas_display()
        except sqlite3.Error as e: conn_global.rollback(); messagebox.showerror("Erro DB", f"Falha: {e}", parent=self.current_toplevel)


    def atualizar_lista_reservas_display(self):
       
        global listbox_reservas_registradas, reservas_data
        if not (listbox_reservas_registradas and listbox_reservas_registradas.winfo_exists()): return
        listbox_reservas_registradas.delete(0, tk.END); reservas_data.clear()
        query = """ SELECT r.id, r.ambiente, r.data_reserva, r.horario_inicio, r.status, u.nome_completo FROM reservas_ambientes r JOIN usuarios u ON r.id_usuario_reserva = u.id """
        params = []
        if CURRENT_USER_INFO['perfil'] == 'morador': query += " WHERE r.id_usuario_reserva = ?"; params.append(CURRENT_USER_INFO['id'])
        query += " ORDER BY r.data_reserva DESC, r.horario_inicio ASC"
        cursor_global.execute(query, params)
        for row in cursor_global.fetchall():
            res_id, ambiente, data_res, hor_ini, status, nome_res = row
            display = f"ID:{res_id} [{ambiente}] Data: {data_res} às {hor_ini} - Status: {status} (Por: {nome_res})"
            listbox_reservas_registradas.insert(tk.END, display)
            reservas_data.append({'id': res_id, 'status_atual': status})

    def admin_cancelar_reserva_selecionada(self):
        global listbox_reservas_registradas, reservas_data
        if CURRENT_USER_INFO['perfil'] != 'admin': return
        sel_idx_tuple = listbox_reservas_registradas.curselection()
        if not sel_idx_tuple: messagebox.showwarning("Atenção", "Selecione uma reserva para cancelar.", parent=self.current_toplevel); return
        
        selected_reserva = reservas_data[sel_idx_tuple[0]]
        res_id = selected_reserva['id']

        if selected_reserva['status_atual'] == 'Cancelada':
            messagebox.showinfo("Info", "Esta reserva já está cancelada.", parent=self.current_toplevel)
            return

        if messagebox.askyesno("Admin - Cancelar Reserva", f"Cancelar a reserva ID {res_id}?", parent=self.current_toplevel):
            try:
                cursor_global.execute("UPDATE reservas_ambientes SET status = 'Cancelada' WHERE id = ?", (res_id,))
                conn_global.commit()
                # Opcional: Devolver BitKondu se o cancelamento foi feito pelo admin?
                # Se sim, precisa saber quem fez a reserva original.
                # cursor_global.execute("SELECT id_usuario_reserva FROM reservas_ambientes WHERE id = ?", (res_id,))
                # id_usuario_original = cursor_global.fetchone()
                # if id_usuario_original:
                #     registrar_transacao_bitkondu(id_usuario_original[0], f"Devolução BK Reserva {res_id} Cancelada", -1, self.current_toplevel) # Subtrai o ganho
                messagebox.showinfo("Sucesso", "Reserva cancelada pelo administrador.", parent=self.current_toplevel)
                self.atualizar_lista_reservas_display()
            except sqlite3.Error as e: conn_global.rollback(); messagebox.showerror("Erro DB", f"Falha ao cancelar reserva: {e}", parent=self.current_toplevel)


    # --- Aba Gerenciar BitKondu (NOVA com funcionalidades) ---
    def _criar_aba_gerenciar_bitkondu(self, notebook_pai):
        global combo_bitkondu_manage_user_admin, entry_bitkondu_manage_quantidade, entry_bitkondu_manage_acao
        global listbox_bitkondu_historico_geral

        aba_bk = ttk.Frame(notebook_pai); notebook_pai.add(aba_bk, text="BitKondu")
        main_frame_bk = ttk.Frame(aba_bk, padding=10); main_frame_bk.pack(fill=tk.BOTH, expand=True)

        # Saldo do usuário logado
        self.label_meu_saldo_bitkondu_gerenciar = ttk.Label(main_frame_bk, text=f"Meu Saldo Atual: {CURRENT_USER_INFO['bitkondu_saldo']} BitKondus", font=("Arial", 14))
        self.label_meu_saldo_bitkondu_gerenciar.pack(pady=10)
        
        # Frame para Admin gerenciar BitKondus de outros
        if CURRENT_USER_INFO['perfil'] == 'admin':
            frame_admin_manage_bk = ttk.LabelFrame(main_frame_bk, text="Admin: Gerenciar BitKondus de Usuários", padding=10)
            frame_admin_manage_bk.pack(fill=tk.X, pady=10)
            ttk.Label(frame_admin_manage_bk, text="Usuário:").grid(row=0, column=0, padx=5, pady=3, sticky=tk.W)
            combo_bitkondu_manage_user_admin = ttk.Combobox(frame_admin_manage_bk, width=30, state="readonly")
            combo_bitkondu_manage_user_admin.grid(row=0, column=1, padx=5, pady=3, sticky=tk.EW)
            ttk.Label(frame_admin_manage_bk, text="Quantidade:").grid(row=1, column=0, padx=5, pady=3, sticky=tk.W)
            entry_bitkondu_manage_quantidade = ttk.Entry(frame_admin_manage_bk, width=10)
            entry_bitkondu_manage_quantidade.grid(row=1, column=1, padx=5, pady=3, sticky=tk.W)
            ttk.Label(frame_admin_manage_bk, text="Ação/Motivo:").grid(row=2, column=0, padx=5, pady=3, sticky=tk.W)
            entry_bitkondu_manage_acao = ttk.Entry(frame_admin_manage_bk, width=40)
            entry_bitkondu_manage_acao.grid(row=2, column=1, padx=5, pady=3, sticky=tk.EW)
            frame_admin_manage_bk.columnconfigure(1, weight=1)
            btn_frame_admin_bk = ttk.Frame(frame_admin_manage_bk)
            btn_frame_admin_bk.grid(row=3, column=0, columnspan=2, pady=10)
            ttk.Button(btn_frame_admin_bk, text="Adicionar BK", command=lambda: self.admin_operar_bitkondu_outro_usuario(adicionar=True)).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame_admin_bk, text="Subtrair BK", command=lambda: self.admin_operar_bitkondu_outro_usuario(adicionar=False)).pack(side=tk.LEFT, padx=5)

        # Histórico de Transações (Admin vê todas, Morador vê as suas)
        frame_hist_bk = ttk.LabelFrame(main_frame_bk, text="Histórico de Transações BitKondu", padding=10)
        frame_hist_bk.pack(fill=tk.BOTH, expand=True, pady=5)
        listbox_bitkondu_historico_geral = tk.Listbox(frame_hist_bk, height=10) # Reduzir altura se admin tiver a seção acima
        listbox_bitkondu_historico_geral.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))
        scroll_bk_hist = ttk.Scrollbar(frame_hist_bk, orient="vertical", command=listbox_bitkondu_historico_geral.yview)
        scroll_bk_hist.pack(side=tk.RIGHT, fill=tk.Y)
        listbox_bitkondu_historico_geral.config(yscrollcommand=scroll_bk_hist.set)
        self.atualizar_lista_bitkondu_historico_geral_display()


    def admin_operar_bitkondu_outro_usuario(self, adicionar: bool):
        global combo_bitkondu_manage_user_admin, entry_bitkondu_manage_quantidade, entry_bitkondu_manage_acao
        if CURRENT_USER_INFO['perfil'] != 'admin': return

        selected_display_user = combo_bitkondu_manage_user_admin.get()
        map_key = id(combo_bitkondu_manage_user_admin) # Usa o ID do widget como chave
        id_usuario_alvo = self.combobox_user_maps[map_key].get(selected_display_user)

        if not id_usuario_alvo: messagebox.showwarning("Atenção", "Selecione um usuário.", parent=self.current_toplevel); return
        
        try:
            quantidade_str = entry_bitkondu_manage_quantidade.get()
            quantidade = int(quantidade_str)
            if quantidade <= 0: raise ValueError("Quantidade deve ser positiva.")
        except ValueError: messagebox.showwarning("Atenção", "Quantidade inválida (deve ser número inteiro positivo).", parent=self.current_toplevel); return
        
        acao = entry_bitkondu_manage_acao.get().strip()
        if not acao: messagebox.showwarning("Atenção", "Ação/Motivo é obrigatório.", parent=self.current_toplevel); return

        if not adicionar: # Se for subtrair
            cursor_global.execute("SELECT bitkondu_saldo FROM usuarios WHERE id = ?", (id_usuario_alvo,))
            saldo_alvo = cursor_global.fetchone()
            if not saldo_alvo or saldo_alvo[0] < quantidade:
                messagebox.showwarning("Atenção", f"Usuário alvo não tem BitKondus suficientes (Saldo: {saldo_alvo[0] if saldo_alvo else 'N/A'}).", parent=self.current_toplevel)
                return
            quantidade_transacao = -quantidade # Negativo para subtração
        else:
            quantidade_transacao = quantidade

        # registrar_transacao_bitkondu já atualiza o saldo na tabela usuarios
        if registrar_transacao_bitkondu(id_usuario_alvo, f"Admin: {acao}", quantidade_transacao, self.current_toplevel):
            messagebox.showinfo("Sucesso", f"BitKondus {'adicionados' if adicionar else 'subtraídos'} com sucesso para o usuário!", parent=self.current_toplevel)
            entry_bitkondu_manage_quantidade.delete(0, tk.END)
            entry_bitkondu_manage_acao.delete(0, tk.END)
            self.atualizar_lista_bitkondu_historico_geral_display() # Atualiza o histórico
            # Se o admin operou em si mesmo, atualiza o saldo na aba de perfil e nesta aba
            if id_usuario_alvo == CURRENT_USER_INFO['id']:
                self.update_user_info_display_live() 
        # else: Erro já tratado por registrar_transacao_bitkondu


    def atualizar_lista_bitkondu_historico_geral_display(self):
        global listbox_bitkondu_historico_geral
        if not (listbox_bitkondu_historico_geral and listbox_bitkondu_historico_geral.winfo_exists()): return

        listbox_bitkondu_historico_geral.delete(0, tk.END)
        
        query = """ SELECT t.datahora, t.acao, t.quantidade, u.nome_completo 
                    FROM bitkondu_transacoes t JOIN usuarios u ON t.id_usuario = u.id """
        params = []
        if CURRENT_USER_INFO['perfil'] == 'morador': # Morador só vê suas transações
            query += " WHERE t.id_usuario = ?"
            params.append(CURRENT_USER_INFO['id'])
        query += " ORDER BY t.datahora DESC"
        
        conn_read = sqlite3.connect(DB_NAME); cursor_read = conn_read.cursor()
        cursor_read.execute(query, params)
        transacoes = cursor_read.fetchall(); conn_read.close()

        for datahora, acao, qtd, nome_usuario_transacao in transacoes:
            try: dt_obj = datetime.datetime.strptime(datahora, "%Y-%m-%d %H:%M:%S"); data_f = dt_obj.strftime("%d/%m/%Y %H:%M")
            except ValueError: data_f = datahora
            
            user_info_str = f" (Para: {nome_usuario_transacao})" if CURRENT_USER_INFO['perfil'] == 'admin' else ""
            sinal = "+" if qtd > 0 else ""
            listbox_bitkondu_historico_geral.insert(tk.END, f"[{data_f}] {acao}{user_info_str}: {sinal}{qtd} BK")


    def logout(self, show_login_after=True):
        
        global CURRENT_USER_INFO
        CURRENT_USER_INFO = None
        if self.current_toplevel and self.current_toplevel.winfo_exists(): self.current_toplevel.destroy(); self.current_toplevel = None
        if self.notebook and self.notebook.winfo_exists(): self.notebook.destroy(); self.notebook = None
        if show_login_after: self.mostrar_tela_login()

# --- Inicialização ---
if __name__ == "__main__":
    criar_tabelas() 
    root_main_tk = tk.Tk()
    app = KonduApp(root_main_tk)
    try:
        root_main_tk.mainloop()
    finally:
        if conn_global: conn_global.close()
        print("Aplicação Kondu (Interativa) encerrada.")