import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

def criar_banco():
    conn = sqlite3.connect("condominio.db")
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS moradores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        apartamento TEXT NOT NULL
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS unidades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero TEXT NOT NULL,
        proprietario TEXT NOT NULL
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS manutencao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        descricao TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pendente'
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS comunicacao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        remetente TEXT NOT NULL,
        mensagem TEXT NOT NULL,
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pagamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        unidade TEXT NOT NULL,
        valor REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pendente'
    )
    ''')
    
    conn.commit()
    conn.close()

def cadastrar_morador():
    def salvar():
        nome = entry_nome.get()
        apartamento = entry_apartamento.get()
        if nome and apartamento:
            conn = sqlite3.connect("condominio.db")
            cursor = conn.cursor()
            cursor.execute("INSERT INTO moradores (nome, apartamento) VALUES (?, ?)", (nome, apartamento))
            conn.commit()
            conn.close()
            messagebox.showinfo("Sucesso", "Morador cadastrado com sucesso!")
            janela.destroy()
        else:
            messagebox.showerror("Erro", "Preencha todos os campos!")
    
    janela = tk.Toplevel()
    janela.title("Cadastrar Morador")
    
    tk.Label(janela, text="Nome:").pack()
    entry_nome = tk.Entry(janela)
    entry_nome.pack()
    
    tk.Label(janela, text="Apartamento:").pack()
    entry_apartamento = tk.Entry(janela)
    entry_apartamento.pack()
    
    tk.Button(janela, text="Salvar", command=salvar).pack()

def listar_moradores():
    janela = tk.Toplevel()
    janela.title("Lista de Moradores")
    
    tree = ttk.Treeview(janela, columns=("ID", "Nome", "Apartamento"), show="headings")
    tree.heading("ID", text="ID")
    tree.heading("Nome", text="Nome")
    tree.heading("Apartamento", text="Apartamento")
    tree.pack()
    
    conn = sqlite3.connect("condominio.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM moradores")
    for row in cursor.fetchall():
        tree.insert("", "end", values=row)
    conn.close()

def cadastrar_manutencao():
    def salvar():
        descricao = entry_descricao.get()
        if descricao:
            conn = sqlite3.connect("condominio.db")
            cursor = conn.cursor()
            cursor.execute("INSERT INTO manutencao (descricao) VALUES (?)", (descricao,))
            conn.commit()
            conn.close()
            messagebox.showinfo("Sucesso", "Manutenção cadastrada com sucesso!")
            janela.destroy()
        else:
            messagebox.showerror("Erro", "Preencha todos os campos!")
    
    janela = tk.Toplevel()
    janela.title("Cadastrar Manutenção")
    
    tk.Label(janela, text="Descrição:").pack()
    entry_descricao = tk.Entry(janela)
    entry_descricao.pack()
    
    tk.Button(janela, text="Salvar", command=salvar).pack()

def enviar_mensagem():
    def salvar():
        remetente = entry_remetente.get()
        mensagem = text_mensagem.get("1.0", tk.END).strip()
        if remetente and mensagem:
            conn = sqlite3.connect("condominio.db")
            cursor = conn.cursor()
            cursor.execute("INSERT INTO comunicacao (remetente, mensagem) VALUES (?, ?)", (remetente, mensagem))
            conn.commit()
            conn.close()
            messagebox.showinfo("Sucesso", "Mensagem enviada com sucesso!")
            janela.destroy()
        else:
            messagebox.showerror("Erro", "Preencha todos os campos!")
    
    janela = tk.Toplevel()
    janela.title("Nova Mensagem")
    
    tk.Label(janela, text="Nome:").pack()
    entry_remetente = tk.Entry(janela)
    entry_remetente.pack()
    
    tk.Label(janela, text="Mensagem:").pack()
    text_mensagem = tk.Text(janela, height=5, width=40)
    text_mensagem.pack()
    
    tk.Button(janela, text="Enviar", command=salvar).pack()

def visualizar_mensagens():
    janela = tk.Toplevel()
    janela.title("Comunicação do Condomínio")
    
    tree = ttk.Treeview(janela, columns=("ID", "Remetente", "Mensagem", "Data"), show="headings")
    tree.heading("ID", text="ID")
    tree.heading("Remetente", text="Remetente")
    tree.heading("Mensagem", text="Mensagem")
    tree.heading("Data", text="Data")
    tree.pack()
    
    conn = sqlite3.connect("condominio.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM comunicacao ORDER BY data DESC")
    for row in cursor.fetchall():
        tree.insert("", "end", values=row)
    conn.close()

def interface():
    root = tk.Tk()
    root.title("Sistema de Condomínio")
    
    tk.Button(root, text="Cadastrar Morador", command=cadastrar_morador).pack(pady=10)
    tk.Button(root, text="Listar Moradores", command=listar_moradores).pack(pady=10)
    tk.Button(root, text="Cadastrar Manutenção", command=cadastrar_manutencao).pack(pady=10)
    tk.Button(root, text="Enviar Mensagem", command=enviar_mensagem).pack(pady=10)
    tk.Button(root, text="Ver Mensagens", command=visualizar_mensagens).pack(pady=10)
    tk.Button(root, text="Sair", command=root.quit).pack(pady=10)
    
    root.mainloop()

if __name__ == "__main__":
    criar_banco()
    interface()
