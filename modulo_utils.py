"""
Módulo de Utilitários - Funções auxiliares e helpers
"""

import sys
import subprocess
import pkg_resources

def verificar_dependencias():
    """Verifica se todas as dependências estão instaladas"""
    try:
        with open('requirements.txt', 'r') as f:
            requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        instalados = {pkg.key for pkg in pkg_resources.working_set}
        
        for req in requirements:
            if '==' in req:
                pkg_name = req.split('==')[0]
            else:
                pkg_name = req
            
            if pkg_name.lower() not in instalados:
                return False
        
        return True
    except:
        # Se não conseguir verificar, assume que está OK
        return True

def criar_diretorios():
    """Cria os diretórios necessários para a aplicação"""
    import os
    
    diretorios = [
        'data',
        'data/relatorios',
        'data/processados',
        'data/saida'
    ]
    
    for diretorio in diretorios:
        os.makedirs(diretorio, exist_ok=True)
    
    return True

def formatar_cpf(cpf):
    """Formata CPF para exibição"""
    if not cpf:
        return ""
    
    cpf = str(cpf).replace(".", "").replace("-", "")
    
    if len(cpf) == 11:
        return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    
    return cpf

def validar_periodo(periodo_inicial, periodo_final):
    """Valida os períodos informados"""
    if periodo_inicial > periodo_final:
        return False, "Período inicial não pode ser maior que o final"
    
    # Validação básica de formato (ex: 2023.1)
    try:
        ano_inicial, sem_inicial = periodo_inicial.split('.')
        ano_final, sem_final = periodo_final.split('.')
        
        if int(sem_inicial) not in [1, 2] or int(sem_final) not in [1, 2]:
            return False, "Semestre deve ser 1 ou 2"
        
        if int(ano_inicial) < 2000 or int(ano_final) > 2100:
            return False, "Ano fora do intervalo válido"
        
        return True, ""
    except:
        return False, "Formato inválido. Use: YYYY.S (ex: 2023.1)"

def limpar_cache():
    """Limpa o cache da aplicação"""
    import shutil
    import os
    
    try:
        if os.path.exists('__pycache__'):
            shutil.rmtree('__pycache__')
        
        for root, dirs, files in os.walk('.'):
            if '__pycache__' in dirs:
                shutil.rmtree(os.path.join(root, '__pycache__'))
        
        return True, "Cache limpo com sucesso"
    except Exception as e:
        return False, f"Erro ao limpar cache: {e}"
