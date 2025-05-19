import tkinter as tk
from tkinter import messagebox, ttk
import sqlite3
import datetime

# Conexão com banco de dados
conn = sqlite3.connect("condominio.db")
cursor = conn.cursor()


def add_column_if_not_exists(table_name, column_name, column_type_with_constraints):
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [info[1] for info in cursor.fetchall()]
    if column_name not in columns:
        try:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type_with_constraints}")
            conn.commit()
            print(f"Coluna {column_name} adicionada à tabela {table_name}.")
        except sqlite3.Error as e:
            print(f"Erro ao adicionar coluna {column_name} à {table_name}: {e}")

# Criação das tabelas
cursor.execute("""
    CREATE TABLE IF NOT EXISTS moradores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        apartamento TEXT NOT NULL,
        condominio TEXT NOT NULL,
        telefone TEXT,
        email TEXT,
        endereco TEXT,
        bitkondu INTEGER DEFAULT 0
    )
""")
# Aplicar migrações para moradores (para bancos de dados existentes)
add_column_if_not_exists("moradores", "telefone", "TEXT")
add_column_if_not_exists("moradores", "email", "TEXT")
add_column_if_not_exists("moradores", "endereco", "TEXT")
# A coluna bitkondu já é criada com DEFAULT 0, mas para garantir em DBs muito antigos:
add_column_if_not_exists("moradores", "bitkondu", "INTEGER DEFAULT 0")


cursor.execute("""
    CREATE TABLE IF NOT EXISTS mural (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mensagem TEXT NOT NULL
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS manutencao_geral (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo TEXT NOT NULL,
        descricao TEXT NOT NULL,
        data TEXT NOT NULL,
        local TEXT NOT NULL
        /* id_morador será adicionado pela função helper abaixo se não existir */
    )
""")
# Aplicar migração para manutencao_geral
add_column_if_not_exists("manutencao_geral", "id_morador", "INTEGER REFERENCES moradores(id) ON DELETE SET NULL")


cursor.execute("""
    CREATE TABLE IF NOT EXISTS reservas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        id_morador INTEGER NOT NULL,
        ambiente TEXT NOT NULL,
        data TEXT NOT NULL,
        horario TEXT NOT NULL,
        observacoes TEXT,
        FOREIGN KEY(id_morador) REFERENCES moradores(id) ON DELETE CASCADE
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS financeiro (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        id_morador INTEGER NOT NULL,
        valor REAL NOT NULL,
        data TEXT NOT NULL,
        descricao TEXT NOT NULL,
        FOREIGN KEY(id_morador) REFERENCES moradores(id) ON DELETE CASCADE
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS bitkondu (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        id_morador INTEGER NOT NULL,
        acao TEXT NOT NULL,
        quantidade INTEGER NOT NULL, -- Positive for credit, negative for debit
        datahora TEXT NOT NULL,
        FOREIGN KEY(id_morador) REFERENCES moradores(id) ON DELETE CASCADE
    )
""")
conn.commit()

# Listas globais para armazenar IDs de itens de caixa de listagem
moradores_list_data = []
manutencao_ids = []
financeiro_ids = []
reservas_ids = []
bitkondu_transacoes_list_data = []

# Janelas de edição (variáveis globais para os widgets da Toplevel)
edit_morador_window = None
entry_nome_edit, entry_apartamento_edit, entry_condominio_edit = None, None, None
entry_telefone_edit, entry_email_edit, entry_endereco_edit = None, None, None # NOVOS CAMPOS DE EDIÇÃO
current_editing_morador_id = None

edit_manutencao_window = None
tipo_var_geral_edit, entry_descricao_geral_edit, entry_data_geral_edit, entry_local_geral_edit = None, None, None, None
combo_morador_manutencao_edit = None
current_editing_manutencao_id = None

edit_financeiro_window = None
combo_moradores_edit_fin, entry_valor_edit_fin, entry_data_edit_fin, entry_descricao_edit_fin = None, None, None, None
current_editing_financeiro_id = None

edit_reserva_window = None
combo_moradores_reserva_edit, entry_ambiente_edit, entry_data_reserva_edit, entry_horario_edit, entry_observacoes_edit = None, None, None, None, None
current_editing_reserva_id = None

edit_bitkondu_trans_window = None
entry_acao_bitkondu_edit = None
current_editing_bitkondu_trans_id = None


# --- Funções de Moradores ---
def cadastrar_morador():
    nome = entry_nome.get()
    apartamento = entry_apartamento.get()
    condominio = entry_condominio.get()
    telefone = entry_telefone.get() # NOVO
    email = entry_email.get()       # NOVO
    endereco = entry_endereco.get() # NOVO

    if nome and apartamento and condominio: # Campos principais ainda obrigatórios
        try:
            cursor.execute("""INSERT INTO moradores (nome, apartamento, condominio, telefone, email, endereco)
                              VALUES (?, ?, ?, ?, ?, ?)""",
                           (nome, apartamento, condominio, telefone, email, endereco))
            conn.commit()
            messagebox.showinfo("Sucesso", "Morador cadastrado!")
            entry_nome.delete(0, tk.END)
            entry_apartamento.delete(0, tk.END)
            entry_condominio.delete(0, tk.END)
            entry_telefone.delete(0, tk.END) # NOVO
            entry_email.delete(0, tk.END)    # NOVO
            entry_endereco.delete(0, tk.END) # NOVO
            atualizar_lista_moradores()
            carregar_moradores_combobox()
            atualizar_bitkondu()
        except sqlite3.Error as e:
            conn.rollback()
            messagebox.showerror("Erro no Banco de Dados", f"Não foi possível cadastrar o morador: {e}")
    else:
        messagebox.showwarning("Atenção", "Preencha os campos Nome, Apartamento e Condomínio.")

def atualizar_lista_moradores():
    global moradores_list_data
    moradores_list_data = []
    listbox_moradores.delete(0, tk.END)
    # A lista de moradores continuará mostrando apenas nome, apt e condomínio para brevidade.
    # Os detalhes completos estarão na janela de edição.
    cursor.execute("SELECT id, nome, apartamento, condominio FROM moradores ORDER BY nome ASC")
    for morador in cursor.fetchall():
        display_string = f"{morador[1]} - Apt {morador[2]} - {morador[3]}"
        moradores_list_data.append({'id': morador[0], 'nome': morador[1]}) # Armazena apenas id e nome para simplicidade de referência
        listbox_moradores.insert(tk.END, display_string)

def excluir_morador():
    selecionado_idx_tuple = listbox_moradores.curselection()
    if selecionado_idx_tuple:
        selecionado_idx = selecionado_idx_tuple[0]
        morador_info = moradores_list_data[selecionado_idx]
        morador_id = morador_info['id']
        morador_nome = morador_info['nome']
        if messagebox.askyesno("Confirmação", f"Excluir o morador {morador_nome}? Todas as suas reservas, cobranças e transações BitKondu serão removidas (se houver)."):
            try:
                cursor.execute("DELETE FROM moradores WHERE id = ?", (morador_id,))
                conn.commit()
                atualizar_lista_moradores()
                carregar_moradores_combobox()
                atualizar_lista_reservas()
                atualizar_lista_financeiro()
                atualizar_lista_manutencao_geral() # Morador pode ser responsável
                atualizar_bitkondu()
                atualizar_lista_transacoes_bitkondu()
            except sqlite3.Error as e:
                conn.rollback()
                messagebox.showerror("Erro no Banco de Dados", f"Não foi possível excluir o morador: {e}")
    else:
        messagebox.showwarning("Atenção", "Selecione um morador para excluir.")

