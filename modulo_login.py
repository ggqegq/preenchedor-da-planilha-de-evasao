"""
Módulo de Interface - Configurações e componentes visuais
"""

import streamlit as st

def configurar_pagina():
    """Configura a página do Streamlit"""
    st.set_page_config(
        page_title="Cálculo de Evasão - UFF",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Estilos CSS personalizados
    st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #374151;
        text-align: center;
        margin-bottom: 2rem;
    }
    .info-box {
        background-color: #F0F9FF;
        border-left: 4px solid #3B82F6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .warning-box {
        background-color: #FEF3C7;
        border-left: 4px solid #F59E0B;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .success-box {
        background-color: #D1FAE5;
        border-left: 4px solid #10B981;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    </style>
    """, unsafe_allow_html=True)

def exibir_cabecalho():
    """Exibe o cabeçalho da aplicação"""
    st.markdown('<h1 class="main-header">📊 Cálculo de Evasão - Cursos de Química UFF</h1>', 
                unsafe_allow_html=True)
    
    st.markdown("""
    <div class="sub-header">
    Sistema automatizado para coleta e análise de dados de evasão dos cursos de Química
    </div>
    """, unsafe_allow_html=True)
    
    # Exibir modo atual
    if st.session_state.get('modo_manual', False):
        st.markdown("""
        <div class="info-box">
        <strong>🔧 Modo Upload Manual Ativo</strong><br>
        Você está utilizando a funcionalidade de upload manual de arquivos.
        </div>
        """, unsafe_allow_html=True)

def exibir_mensagem_erro(mensagem):
    """Exibe uma mensagem de erro formatada"""
    st.error(f"❌ {mensagem}")

def exibir_mensagem_sucesso(mensagem):
    """Exibe uma mensagem de sucesso formatada"""
    st.success(f"✅ {mensagem}")

def exibir_mensagem_info(mensagem):
    """Exibe uma mensagem informativa formatada"""
    st.info(f"ℹ️ {mensagem}")

def exibir_mensagem_aviso(mensagem):
    """Exibe uma mensagem de aviso formatada"""
    st.warning(f"⚠️ {mensagem}")
