# config.py - Configurações do sistema
import os
from dataclasses import dataclass

@dataclass
class SistemaConfig:
    """Configurações do sistema acadêmico"""
    BASE_URL = "https://app.uff.br"
    LOGIN_URL = f"{BASE_URL}/graduacao/administracaoacademica"
    RELATORIOS_URL = f"{BASE_URL}/graduacao/administracaoacademica/relatorios/listagens_alunos"
    
    # Cursos específicos para análise
    CURSOS_QUIMICA = {
        'licenciatura': {
            'nome': 'Química (Licenciatura)',
            'codigo': '12700',
            'desdobramento': 'Química (Licenciatura) (12700)'
        },
        'bacharelado': {
            'nome': 'Química (Bacharelado)',
            'codigo': '312700',
            'desdobramento': 'Química (Bacharelado) (312700)'
        },
        'industrial': {
            'nome': 'Química Industrial',
            'codigo': '12709',
            'desdobramento': 'Química Industrial (12709)'
        }
    }
    
    # Mapeamento de formas de ingresso
    FORMAS_INGRESSO = {
        'SISU_1': 'SISU 1ª Edição',
        'SISU_2': 'SISU 2ª Edição'
    }
    
    # Localidades
    LOCALIDADES = {
        '1': 'Niterói',
        '2': 'Campos dos Goytacazes',
        '3': 'Volta Redonda',
        '4': 'Santo Antônio de Pádua',
        '5': 'Nova Iguaçu',
        '6': 'Angra dos Reis',
        '7': 'Itaperuna',
        '8': 'Miracema',
        '9': 'Macaé',
        '10': 'Bom Jesus do Itabapoana',
        '11': 'Cabo Frio',
        '12': 'São João de Meriti',
        '13': 'Arraial do Cabo',
        '14': 'Rio das Ostras',
        '15': 'Quissamã',
        '16': 'Nova Friburgo',
        '20': 'Petrópolis',
        '47': 'Curso Sequencial',
        '48': 'Curso à Distância',
        '49': 'Pinheiral',
        '50': 'Curso Semipresencial'
    }

# Configurações do Streamlit
class StreamlitConfig:
    PAGE_TITLE = "Sistema de Análise de Evasão - UFF"
    PAGE_ICON = "🎓"
    LAYOUT = "wide"
    
    @staticmethod
    def setup():
        import streamlit as st
        st.set_page_config(
            page_title=StreamlitConfig.PAGE_TITLE,
            page_icon=StreamlitConfig.PAGE_ICON,
            layout=StreamlitConfig.LAYOUT
        )
