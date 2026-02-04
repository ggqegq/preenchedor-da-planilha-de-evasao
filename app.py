"""
Módulo Principal - Aplicativo de Cálculo de Evasão UFF
Autor: Suporte UFF
Versão: 1.0.0
"""

import streamlit as st
import sys
import os

# Adiciona o diretório atual ao path para importar módulos locais
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importação dos módulos (vamos criar um por um)
try:
    from modulo_interface import configurar_pagina, exibir_cabecalho
    from modulo_login import realizar_login
    from modulo_utils import verificar_dependencias
except ImportError as e:
    st.error(f"Erro ao importar módulos: {e}")
    st.info("Certifique-se de que todos os módulos estão no diretório correto.")
    st.stop()

def main():
    """Função principal do aplicativo"""
    
    # Configuração da página
    configurar_pagina()
    
    # Exibir cabeçalho
    exibir_cabecalho()
    
    # Verificar dependências
    if not verificar_dependencias():
        st.error("Algumas dependências não estão instaladas. Execute: pip install -r requirements.txt")
        st.stop()
    
    # Inicializar estado da sessão
    if 'logado' not in st.session_state:
        st.session_state.logado = False
    if 'usuario' not in st.session_state:
        st.session_state.usuario = None
    
    # Menu lateral
aba_selecionada = st.sidebar.radio(
    "Selecione a etapa:",
    ["🔐 Login", "📋 Consultar Relatórios", "📤 Upload Manual", 
     "📈 Gerar Planilha", "🔍 Debug Login", "⚙️ Configurações"]
)
def exibir_tela_debug():
    """Exibe a tela de debug do login"""
    st.header("🔍 Debug do Sistema de Login")
    
    from modulo_login import debug_pagina_login
    debug_pagina_login()
    
    # Estado da aplicação
    aba_selecionada = st.sidebar.radio(
        "Selecione a etapa:",
        ["🔐 Login", "📋 Consultar Relatórios", "📤 Upload Manual", "📈 Gerar Planilha", "⚙️ Configurações"]
    )
    
      # Mapeamento das abas
if aba_selecionada == "🔐 Login":
    exibir_tela_login()
elif aba_selecionada == "📋 Consultar Relatórios":
    if st.session_state.logado:
        exibir_tela_consulta()
    else:
        st.warning("⚠️ Faça login primeiro para acessar esta funcionalidade.")
        exibir_tela_login()
elif aba_selecionada == "📤 Upload Manual":
    exibir_tela_upload()
elif aba_selecionada == "📈 Gerar Planilha":
    exibir_tela_gerar_planilha()
elif aba_selecionada == "🔍 Debug Login":  # NOVO
    exibir_tela_debug()
else:  # Configurações
    exibir_tela_configuracoes()

