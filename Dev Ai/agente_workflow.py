from google.adk.agents import LlmAgent
import textwrap
import os
import google.generativeai as genai 
from google.api_core import exceptions
import streamlit as st # Necessário para acessar st.session_state

# ---------------------------------------------------------
# CONFIGURAÇÃO E CHAVE API
# ---------------------------------------------------------

# Use a chave hardcoded fornecida (MUITO CUIDADO com isso em código público!)
# Prioriza a variável de ambiente, depois o valor padrão
CHAVE_API = os.getenv("GOOGLE_API_KEY", "key")
os.environ["GOOGLE_API_KEY"] = CHAVE_API

try:
    # A configuração global é feita aqui na importação
    genai.configure(api_key=CHAVE_API)
except Exception as e:
    print(f"Erro ao configurar o cliente Gemini: {e}")

# ---------------------------------------------------------
# INSTRUÇÕES DOS AGENTES
# ---------------------------------------------------------

instrucao_eng_software = textwrap.dedent("""\
    Você é um engenheiro de software renomado. Sua tarefa é receber o 'PEDIDO DO CLIENTE' (que pode conter um código existente
    e/ou uma nova funcionalidade) e transformá-lo em uma especificação técnica detalhada e clara para o desenvolvedor.

    1. **Fidelidade:** Mantenha total fidelidade ao que foi solicitado. Não altere nem adicione funcionalidades não pedidas.
    2. **Nova Funcionalidade/Criação:** Se houver código existente, a especificação deve focar em como a nova funcionalidade 
    será integrada ao código fornecido. Se não houver código, gere a especificação para criação do zero.
    
    Sua resposta deve ser dividida em duas seções CLARAS, para garantir que o contexto não se perca:

    --- ESPECIFICACAO TECNICA ---
    [Defina funções, entradas, saídas e requisitos da nova aplicação OU da nova funcionalidade. NÃO escreva código.]

    --- CONTEXTO ORIGINAL DO CLIENTE ---
    [Cole o 'PEDIDO DO CLIENTE' exatamente como foi recebido, incluindo qualquer código existente e o prompt original.]
    """)

instrucao_dev = textwrap.dedent("""\
    Você é um DEV Senior. Você receberá uma 'ESPECIFICACAO TECNICA' e o 'CONTEXTO ORIGINAL DO CLIENTE'.

    1. **Prioridade Máxima:** Codifique a solução conforme a especificação.
    2. **Código Base (Memória):** O código original (se aplicável) **NÃO ESTÁ NO PROMPT**. Ele está na sua memória.
       - Se o 'CONTEXTO ORIGINAL' indicar que o código base é **APLICÁVEL**, você **DEVE** modificar o código que está na sua memória (use-o como ponto de partida).
       - Se o 'CONTEXTO ORIGINAL' indicar **NÃO APLICÁVEL**, crie o código do zero (Ex: o Streamlit).
    3. **Caso o contexto do cliente inclua a criação de uma nova classe com base no código passado, sua especificação deve detalhar:
       - Quais funções/métodos da classe existente a nova classe deve importar?
       - Quais variáveis da classe existente a nova classe deve importar?
       - Como a nova classe irá implementar a classe passada pelo usuário?
    4. **Em caso de Feedback (Correção):** Se a entrada for apenas uma lista de tarefas/feedback de erros, reescreva o código 
    corrigindo TODOS os pontos apontados, mas **use o CONTEXTO ORIGINAL** para saber qual código corrigir e qual a funcionalidade
     pedida.

    Sua resposta deve ser estruturada exatamente assim:

    --- CODIGO PYTHON ---
    [Cole o bloco de código Python final, pronto para ser usado.]

    --- CONTEXTO ORIGINAL DO CLIENTE ---
    [Cole o 'CONTEXTO ORIGINAL DO CLIENTE' sem o código, caso algum tenha sido recebido. O restante, 
    repasse exatamente como recebido do Engenheiro/Gerente.]
    """)

instrucao_revisor = textwrap.dedent("""\
    Você é um revisor de código. Analise erros de sintaxe e PEP8. Se atenha ao que o usuário pediu, 
    verificando se o código atende o CONTEXTO ORIGINAL.
    - Se encontrar erros: Liste-os.
    - Se o código estiver perfeito sintaticamente E atender ao contexto original: Responda APENAS com a frase 'STATUS: APROVADO'.""")

instrucao_beta_tester = textwrap.dedent("""\
    Você é um Beta Tester. Tente quebrar a lógica do código, focando na funcionalidade pedida no CONTEXTO ORIGINAL.
    - Se encontrar falhas ou bugs lógicos: Descreva-os. 
    - Se a lógica estiver sólida E atender ao contexto original: Responda APENAS com a frase 'STATUS: APROVADO'.""")

