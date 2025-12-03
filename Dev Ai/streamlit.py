import streamlit as st
import time
import re 
from typing import Tuple

try:
    from agente_workflow import executar_workflow_de_desenvolvimento, CHAVE_API
except ImportError:
    st.error("🚨 Erro de Importação: Certifique-se de que o arquivo 'agente_workflow.py' está no mesmo diretório e não tem erros de sintaxe.")
    st.stop()
except Exception as e:
    st.error(f"Erro ao carregar o módulo: {e}")
    st.stop()


# ---------------------------------------------------------
# INICIALIZAÇÃO DE ESTADO E CALLBACKS
# ---------------------------------------------------------
if 'workflow_em_execucao' not in st.session_state:
    st.session_state.workflow_em_execucao = False
if 'abort_workflow' not in st.session_state:
    st.session_state.abort_workflow = False

def set_start_flag():
    """Callback para iniciar o workflow."""
    st.session_state.workflow_em_execucao = True
    st.session_state.abort_workflow = False 

def set_abort_flag():
    """Callback para definir o flag de interrupção."""
    st.session_state.abort_workflow = True

def extrair_codigo_base(texto_cliente: str) -> Tuple[str, str]:
    """
    Extrai o código base do pedido do cliente usando um marcador.
    """
    match = re.search(r"(?:CÓDIGO DADO:|CÓDIGO BASE:)\s*(.*)", texto_cliente, re.DOTALL | re.IGNORECASE)
    
    if match:
        codigo = match.group(1).strip()
        codigo = re.sub(r"```python\s*|```", "", codigo).strip()
        pedido_textual = texto_cliente.replace(match.group(0), "").strip()
        return pedido_textual, codigo
    
    return texto_cliente, "" 

# ---------------------------------------------------------
# INTERFACE STREAMLIT
# ---------------------------------------------------------

st.set_page_config(page_title="Agente Desenvolvedor Gemini", layout="wide")

st.title("🤖 Agente Desenvolvedor com Ciclo de QA (Gemini)")
st.caption(f"Status da API: {'🔑 Configurada' if CHAVE_API else '🚨 Chave Ausente'}")

if not CHAVE_API:
    st.warning("A variável de ambiente `GOOGLE_API_KEY` não está configurada ou está inválida.")

# Texto padrão genérico
texto_padrao_generico = (
    "Descreva a funcionalidade que você deseja criar (e a linguagem de preferência, ex: Java, JavaScript, Python).\n"
    "Se houver um código existente para modificar, cole-o no final.\n\n"
    "CÓDIGO DADO:\n"
    "// Cole seu código aqui, se aplicável"
)

pedido_completo = st.text_area(
    "📝 Pedido do Cliente:",
    height=300,
    placeholder=texto_padrao_generico,
    disabled=st.session_state.workflow_em_execucao 
)

# Configurações adicionais
st.sidebar.header("⚙️ Configurações do Workflow")
max_iter = st.sidebar.slider(
    "Número Máximo de Iterações", 
    min_value=5, 
    max_value=30, 
    value=10, 
    disabled=st.session_state.workflow_em_execucao
)

# CONTROLES DE INÍCIO E PARADA
col1, col2 = st.columns([1, 1])

col1.button(
    "🚀 Iniciar Workflow de Desenvolvimento", 
    disabled=st.session_state.workflow_em_execucao,
    on_click=set_start_flag 
)

col2.button(
    "🚫 Abortar Operação", 
    disabled=not st.session_state.workflow_em_execucao, 
    on_click=set_abort_flag
)

# ---------------------------------------------------------
# LÓGICA DE EXECUÇÃO DO WORKFLOW
# ---------------------------------------------------------

