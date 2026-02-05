# utils.py - Funções auxiliares
import re
import pandas as pd
from typing import List, Dict, Tuple

def validar_periodo_letivo(periodo: str) -> Tuple[bool, str]:
    """
    Valida o formato do período letivo
    Formato esperado: AAAA.S ou AAAA/S ou AAAA semestre
    """
    # Padronizar entrada
    periodo = str(periodo).strip()
    
    # Verificar formato AAAA.S
    if re.match(r'^\d{4}\.\d{1}$', periodo):
        ano = int(periodo.split('.')[0])
        semestre = int(periodo.split('.')[1])
        if 2000 <= ano <= 2100 and semestre in [1, 2]:
            return True, f"{ano}.{semestre}"
    
    # Verificar formato AAAA/S
    if re.match(r'^\d{4}/\d{1}$', periodo):
        ano = int(periodo.split('/')[0])
        semestre = int(periodo.split('/')[1])
        if 2000 <= ano <= 2100 and semestre in [1, 2]:
            return True, f"{ano}.{semestre}"
    
    # Verificar formato AAAA semestre
    match = re.match(r'^(\d{4})\s*[/\\]\s*(\d+)[º°]?$', periodo)
    if match:
        ano = int(match.group(1))
        semestre = int(match.group(2).replace('º', '').replace('°', ''))
        if 2000 <= ano <= 2100 and semestre in [1, 2]:
            return True, f"{ano}.{semestre}"
    
    return False, "Formato inválido. Use: 2025.2, 2025/2 ou 2025 2º"

def gerar_periodos_intervalo(inicio: str, fim: str) -> List[str]:
    """
    Gera lista de períodos entre início e fim
    """
    valid_inicio, periodo_inicio = validar_periodo_letivo(inicio)
    valid_fim, periodo_fim = validar_periodo_letivo(fim)
    
    if not valid_inicio or not valid_fim:
        return []
    
    ano_inicio, sem_inicio = map(int, periodo_inicio.split('.'))
    ano_fim, sem_fim = map(int, periodo_fim.split('.'))
    
    periodos = []
    ano_atual, sem_atual = ano_inicio, sem_inicio
    
    while (ano_atual < ano_fim) or (ano_atual == ano_fim and sem_atual <= sem_fim):
        periodos.append(f"{ano_atual}.{sem_atual}")
        
        # Avançar para próximo período
        if sem_atual == 1:
            sem_atual = 2
        else:
            sem_atual = 1
            ano_atual += 1
    
    return periodos

def classificar_acao_afirmativa(codigo: str) -> str:
    """
    Classifica o código de ação afirmativa
    """
    if not codigo or not isinstance(codigo, str):
        return "Outros"
    
    codigo = codigo.strip().upper()
    
    # Ampla Concorrência
    if codigo.startswith('A') or codigo == 'AC' or codigo == 'A0':
        return "Ampla Concorrência"
    
    # Ações Afirmativas
    if codigo.startswith('L'):
        return "Ações Afirmativas"
    
    return "Outros"

def classificar_motivo_cancelamento(motivo: str) -> str:
    """
    Classifica o motivo de cancelamento conforme especificado
    """
    motivo_lower = str(motivo).lower()
    
    if any(term in motivo_lower for term in ['solicitação oficial', 'solicitacao oficial']):
        return "Solicitação Oficial"
    elif 'abandono' in motivo_lower:
        return "Abandono"
    elif 'insuficiência de aproveitamento' in motivo_lower or 'insuficiencia de aproveitamento' in motivo_lower:
        if 'ingressante' in motivo_lower:
            return "Ingressante - Insuf. Aproveit."
        else:
            return "Insuficiência de Aproveitamento"
    elif 'mudança de curso' in motivo_lower or 'mudanca de curso' in motivo_lower:
        return "Mudança de Curso"
    else:
        return "Outros"