instrucao_controle_qualidade = textwrap.dedent("""\
    Você é o QA (Controle de Qualidade). Avalie a experiência e requisitos, garantindo que o código final atenda ao CONTEXTO ORIGINAL 
    do cliente.
    - Se houver problemas de usabilidade ou requisitos não atendidos: Liste-os.
    - Se estiver tudo excelente E atender ao contexto original: Responda APENAS com a frase 'STATUS: APROVADO'.""")

instrucao_gerente_lancamento = textwrap.dedent("""\
    Você é o Release Manager. Leia os relatórios do Revisor, Beta Tester e QA.
    Regras Rígidas:
    1. Se E SOMENTE SE os três relatórios contiverem a frase 'STATUS: APROVADO':
        Sua resposta deve ser EXATAMENTE: 'TERMINATE'.
    2. Caso contrário (se houver qualquer erro):
        Consolide todos os feedbacks negativos em uma lista de tarefas CLARAS para o Dev. 
        **Você DEVE incluir o 'CONTEXTO ORIGINAL DO CLIENTE' (que está na sua entrada de trabalho) na sua resposta**, 
        para que o Dev saiba qual código corrigir e qual funcionalidade implementar/corrigir.
        NÃO gere código. Apenas as instruções de correção e o contexto original formatados como 
        '--- CONTEXTO ORIGINAL DO CLIENTE --- [Conteúdo]'.
    """)

# ---------------------------------------------------------
# DEFINIÇÃO DOS AGENTES
# ---------------------------------------------------------

eng_software = LlmAgent(
    name="eng_software", 
    model="gemini-2.5-flash", 
    description="Decidir qual a melhor forma de desenvolver uma aplicação", 
    instruction=instrucao_eng_software)

dev = LlmAgent(
    name="dev", 
    model="gemini-2.5-flash", 
    description="Codificar a aplicação conforme instrução do engenheiro de software", 
    instruction=instrucao_dev)

revisor = LlmAgent(
    name="Revisor", 
    model="gemini-2.5-flash", 
    description="Revisar erros no código do desenvolvedor que impedem a compilação do mesmo", 
    instruction=instrucao_revisor)

beta_tester = LlmAgent(
    name="beta_tester", 
    model="gemini-2.5-flash", 
    description="Testar o código do desenvolvedor para procurar possíveis bugs e mal funcionamento", 
    instruction=instrucao_beta_tester)

controle_qualidade = LlmAgent(
    name="controle_qualidade", 
    model="gemini-2.5-flash", 
    description="Garantir que o usuário da aplicação recebida tenha uma boa experiência com o seu produto", 
    instruction=instrucao_controle_qualidade)

gerente_lancamento = LlmAgent(
    name="gerente_lancamento", 
    model="gemini-2.5-flash", 
    description="Gerente que decide se o software vai para produção.", 
    instruction=instrucao_gerente_lancamento) 

# Lista de agentes para uso no workflow
AGENTES_VERIFICADORES = [revisor, beta_tester, controle_qualidade]
AGENTE_GERENTE = gerente_lancamento

# ---------------------------------------------------------
# FUNÇÃO DE EXECUÇÃO SÍNCRONA
# ---------------------------------------------------------

def executar_agente_sincronamente(agente, entrada, codigo_base_na_memoria=None):
    """
    Função wrapper para executar um agente Gemini, com injeção de código base
    para o DEV quando necessário.
    """
    prompt_injetado = ""
    # Injeção de memória ocorre apenas para o DEV e se o código base for aplicável
    if agente.name == "dev" and codigo_base_na_memoria and 'APLICÁVEL' in entrada:
        prompt_injetado = (
            f"\n\n🚨 CÓDIGO BASE NA MEMÓRIA (INÍCIO DO TRABALHO) 🚨\n"
            f"{codigo_base_na_memoria}"
            f"\n🚨 CÓDIGO BASE NA MEMÓRIA (FIM DO TRABALHO) 🚨\n"
        )
            
    prompt_completo = (
        f"Instrução do Agente '{agente.name}' ({agente.description}): {agente.instruction}\n\n"
        f"{prompt_injetado}" 
        f"ENTRADA DE TRABALHO: {entrada}"
    )
    
    # O cliente pega a chave do os.environ, que foi configurada no topo do arquivo.
    client = genai.GenerativeModel(model_name=agente.model)
    
    try:
        response = client.generate_content(
            contents=prompt_completo,
            generation_config={'temperature': 0.0} 
        )
        return response.text
    except exceptions.ResourceExhausted:
         return f"ERRO DE EXECUÇÃO DO LLM PARA {agente.name}: Limite de quota excedido."
    except Exception as e:
        return f"ERRO DE EXECUÇÃO DO LLM PARA {agente.name}: {e}"

# ---------------------------------------------------------
# FUNÇÃO PRINCIPAL DO WORKFLOW (GERADOR COM CHECK DE ABORT)
# ---------------------------------------------------------

