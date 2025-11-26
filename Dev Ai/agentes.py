from google.adk.agents import LlmAgent
import textwrap
import os
import google.generativeai as genai # ⬅️ Novo import

os.environ["GOOGLE_API_KEY"] = "key"
try:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
except Exception as e:
    print(f"Erro ao configurar o cliente Gemini: {e}")

########################################################## INSTRUÇÕES ####################################################

instrucao_eng_software = textwrap.dedent("""\
    Você é um engenheiro de software renomado. 
    Sua tarefa é receber um pedido vago e transformá-lo em uma especificação técnica detalhada e clara para o desenvolvedor.
    Defina funções, entradas, saídas e requisitos. Não defina nada além do que foi especificado pelo cliente, e nem altere o pedido dele.
    Sempre se atenha ao que foi pedido pelo usuário.
    Repasse também o prompt do usuário para o desenvolvedor, exatamente como foi escrito.
    NÃO escreva código, apenas a especificação.""")

instrucao_dev = textwrap.dedent("""\
    Você é um DEV Senior. 
    1. Se receber uma especificação técnica, crie o código Python correspondente seguindo boas práticas e PEP8.
    2. Se receber uma lista de tarefas/feedback de erros, reescreva o código corrigindo TODOS os pontos apontados.
    Faça o código em português. Se atente ao pedido do usuário, não extrapole ou mude o que foi pedido. Faça apenas a versão de produção
    do software, para que o cliente apenas pegue, compile e use. Não deixe resquícios de variáveis de teste ou sugestões.
    SAÍDA: O bloco de código Python e o prompt do usuário exatamente como foi recebido.""")

instrucao_revisor = textwrap.dedent("""\
    Você é um revisor de código. Analise erros de sintaxe e PEP8. Se atenha ao que o usuário pediu
    - Se encontrar erros: Liste-os.
    - Se o código estiver perfeito sintaticamente: Responda APENAS com a frase 'STATUS: APROVADO'.""")

instrucao_beta_tester = textwrap.dedent("""\
    Você é um Beta Tester. Tente quebrar a lógica do código.
    - Se encontrar falhas ou bugs lógicos: Descreva-os. 
    - Se a lógica estiver sólida: Responda APENAS com a frase 'STATUS: APROVADO'.""")

instrucao_controle_qualidade = textwrap.dedent("""\
    Você é o QA (Controle de Qualidade). Avalie a experiência e requisitos.
    - Se houver problemas de usabilidade ou requisitos não atendidos: Liste-os.
    - Se estiver tudo excelente: Responda APENAS com a frase 'STATUS: APROVADO'.""")

instrucao_gerente_lancamento = textwrap.dedent("""\
    Você é o Release Manager. Leia os relatórios do Revisor, Beta Tester e QA.
    Regras Rígidas:
    1. Se E SOMENTE SE os três relatórios contiverem a frase 'STATUS: APROVADO':
       Sua resposta deve ser EXATAMENTE: 'TERMINATE'.
    2. Caso contrário (se houver qualquer erro):
       Consolide todos os feedbacks negativos em uma lista de tarefas para o Dev e mande de volta.
       Repasse também o prompt inicial do usuário
       NÃO gere código. Apenas as instruções de correção.""")

####################################################### AGENTES ############################################################

eng_software = LlmAgent(
    name="eng_software",
    model="gemini-2.5-pro",
    description="Decidir qual a melhor forma de desenvolver uma aplicação",
    instruction=instrucao_eng_software
)

dev = LlmAgent(
    name="dev",
    model="gemini-2.5-pro",
    description="Codificar a aplicação conforme instrução do engenheiro de software",
    instruction=instrucao_dev
)

revisor = LlmAgent(
    name="Revisor",
    model="gemini-2.5-pro",
    description="Revisar erros no código do desenvolvedor que impedem a compilação do mesmo",
    instruction=instrucao_revisor
)

beta_tester = LlmAgent(
    name="beta_tester",
    model="gemini-2.5-pro",
    description="Testar o código do desenvolvedor para procurar possíveis bugs e mal funcionamento",
    instruction=instrucao_beta_tester
)

controle_qualidade = LlmAgent(
    name="controle_qualidade",
    model="gemini-2.5-pro",
    description="Garantir que o usuário da aplicação recebida tenha uma boa experiência com o seu produto",
    instruction=instrucao_controle_qualidade
)

