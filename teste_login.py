"""
Script para testar o login isoladamente
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modulo_login import realizar_login

def testar_login():
    print("=== TESTE DE LOGIN UFF ===")
    print("Modos disponíveis:")
    print("1. Modo real (com credenciais)")
    print("2. Modo teste (simulação)")
    print("3. Modo teste com erro")
    
    opcao = input("\nEscolha uma opção (1-3): ")
    
    if opcao == "1":
        usuario = input("Usuário (CPF/email): ")
        senha = input("Senha: ")
        modo_teste = False
    elif opcao == "2":
        usuario = "teste@uff.br"
        senha = "senhateste"
        modo_teste = True
    elif opcao == "3":
        usuario = "erro"
        senha = "senha"
        modo_teste = True
    else:
        print("Opção inválida")
        return
    
    print(f"\nTestando login...")
    print(f"Usuário: {usuario}")
    print(f"Modo teste: {modo_teste}")
    
    sucesso, mensagem = realizar_login(usuario, senha, modo_teste=modo_teste)
    
    print(f"\nResultado: {'SUCESSO' if sucesso else 'FALHA'}")
    print(f"Mensagem: {mensagem}")

if __name__ == "__main__":
    testar_login()