def executar_workflow_de_desenvolvimento(pedido_do_cliente: str, codigo_base: str = "", max_iteracoes: int = 10):
    """
    Executa o ciclo completo de agentes, checando se há um pedido de interrupção 
    na st.session_state em cada iteração e retornando o status (yield).
    """
    
    # 1. Engenheiro Gera a Spec
    yield {"status": "iniciado", "mensagem": "1. Engenheiro gerando especificação técnica..."}
    entrada_engenheiro = f"PEDIDO TEXTUAL: {pedido_do_cliente}\n\nStatus do Código Base: {'Presente' if codigo_base else 'Ausente'}"
    especificacao_e_contexto = executar_agente_sincronamente(eng_software, entrada_engenheiro)

    entrada_atual = especificacao_e_contexto
    ultimo_codigo_valido = "Nenhuma tentativa de código ainda."
    contexto_original_dev = ""
    loop_terminado = False
    
    # Inferência de linguagem para o destaque de sintaxe na UI
    linguagem_pedida = "python"
    if "javascript" in pedido_do_cliente.lower() or "js" in pedido_do_cliente.lower():
        linguagem_pedida = "javascript"
    elif "java" in pedido_do_cliente.lower():
        linguagem_pedida = "java"
    elif "html" in pedido_do_cliente.lower() or "css" in pedido_do_cliente.lower():
        linguagem_pedida = "html"
    
    yield {"status": "engenheiro_completo", "mensagem": "✅ Especificação gerada. Iniciando loop de desenvolvimento."}

    for iteracao_atual in range(1, max_iteracoes + 1):
        
        # 💥 CHECAGEM DE INTERRUPÇÃO 💥
        if st.session_state.get('abort_workflow', False):
            yield {"status": "terminado", "sucesso": False, "codigo": ultimo_codigo_valido, "linguagem": linguagem_pedida, "mensagem": "🚫 Operação abortada pelo usuário."}
            st.session_state['abort_workflow'] = False # Reseta o flag
            return

        yield {"status": "iteracao_inicio", "iteracao": iteracao_atual, "mensagem": f"🔄 Iteração {iteracao_atual}/{max_iteracoes}: Desenvolvedor trabalhando..."}
        
        # A. Desenvolvedor trabalha
        codigo_e_contexto = executar_agente_sincronamente(dev, entrada_atual, codigo_base_na_memoria=codigo_base)

        # 💥 Lógica de Parsing
        if "--- CONTEXTO ORIGINAL DO CLIENTE ---" in codigo_e_contexto:
             parts = codigo_e_contexto.split("--- CONTEXTO ORIGINAL DO CLIENTE ---", 1)
             codigo_gerado = parts[0].replace("--- CODIGO PYTHON ---", "").strip()
             contexto_original_dev = "--- CONTEXTO ORIGINAL DO CLIENTE ---" + parts[1].strip()
        else:
             codigo_gerado = codigo_e_contexto 
             contexto_original_dev = entrada_atual
        
        ultimo_codigo_valido = codigo_gerado
        yield {"status": "dev_completo", "iteracao": iteracao_atual, "mensagem": f"🛠️ Código gerado. Rodando verificadores..."}

        # B. Verificadores analisam
        relatorios = []
        aprovados = 0
        for agente in AGENTES_VERIFICADORES:
            analise_input = f"Pedido do Cliente: {pedido_do_cliente}\n\nAnalise o seguinte código:\n{codigo_gerado}"
            relatorio = executar_agente_sincronamente(agente, analise_input)
            relatorios.append(relatorio)
            if 'STATUS: APROVADO' in relatorio:
                 aprovados += 1
            yield {"status": "analise", "agente": agente.name, "mensagem": f"   -> {agente.name}: {relatorio.split(':')[0]}..."}
        
        yield {"status": "verificadores_completos", "iteracao": iteracao_atual, "mensagem": f"🔎 Análise concluída ({aprovados}/{len(AGENTES_VERIFICADORES)} aprovados). Gerente decidindo..."}

        # C. Gerente Decide
        relatorio_completo = "\n".join(relatorios)
        gerente_input = f"RELATÓRIOS DOS REVISORES:\n{relatorio_completo}\n\nCONTEXTO NECESSÁRIO PARA O FEEDBACK:\n{contexto_original_dev}"
        decisao = executar_agente_sincronamente(AGENTE_GERENTE, gerente_input) 

        # D. Lógica de Parada
        if "TERMINATE" in decisao:
            loop_terminado = True
            yield {"status": "terminado", "sucesso": True, "codigo": ultimo_codigo_valido, "linguagem": linguagem_pedida}
            return
        else:
            entrada_atual = decisao
            yield {"status": "feedback", "iteracao": iteracao_atual, "mensagem": f"❌ Reprovado. Feedback enviado ao Dev:\n{decisao.split('--- CONTEXTO ORIGINAL DO CLIENTE ---')[0].strip()}"}

    # Se atingir o limite de iterações sem TERMINATE
    yield {"status": "terminado", "sucesso": False, "codigo": ultimo_codigo_valido, "linguagem": linguagem_pedida, "mensagem": f"Falha: Limite de {max_iteracoes} iterações atingido sem consenso."}