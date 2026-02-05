# utils.py - FUNÇÕES AUXILIARES ATUALIZADAS
import re
import pandas as pd
from typing import List, Dict, Tuple, Optional

def validar_periodo_letivo(periodo: str) -> Tuple[bool, str]:
    """
    Valida o formato do período letivo
    Retorna: (sucesso, período_formatado)
    """
    if not periodo or not isinstance(periodo, str):
        return False, "Período inválido"
    
    periodo = periodo.strip()
    
    # Padrões aceitos
    padroes = [
        (r'^(\d{4})\.(\d{1})$', lambda m: (int(m.group(1)), int(m.group(2)))),  # 2025.1
        (r'^(\d{4})/(\d{1})$', lambda m: (int(m.group(1)), int(m.group(2)))),   # 2025/1
        (r'^(\d{4})\s*/\s*(\d+)[º°]?$', lambda m: (int(m.group(1)), int(m.group(2).replace('º', '').replace('°', '')))),  # 2025 / 1º
    ]
    
    for padrao, parser in padroes:
        match = re.match(padrao, periodo)
        if match:
            try:
                ano, semestre = parser(match)
                if 2000 <= ano <= 2100 and semestre in [1, 2]:
                    return True, f"{ano}.{semestre}"
            except:
                continue
    
    return False, f"Formato inválido: {periodo}. Use: 2025.2, 2025/2 ou 2025 / 2º"

def gerar_lista_periodos(inicio: str, fim: str) -> List[str]:
    """
    Gera lista de períodos entre início e fim (inclusive)
    """
    valido_inicio, periodo_inicio = validar_periodo_letivo(inicio)
    valido_fim, periodo_fim = validar_periodo_letivo(fim)
    
    if not valido_inicio or not valido_fim:
        return []
    
    ano_inicio, sem_inicio = map(int, periodo_inicio.split('.'))
    ano_fim, sem_fim = map(int, periodo_fim.split('.'))
    
    periodos = []
    ano_atual, sem_atual = ano_inicio, sem_inicio
    
    while True:
        periodos.append(f"{ano_atual}.{sem_atual}")
        
        # Verificar se chegou ao fim
        if ano_atual == ano_fim and sem_atual == sem_fim:
            break
        
        # Avançar para próximo período
        if sem_atual == 1:
            sem_atual = 2
        else:
            sem_atual = 1
            ano_atual += 1
        
        # Segurança contra loop infinito
        if ano_atual > ano_fim + 10:
            break
    
    return periodos

def converter_periodo_para_valor_sistema(periodo_texto: str) -> Optional[str]:
    """
    Converte período no formato '2025 / 1º' para valor do sistema '20251'
    """
    if not periodo_texto:
        return None
    
    match = re.search(r'(\d{4})\s*/\s*(\d+)', periodo_texto)
    if match:
        ano = match.group(1)
        semestre = match.group(2).replace('º', '').replace('°', '')
        return f"{ano}{semestre}"
    
    return None

def classificar_modalidade_ingresso(codigo_acao_afirmativa: str) -> str:
    """
    Classifica a modalidade de ingresso baseado no código
    """
    if not codigo_acao_afirmativa:
        return "Não informado"
    
    codigo = str(codigo_acao_afirmativa).strip().upper()
    
    # Ampla Concorrência
    if codigo.startswith('A') or codigo in ['AC', 'A0', 'A1']:
        return "Ampla Concorrência"
    
    # Ações Afirmativas
    if codigo.startswith('L'):
        return "Ações Afirmativas"
    
    # Outros códigos específicos
    if codigo in ['CD-P', 'P1', 'P2', 'P4', 'P5', 'P6', 'AU1', 'AU2']:
        return "Ações Afirmativas"
    
    if codigo in ['LB_EP', 'LB_PPI', 'LB_Q', 'LB_PCD', 'LI_EP', 'LI_PPI', 'LI_Q', 'LI_PCD']:
        return "Ações Afirmativas"
    
    return "Outros"

def classificar_motivo_cancelamento(motivo: str) -> str:
    """
    Classifica motivo de cancelamento nas categorias especificadas
    """
    if not motivo:
        return "Outros"
    
    motivo_lower = str(motivo).lower()
    
    # Mapeamento de termos
    mapeamento = {
        'solicitação oficial': 'Solicitação Oficial',
        'solicitacao oficial': 'Solicitação Oficial',
        'abandono': 'Abandono',
        'insuficiência de aproveitamento': 'Insuficiência de Aproveitamento',
        'insuficiencia de aproveitamento': 'Insuficiência de Aproveitamento',
        'ingressante - insuf. aproveit.': 'Ingressante - Insuf. Aproveit.',
        'ingressante insuf. aproveit.': 'Ingressante - Insuf. Aproveit.',
        'mudança de curso': 'Mudança de Curso',
        'mudanca de curso': 'Mudança de Curso',
    }
    
    # Verificar correspondências exatas primeiro
    for termo, categoria in mapeamento.items():
        if termo in motivo_lower:
            return categoria
    
    # Verificar correspondências parciais
    if 'abandono' in motivo_lower:
        return 'Abandono'
    elif 'insuficiencia' in motivo_lower or 'insuficiência' in motivo_lower:
        if 'ingressante' in motivo_lower:
            return 'Ingressante - Insuf. Aproveit.'
        else:
            return 'Insuficiência de Aproveitamento'
    elif 'solicitação' in motivo_lower or 'solicitacao' in motivo_lower:
        return 'Solicitação Oficial'
    elif 'mudança' in motivo_lower or 'mudanca' in motivo_lower:
        return 'Mudança de Curso'
    
    return 'Outros'

def calcular_taxa_evasao(matriculas_ativas: int, cancelamentos: int) -> float:
    """
    Calcula taxa de evasão em porcentagem
    """
    if matriculas_ativas <= 0:
        return 0.0
    
    return round((cancelamentos / matriculas_ativas) * 100, 2)

# Funções específicas para processamento de relatórios UFF
def normalizar_situacao_aluno(situacao: str) -> str:
    """
    Normaliza legendas de situação do aluno conforme especificado
    """
    if not situacao:
        return "Desconhecido"
    
    situacao_lower = str(situacao).lower().strip()
    
    mapeamento = {
        'inscrito': 'Inscritos/Pendentes/Concluintes',
        'concluinte': 'Inscritos/Pendentes/Concluintes', 
        'pendente': 'Inscritos/Pendentes/Concluintes',
        'trancado': 'Trancados',
        'formado': 'Formados',
        'permanência de vínculo': 'Formados',
        'permanencia de vinculo': 'Formados',
    }
    
    for termo, normalizado in mapeamento.items():
        if termo in situacao_lower:
            return normalizado
    
    return situacao

def calcular_matriculas_ativas(df: pd.DataFrame) -> int:
    """
    Calcula total de matrículas ativas conforme regras
    """
    if df.empty:
        return 0
    
    # Situações consideradas ativas
    situacoes_ativas = [
        'Inscritos/Pendentes/Concluintes',
        'Trancados',
        'Formados'
    ]
    
    # Verificar se há coluna de situação normalizada
    if 'situacao_normalizada' in df.columns:
        return df[df['situacao_normalizada'].isin(situacoes_ativas)].shape[0]
    elif 'situacao' in df.columns:
        # Normalizar na hora
        df_temp = df.copy()
        df_temp['situacao_norm'] = df_temp['situacao'].apply(normalizar_situacao_aluno)
        return df_temp[df_temp['situacao_norm'].isin(situacoes_ativas)].shape[0]
    
    return 0