if st.session_state.workflow_em_execucao:
    # --- Validação de Início ---
    if not pedido_completo:
        st.warning("Por favor, insira um pedido válido para iniciar.")
        st.session_state.workflow_em_execucao = False
        st.stop()
        
    # 1. Extrai o código base
    pedido_textual, codigo_base_extraido = extrair_codigo_base(pedido_completo)

    # 2. Inicia o feedback em tempo real
    st.divider()
    
    # Placeholders para o display dinâmico
    status_box = st.empty()
    progresso_bar = st.progress(0, text="Aguardando...")
    
    # Container para o histórico detalhado
    st.subheader("📜 Histórico de Iterações e Reprovações")
    historico = st.container()

    start_time = time.time()
    iter_total = 0
    
    # Variável para controlar o expander atual fora do loop
    expander_atual = None

    try:
        # Itera sobre o gerador do workflow para obter atualizações
        for update in executar_workflow_de_desenvolvimento(
            pedido_do_cliente=pedido_textual,
            codigo_base=codigo_base_extraido,
            max_iteracoes=max_iter
        ):
            # 3. Atualiza o status e o histórico
            status_type = update.get("status")
            iter_total = update.get("iteracao", iter_total)
            mensagem = update.get("mensagem")

            # Atualiza a barra de progresso
            if status_type in ["iteracao_inicio", "dev_completo", "feedback"]:
                 progresso_value = iter_total / max_iter
                 progresso_bar.progress(progresso_value, text=f"Iteração {iter_total}/{max_iter}")
            
            # --- LÓGICA DE VISUALIZAÇÃO DETALHADA ---
            
            if status_type == "iniciado":
                status_box.info(f"➡️ **{mensagem}**")
                
            elif status_type == "engenheiro_completo":
                status_box.success(f"➡️ **{mensagem}**")
                
            elif status_type == "iteracao_inicio":
                status_box.info(f"**Trabalhando na Iteração {iter_total}...**")
                # Cria um novo expander para esta iteração dentro do histórico
                # 'expanded=True' mantém aberto para ver o progresso atual
                with historico:
                    expander_atual = st.expander(f"🔄 Detalhes da Iteração {iter_total}", expanded=True)
                    expander_atual.markdown("---")
            
            elif status_type == "dev_completo":
                if expander_atual:
                    expander_atual.info("🛠️ **Dev:** Código gerado e enviado para verificação.")

            elif status_type == "analise":
                status_box.caption(f"Analisando: {mensagem}")
                # Mostra o relatório do verificador dentro do expander
                if expander_atual:
                    agente_nome = update.get("agente")
                    # Formatação visual para cada agente
                    icon = "🕵️" if "Revisor" in agente_nome else "🧪" if "Beta" in agente_nome else "🛡️"
                    expander_atual.markdown(f"**{icon} {agente_nome}:** {mensagem.split(':', 1)[1]}")

            elif status_type == "verificadores_completos":
                status_box.info(mensagem)

            elif status_type == "feedback":
                # AQUI ESTÁ O MOTIVO DA REPROVAÇÃO
                status_box.warning(f"⚠️ Iteração {iter_total}: Código Reprovado.")
                if expander_atual:
                    expander_atual.error("❌ **GERENTE REPROVOU**")
                    expander_atual.markdown("**Motivo / Feedback enviado ao Dev:**")
                    # Exibe o feedback completo como código para facilitar leitura
                    # A mensagem aqui contém o texto extraído do 'else' no agente_workflow.py
                    expander_atual.code(mensagem, language='text')

            time.sleep(0.1) 
            
            # 4. Lógica de Término
            if status_type == "terminado":
                sucesso = update.get("sucesso")
                resultado = update.get("codigo") if sucesso else update.get("mensagem")
                linguagem = update.get("linguagem", "python")

                progresso_bar.empty()
                status_box.empty()
                
                st.markdown(f"---")
                st.markdown(f"**Tempo Total:** `{time.time() - start_time:.2f} segundos`")
                
                if sucesso:
                    st.success("🎉 Projeto Concluído e Aprovado!")
                    st.subheader("Código Final:")
                    st.code(resultado, language=linguagem)
                else:
                    st.error("🚨 Workflow Interrompido ou Falhou.")
                    st.subheader("Último Estado / Erro:")
                    st.text_area("Detalhes", resultado, height=300)

                # Limpeza final do estado sem rerun imediato para manter o resultado na tela
                st.session_state.workflow_em_execucao = False
                st.session_state.abort_workflow = False
                break
                
    except Exception as e:
        status_box.error(f"❌ Erro Crítico durante o Workflow: {e}")
        progresso_bar.empty()
        st.session_state.workflow_em_execucao = False
        st.session_state.abort_workflow = False