def abrir_janela_edicao_morador(morador_id):
    global edit_morador_window, entry_nome_edit, entry_apartamento_edit, entry_condominio_edit
    global entry_telefone_edit, entry_email_edit, entry_endereco_edit, current_editing_morador_id

    if edit_morador_window is not None and edit_morador_window.winfo_exists():
        edit_morador_window.destroy()

    current_editing_morador_id = morador_id
    cursor.execute("SELECT nome, apartamento, condominio, telefone, email, endereco FROM moradores WHERE id = ?", (morador_id,))
    morador = cursor.fetchone()
    if not morador:
        messagebox.showerror("Erro", "Morador não encontrado para edição.")
        return

    edit_morador_window = tk.Toplevel(root)
    edit_morador_window.title("Editar Morador")
    edit_morador_window.geometry("400x330") # Ajustar tamanho
    edit_morador_window.grab_set()

    tk.Label(edit_morador_window, text="Nome:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
    entry_nome_edit = tk.Entry(edit_morador_window, width=35)
    entry_nome_edit.grid(row=0, column=1, padx=5, pady=5)
    entry_nome_edit.insert(0, morador[0])

    tk.Label(edit_morador_window, text="Apartamento:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
    entry_apartamento_edit = tk.Entry(edit_morador_window, width=35)
    entry_apartamento_edit.grid(row=1, column=1, padx=5, pady=5)
    entry_apartamento_edit.insert(0, morador[1])

    tk.Label(edit_morador_window, text="Condomínio:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
    entry_condominio_edit = tk.Entry(edit_morador_window, width=35)
    entry_condominio_edit.grid(row=2, column=1, padx=5, pady=5)
    entry_condominio_edit.insert(0, morador[2])

    tk.Label(edit_morador_window, text="Telefone:").grid(row=3, column=0, padx=5, pady=5, sticky="e") # NOVO
    entry_telefone_edit = tk.Entry(edit_morador_window, width=35)
    entry_telefone_edit.grid(row=3, column=1, padx=5, pady=5)
    entry_telefone_edit.insert(0, morador[3] or "")

    tk.Label(edit_morador_window, text="E-mail:").grid(row=4, column=0, padx=5, pady=5, sticky="e") # NOVO
    entry_email_edit = tk.Entry(edit_morador_window, width=35)
    entry_email_edit.grid(row=4, column=1, padx=5, pady=5)
    entry_email_edit.insert(0, morador[4] or "")

    tk.Label(edit_morador_window, text="Endereço:").grid(row=5, column=0, padx=5, pady=5, sticky="e") # NOVO
    entry_endereco_edit = tk.Entry(edit_morador_window, width=35)
    entry_endereco_edit.grid(row=5, column=1, padx=5, pady=5)
    entry_endereco_edit.insert(0, morador[5] or "")


    btn_salvar = tk.Button(edit_morador_window, text="Salvar Alterações", command=salvar_edicao_morador)
    btn_salvar.grid(row=6, column=0, columnspan=2, pady=10)
    btn_cancelar = tk.Button(edit_morador_window, text="Cancelar", command=edit_morador_window.destroy)
    btn_cancelar.grid(row=7, column=0, columnspan=2, pady=5)

def salvar_edicao_morador():
    global current_editing_morador_id
    nome = entry_nome_edit.get()
    apartamento = entry_apartamento_edit.get()
    condominio = entry_condominio_edit.get()
    telefone = entry_telefone_edit.get() # NOVO
    email = entry_email_edit.get()       # NOVO
    endereco = entry_endereco_edit.get() # NOVO


    if nome and apartamento and condominio: # Campos principais obrigatórios
        try:
            cursor.execute("""UPDATE moradores SET nome = ?, apartamento = ?, condominio = ?,
                              telefone = ?, email = ?, endereco = ?
                              WHERE id = ?""",
                           (nome, apartamento, condominio, telefone, email, endereco, current_editing_morador_id))
            conn.commit()
            messagebox.showinfo("Sucesso", "Morador atualizado!", parent=edit_morador_window)
            edit_morador_window.destroy()
            atualizar_lista_moradores() # Nome do morador pode ter mudado
            carregar_moradores_combobox() # Atualiza nomes em todos os comboboxes
            # Atualizar outras listas caso o nome do morador apareça nelas
            atualizar_lista_reservas()
            atualizar_lista_financeiro()
            atualizar_lista_manutencao_geral()
            atualizar_bitkondu() # Para o nome na tabela de saldos
            atualizar_lista_transacoes_bitkondu()
        except sqlite3.Error as e:
            conn.rollback()
            messagebox.showerror("Erro no Banco de Dados", f"Não foi possível atualizar o morador: {e}", parent=edit_morador_window)
    else:
        messagebox.showwarning("Atenção", "Preencha os campos Nome, Apartamento e Condomínio.", parent=edit_morador_window)

def editar_morador_selecionado():
    selecionado_idx_tuple = listbox_moradores.curselection()
    if selecionado_idx_tuple:
        selecionado_idx = selecionado_idx_tuple[0]
        morador_info = moradores_list_data[selecionado_idx] # Aqui temos apenas id e nome
        # Precisamos buscar o ID correto
        cursor.execute("SELECT id FROM moradores WHERE nome = ?", (morador_info['nome'],))
        morador_db_id_tuple = cursor.fetchone()
        if morador_db_id_tuple:
            abrir_janela_edicao_morador(morador_db_id_tuple[0])
        else:
            # Fallback se o nome não for único ou algo der errado (improvável se a lista está correta)
            # Tentar pelo ID armazenado se a lógica de moradores_list_data for ajustada para ter o ID
            # Por enquanto, vamos assumir que o nome na lista é suficiente para encontrar o ID.
            # Se 'moradores_list_data' apenas armazena o ID, então morador_info['id'] já seria o correto.
            # Dado que moradores_list_data armazena {'id': ..., 'nome': ...}, podemos usar morador_info['id']
             abrir_janela_edicao_morador(morador_info['id'])

    else:
        messagebox.showwarning("Atenção", "Selecione um morador para editar.")

# --- Funções de Mural ---
def postar_aviso():
    aviso = entry_aviso.get()
    if aviso:
        try:
            cursor.execute("INSERT INTO mural (mensagem) VALUES (?)", (aviso,))
            conn.commit()
            entry_aviso.delete(0, tk.END)
            atualizar_mural()
        except sqlite3.Error as e:
            conn.rollback()
            messagebox.showerror("Erro no Banco de Dados", f"Não foi possível postar o aviso: {e}")
    else:
        messagebox.showwarning("Atenção", "Digite uma mensagem.")

def atualizar_mural():
    text_mural.config(state=tk.NORMAL)
    text_mural.delete(1.0, tk.END)
    cursor.execute("SELECT mensagem FROM mural ORDER BY id DESC")
    for aviso in cursor.fetchall():
        text_mural.insert(tk.END, f"- {aviso[0]}\n")
    text_mural.config(state=tk.DISABLED)

def excluir_aviso():
    cursor.execute("SELECT id FROM mural ORDER BY id DESC LIMIT 1")
    aviso = cursor.fetchone()
    if aviso:
        if messagebox.askyesno("Confirmação", "Deseja excluir o aviso mais recente?"):
            try:
                cursor.execute("DELETE FROM mural WHERE id = ?", (aviso[0],))
                conn.commit()
                atualizar_mural()
            except sqlite3.Error as e:
                conn.rollback()
                messagebox.showerror("Erro no Banco de Dados", f"Não foi possível excluir o aviso: {e}")
    else:
        messagebox.showinfo("Informação", "Nenhum aviso para excluir.")

# --- Funções de Manutenção Geral ---
def registrar_manutencao_geral():
    tipo = tipo_var_geral.get()
    descricao = entry_descricao_geral.get()
    data = entry_data_geral.get()
    local = entry_local_geral.get()
    morador_nome_resp = combo_morador_manutencao_reg.get()
    id_morador_resp = None

    if morador_nome_resp and morador_nome_resp not in ["Escolha o Morador", "Nenhum morador cadastrado", "Nenhum (Geral)"]:
        cursor.execute("SELECT id FROM moradores WHERE nome = ?", (morador_nome_resp,))
        res = cursor.fetchone()
        if res:
            id_morador_resp = res[0]

    if tipo and descricao and data and local:
        try:
            cursor.execute("INSERT INTO manutencao_geral (tipo, descricao, data, local, id_morador) VALUES (?, ?, ?, ?, ?)",
                           (tipo, descricao, data, local, id_morador_resp))
            conn.commit()
            messagebox.showinfo("Sucesso", "Manutenção registrada!")
            entry_descricao_geral.delete(0, tk.END)
            entry_data_geral.delete(0, tk.END)
            entry_local_geral.delete(0, tk.END)
            combo_morador_manutencao_reg.set("Nenhum (Geral)")
            atualizar_lista_manutencao_geral()
        except sqlite3.Error as e:
            conn.rollback()
            messagebox.showerror("Erro no Banco de Dados", f"Não foi possível registrar a manutenção: {e}")
    else:
        messagebox.showwarning("Atenção", "Preencha todos os campos obrigatórios (Tipo, Descrição, Data, Local).")

def atualizar_lista_manutencao_geral():
    global manutencao_ids
    manutencao_ids = []
    listbox_manutencao_geral.delete(0, tk.END)
    cursor.execute("""
        SELECT mg.id, mg.tipo, mg.descricao, mg.data, mg.local, m.nome
        FROM manutencao_geral mg
        LEFT JOIN moradores m ON mg.id_morador = m.id
        ORDER BY mg.data DESC, mg.id DESC
    """)
    for m_data in cursor.fetchall():
        manutencao_ids.append(m_data[0])
        responsavel_str = f" (Resp: {m_data[5]})" if m_data[5] else ""
        listbox_manutencao_geral.insert(tk.END, f"[{m_data[1]}] {m_data[3]} - {m_data[4]}: {m_data[2]}{responsavel_str}")

def excluir_manutencao_geral():
    global manutencao_ids
    selecionado_idx_tuple = listbox_manutencao_geral.curselection()
    if selecionado_idx_tuple:
        id_manutencao = manutencao_ids[selecionado_idx_tuple[0]]
        texto_selecionado = listbox_manutencao_geral.get(selecionado_idx_tuple[0])
        if messagebox.askyesno("Confirmação", f"Excluir esta manutenção?\n{texto_selecionado}"):
            try:
                cursor.execute("DELETE FROM manutencao_geral WHERE id = ?", (id_manutencao,))
                conn.commit()
                atualizar_lista_manutencao_geral()
            except sqlite3.Error as e:
                conn.rollback()
                messagebox.showerror("Erro no Banco de Dados", f"Não foi possível excluir a manutenção: {e}")
    else:
        messagebox.showwarning("Atenção", "Selecione uma manutenção para excluir.")

def abrir_janela_edicao_manutencao(manutencao_id):
    global edit_manutencao_window, tipo_var_geral_edit, entry_descricao_geral_edit
    global entry_data_geral_edit, entry_local_geral_edit, combo_morador_manutencao_edit, current_editing_manutencao_id

    if edit_manutencao_window is not None and edit_manutencao_window.winfo_exists():
        edit_manutencao_window.destroy()

    current_editing_manutencao_id = manutencao_id
    cursor.execute("""
        SELECT mg.tipo, mg.descricao, mg.data, mg.local, mg.id_morador, m.nome
        FROM manutencao_geral mg
        LEFT JOIN moradores m ON mg.id_morador = m.id
        WHERE mg.id = ?
    """, (manutencao_id,))
    manutencao = cursor.fetchone()

    if not manutencao:
        messagebox.showerror("Erro", "Manutenção não encontrada para edição.")
        return

    edit_manutencao_window = tk.Toplevel(root)
    edit_manutencao_window.title("Editar Manutenção")
    edit_manutencao_window.geometry("450x300")
    edit_manutencao_window.grab_set()

    tk.Label(edit_manutencao_window, text="Tipo:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
    tipo_var_geral_edit = tk.StringVar(value=manutencao[0])
    tk.OptionMenu(edit_manutencao_window, tipo_var_geral_edit, "Preventiva", "Corretiva").grid(row=0, column=1, sticky="w", padx=5, pady=2)

    tk.Label(edit_manutencao_window, text="Descrição:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
    entry_descricao_geral_edit = tk.Entry(edit_manutencao_window, width=40)
    entry_descricao_geral_edit.grid(row=1, column=1, padx=5, pady=5)
    entry_descricao_geral_edit.insert(0, manutencao[1])

    tk.Label(edit_manutencao_window, text="Data (DD/MM/AAAA):").grid(row=2, column=0, padx=5, pady=5, sticky="e")
    entry_data_geral_edit = tk.Entry(edit_manutencao_window, width=40)
    entry_data_geral_edit.grid(row=2, column=1, padx=5, pady=5)
    entry_data_geral_edit.insert(0, manutencao[2])

    tk.Label(edit_manutencao_window, text="Local:").grid(row=3, column=0, padx=5, pady=5, sticky="e")
    entry_local_geral_edit = tk.Entry(edit_manutencao_window, width=40)
    entry_local_geral_edit.grid(row=3, column=1, padx=5, pady=5)
    entry_local_geral_edit.insert(0, manutencao[3])

    tk.Label(edit_manutencao_window, text="Morador Responsável:").grid(row=4, column=0, padx=5, pady=5, sticky="e")
    combo_morador_manutencao_edit = ttk.Combobox(edit_manutencao_window, width=37, state="readonly")
    combo_morador_manutencao_edit.grid(row=4, column=1, padx=5, pady=5, sticky="w")

    cursor.execute("SELECT nome FROM moradores ORDER BY nome ASC")
    nomes_moradores_raw = [m[0] for m in cursor.fetchall()]
    nomes_moradores_options = ["Nenhum (Geral)"]
    if nomes_moradores_raw:
        nomes_moradores_options.extend(nomes_moradores_raw)
    else: # Se não houver moradores cadastrados no sistema
        # Não adiciona "Nenhum morador cadastrado" aqui, pois "Nenhum (Geral)" já cobre
        pass


    combo_morador_manutencao_edit['values'] = nomes_moradores_options

    if manutencao[4] and manutencao[5]: # Se tem id_morador e nome do morador
        combo_morador_manutencao_edit.set(manutencao[5])
    else:
        combo_morador_manutencao_edit.set("Nenhum (Geral)")

    btn_salvar = tk.Button(edit_manutencao_window, text="Salvar Alterações", command=salvar_edicao_manutencao)
    btn_salvar.grid(row=5, column=0, columnspan=2, pady=10)
    btn_cancelar = tk.Button(edit_manutencao_window, text="Cancelar", command=edit_manutencao_window.destroy)
    btn_cancelar.grid(row=6, column=0, columnspan=2, pady=5)

def salvar_edicao_manutencao():
    global current_editing_manutencao_id
    tipo = tipo_var_geral_edit.get()
    descricao = entry_descricao_geral_edit.get()
    data = entry_data_geral_edit.get()
    local = entry_local_geral_edit.get()
    morador_nome_resp = combo_morador_manutencao_edit.get()
    id_morador_resp = None

    if morador_nome_resp and morador_nome_resp not in ["Nenhum (Geral)", "Nenhum morador cadastrado"]: # O segundo é se a lista estiver vazia
        cursor.execute("SELECT id FROM moradores WHERE nome = ?", (morador_nome_resp,))
        res = cursor.fetchone()
        if res:
            id_morador_resp = res[0]
        else:
            # Isso não deveria acontecer se o combobox estiver populado corretamente
            # A menos que o nome do morador tenha sido alterado e a lista do combobox não atualizada (improvável aqui)
            messagebox.showwarning("Atenção", "Morador responsável inválido selecionado.", parent=edit_manutencao_window)
            return

    if tipo and descricao and data and local:
        try:
            cursor.execute("""UPDATE manutencao_geral
                              SET tipo = ?, descricao = ?, data = ?, local = ?, id_morador = ?
                              WHERE id = ?""",
                           (tipo, descricao, data, local, id_morador_resp, current_editing_manutencao_id))
            conn.commit()
            messagebox.showinfo("Sucesso", "Manutenção atualizada!", parent=edit_manutencao_window)
            edit_manutencao_window.destroy()
            atualizar_lista_manutencao_geral()
        except sqlite3.Error as e:
            conn.rollback()
            messagebox.showerror("Erro no Banco de Dados", f"Não foi possível atualizar a manutenção: {e}", parent=edit_manutencao_window)
    else:
        messagebox.showwarning("Atenção", "Preencha todos os campos obrigatórios.", parent=edit_manutencao_window)

def editar_manutencao_selecionada():
    selecionado_idx_tuple = listbox_manutencao_geral.curselection()
    if selecionado_idx_tuple:
        id_manutencao = manutencao_ids[selecionado_idx_tuple[0]]
        abrir_janela_edicao_manutencao(id_manutencao)
    else:
        messagebox.showwarning("Atenção", "Selecione uma manutenção para editar.")

# --- Funções de Financeiro ---
def registrar_cobranca():
    morador_nome = combo_moradores.get()
    valor_str = entry_valor.get()
    data_cob = entry_data_cobranca.get() # Renomeado para evitar conflito com entry_data_geral
    descricao = entry_descricao_cobranca.get() # Renomeado

    if morador_nome == "Escolha o Morador" or morador_nome == "Nenhum morador cadastrado":
        messagebox.showwarning("Atenção", "Selecione um morador válido.")
        return

    if not valor_str:
        messagebox.showwarning("Atenção", "Preencha o valor.")
        return
    try:
        valor = float(valor_str.replace(",", ".")) # Aceita vírgula como separador decimal
    except ValueError:
        messagebox.showwarning("Atenção", "Valor inválido. Use '.' ou ',' como separador decimal.")
        return

    if morador_nome and valor and data_cob and descricao:
        cursor.execute("SELECT id FROM moradores WHERE nome = ?", (morador_nome,))
        morador_id_tuple = cursor.fetchone()
        if morador_id_tuple:
            morador_id = morador_id_tuple[0]
            try:
                cursor.execute("INSERT INTO financeiro (id_morador, valor, data, descricao) VALUES (?, ?, ?, ?)",
                               (morador_id, valor, data_cob, descricao))
                conn.commit()
                messagebox.showinfo("Sucesso", "Cobrança registrada!")
                entry_valor.delete(0, tk.END)
                entry_data_cobranca.delete(0, tk.END)
                entry_descricao_cobranca.delete(0, tk.END)
                combo_moradores.set("Escolha o Morador")
                atualizar_lista_financeiro()
            except sqlite3.Error as e:
                conn.rollback()
                messagebox.showerror("Erro no Banco de Dados", f"Não foi possível registrar a cobrança: {e}")
        else:
            messagebox.showwarning("Atenção", "Morador não encontrado.")
    else:
        messagebox.showwarning("Atenção", "Preencha todos os campos.")

def atualizar_lista_financeiro():
    global financeiro_ids
    financeiro_ids = []
    listbox_financeiro.delete(0, tk.END)
    cursor.execute("""
        SELECT financeiro.id, moradores.nome, financeiro.valor, financeiro.data, financeiro.descricao
        FROM financeiro
        JOIN moradores ON financeiro.id_morador = moradores.id
        ORDER BY financeiro.data DESC, financeiro.id DESC
    """)
    for cobranca in cursor.fetchall():
        financeiro_ids.append(cobranca[0])
        listbox_financeiro.insert(tk.END, f"{cobranca[1]} - R${cobranca[2]:.2f} - {cobranca[3]} - {cobranca[4]}")

def excluir_financeiro():
    global financeiro_ids
    selecionado_idx_tuple = listbox_financeiro.curselection()
    if selecionado_idx_tuple:
        id_financeiro = financeiro_ids[selecionado_idx_tuple[0]]
        texto_selecionado = listbox_financeiro.get(selecionado_idx_tuple[0])
        if messagebox.askyesno("Confirmação", f"Excluir esta cobrança?\n{texto_selecionado}"):
            try:
                cursor.execute("DELETE FROM financeiro WHERE id = ?", (id_financeiro,))
                conn.commit()
                atualizar_lista_financeiro()
            except sqlite3.Error as e:
                conn.rollback()
                messagebox.showerror("Erro no Banco de Dados", f"Não foi possível excluir a cobrança: {e}")
    else:
        messagebox.showwarning("Atenção", "Selecione uma cobrança para excluir.")

def abrir_janela_edicao_financeiro(financeiro_id):
    global edit_financeiro_window, combo_moradores_edit_fin, entry_valor_edit_fin
    global entry_data_edit_fin, entry_descricao_edit_fin, current_editing_financeiro_id

    if edit_financeiro_window is not None and edit_financeiro_window.winfo_exists():
        edit_financeiro_window.destroy()

    current_editing_financeiro_id = financeiro_id
    cursor.execute("""
        SELECT f.id_morador, m.nome, f.valor, f.data, f.descricao
        FROM financeiro f
        JOIN moradores m ON f.id_morador = m.id
        WHERE f.id = ?
    """, (financeiro_id,))
    cobranca = cursor.fetchone()

    if not cobranca:
        messagebox.showerror("Erro", "Cobrança não encontrada para edição.")
        return

    edit_financeiro_window = tk.Toplevel(root)
    edit_financeiro_window.title("Editar Cobrança")
    edit_financeiro_window.geometry("400x280")
    edit_financeiro_window.grab_set()

    tk.Label(edit_financeiro_window, text="Morador:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
    combo_moradores_edit_fin = ttk.Combobox(edit_financeiro_window, width=30, state="readonly")
    combo_moradores_edit_fin.grid(row=0, column=1, padx=5, pady=5)

    cursor.execute("SELECT nome FROM moradores ORDER BY nome ASC")
    nomes_moradores_raw = [m[0] for m in cursor.fetchall()]
    if not nomes_moradores_raw : # Caso extremo
        nomes_moradores_options = ["Nenhum morador disponível"]
    else:
        nomes_moradores_options = nomes_moradores_raw
    combo_moradores_edit_fin['values'] = nomes_moradores_options
    combo_moradores_edit_fin.set(cobranca[1])

    tk.Label(edit_financeiro_window, text="Valor (R$):").grid(row=1, column=0, sticky="e", padx=5, pady=5)
    entry_valor_edit_fin = tk.Entry(edit_financeiro_window, width=33)
    entry_valor_edit_fin.grid(row=1, column=1, padx=5, pady=5)
    entry_valor_edit_fin.insert(0, f"{cobranca[2]:.2f}")

    tk.Label(edit_financeiro_window, text="Data (DD/MM/AAAA):").grid(row=2, column=0, sticky="e", padx=5, pady=5)
    entry_data_edit_fin = tk.Entry(edit_financeiro_window, width=33)
    entry_data_edit_fin.grid(row=2, column=1, padx=5, pady=5)
    entry_data_edit_fin.insert(0, cobranca[3])

    tk.Label(edit_financeiro_window, text="Descrição:").grid(row=3, column=0, sticky="e", padx=5, pady=5)
    entry_descricao_edit_fin = tk.Entry(edit_financeiro_window, width=33)
    entry_descricao_edit_fin.grid(row=3, column=1, padx=5, pady=5)
    entry_descricao_edit_fin.insert(0, cobranca[4])

    btn_salvar = tk.Button(edit_financeiro_window, text="Salvar Alterações", command=salvar_edicao_financeiro)
    btn_salvar.grid(row=4, column=0, columnspan=2, pady=10)
    btn_cancelar = tk.Button(edit_financeiro_window, text="Cancelar", command=edit_financeiro_window.destroy)
    btn_cancelar.grid(row=5, column=0, columnspan=2, pady=5)

def salvar_edicao_financeiro():
    global current_editing_financeiro_id
    morador_nome = combo_moradores_edit_fin.get()
    valor_str = entry_valor_edit_fin.get()
    data = entry_data_edit_fin.get()
    descricao = entry_descricao_edit_fin.get()

    if morador_nome == "Nenhum morador disponível":
        messagebox.showwarning("Atenção", "Selecione um morador válido.", parent=edit_financeiro_window)
        return

    try:
        valor = float(valor_str.replace(",", "."))
    except ValueError:
        messagebox.showwarning("Atenção", "Valor inválido. Use '.' ou ',' como separador decimal.", parent=edit_financeiro_window)
        return

    if morador_nome and valor and data and descricao:
        cursor.execute("SELECT id FROM moradores WHERE nome = ?", (morador_nome,))
        morador_id_tuple = cursor.fetchone()
        if morador_id_tuple:
            morador_id = morador_id_tuple[0]
            try:
                cursor.execute("""UPDATE financeiro
                                  SET id_morador = ?, valor = ?, data = ?, descricao = ?
                                  WHERE id = ?""",
                               (morador_id, valor, data, descricao, current_editing_financeiro_id))
                conn.commit()
                messagebox.showinfo("Sucesso", "Cobrança atualizada!", parent=edit_financeiro_window)
                edit_financeiro_window.destroy()
                atualizar_lista_financeiro()
            except sqlite3.Error as e:
                conn.rollback()
                messagebox.showerror("Erro no Banco de Dados", f"Não foi possível atualizar a cobrança: {e}", parent=edit_financeiro_window)
        else:
            messagebox.showwarning("Atenção", "Morador não encontrado.", parent=edit_financeiro_window)
    else:
        messagebox.showwarning("Atenção", "Preencha todos os campos.", parent=edit_financeiro_window)

def editar_financeiro_selecionado():
    selecionado_idx_tuple = listbox_financeiro.curselection()
    if selecionado_idx_tuple:
        id_financeiro = financeiro_ids[selecionado_idx_tuple[0]]
        abrir_janela_edicao_financeiro(id_financeiro)
    else:
        messagebox.showwarning("Atenção", "Selecione uma cobrança para editar.")

# --- Funções de Reserva de Ambientes ---
def registrar_reserva():
    morador_nome = combo_moradores_reserva.get()
    ambiente = entry_ambiente.get()
    data = entry_data_reserva.get()
    horario = entry_horario.get()
    observacoes = entry_observacoes.get()

    if morador_nome == "Escolha o Morador" or morador_nome == "Nenhum morador cadastrado":
        messagebox.showwarning("Atenção", "Selecione um morador válido.")
        return

    if morador_nome and ambiente and data and horario:
        cursor.execute("SELECT id FROM moradores WHERE nome = ?", (morador_nome,))
        morador_id_tuple = cursor.fetchone()
        if morador_id_tuple:
            morador_id = morador_id_tuple[0]
            try:
                cursor.execute("""INSERT INTO reservas (id_morador, ambiente, data, horario, observacoes)
                                  VALUES (?, ?, ?, ?, ?)""",
                               (morador_id, ambiente, data, horario, observacoes))
                conn.commit()
                messagebox.showinfo("Sucesso", "Reserva registrada!")
                entry_ambiente.delete(0, tk.END)
                entry_data_reserva.delete(0, tk.END)
                entry_horario.delete(0, tk.END)
                entry_observacoes.delete(0, tk.END)
                combo_moradores_reserva.set("Escolha o Morador")
                atualizar_lista_reservas()
            except sqlite3.Error as e:
                conn.rollback()
                messagebox.showerror("Erro no Banco de Dados", f"Não foi possível registrar a reserva: {e}")
        else:
            messagebox.showwarning("Atenção", "Morador não encontrado.")
    else:
        messagebox.showwarning("Atenção", "Preencha todos os campos obrigatórios.")

def atualizar_lista_reservas():
    global reservas_ids
    reservas_ids = []
    listbox_reservas.delete(0, tk.END)
    cursor.execute("""
        SELECT reservas.id, moradores.nome, ambiente, data, horario, observacoes
        FROM reservas
        JOIN moradores ON reservas.id_morador = moradores.id
        ORDER BY reservas.data ASC, reservas.horario ASC
    """)
    for r in cursor.fetchall():
        reservas_ids.append(r[0])
        listbox_reservas.insert(tk.END, f"{r[1]} - {r[2]} - {r[3]} às {r[4]} - {r[5] or 'Sem observações'}")

def excluir_reserva():
    global reservas_ids
    selecionado_idx_tuple = listbox_reservas.curselection()
    if selecionado_idx_tuple:
        id_reserva = reservas_ids[selecionado_idx_tuple[0]]
        resposta = messagebox.askyesno("Confirmação", "Deseja realmente excluir esta reserva?")
        if resposta:
            try:
                cursor.execute("DELETE FROM reservas WHERE id = ?", (id_reserva,))
                conn.commit()
                atualizar_lista_reservas()
            except sqlite3.Error as e:
                conn.rollback()
                messagebox.showerror("Erro no Banco de Dados", f"Não foi possível excluir a reserva: {e}")
    else:
        messagebox.showwarning("Atenção", "Selecione uma reserva para excluir.")

def abrir_janela_edicao_reserva(reserva_id):
    global edit_reserva_window, combo_moradores_reserva_edit, entry_ambiente_edit, entry_data_reserva_edit
    global entry_horario_edit, entry_observacoes_edit, current_editing_reserva_id

    if edit_reserva_window is not None and edit_reserva_window.winfo_exists():
        edit_reserva_window.destroy()

    current_editing_reserva_id = reserva_id
    cursor.execute("""
        SELECT r.id_morador, m.nome, r.ambiente, r.data, r.horario, r.observacoes
        FROM reservas r
        JOIN moradores m ON r.id_morador = m.id
        WHERE r.id = ?
    """, (reserva_id,))
    reserva = cursor.fetchone()

    if not reserva:
        messagebox.showerror("Erro", "Reserva não encontrada para edição.")
        return

    edit_reserva_window = tk.Toplevel(root)
    edit_reserva_window.title("Editar Reserva")
    edit_reserva_window.geometry("400x320")
    edit_reserva_window.grab_set()

    tk.Label(edit_reserva_window, text="Morador:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
    combo_moradores_reserva_edit = ttk.Combobox(edit_reserva_window, width=30, state="readonly")
    combo_moradores_reserva_edit.grid(row=0, column=1, padx=5, pady=5)

    cursor.execute("SELECT nome FROM moradores ORDER BY nome ASC")
    nomes_moradores_raw = [m[0] for m in cursor.fetchall()]
    if not nomes_moradores_raw:
        nomes_moradores_options = ["Nenhum morador disponível"]
    else:
        nomes_moradores_options = nomes_moradores_raw
    combo_moradores_reserva_edit['values'] = nomes_moradores_options
    combo_moradores_reserva_edit.set(reserva[1])

    tk.Label(edit_reserva_window, text="Ambiente:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
    entry_ambiente_edit = tk.Entry(edit_reserva_window, width=33)
    entry_ambiente_edit.grid(row=1, column=1, padx=5, pady=5)
    entry_ambiente_edit.insert(0, reserva[2])

    tk.Label(edit_reserva_window, text="Data (DD/MM/AAAA):").grid(row=2, column=0, sticky="e", padx=5, pady=5)
    entry_data_reserva_edit = tk.Entry(edit_reserva_window, width=33)
    entry_data_reserva_edit.grid(row=2, column=1, padx=5, pady=5)
    entry_data_reserva_edit.insert(0, reserva[3])

    tk.Label(edit_reserva_window, text="Horário (HH:MM):").grid(row=3, column=0, sticky="e", padx=5, pady=5)
    entry_horario_edit = tk.Entry(edit_reserva_window, width=33)
    entry_horario_edit.grid(row=3, column=1, padx=5, pady=5)
    entry_horario_edit.insert(0, reserva[4])

    tk.Label(edit_reserva_window, text="Observações:").grid(row=4, column=0, sticky="ne", padx=5, pady=5)
    entry_observacoes_edit = tk.Entry(edit_reserva_window, width=33)
    entry_observacoes_edit.grid(row=4, column=1, padx=5, pady=5)
    entry_observacoes_edit.insert(0, reserva[5] or "")

    btn_salvar = tk.Button(edit_reserva_window, text="Salvar Alterações", command=salvar_edicao_reserva)
    btn_salvar.grid(row=5, column=0, columnspan=2, pady=10)
    btn_cancelar = tk.Button(edit_reserva_window, text="Cancelar", command=edit_reserva_window.destroy)
    btn_cancelar.grid(row=6, column=0, columnspan=2, pady=5)

def salvar_edicao_reserva():
    global current_editing_reserva_id
    morador_nome = combo_moradores_reserva_edit.get()
    ambiente = entry_ambiente_edit.get()
    data = entry_data_reserva_edit.get()
    horario = entry_horario_edit.get()
    observacoes = entry_observacoes_edit.get()

    if morador_nome == "Nenhum morador disponível":
        messagebox.showwarning("Atenção", "Selecione um morador válido.", parent=edit_reserva_window)
        return

    if morador_nome and ambiente and data and horario:
        cursor.execute("SELECT id FROM moradores WHERE nome = ?", (morador_nome,))
        morador_id_tuple = cursor.fetchone()
        if morador_id_tuple:
            morador_id = morador_id_tuple[0]
            try:
                cursor.execute("""UPDATE reservas
                                  SET id_morador = ?, ambiente = ?, data = ?, horario = ?, observacoes = ?
                                  WHERE id = ?""",
                               (morador_id, ambiente, data, horario, observacoes, current_editing_reserva_id))
                conn.commit()
                messagebox.showinfo("Sucesso", "Reserva atualizada!", parent=edit_reserva_window)
                edit_reserva_window.destroy()
                atualizar_lista_reservas()
            except sqlite3.Error as e:
                conn.rollback()
                messagebox.showerror("Erro no Banco de Dados", f"Não foi possível atualizar a reserva: {e}", parent=edit_reserva_window)
        else:
            messagebox.showwarning("Atenção", "Morador não encontrado.", parent=edit_reserva_window)
    else:
        messagebox.showwarning("Atenção", "Preencha todos os campos obrigatórios.", parent=edit_reserva_window)

def editar_reserva_selecionada():
    selecionado_idx_tuple = listbox_reservas.curselection()
    if selecionado_idx_tuple:
        id_reserva = reservas_ids[selecionado_idx_tuple[0]]
        abrir_janela_edicao_reserva(id_reserva)
    else:
        messagebox.showwarning("Atenção", "Selecione uma reserva para editar.")

# --- Funções BitKondu ---
def operar_bitkondu(adicionar_flag):
    morador_nome = combo_moradores_bitkondu.get()
    if not morador_nome or morador_nome == "Escolha o Morador" or morador_nome == "Nenhum morador cadastrado":
        messagebox.showwarning("Atenção", "Selecione um morador.")
        return

    try:
        quantidade_str = entry_quantidade_bitkondu.get()
        if not quantidade_str:
            messagebox.showwarning("Atenção", "Digite a quantidade.")
            return
        quantidade = int(quantidade_str)
        if quantidade <= 0:
            messagebox.showwarning("Atenção", "Quantidade deve ser um número positivo maior que zero.")
            return
    except ValueError:
        messagebox.showwarning("Atenção", "Quantidade deve ser um número inteiro válido.")
        return

    acao = entry_acao_bitkondu.get()
    if not acao:
        messagebox.showwarning("Atenção", "Digite a ação/motivo.")
        return

    cursor.execute("SELECT id, bitkondu FROM moradores WHERE nome = ?", (morador_nome,))
    morador_data = cursor.fetchone()
    if not morador_data:
        messagebox.showerror("Erro", "Morador não encontrado.")
        return

    morador_id, saldo_atual = morador_data

    if adicionar_flag:
        novo_saldo = saldo_atual + quantidade
        quantidade_transacao = quantidade
    else: # Subtrair
        if saldo_atual < quantidade:
            messagebox.showwarning("Atenção", f"Saldo insuficiente. Morador {morador_nome} tem {saldo_atual} BitKondu.")
            return
        novo_saldo = saldo_atual - quantidade
        quantidade_transacao = -quantidade

    try:
        cursor.execute("UPDATE moradores SET bitkondu = ? WHERE id = ?", (novo_saldo, morador_id))
        datahora_atual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO bitkondu (id_morador, acao, quantidade, datahora) VALUES (?, ?, ?, ?)",
                       (morador_id, acao, quantidade_transacao, datahora_atual))
        conn.commit()
        messagebox.showinfo("Sucesso", f"BitKondu {'adicionado' if adicionar_flag else 'subtraído'} com sucesso!")
        entry_quantidade_bitkondu.delete(0, tk.END)
        entry_acao_bitkondu.delete(0, tk.END)
        combo_moradores_bitkondu.set("Escolha o Morador")
        atualizar_bitkondu()
        atualizar_lista_transacoes_bitkondu()
    except sqlite3.Error as e:
        conn.rollback()
        messagebox.showerror("Erro no Banco de Dados", f"Não foi possível completar a operação: {e}")

def atualizar_bitkondu(): # Updates the balance display table
    for i in tabela_bitkondu.get_children():
        tabela_bitkondu.delete(i)
    cursor.execute("SELECT nome, bitkondu FROM moradores ORDER BY nome ASC")
    for nome, bitkondu_val in cursor.fetchall():
        tabela_bitkondu.insert("", "end", values=(nome, bitkondu_val if bitkondu_val is not None else 0))

def atualizar_lista_transacoes_bitkondu():
    global bitkondu_transacoes_list_data
    bitkondu_transacoes_list_data = []
    listbox_transacoes_bitkondu.delete(0, tk.END)
    cursor.execute("""
        SELECT b.id, m.nome, b.acao, b.quantidade, b.datahora
        FROM bitkondu b
        JOIN moradores m ON b.id_morador = m.id
        ORDER BY b.datahora DESC
    """)
    for row in cursor.fetchall():
        trans_id, nome, acao, quantidade, datahora = row
        sinal = ""
        if quantidade > 0: sinal = "+"
        display_string = f"{datahora} - {nome} - {acao}: {sinal}{quantidade} BK"
        bitkondu_transacoes_list_data.append({'id': trans_id})
        listbox_transacoes_bitkondu.insert(tk.END, display_string)

def abrir_janela_edicao_trans_bitkondu(transacao_id):
    global edit_bitkondu_trans_window, entry_acao_bitkondu_edit, current_editing_bitkondu_trans_id

    if edit_bitkondu_trans_window is not None and edit_bitkondu_trans_window.winfo_exists():
        edit_bitkondu_trans_window.destroy()

    current_editing_bitkondu_trans_id = transacao_id
    cursor.execute("""
        SELECT m.nome, b.acao, b.quantidade, b.datahora
        FROM bitkondu b
        JOIN moradores m ON b.id_morador = m.id
        WHERE b.id = ?
    """, (transacao_id,))
    transacao = cursor.fetchone()

    if not transacao:
        messagebox.showerror("Erro", "Transação BitKondu não encontrada para edição.")
        return

    edit_bitkondu_trans_window = tk.Toplevel(root)
    edit_bitkondu_trans_window.title("Editar Ação da Transação BitKondu")
    edit_bitkondu_trans_window.geometry("450x220")
    edit_bitkondu_trans_window.grab_set()

    tk.Label(edit_bitkondu_trans_window, text=f"Morador: {transacao[0]}").grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="w")
    tk.Label(edit_bitkondu_trans_window, text=f"Data/Hora: {transacao[3]}").grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="w")
    tk.Label(edit_bitkondu_trans_window, text=f"Quantidade: {transacao[2]} BK (Não editável)").grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="w")

    tk.Label(edit_bitkondu_trans_window, text="Nova Ação/Motivo:").grid(row=3, column=0, padx=5, pady=5, sticky="e")
    entry_acao_bitkondu_edit = tk.Entry(edit_bitkondu_trans_window, width=40)
    entry_acao_bitkondu_edit.grid(row=3, column=1, padx=5, pady=5, sticky="w")
    entry_acao_bitkondu_edit.insert(0, transacao[1])

    btn_salvar = tk.Button(edit_bitkondu_trans_window, text="Salvar Nova Ação", command=salvar_edicao_trans_bitkondu)
    btn_salvar.grid(row=4, column=0, columnspan=2, pady=10)
    btn_cancelar = tk.Button(edit_bitkondu_trans_window, text="Cancelar", command=edit_bitkondu_trans_window.destroy)
    btn_cancelar.grid(row=5, column=0, columnspan=2, pady=5)

def salvar_edicao_trans_bitkondu():
    global current_editing_bitkondu_trans_id
    nova_acao = entry_acao_bitkondu_edit.get()

    if not nova_acao:
        messagebox.showwarning("Atenção", "A ação/motivo não pode ser vazia.", parent=edit_bitkondu_trans_window)
        return

    try:
        cursor.execute("UPDATE bitkondu SET acao = ? WHERE id = ?", (nova_acao, current_editing_bitkondu_trans_id))
        conn.commit()
        messagebox.showinfo("Sucesso", "Ação da transação BitKondu atualizada!", parent=edit_bitkondu_trans_window)
        edit_bitkondu_trans_window.destroy()
        atualizar_lista_transacoes_bitkondu()
    except sqlite3.Error as e:
        conn.rollback()
        messagebox.showerror("Erro no Banco de Dados", f"Não foi possível atualizar a ação da transação: {e}", parent=edit_bitkondu_trans_window)

def editar_transacao_bitkondu_selecionada():
    selecionado_idx_tuple = listbox_transacoes_bitkondu.curselection()
    if selecionado_idx_tuple:
        selecionado_idx = selecionado_idx_tuple[0]
        if selecionado_idx < len(bitkondu_transacoes_list_data):
            transacao_info = bitkondu_transacoes_list_data[selecionado_idx]
            abrir_janela_edicao_trans_bitkondu(transacao_info['id'])
        else:
            messagebox.showerror("Erro", "Erro ao obter dados da transação selecionada.")
    else:
        messagebox.showwarning("Atenção", "Selecione uma transação para editar a ação/motivo.")


# --- Função Comum ---
def carregar_moradores_combobox():
    cursor.execute("SELECT nome FROM moradores ORDER BY nome ASC")
    nomes = [linha[0] for linha in cursor.fetchall()]

    default_selection = "Escolha o Morador"
    opcoes_combobox_com_nenhum_geral = ["Nenhum (Geral)"]

    if not nomes:
        nomes_para_combobox = ["Nenhum morador cadastrado"]
        default_selection = nomes_para_combobox[0]
    else:
        nomes_para_combobox = nomes
        opcoes_combobox_com_nenhum_geral.extend(nomes)

    combo_moradores['values'] = nomes_para_combobox
    combo_moradores_reserva['values'] = nomes_para_combobox

    if 'combo_moradores_bitkondu' in globals(): # Verifica se o widget já foi criado
        combo_moradores_bitkondu['values'] = nomes_para_combobox
        combo_moradores_bitkondu.set(default_selection if nomes else "Nenhum morador cadastrado")

    if 'combo_morador_manutencao_reg' in globals(): # Verifica se o widget já foi criado
        combo_morador_manutencao_reg['values'] = opcoes_combobox_com_nenhum_geral
        combo_morador_manutencao_reg.set("Nenhum (Geral)")

    combo_moradores.set(default_selection if nomes else "Nenhum morador cadastrado")
    combo_moradores_reserva.set(default_selection if nomes else "Nenhum morador cadastrado")


# --- Interface ---
root = tk.Tk()
root.title("Sistema de Condomínio")
root.geometry("850x750") # Aumentar um pouco para os novos campos

notebook = ttk.Notebook(root)
notebook.pack(padx=10, pady=10, fill='both', expand=True)

# Aba Moradores e Avisos
aba_moradores_avisos = tk.Frame(notebook)
notebook.add(aba_moradores_avisos, text="Moradores e Avisos")

frame_cadastro = tk.LabelFrame(aba_moradores_avisos, text="Cadastrar Morador")
frame_cadastro.pack(padx=10, pady=10, fill="x")
tk.Label(frame_cadastro, text="Nome:").grid(row=0, column=0, sticky="e", padx=5, pady=2)
entry_nome = tk.Entry(frame_cadastro, width=40) # Aumentar width
entry_nome.grid(row=0, column=1, padx=5, pady=2)
tk.Label(frame_cadastro, text="Apartamento:").grid(row=1, column=0, sticky="e", padx=5, pady=2)
entry_apartamento = tk.Entry(frame_cadastro, width=40)
entry_apartamento.grid(row=1, column=1, padx=5, pady=2)
tk.Label(frame_cadastro, text="Condomínio:").grid(row=2, column=0, sticky="e", padx=5, pady=2)
entry_condominio = tk.Entry(frame_cadastro, width=40)
entry_condominio.grid(row=2, column=1, padx=5, pady=2)

tk.Label(frame_cadastro, text="Telefone:").grid(row=3, column=0, sticky="e", padx=5, pady=2) # NOVO
entry_telefone = tk.Entry(frame_cadastro, width=40)
entry_telefone.grid(row=3, column=1, padx=5, pady=2)

tk.Label(frame_cadastro, text="E-mail:").grid(row=4, column=0, sticky="e", padx=5, pady=2) # NOVO
entry_email = tk.Entry(frame_cadastro, width=40)
entry_email.grid(row=4, column=1, padx=5, pady=2)

tk.Label(frame_cadastro, text="Endereço:").grid(row=5, column=0, sticky="e", padx=5, pady=2) # NOVO
entry_endereco = tk.Entry(frame_cadastro, width=40)
entry_endereco.grid(row=5, column=1, padx=5, pady=2)

btn_cadastrar = tk.Button(frame_cadastro, text="Cadastrar", command=cadastrar_morador)
btn_cadastrar.grid(row=6, column=0, columnspan=2, pady=10) # Ajustar row

listbox_moradores = tk.Listbox(aba_moradores_avisos, width=60, height=6) # Diminuir um pouco height
listbox_moradores.pack(padx=10, pady=5, fill="x")

frame_botoes_moradores = tk.Frame(aba_moradores_avisos)
frame_botoes_moradores.pack(pady=5)
btn_editar_morador = tk.Button(frame_botoes_moradores, text="Editar Selecionado", command=editar_morador_selecionado)
btn_editar_morador.pack(side=tk.LEFT, padx=5)
btn_excluir_morador = tk.Button(frame_botoes_moradores, text="Excluir Selecionado", command=excluir_morador)
btn_excluir_morador.pack(side=tk.LEFT, padx=5)

frame_mural = tk.LabelFrame(aba_moradores_avisos, text="Mural de Avisos")
frame_mural.pack(padx=10, pady=10, fill="both", expand=True)
frame_mural.columnconfigure(0, weight=1)
entry_aviso = tk.Entry(frame_mural, width=50)
entry_aviso.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
btn_postar = tk.Button(frame_mural, text="Postar", command=postar_aviso)
btn_postar.grid(row=0, column=1, padx=5, pady=5)
btn_excluir_aviso = tk.Button(frame_mural, text="Excluir", command=excluir_aviso)
btn_excluir_aviso.grid(row=0, column=2, padx=5, pady=5)
text_mural = tk.Text(frame_mural, height=6, width=70, state=tk.DISABLED) # Diminuir height
text_mural.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
frame_mural.rowconfigure(1, weight=1)


# Aba Manutenção Geral
aba_manutencao_geral = tk.Frame(notebook)
notebook.add(aba_manutencao_geral, text="Manutenção Geral")

frame_manutencao_geral = tk.LabelFrame(aba_manutencao_geral, text="Registrar Manutenção Geral")
frame_manutencao_geral.pack(padx=10, pady=10, fill="x")
tk.Label(frame_manutencao_geral, text="Tipo:").grid(row=0, column=0, sticky="e", padx=5, pady=2)
tipo_var_geral = tk.StringVar(value="Preventiva")
tk.OptionMenu(frame_manutencao_geral, tipo_var_geral, "Preventiva", "Corretiva").grid(row=0, column=1, sticky="w", padx=5, pady=2)
tk.Label(frame_manutencao_geral, text="Descrição:").grid(row=1, column=0, sticky="e", padx=5, pady=2)
entry_descricao_geral = tk.Entry(frame_manutencao_geral, width=40)
entry_descricao_geral.grid(row=1, column=1, padx=5, pady=2)
tk.Label(frame_manutencao_geral, text="Data (DD/MM/AAAA):").grid(row=2, column=0, sticky="e", padx=5, pady=2)
entry_data_geral = tk.Entry(frame_manutencao_geral, width=40)
entry_data_geral.grid(row=2, column=1, padx=5, pady=2)
tk.Label(frame_manutencao_geral, text="Local:").grid(row=3, column=0, sticky="e", padx=5, pady=2)
entry_local_geral = tk.Entry(frame_manutencao_geral, width=40)
entry_local_geral.grid(row=3, column=1, padx=5, pady=2)
tk.Label(frame_manutencao_geral, text="Morador Resp.:").grid(row=4, column=0, sticky="e", padx=5, pady=2)
combo_morador_manutencao_reg = ttk.Combobox(frame_manutencao_geral, width=37, state="readonly")
combo_morador_manutencao_reg.grid(row=4, column=1, padx=5, pady=2, sticky="w")
btn_registrar_geral = tk.Button(frame_manutencao_geral, text="Registrar", command=registrar_manutencao_geral)
btn_registrar_geral.grid(row=5, column=0, columnspan=2, pady=10)

listbox_manutencao_geral = tk.Listbox(aba_manutencao_geral, width=80, height=10)
listbox_manutencao_geral.pack(padx=10, pady=5, fill="both", expand=True)

frame_botoes_manutencao = tk.Frame(aba_manutencao_geral)
frame_botoes_manutencao.pack(pady=5)
btn_editar_manutencao = tk.Button(frame_botoes_manutencao, text="Editar Selecionada", command=editar_manutencao_selecionada)
btn_editar_manutencao.pack(side=tk.LEFT, padx=5)
btn_excluir_manutencao = tk.Button(frame_botoes_manutencao, text="Excluir Selecionada", command=excluir_manutencao_geral)
btn_excluir_manutencao.pack(side=tk.LEFT, padx=5)


# Aba Financeiro
aba_financeiro = tk.Frame(notebook)
notebook.add(aba_financeiro, text="Financeiro")

frame_financeiro = tk.LabelFrame(aba_financeiro, text="Registrar Cobrança")
frame_financeiro.pack(padx=10, pady=10, fill="x")
tk.Label(frame_financeiro, text="Morador:").grid(row=0, column=0, sticky="e", padx=5, pady=2)
combo_moradores = ttk.Combobox(frame_financeiro, width=30, state="readonly")
combo_moradores.grid(row=0, column=1, padx=5, pady=2)
tk.Label(frame_financeiro, text="Valor (R$):").grid(row=1, column=0, sticky="e", padx=5, pady=2)
entry_valor = tk.Entry(frame_financeiro, width=30)
entry_valor.grid(row=1, column=1, padx=5, pady=2)
tk.Label(frame_financeiro, text="Data (DD/MM/AAAA):").grid(row=2, column=0, sticky="e", padx=5, pady=2)
entry_data_cobranca = tk.Entry(frame_financeiro, width=30)
entry_data_cobranca.grid(row=2, column=1, padx=5, pady=2)
tk.Label(frame_financeiro, text="Descrição:").grid(row=3, column=0, sticky="e", padx=5, pady=2)
entry_descricao_cobranca = tk.Entry(frame_financeiro, width=30)
entry_descricao_cobranca.grid(row=3, column=1, padx=5, pady=2)
btn_registrar_cobranca = tk.Button(frame_financeiro, text="Registrar", command=registrar_cobranca)
btn_registrar_cobranca.grid(row=4, column=0, columnspan=2, pady=10)

listbox_financeiro = tk.Listbox(aba_financeiro, width=80, height=10)
listbox_financeiro.pack(padx=10, pady=5, fill="both", expand=True)

frame_botoes_financeiro = tk.Frame(aba_financeiro)
frame_botoes_financeiro.pack(pady=5)
btn_editar_financeiro = tk.Button(frame_botoes_financeiro, text="Editar Selecionada", command=editar_financeiro_selecionado)
btn_editar_financeiro.pack(side=tk.LEFT, padx=5)
btn_excluir_financeiro = tk.Button(frame_botoes_financeiro, text="Excluir Selecionada", command=excluir_financeiro)
btn_excluir_financeiro.pack(side=tk.LEFT, padx=5)


# Aba Reserva de Ambientes
aba_reservas = tk.Frame(notebook)
notebook.add(aba_reservas, text="Reserva de Ambientes")

frame_reservas = tk.LabelFrame(aba_reservas, text="Nova Reserva")
frame_reservas.pack(padx=10, pady=10, fill="x")
tk.Label(frame_reservas, text="Morador:").grid(row=0, column=0, sticky="e", padx=5, pady=2)
combo_moradores_reserva = ttk.Combobox(frame_reservas, width=30, state="readonly")
combo_moradores_reserva.grid(row=0, column=1, padx=5, pady=2)
tk.Label(frame_reservas, text="Ambiente:").grid(row=1, column=0, sticky="e", padx=5, pady=2)
entry_ambiente = tk.Entry(frame_reservas, width=30)
entry_ambiente.grid(row=1, column=1, padx=5, pady=2)
tk.Label(frame_reservas, text="Data (DD/MM/AAAA):").grid(row=2, column=0, sticky="e", padx=5, pady=2)
entry_data_reserva = tk.Entry(frame_reservas, width=30)
entry_data_reserva.grid(row=2, column=1, padx=5, pady=2)
tk.Label(frame_reservas, text="Horário (HH:MM):").grid(row=3, column=0, sticky="e", padx=5, pady=2)
entry_horario = tk.Entry(frame_reservas, width=30)
entry_horario.grid(row=3, column=1, padx=5, pady=2)
tk.Label(frame_reservas, text="Observações:").grid(row=4, column=0, sticky="ne", padx=5, pady=2)
entry_observacoes = tk.Entry(frame_reservas, width=30)
entry_observacoes.grid(row=4, column=1, padx=5, pady=2)
btn_registrar_reserva = tk.Button(frame_reservas, text="Registrar Reserva", command=registrar_reserva)
btn_registrar_reserva.grid(row=5, column=0, columnspan=2, pady=10)

frame_lista_reservas = tk.LabelFrame(aba_reservas, text="Reservas Registradas")
frame_lista_reservas.pack(padx=10, pady=5, fill="both", expand=True)
listbox_reservas = tk.Listbox(frame_lista_reservas, width=80, height=8)
listbox_reservas.pack(side="left", fill="both", expand=True, padx=(5,0), pady=5)
scroll_reservas = tk.Scrollbar(frame_lista_reservas, orient="vertical", command=listbox_reservas.yview)
scroll_reservas.pack(side="right", fill="y", padx=(0,5), pady=5)
listbox_reservas.config(yscrollcommand=scroll_reservas.set)

frame_botoes_reservas = tk.Frame(aba_reservas)
frame_botoes_reservas.pack(pady=5)
btn_editar_reserva = tk.Button(frame_botoes_reservas, text="Editar Selecionada", command=editar_reserva_selecionada)
btn_editar_reserva.pack(side=tk.LEFT, padx=5)
btn_excluir_reserva = tk.Button(frame_botoes_reservas, text="Excluir Selecionada", command=excluir_reserva)
btn_excluir_reserva.pack(side=tk.LEFT, padx=5)


# Aba BitKondu (Moeda Virtual)
aba_bitkondu = ttk.Frame(notebook)
notebook.add(aba_bitkondu, text='BitKondu')

frame_gerenciar_bitkondu = tk.LabelFrame(aba_bitkondu, text="Gerenciar BitKondu")
frame_gerenciar_bitkondu.pack(padx=10, pady=10, fill="x")
tk.Label(frame_gerenciar_bitkondu, text="Morador:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
combo_moradores_bitkondu = ttk.Combobox(frame_gerenciar_bitkondu, width=30, state="readonly")
combo_moradores_bitkondu.grid(row=0, column=1, padx=5, pady=5, sticky="w")
tk.Label(frame_gerenciar_bitkondu, text="Quantidade:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
entry_quantidade_bitkondu = tk.Entry(frame_gerenciar_bitkondu, width=10)
entry_quantidade_bitkondu.grid(row=1, column=1, sticky="w", padx=5, pady=5)
tk.Label(frame_gerenciar_bitkondu, text="Ação/Motivo:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
entry_acao_bitkondu = tk.Entry(frame_gerenciar_bitkondu, width=32)
entry_acao_bitkondu.grid(row=2, column=1, padx=5, pady=5, sticky="w")
btn_adicionar_bitkondu = tk.Button(frame_gerenciar_bitkondu, text="Adicionar BitKondu", command=lambda: operar_bitkondu(True))
btn_adicionar_bitkondu.grid(row=3, column=0, padx=5, pady=10)
btn_subtrair_bitkondu = tk.Button(frame_gerenciar_bitkondu, text="Subtrair BitKondu", command=lambda: operar_bitkondu(False))
btn_subtrair_bitkondu.grid(row=3, column=1, padx=5, pady=10, sticky="w")

frame_saldos_bitkondu = tk.LabelFrame(aba_bitkondu, text="Saldos de BitKondu dos Moradores")
frame_saldos_bitkondu.pack(padx=10, pady=10, fill="x")
tabela_bitkondu_frame_inner = tk.Frame(frame_saldos_bitkondu)
tabela_bitkondu_frame_inner.pack(fill="both", expand=True)
tabela_bitkondu = ttk.Treeview(tabela_bitkondu_frame_inner, columns=("nome", "bitkondu"), show="headings", height=5)
tabela_bitkondu.heading("nome", text="Morador")
tabela_bitkondu.column("nome", width=300)
tabela_bitkondu.heading("bitkondu", text="Saldo BitKondu")
tabela_bitkondu.column("bitkondu", width=100, anchor="center")
tabela_bitkondu.pack(side="left", fill="both", expand=True, padx=(5,0), pady=5)
scroll_saldos_bitkondu = ttk.Scrollbar(tabela_bitkondu_frame_inner, orient="vertical", command=tabela_bitkondu.yview)
scroll_saldos_bitkondu.pack(side="right", fill="y", padx=(0,5), pady=5)
tabela_bitkondu.configure(yscrollcommand=scroll_saldos_bitkondu.set)

frame_historico_bitkondu = tk.LabelFrame(aba_bitkondu, text="Histórico de Transações BitKondu")
frame_historico_bitkondu.pack(padx=10, pady=10, fill="both", expand=True)
listbox_transacoes_bitkondu = tk.Listbox(frame_historico_bitkondu, width=80, height=7)
listbox_transacoes_bitkondu.pack(side="left", fill="both", expand=True, padx=(5,0), pady=5)
scroll_transacoes_bitkondu = tk.Scrollbar(frame_historico_bitkondu, orient="vertical", command=listbox_transacoes_bitkondu.yview)
scroll_transacoes_bitkondu.pack(side="right", fill="y", padx=(0,5), pady=5)
listbox_transacoes_bitkondu.config(yscrollcommand=scroll_transacoes_bitkondu.set)
btn_editar_acao_trans_bitkondu = tk.Button(frame_historico_bitkondu, text="Editar Ação da Transação Selecionada", command=editar_transacao_bitkondu_selecionada)
btn_editar_acao_trans_bitkondu.pack(pady=5, side="bottom")


# Carregar dados iniciais
atualizar_lista_moradores()
atualizar_mural()
atualizar_lista_manutencao_geral()
atualizar_lista_financeiro()
carregar_moradores_combobox()
atualizar_lista_reservas()
atualizar_bitkondu()
atualizar_lista_transacoes_bitkondu()

root.mainloop()
conn.close()