gerente_lancamento = LlmAgent(
    name="gerente_lancamento",
    model="gemini-2.5-pro",
    description="Gerente que decide se o software vai para produção.",
    instruction=instrucao_gerente_lancamento        
)

# ... (Mantenha todos os seus imports e definições de Agentes) ...

####################################################### FUNÇÃO DE EXECUÇÃO SÍNCRONA ############################################################

def executar_agente_sincronamente(agente, entrada):
    """
    Substitui o método .run(). Usa o SDK do Gemini diretamente para 
    garantir uma chamada síncrona e retorna uma string pura.
    """
    # Combina a instrução do agente e a entrada de trabalho
    prompt_completo = (
        f"Instrução do Agente '{agente.name}' ({agente.description}): {agente.instruction}\n\n"
        f"ENTRADA DE TRABALHO: {entrada}"
    )

    client = genai.GenerativeModel(model_name=agente.model)
    
    try:
        # 🚨 CORREÇÃO FINAL AQUI 🚨
        # Usamos 'temperature' diretamente ou em um dicionário generation_config simples.
        response = client.generate_content(
            contents=prompt_completo,
            # Passamos a temperatura como um argumento nomeado simples
            # Se a sua versão não aceitar 'config', esta é a sintaxe mais comum
            generation_config={'temperature': 0.0} 
        )
        return response.text
    except Exception as e:
        # Se ocorrer uma falha, retornamos a mensagem de erro.
        return f"ERRO DE EXECUÇÃO DO LLM PARA {agente.name}: {e}"
    
####################################################### EXECUÇÃO ############################################################

if __name__ == "__main__":
    print("\n--- Sistema Iniciado ---")
    pedido_do_cliente = input(">> Digite o software que você quer criar: ")

    # 1. Engenheiro Gera a Spec
    print(f"\n[1] Engenheiro gerando especificação...")
    especificacao = executar_agente_sincronamente(eng_software, pedido_do_cliente)    

    # Variáveis de Controle do Loop
    entrada_atual = especificacao
    ultimo_codigo_valido = ""
    max_iteracoes = 30
    iteracao_atual = 0
    loop_terminado = False

    print("\n--- [2] Iniciando Loop de Desenvolvimento (Controle Manual) ---")

    while iteracao_atual < max_iteracoes and not loop_terminado:
        iteracao_atual += 1
        print(f"\n🔄 ITERAÇÃO {iteracao_atual} de {max_iteracoes}")

        # A. Desenvolvedor trabalha (Cria ou Corrige)
        # O output dele é o código que queremos salvar
        codigo_gerado = executar_agente_sincronamente(dev, entrada_atual)        
        ultimo_codigo_valido = codigo_gerado 
        print(f"   -> Dev gerou nova versão do código.")

        # B. Verificadores analisam o código gerado
        print("   -> Rodando verificadores...")
        # Dica: Passamos o código para eles analisarem
        analise_revisor = executar_agente_sincronamente(revisor, f"Analise este código:\n{codigo_gerado}")
        analise_tester = executar_agente_sincronamente(beta_tester, f"Teste este código:\n{codigo_gerado}")
        analise_qa = executar_agente_sincronamente(controle_qualidade, f"Verifique qualidade deste código:\n{codigo_gerado}")

        # C. Compilando os relatórios para o Gerente
        relatorio_completo = (
            f"Relatório Revisor: {analise_revisor}\n"
            f"Relatório Tester: {analise_tester}\n"
            f"Relatório QA: {analise_qa}"
        )

        # D. Gerente Decide
        decisao = executar_agente_sincronamente(gerente_lancamento, relatorio_completo)   

        # Lógica de Parada
        if "TERMINATE" in decisao:
            print("   ✅ GERENTE APROVOU! O loop será encerrado.")
            loop_terminado = True
        else:
            print("   ❌ GERENTE REPROVOU. Feedback enviado ao Dev.")
            # O feedback do gerente vira a entrada para o Dev na próxima volta
            entrada_atual = decisao

    # --- RESULTADO FINAL ---
    print(f"\n==============================================")
    if loop_terminado:
        print(f"SUCESSO! Projeto concluído em {iteracao_atual} iterações.")
        print(f"==============================================\n")
        print(f"--- CÓDIGO FINAL ---\n{ultimo_codigo_valido}")
    else:
        print(f"FALHA! O limite de {max_iteracoes} iterações foi atingido sem consenso.")
        print(f"Última versão do código:\n{ultimo_codigo_valido}")