def exibir_tela_login():
    """Exibe a tela de login"""
    st.header("🔐 Login no Sistema Acadêmico UFF")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        ### Credenciais de Acesso
        Utilize suas credenciais do **IdUFF** para acesso ao sistema acadêmico.
        
        **Formato aceito:**
        - CPF (apenas números)
        - E-mail institucional
        - Passaporte (estrangeiros)
        """)
        
        usuario = st.text_input("Usuário (CPF/E-mail/Passaporte)", 
                               placeholder="Digite seu usuário IdUFF")
        senha = st.text_input("Senha", type="password",
                             placeholder="Digite sua senha")
        
        # Opções de login
        col_auto, col_manual = st.columns(2)
        with col_auto:
            btn_login_auto = st.button("🚀 Login Automático", 
                                      type="primary", 
                                      use_container_width=True)
        
        with col_manual:
            btn_modo_manual = st.button("📤 Modo Upload Manual", 
                                       use_container_width=True)
        
        # Ações dos botões
        if btn_login_auto:
            if not usuario or not senha:
                st.error("Por favor, preencha usuário e senha.")
            else:
                with st.spinner("Realizando login no sistema acadêmico..."):
                    sucesso, mensagem = realizar_login(usuario, senha)
                    
                    if sucesso:
                        st.session_state.logado = True
                        st.session_state.usuario = usuario
                        st.success(f"✅ Login realizado com sucesso! Bem-vindo, {usuario}.")
                        st.balloons()
                        # Aguarda 2 segundos e redireciona
                        st.rerun()
                    else:
                        st.error(f"❌ Falha no login: {mensagem}")
        
        if btn_modo_manual:
            st.session_state.logado = True  # Permite acesso ao modo manual
            st.session_state.modo_manual = True
            st.info("📤 Modo upload manual ativado. Você pode fazer upload dos arquivos exportados manualmente.")
            st.rerun()
    
    with col2:
        st.markdown("""
        ### ℹ️ Informações Importantes
        
        **Atenção:**
        1. O login automático depende do funcionamento do sistema acadêmico
        2. Em caso de 2FA ou CAPTCHA, use o modo upload manual
        3. Suas credenciais não são armazenadas
        4. O tempo limite de conexão é de 5 minutos
        
        **Solução de problemas:**
        - Verifique sua conexão com a internet
        - Confirme se o IdUFF está funcionando
        - Use o modo manual se necessário
        """)

def exibir_tela_consulta():
    """Exibe a tela de consulta de relatórios (será implementada no próximo módulo)"""
    st.header("📋 Consulta de Relatórios")
    st.info("🚧 Funcionalidade em desenvolvimento. Em breve você poderá consultar os relatórios automaticamente.")
    
    # Placeholder para a funcionalidade futura
    st.write("Aqui você poderá:")
    st.write("1. Selecionar períodos")
    st.write("2. Escolher os cursos")
    st.write("3. Configurar parâmetros de consulta")
    st.write("4. Executar a coleta automática")

def exibir_tela_upload():
    """Exibe a tela de upload manual (será implementada)"""
    st.header("📤 Upload Manual de Arquivos")
    st.info("🚧 Funcionalidade em desenvolvimento. Em breve você poderá fazer upload dos arquivos Excel.")

def exibir_tela_gerar_planilha():
    """Exibe a tela de geração de planilha (será implementada)"""
    st.header("📈 Gerar Planilha de Evasão")
    st.info("🚧 Funcionalidade em desenvolvimento. Em breve você poderá gerar a planilha consolidada.")

def exibir_tela_configuracoes():
    """Exibe a tela de configurações"""
    st.header("⚙️ Configurações")
    
    st.subheader("Configurações da Aplicação")
    
    # Configuração de tempo limite
    timeout = st.slider(
        "Tempo limite de consulta (minutos)",
        min_value=1,
        max_value=10,
        value=5,
        help="Tempo máximo de espera por cada relatório"
    )
    
    # Configuração de cursos
    st.subheader("Cursos Monitorados")
    
    cursos = {
        "Química Licenciatura": True,
        "Química Bacharelado": True,
        "Química Industrial": True
    }
    
    for curso, padrao in cursos.items():
        cursos[curso] = st.checkbox(curso, value=padrao)
    
    # Botão de salvar configurações
    if st.button("💾 Salvar Configurações"):
        st.session_state.timeout = timeout
        st.session_state.cursos_selecionados = [c for c, s in cursos.items() if s]
        st.success("Configurações salvas com sucesso!")
    
    # Informações do sistema
    st.subheader("Informações do Sistema")
    
    col_info1, col_info2 = st.columns(2)
    
    with col_info1:
        st.metric("Status do Login", 
                 "✅ Logado" if st.session_state.logado else "❌ Deslogado")
        if st.session_state.usuario:
            st.metric("Usuário", st.session_state.usuario[:10] + "...")
    
    with col_info2:
        st.metric("Modo de Operação", 
                 "Manual" if st.session_state.get('modo_manual', False) else "Automático")
    
    # Botão de logout
    if st.session_state.logado:
        if st.button("🚪 Logout", type="secondary"):
            st.session_state.logado = False
            st.session_state.usuario = None
            st.session_state.modo_manual = False
            st.success("Logout realizado com sucesso!")
            st.rerun()

if __name__ == "__main__":
    main()
