# exemplo_planilha.py
"""
Exemplo da estrutura da planilha de saída
"""
import pandas as pd
from datetime import datetime

def criar_exemplo_planilha():
    """Cria um exemplo da planilha de saída"""
    
    # Dados de exemplo para RESUMO GERAL
    dados_resumo = [
        {
            'Curso': 'Química (Licenciatura)',
            'Total Matrículas': 150,
            'Total Cancelamentos': 45,
            'Total Formados': 30,
            'Total Ativos': 75,
            '% Cancelamentos': 30.0,
            '% Formados': 20.0,
            '% Ativos': 50.0
        },
        {
            'Curso': 'Química (Bacharelado)',
            'Total Matrículas': 120,
            'Total Cancelamentos': 36,
            'Total Formados': 24,
            'Total Ativos': 60,
            '% Cancelamentos': 30.0,
            '% Formados': 20.0,
            '% Ativos': 50.0
        },
        {
            'Curso': 'Química Industrial',
            'Total Matrículas': 80,
            'Total Cancelamentos': 24,
            'Total Formados': 16,
            'Total Ativos': 40,
            '% Cancelamentos': 30.0,
            '% Formados': 20.0,
            '% Ativos': 50.0
        }
    ]
    
    # Dados de exemplo para DETALHES
    dados_detalhes = [
        {
            'Curso': 'Química (Licenciatura)',
            'Período': '2025/1',
            'Total Registros': 50,
            'Matrículas Ativas': 25,
            'Ampla Concorrência': 30,
            'Ações Afirmativas': 20,
            'Inscritos/Pendentes/Concluintes (qtd)': 20,
            'Inscritos/Pendentes/Concluintes (%)': 40.0,
            'Trancados (qtd)': 5,
            'Trancados (%)': 10.0,
            'Formados (qtd)': 10,
            'Formados (%)': 20.0,
            'Cancel: Solicitação Oficial': 5,
            'Cancel: Abandono': 8,
            'Cancel: Outros': 2
        }
    ]
    
    # Dados de exemplo para CANCELAMENTOS
    dados_cancel = [
        {
            'Curso': 'Química (Licenciatura)',
            'Período': '2025/1',
            'Motivo Cancelamento': 'Solicitação Oficial',
            'Quantidade': 5,
            'Percentual': 33.3
        },
        {
            'Curso': 'Química (Licenciatura)',
            'Período': '2025/1',
            'Motivo Cancelamento': 'Abandono',
            'Quantidade': 8,
            'Percentual': 53.3
        },
        {
            'Curso': 'Química (Licenciatura)',
            'Período': '2025/1',
            'Motivo Cancelamento': 'Outros',
            'Quantidade': 2,
            'Percentual': 13.3
        }
    ]
    
    # Dados de exemplo para MODALIDADES
    dados_modal = [
        {
            'Curso': 'Química (Licenciatura)',
            'Período': '2025/1',
            'Total': 50,
            'Ampla Concorrência': 30,
            '% Ampla': 60.0,
            'Ações Afirmativas': 20,
            '% Ações': 40.0
        }
    ]
    
    # Criar planilha Excel
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    nome_arquivo = f"exemplo_estatisticas_{timestamp}.xlsx"
    
    with pd.ExcelWriter(nome_arquivo, engine='xlsxwriter') as writer:
        # RESUMO GERAL
        df_resumo = pd.DataFrame(dados_resumo)
        df_resumo.to_excel(writer, sheet_name='RESUMO GERAL', index=False)
        
        # DETALHES
        df_detalhes = pd.DataFrame(dados_detalhes)
        df_detalhes.to_excel(writer, sheet_name='DETALHES', index=False)
        
        # CANCELAMENTOS
        df_cancel = pd.DataFrame(dados_cancel)
        df_cancel.to_excel(writer, sheet_name='CANCELAMENTOS', index=False)
        
        # MODALIDADES
        df_modal = pd.DataFrame(dados_modal)
        df_modal.to_excel(writer, sheet_name='MODALIDADES', index=False)
    
    print(f"Exemplo de planilha criado: {nome_arquivo}")
    return nome_arquivo

if __name__ == "__main__":
    criar_exemplo_planilha()
