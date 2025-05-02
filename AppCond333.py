import tkinter as tk
from tkinter import messagebox, ttk
import sqlite3

# Conexão com banco de dados
conn = sqlite3.connect("condominio.db")
cursor = conn.cursor()

# Criação das tabelas
cursor.execute("""
    CREATE TABLE IF NOT EXISTS moradores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        apartamento TEXT NOT NULL,
        condominio TEXT NOT NULL
    )
""")

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
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS reservas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        id_morador INTEGER NOT NULL,
        ambiente TEXT NOT NULL,
        data TEXT NOT NULL,
        horario TEXT NOT NULL,
        observacoes TEXT,
        FOREIGN KEY(id_morador) REFERENCES moradores(id)
    )
""")


cursor.execute("""
    CREATE TABLE IF NOT EXISTS financeiro (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        id_morador INTEGER NOT NULL,
        valor REAL NOT NULL,
        data TEXT NOT NULL,
        descricao TEXT NOT NULL,
        FOREIGN KEY(id_morador) REFERENCES moradores(id)
    )
""")

conn.commit()

# Funções de cadastro de moradores e mural
def cadastrar_morador():
    nome = entry_nome.get()
    apartamento = entry_apartamento.get()
    condominio = entry_condominio.get()
    if nome and apartamento and condominio:
        cursor.execute("INSERT INTO moradores (nome, apartamento, condominio) VALUES (?, ?, ?)",
                       (nome, apartamento, condominio))
        conn.commit()
        messagebox.showinfo("Sucesso", "Morador cadastrado!")
        entry_nome.delete(0, tk.END)
        entry_apartamento.delete(0, tk.END)
        entry_condominio.delete(0, tk.END)
        atualizar_lista_moradores()
        carregar_moradores_combobox()
    else:
        messagebox.showwarning("Atenção", "Preencha todos os campos.")

def atualizar_lista_moradores():
    listbox_moradores.delete(0, tk.END)
    cursor.execute("SELECT nome, apartamento, condominio FROM moradores")
    for morador in cursor.fetchall():
        listbox_moradores.insert(tk.END, f"{morador[0]} - Apt {morador[1]} - {morador[2]}")

# Função para excluir morador
def excluir_morador():
    selecionado = listbox_moradores.curselection()
    if selecionado:
        texto = listbox_moradores.get(selecionado)
        nome = texto.split(" - ")[0]
        if messagebox.askyesno("Confirmação", f"Excluir o morador {nome}?"):
            cursor.execute("DELETE FROM moradores WHERE nome = ?", (nome,))
            conn.commit()
            atualizar_lista_moradores()
            carregar_moradores_combobox()
    else:
        messagebox.showwarning("Atenção", "Selecione um morador para excluir.")

# Função para excluir manutenção geral
def excluir_manutencao_geral():
    selecionado = listbox_manutencao_geral.curselection()
    if selecionado:
        texto = listbox_manutencao_geral.get(selecionado)
        descricao = texto.split(": ", 1)[-1]
        if messagebox.askyesno("Confirmação", f"Excluir manutenção: {descricao}?"):
            cursor.execute("DELETE FROM manutencao_geral WHERE descricao = ?", (descricao,))
            conn.commit()
            atualizar_lista_manutencao_geral()
    else:
        messagebox.showwarning("Atenção", "Selecione uma manutenção para excluir.")

# Função para excluir financeiro
def excluir_financeiro():
    selecionado = listbox_financeiro.curselection()
    if selecionado:
        texto = listbox_financeiro.get(selecionado)
        partes = texto.split(" - ")
        nome = partes[0]
        valor = partes[1].replace("R$", "").strip()
        data = partes[2]
        if messagebox.askyesno("Confirmação", f"Excluir cobrança de {nome} no valor R${valor}?"):
            cursor.execute("""
                DELETE FROM financeiro
                WHERE id_morador = (SELECT id FROM moradores WHERE nome = ?)
                AND valor = ?
                AND data = ?
            """, (nome, valor, data))
            conn.commit()
            atualizar_lista_financeiro()
    else:
        messagebox.showwarning("Atenção", "Selecione uma cobrança para excluir.")




def postar_aviso():
    aviso = entry_aviso.get()
    if aviso:
        cursor.execute("INSERT INTO mural (mensagem) VALUES (?)", (aviso,))
        conn.commit()
        entry_aviso.delete(0, tk.END)
        atualizar_mural()
    else:
        messagebox.showwarning("Atenção", "Digite uma mensagem.")

def atualizar_mural():
    text_mural.config(state=tk.NORMAL)
    text_mural.delete(1.0, tk.END)
    cursor.execute("SELECT mensagem FROM mural ORDER BY id DESC")
    for aviso in cursor.fetchall():
        text_mural.insert(tk.END, f"- {aviso[0]}\n")
    text_mural.config(state=tk.DISABLED)

# Funções de manutenção geral
def registrar_manutencao_geral():
    tipo = tipo_var_geral.get()
    descricao = entry_descricao_geral.get()
    data = entry_data_geral.get()
    local = entry_local_geral.get()
    if tipo and descricao and data and local:
        cursor.execute("INSERT INTO manutencao_geral (tipo, descricao, data, local) VALUES (?, ?, ?, ?)",
                       (tipo, descricao, data, local))
        conn.commit()
        messagebox.showinfo("Sucesso", "Manutenção registrada!")
        entry_descricao_geral.delete(0, tk.END)
        entry_data_geral.delete(0, tk.END)
        entry_local_geral.delete(0, tk.END)
        atualizar_lista_manutencao_geral()
    else:
        messagebox.showwarning("Atenção", "Preencha todos os campos.")

def atualizar_lista_manutencao_geral():
    listbox_manutencao_geral.delete(0, tk.END)
    cursor.execute("SELECT tipo, descricao, data, local FROM manutencao_geral ORDER BY id DESC")
    for m in cursor.fetchall():
        listbox_manutencao_geral.insert(tk.END, f"[{m[0]}] {m[2]} - {m[3]}: {m[1]}")




# Funções do financeiro
def registrar_cobranca():
    morador_nome = combo_moradores.get()
    valor = entry_valor.get()
    data = entry_data.get()
    descricao = entry_descricao.get()
    if morador_nome and valor and data and descricao:
        cursor.execute("SELECT id FROM moradores WHERE nome = ?", (morador_nome,))
        morador_id = cursor.fetchone()
        if morador_id:
            cursor.execute("INSERT INTO financeiro (id_morador, valor, data, descricao) VALUES (?, ?, ?, ?)",
                           (morador_id[0], valor, data, descricao))
            conn.commit()
            messagebox.showinfo("Sucesso", "Cobrança registrada!")
            entry_valor.delete(0, tk.END)
            entry_data.delete(0, tk.END)
            entry_descricao.delete(0, tk.END)
            atualizar_lista_financeiro()
        else:
            messagebox.showwarning("Atenção", "Morador não encontrado.")
    else:
        messagebox.showwarning("Atenção", "Preencha todos os campos.")

def atualizar_lista_financeiro():
    listbox_financeiro.delete(0, tk.END)
    cursor.execute("""
        SELECT moradores.nome, financeiro.valor, financeiro.data, financeiro.descricao
        FROM financeiro
        JOIN moradores ON financeiro.id_morador = moradores.id
        ORDER BY financeiro.id DESC
    """)
    for cobranca in cursor.fetchall():
        listbox_financeiro.insert(tk.END, f"{cobranca[0]} - R${cobranca[1]} - {cobranca[2]} - {cobranca[3]}")


def carregar_moradores_combobox():
    cursor.execute("SELECT nome FROM moradores")
    nomes = [linha[0] for linha in cursor.fetchall()]
    combo_moradores['values'] = nomes



def registrar_reserva():
    morador_nome = combo_moradores_reserva.get()
    ambiente = entry_ambiente.get()
    data = entry_data_reserva.get()
    horario = entry_horario.get()
    observacoes = entry_observacoes.get()
    if morador_nome and ambiente and data and horario:
        cursor.execute("SELECT id FROM moradores WHERE nome = ?", (morador_nome,))
        morador_id = cursor.fetchone()
        if morador_id:
            cursor.execute("""INSERT INTO reservas (id_morador, ambiente, data, horario, observacoes)
                              VALUES (?, ?, ?, ?, ?)""",
                           (morador_id[0], ambiente, data, horario, observacoes))
            conn.commit()
            messagebox.showinfo("Sucesso", "Reserva registrada!")
            entry_ambiente.delete(0, tk.END)
            entry_data_reserva.delete(0, tk.END)
            entry_horario.delete(0, tk.END)
            entry_observacoes.delete(0, tk.END)
            atualizar_lista_reservas()
        else:
            messagebox.showwarning("Atenção", "Morador não encontrado.")
    else:
        messagebox.showwarning("Atenção", "Preencha todos os campos obrigatórios.")

def atualizar_lista_reservas():
    listbox_reservas.delete(0, tk.END)
    cursor.execute("""
        SELECT reservas.id, moradores.nome, ambiente, data, horario, observacoes
        FROM reservas
        JOIN moradores ON reservas.id_morador = moradores.id
        ORDER BY reservas.data ASC
    """)
    global reservas_ids
    reservas_ids = []
    for r in cursor.fetchall():
        reservas_ids.append(r[0])
        listbox_reservas.insert(tk.END, f"{r[1]} - {r[2]} - {r[3]} às {r[4]} - {r[5] or 'Sem observações'}")

def excluir_reserva():
    selecionado = listbox_reservas.curselection()
    if selecionado:
        id_reserva = reservas_ids[selecionado[0]]
        resposta = messagebox.askyesno("Confirmação", "Deseja realmente excluir esta reserva?")
        if resposta:
            cursor.execute("DELETE FROM reservas WHERE id = ?", (id_reserva,))
            conn.commit()
            atualizar_lista_reservas()
    else:
        messagebox.showwarning("Atenção", "Selecione uma reserva para excluir.")



# Interface
root = tk.Tk()
root.title("Sistema de Condomínio")

notebook = ttk.Notebook(root)
notebook.pack(padx=10, pady=10, fill='both', expand=True)

# Aba Moradores e Avisos
aba_moradores_avisos = tk.Frame(notebook)
notebook.add(aba_moradores_avisos, text="Moradores e Avisos")

frame_cadastro = tk.LabelFrame(aba_moradores_avisos, text="Cadastrar Morador")
frame_cadastro.pack(padx=10, pady=10)

tk.Label(frame_cadastro, text="Nome:").grid(row=0, column=0, sticky="e")
entry_nome = tk.Entry(frame_cadastro)
entry_nome.grid(row=0, column=1)

tk.Label(frame_cadastro, text="Apartamento:").grid(row=1, column=0, sticky="e")
entry_apartamento = tk.Entry(frame_cadastro)
entry_apartamento.grid(row=1, column=1)

tk.Label(frame_cadastro, text="Condomínio:").grid(row=2, column=0, sticky="e")
entry_condominio = tk.Entry(frame_cadastro)
entry_condominio.grid(row=2, column=1)

btn_cadastrar = tk.Button(frame_cadastro, text="Cadastrar", command=cadastrar_morador)
btn_cadastrar.grid(row=3, column=0, columnspan=2, pady=5)

btn_excluir_morador = tk.Button(aba_moradores_avisos, text="Excluir Morador", command=excluir_morador)
btn_excluir_morador.pack(pady=5)


listbox_moradores = tk.Listbox(aba_moradores_avisos, width=60, height=8)
listbox_moradores.pack(padx=10, pady=10)

frame_mural = tk.LabelFrame(aba_moradores_avisos, text="Mural de Avisos")
frame_mural.pack(padx=10, pady=10)

entry_aviso = tk.Entry(frame_mural, width=70)
entry_aviso.grid(row=0, column=0)
btn_postar = tk.Button(frame_mural, text="Postar Aviso", command=postar_aviso)
btn_postar.grid(row=0, column=1)

text_mural = tk.Text(frame_mural, height=8, width=90, state=tk.DISABLED)
text_mural.grid(row=1, column=0, columnspan=2)



# Aba Manutenção Geral
aba_manutencao_geral = tk.Frame(notebook)
notebook.add(aba_manutencao_geral, text="Manutenção Geral")

frame_manutencao_geral = tk.LabelFrame(aba_manutencao_geral, text="Registrar Manutenção Geral")
frame_manutencao_geral.pack(padx=10, pady=10)

tk.Label(frame_manutencao_geral, text="Tipo:").grid(row=0, column=0, sticky="e")
tipo_var_geral = tk.StringVar(value="Preventiva")
tk.OptionMenu(frame_manutencao_geral, tipo_var_geral, "Preventiva", "Corretiva").grid(row=0, column=1)

tk.Label(frame_manutencao_geral, text="Descrição:").grid(row=1, column=0, sticky="e")
entry_descricao_geral = tk.Entry(frame_manutencao_geral)
entry_descricao_geral.grid(row=1, column=1)

tk.Label(frame_manutencao_geral, text="Data:").grid(row=2, column=0, sticky="e")
entry_data_geral = tk.Entry(frame_manutencao_geral)
entry_data_geral.grid(row=2, column=1)

tk.Label(frame_manutencao_geral, text="Local:").grid(row=3, column=0, sticky="e")
entry_local_geral = tk.Entry(frame_manutencao_geral)
entry_local_geral.grid(row=3, column=1)

btn_registrar_geral = tk.Button(frame_manutencao_geral, text="Registrar", command=registrar_manutencao_geral)
btn_registrar_geral.grid(row=4, column=0, columnspan=2, pady=5)

btn_excluir_manutencao = tk.Button(aba_manutencao_geral, text="Excluir Manutenção", command=excluir_manutencao_geral)
btn_excluir_manutencao.pack(pady=5)


listbox_manutencao_geral = tk.Listbox(aba_manutencao_geral, width=80, height=10)
listbox_manutencao_geral.pack(padx=10, pady=10)

# Aba Financeiro
aba_financeiro = tk.Frame(notebook)
notebook.add(aba_financeiro, text="Financeiro")

frame_financeiro = tk.LabelFrame(aba_financeiro, text="Registrar Cobrança")
frame_financeiro.pack(padx=10, pady=10)

tk.Label(frame_financeiro, text="Morador:").grid(row=0, column=0, sticky="e")
combo_moradores = ttk.Combobox(frame_financeiro, width=25)
combo_moradores.grid(row=0, column=1)
combo_moradores.set("Escolha o Morador")

tk.Label(frame_financeiro, text="Valor:").grid(row=1, column=0, sticky="e")
entry_valor = tk.Entry(frame_financeiro, width=25)
entry_valor.grid(row=1, column=1)

tk.Label(frame_financeiro, text="Data:").grid(row=2, column=0, sticky="e")
entry_data = tk.Entry(frame_financeiro, width=25)
entry_data.grid(row=2, column=1)

tk.Label(frame_financeiro, text="Descrição:").grid(row=3, column=0, sticky="e")
entry_descricao = tk.Entry(frame_financeiro, width=25)
entry_descricao.grid(row=3, column=1)

btn_registrar_cobranca = tk.Button(frame_financeiro, text="Registrar", command=registrar_cobranca)
btn_registrar_cobranca.grid(row=4, column=0, columnspan=2, pady=5)

btn_excluir_financeiro = tk.Button(aba_financeiro, text="Excluir Cobrança", command=excluir_financeiro)
btn_excluir_financeiro.pack(pady=5)


listbox_financeiro = tk.Listbox(aba_financeiro, width=80, height=10)
listbox_financeiro.pack(padx=10, pady=10)


# Aba Reserva de Ambientes
aba_reservas = tk.Frame(notebook)
notebook.add(aba_reservas, text="Reserva de Ambientes")

frame_reservas = tk.LabelFrame(aba_reservas, text="Nova Reserva")
frame_reservas.pack(padx=10, pady=10)

tk.Label(frame_reservas, text="Morador:").grid(row=0, column=0, sticky="e")
combo_moradores_reserva = ttk.Combobox(frame_reservas, width=25)
combo_moradores_reserva.grid(row=0, column=1)

tk.Label(frame_reservas, text="Ambiente:").grid(row=1, column=0, sticky="e")
entry_ambiente = tk.Entry(frame_reservas, width=25)
entry_ambiente.grid(row=1, column=1)

tk.Label(frame_reservas, text="Data (DD/MM/AAAA):").grid(row=2, column=0, sticky="e")
entry_data_reserva = tk.Entry(frame_reservas, width=25)
entry_data_reserva.grid(row=2, column=1)

tk.Label(frame_reservas, text="Horário (HH:MM):").grid(row=3, column=0, sticky="e")
entry_horario = tk.Entry(frame_reservas, width=25)
entry_horario.grid(row=3, column=1)

tk.Label(frame_reservas, text="Observações:").grid(row=4, column=0, sticky="ne")
entry_observacoes = tk.Entry(frame_reservas, width=25)
entry_observacoes.grid(row=4, column=1)

btn_registrar_reserva = tk.Button(frame_reservas, text="Registrar Reserva", command=registrar_reserva)
btn_registrar_reserva.grid(row=5, column=0, columnspan=2, pady=5)

frame_lista_reservas = tk.LabelFrame(aba_reservas, text="Reservas Registradas")
frame_lista_reservas.pack(padx=10, pady=5, fill="x")

listbox_reservas = tk.Listbox(frame_lista_reservas, width=80, height=10)
listbox_reservas.pack(side="left", padx=(10,0), pady=5)

scroll_reservas = tk.Scrollbar(frame_lista_reservas, orient="vertical")
scroll_reservas.config(command=listbox_reservas.yview)
scroll_reservas.pack(side="right", fill="y", pady=5)
listbox_reservas.config(yscrollcommand=scroll_reservas.set)

btn_excluir_reserva = tk.Button(aba_reservas, text="Excluir Reserva Selecionada", command=excluir_reserva)
btn_excluir_reserva.pack(pady=5)


# Carregar dados iniciais
atualizar_lista_moradores()
atualizar_mural()
atualizar_lista_manutencao_geral()
atualizar_lista_financeiro()
carregar_moradores_combobox()
carregar_moradores_combobox()
combo_moradores_reserva['values'] = combo_moradores['values']
atualizar_lista_reservas()


root.mainloop()
conn.close()
