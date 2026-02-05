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
        linhas.append(f"Processado em: {detalhes['processado_em']}")
    
    linhas.append("")
    linhas.append("FILTROS APLICADOS:")
    linhas.append("-" * 30)
    
    # Filtros
    for chave, valor in filtros.items():
        if valor and valor != '-':
            linhas.append(f"  {chave}: {valor}")
    
    # Etapas
    if status_info.get('etapas'):
        linhas.append("")
        linhas.append("ETAPAS DO PROCESSAMENTO:")
        linhas.append("-" * 30)
        for etapa in status_info['etapas']:
            linhas.append(f"  {etapa}")
    
    return "\n".join(linhas)

def calcular_tempo_estimado(status: str, etapas: List[str]) -> int:
    """Calcula tempo estimado baseado no status atual"""
    # Estimativas em segundos
    estimativas = {
        'EM_PROCESSAMENTO': 300,  # 5 minutos
        'PROCESSADO': 60,  # 1 minuto
        'DESCONHECIDO': 600  # 10 minutos
    }
    
    return estimativas.get(status, 300)

def verificar_espaco_disco(caminho: str, tamanho_minimo_mb: int = 100) -> bool:
    """Verifica se há espaço em disco suficiente"""
    try:
        import shutil
        _, _, livre = shutil.disk_usage(caminho)
        livre_mb = livre / (1024 * 1024)
        
        if livre_mb < tamanho_minimo_mb:
            logger.warning(f"Espaço em disco insuficiente: {livre_mb:.1f}MB disponíveis")
            return False
        
        logger.info(f"Espaço em disco disponível: {livre_mb:.1f}MB")
        return True
    except Exception as e:
        logger.error(f"Erro ao verificar espaço em disco: {str(e)}")
        return True  # Assume que há espaço para não bloquear o processo
