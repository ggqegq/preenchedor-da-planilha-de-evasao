"""
utils.py - Funções utilitárias para o projeto
"""
import json
import csv
import re
from datetime import datetime
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

def validar_email(email: str) -> bool:
    """Valida formato de email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def formatar_data(data_str: str, formato_entrada: str = '%d/%m/%Y', 
                  formato_saida: str = '%Y-%m-%d') -> str:
    """Formata uma data de um formato para outro"""
    try:
        data = datetime.strptime(data_str, formato_entrada)
        return data.strftime(formato_saida)
    except:
        return data_str

def sanitizar_nome_arquivo(nome: str) -> str:
    """Remove caracteres inválidos de nomes de arquivos"""
    # Caracteres inválidos no Windows/Linux
    caracteres_invalidos = r'[<>:"/\\|?*\x00-\x1F]'
    nome_sanitizado = re.sub(caracteres_invalidos, '_', nome)
    
    # Remover espaços no início/fim
    nome_sanitizado = nome_sanitizado.strip()
    
    # Limitar tamanho (255 caracteres é comum para sistemas de arquivos)
    if len(nome_sanitizado) > 255:
        nome_sanitizado = nome_sanitizado[:255]
    
    return nome_sanitizado

def salvar_json(dados: Dict, caminho: str, indent: int = 2) -> bool:
    """Salva dados em formato JSON"""
    try:
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=indent)
        logger.info(f"Dados salvos em: {caminho}")
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar JSON: {str(e)}")
        return False

def carregar_json(caminho: str) -> Optional[Dict]:
    """Carrega dados de arquivo JSON"""
    try:
        with open(caminho, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Erro ao carregar JSON: {str(e)}")
        return None

def criar_resumo_relatorio(status_info: Dict) -> str:
    """Cria um resumo textual do relatório"""
    if not status_info:
        return "Nenhuma informação disponível"
    
    filtros = status_info.get('filtros', {})
    detalhes = status_info.get('detalhes', {})
    
    linhas = []
    linhas.append(f"RELATÓRIO #{status_info.get('id', 'N/A')}")
    linhas.append("=" * 50)
    
    # Informações básicas
    if status_info.get('titulo'):
        linhas.append(f"Título: {status_info['titulo']}")
    
    linhas.append(f"Status: {status_info.get('status', 'Desconhecido')}")
    
    # Datas
    if detalhes.get('criado em'):
        linhas.append(f"Criado em: {detalhes['criado em']}")
    if detalhes.get('enviado para processamento em'):
        linhas.append(f"Enviado: {detalhes['enviado para processamento em']}")
    if detalhes.get('processado_em') and detalhes['processado_em'] not in ['---', '']:
        linhas.append(f"Processado em: {detalhes['processado_em']
