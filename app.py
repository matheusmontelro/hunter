import streamlit as st
from dotenv import load_dotenv
import os
import sys
from datetime import datetime, timezone, timedelta
import re
from funil_vendas import FunilVendas
from langchain_setup import AnaliseFunilChain
import phonenumbers
from phonenumbers import PhoneNumberFormat, NumberParseException
import pycountry
from PIL import Image
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import streamlit as st
import plotly.graph_objects as go
from bokeh.models import Div
from babel.numbers import format_currency
import re
import base64

# Configuração inicial
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
# load_dotenv()

# Configuração do Google Sheets
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
google_sheets_creds_raw = st.secrets["GOOGLE_SHEETS_CREDENTIALS"]

try:
    # Tenta decodificar se estiver em Base64
    google_sheets_creds = json.loads(base64.b64decode(google_sheets_creds_raw))
except:
    # Se falhar, assume que já está em formato JSON
    google_sheets_creds = json.loads(google_sheets_creds_raw)

creds = ServiceAccountCredentials.from_json_keyfile_dict(google_sheets_creds, scope)
try:
    client = gspread.authorize(creds)
except Exception as e:
    st.error(f"Erro ao autorizar Google Sheets: {str(e)}")
    st.stop()

# Abrir a planilha usando o ID
spreadsheet_id = '1MegMHoZGKnAWW9cy4ybe-gxCEef5m5TfHuuH1Gdzdis'
try:
    sheet = client.open_by_key(spreadsheet_id).worksheet('LEADS - Diagnóstico')
except Exception as e:
    st.error(f"Erro ao conectar com o Google Sheets: {str(e)}")
    st.stop()

def clean_text(text):
    # Remove caracteres não imprimíveis, mantendo quebras de linha
    text = ''.join(char for char in text if char.isprintable() or char in ['\n', '\r'])
    
    # Corrige formatação de valores monetários
    text = re.sub(r'R\$\s*(\d+)[\.,](\d+)', r'R$ \1,\2', text)
    
    # Remove asteriscos e números no início das linhas
    lines = [re.sub(r'^[\d\.\s\*]+', '', line.strip()) for line in text.split('\n')]
    
    # Remove linhas vazias
    lines = [line for line in lines if line]
    
    # Agrupa linhas em parágrafos
    paragraphs = []
    current_paragraph = []
    for line in lines:
        if line.endswith((':','.')) or len(line) > 100:
            if current_paragraph:
                paragraphs.append(' '.join(current_paragraph))
                current_paragraph = []
            paragraphs.append(line)
        else:
            current_paragraph.append(line)
    if current_paragraph:
        paragraphs.append(' '.join(current_paragraph))
    
    # Junta os parágrafos com duas quebras de linha
    text = '\n\n'.join(paragraphs)
    
    return text

# Função para inserir dados no Google Sheets
def inserir_dados_sheets(dados):
    try:
        tz = timezone(timedelta(hours=-3))
        agora = datetime.now(tz)
        data_entrada = agora.strftime("%d/%m/%Y %H:%M")
        data_atual = agora.strftime("%d/%m/%Y")
        
        telefone_formatado = ''.join(filter(str.isdigit, dados['telefone']))
        if not telefone_formatado.startswith('55'):
            telefone_formatado = '55' + telefone_formatado

        try:
            cell = sheet.find(telefone_formatado, in_column=5)
            if cell:
                return True
        except gspread.exceptions.CellNotFound:
            pass

        row = [
            data_entrada,
            data_atual,
            dados['nome'],
            dados['email'],
            telefone_formatado,
            dados['nome_clinica'],
            dados['funcao'],
            dados['num_vendedores'],
            dados['investimento_anuncios'],
            'Streamlit',
            'Form',
            'HunterAI',
            'Diagnóstico'
        ]
        
        sheet.append_row(row)
        return True
    except Exception as e:
        print(f"Erro ao inserir dados: {str(e)}")
        return False

# Carregamento da imagem para o avatar
image_path = "arquivos/favicon-bio-1024x1024-1-_1_.webp"
avatar_image = Image.open(image_path) if os.path.exists(image_path) else None

# Funções auxiliares
def format_brl(value):
    try:
        return format_currency(value, 'BRL', locale='pt_BR')
    except:
        return f"R$ {value}"

def parse_brl(valor_str):
    try:
        valor = float(valor_str.replace("R$", "").replace(".", "").replace(",", ".").strip())
        return valor
    except:
        return None

def validar_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

def formatar_telefone(numero, codigo_pais):
    try:
        numero_parseado = phonenumbers.parse(numero, codigo_pais)
        if phonenumbers.is_valid_number(numero_parseado):
            return phonenumbers.format_number(numero_parseado, PhoneNumberFormat.INTERNATIONAL)
        else:
            return None
    except NumberParseException:
        return None

# Inicialização
funil = FunilVendas()
api_key = st.secrets["OPENAI_API_KEY"]
if not api_key:
    st.error("Erro de configuração. Por favor, tente novamente mais tarde.")
    st.stop()

try:
    analise_chain = AnaliseFunilChain(api_key=api_key, funil_vendas=funil)
except Exception as e:
    st.error(f"Erro ao inicializar a análise do funil: {str(e)}")
    st.stop()

# Interface Streamlit
st.title("HunterAI - Análise do Funil de Vendas para Clínicas Odontológicas")

# Inicialização do estado da sessão
if 'stage' not in st.session_state:
    st.session_state['stage'] = 'qualification'
if 'qualification_data' not in st.session_state:
    st.session_state['qualification_data'] = {}
if 'messages' not in st.session_state:
    st.session_state['messages'] = []
if 'pergunta_atual' not in st.session_state:
    st.session_state['pergunta_atual'] = 0
if 'collected_data' not in st.session_state:
    st.session_state['collected_data'] = {}

# Dados e configurações
meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

correcoes = {
    "nome": "Nome", "email": "Email", "nome_clinica": "Nome da Clínica", "funcao": "Função",
    "num_vendedores": "Número de Vendedores", "investimento_anuncios": "Investimento em Anúncios",
    "telefone": "Telefone", "mes": "Mês", "leads": "Leads", "agendamentos": "Agendamentos",
    "comparecimentos": "Comparecimentos", "vendas": "Vendas", "valor_vendido": "Valor Vendido",
    "valor_orcamentos": "Valor de Orçamentos", "investimento_trafego": "Investimento em Tráfego"
}

qualification_questions = [
    {"pergunta": "Nome", "chave": "nome", "tipo": "text"},
    {"pergunta": "Email", "chave": "email", "tipo": "email"},
    {"pergunta": "Telefone", "chave": "telefone", "tipo": "phone"},
    {"pergunta": "Nome da Clínica", "chave": "nome_clinica", "tipo": "text"},
    {"pergunta": "Qual a sua função na clínica?", "chave": "funcao", "tipo": "text"},
    {"pergunta": "Quantos vendedores possui?", "chave": "num_vendedores", "tipo": "select", 
     "opcoes": ["Nenhum", "1", "2", "3", "4", "5", "Mais de 5"]},
    {"pergunta": "Investimento mensal em anúncios (R$)", "chave": "investimento_anuncios", "tipo": "select",
     "opcoes": ["Não invisto em anúncios", "Menos de R$1500,00 por mês", "De R$1500 a R$3.000 por mês", 
                "De R$3.000 a R$6.000 por mês", "De R$6.000 a R$10.000 por mês", "Mais de R$10.000 por mês"]}
]

perguntas_funil = [
    {"pergunta": "Qual o mês referente ao relatório?", "chave": "mes"},
    {"pergunta": "Quantos leads você gerou?", "chave": "leads"},
    {"pergunta": "Quantos agendamentos foram feitos?", "chave": "agendamentos"},
    {"pergunta": "Quantos comparecimentos ocorreram?", "chave": "comparecimentos"},
    {"pergunta": "Quantas vendas foram realizadas?", "chave": "vendas"},
    {"pergunta": "Qual o valor vendido (R$)?", "chave": "valor_vendido"},
    {"pergunta": "Qual o valor de orçamentos (R$)?", "chave": "valor_orcamentos"},
    {"pergunta": "Qual o investimento em tráfego (R$)?", "chave": "investimento_trafego"}
]

# Função para exibir perguntas de qualificação
def show_qualification_questions():
    paises = sorted([(country.alpha_2, country.name) for country in pycountry.countries], key=lambda x: x[1])
    brasil = next((pais for pais in paises if pais[0] == 'BR'), None)
    if brasil:
        paises.remove(brasil)
        paises.insert(0, brasil)

    codigo_pais_selecionado = st.selectbox(
        "Selecione o país de origem:",
        paises,
        format_func=lambda x: x[1],
        index=0
    )

    for question in qualification_questions:
        if question['tipo'] == 'text':
            st.session_state['qualification_data'][question['chave']] = st.text_input(question['pergunta'], key=question['chave'])
        elif question['tipo'] == 'email':
            email = st.text_input(question['pergunta'], key=question['chave'])
            if email and not validar_email(email):
                st.error("Por favor, insira um email válido.")
            else:
                st.session_state['qualification_data'][question['chave']] = email
        elif question['tipo'] == 'phone':
            telefone = st.text_input(question['pergunta'], key=question['chave'])
            if telefone:
                telefone_formatado = formatar_telefone(telefone, codigo_pais_selecionado[0])
                if telefone_formatado:
                    st.session_state['qualification_data'][question['chave']] = telefone_formatado
                else:
                    st.error("Por favor, insira um número de telefone válido.")
        elif question['tipo'] == 'select':
            st.session_state['qualification_data'][question['chave']] = st.selectbox(
                question['pergunta'], 
                question['opcoes'], 
                key=question['chave']
            )

    if st.button("Continuar para coleta de dados do funil"):
        if all(st.session_state['qualification_data'].values()):
            sucesso = inserir_dados_sheets(st.session_state['qualification_data'])
            if sucesso:
                st.session_state['stage'] = 'funnel_data'
                st.rerun()
        else:
            st.error("Por favor, preencha todos os campos antes de continuar.")

def calcular_metricas_atuais(dados):
    leads = dados['leads']
    agendamentos = dados['agendamentos']
    comparecimentos = dados['comparecimentos']
    vendas = dados['vendas']
    valor_vendido = dados['valor_vendido']
    valor_orcamentos = dados['valor_orcamentos']
    investimento_anuncios = dados['investimento_trafego']
    mes = dados.get('mes', 'Não informado')  # Retorna 'Não informado' se a chave 'mes' não estiver presente

    taxa_agendamento = agendamentos / leads if leads > 0 else 0
    taxa_comparecimento = comparecimentos / agendamentos if agendamentos > 0 else 0
    taxa_venda = vendas / comparecimentos if comparecimentos > 0 else 0
    ticket_medio = valor_vendido / vendas if vendas > 0 else 0
    valor_por_orcamento = valor_orcamentos / comparecimentos if comparecimentos > 0 else 0

    return {
        'mes': mes,
        'leads': leads,
        'agendamentos': agendamentos,
        'comparecimentos': comparecimentos,
        'vendas': vendas,
        'valor_vendido': valor_vendido,
        'valor_orcamentos': valor_orcamentos,
        'investimento_anuncios': investimento_anuncios,
        'taxa_agendamento': taxa_agendamento,
        'taxa_comparecimento': taxa_comparecimento,
        'taxa_venda': taxa_venda,
        'ticket_medio': ticket_medio,
        'valor_por_orcamento': valor_por_orcamento
    }

def calcular_metricas_projetadas(dados_atuais):
    leads = dados_atuais['leads']
    taxa_agendamento_ia = 0.5  # 50% de agendamento
    taxa_comparecimento_ia = 0.4  # 40% de comparecimento
    taxa_venda = dados_atuais['taxa_venda']
    ticket_medio = dados_atuais['ticket_medio']
    valor_por_orcamento = dados_atuais['valor_por_orcamento']

    agendamentos_ia = int(leads * taxa_agendamento_ia)
    comparecimentos_ia = int(agendamentos_ia * taxa_comparecimento_ia)
    vendas_ia = int(comparecimentos_ia * taxa_venda)
    valor_vendido_ia = vendas_ia * ticket_medio
    valor_orcamentos_ia = comparecimentos_ia * valor_por_orcamento

    return {
        'leads': leads,
        'agendamentos': agendamentos_ia,
        'comparecimentos': comparecimentos_ia,
        'vendas': vendas_ia,
        'valor_vendido': valor_vendido_ia,
        'valor_orcamentos': valor_orcamentos_ia
    }

# Função para gerar o prompt de análise
def gerar_prompt_analise(dados_atuais, dados_projetados):
    valor_vendido_atual = f"{dados_atuais['valor_vendido']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    valor_orcamentos_atual = f"{dados_atuais['valor_orcamentos']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    investimento_anuncios_atual = f"{dados_atuais['investimento_anuncios']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    
    valor_vendido_projetado = f"{dados_projetados['valor_vendido']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    valor_orcamentos_projetado = f"{dados_projetados['valor_orcamentos']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    prompt = f"""
Você recebeu os seguintes dados do funil de vendas de uma clínica odontológica:

Métricas Atuais:
- Mês: {dados_atuais['mes']}
- Leads: {dados_atuais['leads']}
- Agendamentos: {dados_atuais['agendamentos']} ({dados_atuais['taxa_agendamento']:.2%} dos leads)
- Comparecimentos: {dados_atuais['comparecimentos']} ({dados_atuais['taxa_comparecimento']:.2%} dos agendamentos)
- Vendas: {dados_atuais['vendas']} ({dados_atuais['taxa_venda']:.2%} dos comparecimentos)
- Valor Vendido: {valor_vendido_atual}
- Valor de Orçamentos: {valor_orcamentos_atual}
- Investimento em Anúncios: {investimento_anuncios_atual}
- Ticket Médio: {dados_atuais['ticket_medio']:,.2f}
- Valor por Orçamento: {dados_atuais['valor_por_orcamento']:,.2f}

Projeção com Assistente de IA:
- Leads: {dados_projetados['leads']}
- Agendamentos: {dados_projetados['agendamentos']} (de 30% a 50% dos leads)
- Comparecimentos: {dados_projetados['comparecimentos']} (de 30% a 40% dos agendamentos)
- Vendas: {dados_projetados['vendas']} ({dados_atuais['taxa_venda']:.2%} dos comparecimentos)
- Valor Vendido: {valor_vendido_projetado}
- Valor de Orçamentos: {valor_orcamentos_projetado}

Com base nesses dados, realize uma análise detalhada que inclua:

1. **Diagnóstico:**
   - Avalie as taxas atuais de conversão em cada etapa do funil.
   - Identifique pontos fortes e áreas de melhoria.

2. **Projeções com Assistente de IA:**
   - Analise o impacto das melhorias propostas pelo assistente de IA em cada etapa do funil.
   - Destaque o aumento projetado nas vendas e nos valores vendidos e de orçamentos.

3. **Plano de Ação:**
   - Detalhe as ações recomendadas para otimizar o funil de vendas.
   - Inclua estratégias para implementação do assistente de IA, otimização de investimento em tráfego, treinamento da equipe e monitoramento contínuo.

4. **Conclusão:**
   - Destaque os benefícios da adoção do assistente de IA para a clínica odontológica.
   - Enfatize como a solução pode ajudar a aumentar as conversões e o faturamento da clínica.

Utilize um tom persuasivo, ressaltando como a solução agrega valor e resolve desafios específicos enfrentados pela clínica.
"""
    return prompt

# Função para criar gráficos interativos
def criar_graficos(dados_atuais, dados_projetados):
    cores = ['#FFC107', '#FFDF80']  # Tons de amarelo

    # Gráfico de Funil
    fig_funil = go.Figure(go.Funnel(
        y = ['Leads', 'Agendamentos', 'Comparecimentos', 'Vendas'],
        x = [dados_atuais['leads'], dados_atuais['agendamentos'], 
             dados_atuais['comparecimentos'], dados_atuais['vendas']],
        textinfo = "value+percent initial",
        name = "Atual",
        marker = dict(color = cores[0])
    ))
    fig_funil.add_trace(go.Funnel(
        y = ['Leads', 'Agendamentos', 'Comparecimentos', 'Vendas'],
        x = [dados_projetados['leads'], dados_projetados['agendamentos'], 
             dados_projetados['comparecimentos'], dados_projetados['vendas']],
        textinfo = "value+percent initial",
        name = "Projetado",
        marker = dict(color = cores[1])
    ))
    fig_funil.update_layout(title="Comparação do Funil de Vendas")

    # Gráfico de Barras para Valores
    valor_vendido_atual = dados_atuais['valor_vendido']
    valor_orcamentos_atual = dados_atuais['valor_orcamentos']
    
    taxa_conversao_vendas = dados_atuais['taxa_venda']
    ticket_medio = dados_atuais['ticket_medio']
    valor_por_orcamento = dados_atuais['valor_por_orcamento']
    
    valor_vendido_projetado = dados_projetados['vendas'] * ticket_medio
    valor_orcamentos_projetado = dados_projetados['comparecimentos'] * valor_por_orcamento

    fig_valores = go.Figure(data=[
        go.Bar(name='Atual', x=['Valor Vendido', 'Valor Orçamentos'], 
               y=[valor_vendido_atual, valor_orcamentos_atual],
               marker_color=cores[0]),
        go.Bar(name='Projetado', x=['Valor Vendido', 'Valor Orçamentos'], 
               y=[valor_vendido_projetado, valor_orcamentos_projetado],
               marker_color=cores[1])
    ])
    fig_valores.update_layout(title="Comparação de Valores")

    return fig_funil, fig_valores

# Lógica principal do aplicativo
if st.session_state['stage'] == 'qualification':
    st.write("Bem-vindo à Análise do Funil de Vendas para Clínicas Odontológicas!")
    st.write("Por favor, preencha os dados de qualificação abaixo para começar.")
    show_qualification_questions()

elif st.session_state['stage'] == 'funnel_data':
    if st.session_state['pergunta_atual'] == 0 and not st.session_state['messages']:
        st.session_state['messages'].append({"role": "assistant", "content": "Ótimo! Agora vamos coletar os dados do funil de vendas. Por favor, responda às seguintes perguntas."})
        st.session_state['messages'].append({"role": "assistant", "content": perguntas_funil[0]["pergunta"]})

    # Exibição das mensagens do chat
    for chat in st.session_state['messages']:
        if chat["role"] == "user":
            st.chat_message("user").markdown(chat["content"])
        elif chat["role"] == "assistant":
            st.chat_message("assistant", avatar=avatar_image).markdown(chat["content"])

    # Campo de entrada do usuário
    user_input = st.chat_input("Digite sua resposta:")

    if user_input:
        idx = st.session_state['pergunta_atual']
        if idx < len(perguntas_funil):
            chave = perguntas_funil[idx]["chave"]
            pergunta = perguntas_funil[idx]["pergunta"]
            
            if chave == "mes":
                if user_input.capitalize() in meses:
                    st.session_state['collected_data'][chave] = user_input.capitalize()
                    st.session_state['pergunta_atual'] += 1
                else:
                    st.session_state['messages'].append({"role": "assistant", "content": "Por favor, insira um mês válido (por exemplo, Janeiro, Fevereiro, etc.)."})
            elif chave in ["leads", "agendamentos", "comparecimentos", "vendas"]:
                try:
                    valor = int(user_input)
                    if valor >= 0:
                        st.session_state['collected_data'][chave] = valor
                        st.session_state['pergunta_atual'] += 1
                    else:
                        raise ValueError
                except ValueError:
                    st.session_state['messages'].append({"role": "assistant", "content": "Por favor, insira um número inteiro não negativo."})
            elif chave in ["valor_vendido", "valor_orcamentos", "investimento_trafego"]:
                valor = parse_brl(user_input)
                if valor is not None and valor >= 0:
                    st.session_state['collected_data'][chave] = valor
                    st.session_state['pergunta_atual'] += 1
                else:
                    st.session_state['messages'].append({"role": "assistant", "content": "Por favor, insira um valor monetário válido no formato R$ 0.000,00."})

            st.session_state['messages'].append({"role": "user", "content": user_input})

            if st.session_state['pergunta_atual'] < len(perguntas_funil):
                proxima_pergunta = perguntas_funil[st.session_state['pergunta_atual']]["pergunta"]
                st.session_state['messages'].append({"role": "assistant", "content": proxima_pergunta})
            else:
                st.session_state['messages'].append({"role": "assistant", "content": "Obrigado! Estamos gerando um diagnóstico detalhado do seu relatório. Por favor, aguarde..."})
                st.session_state['stage'] = 'analysis'

        st.rerun()

elif st.session_state['stage'] == 'analysis':
    st.write("## Análise do Funil de Vendas")
    
    # Calcular métricas atuais e projetadas
    dados_atuais = calcular_metricas_atuais(st.session_state['collected_data'])
    dados_projetados = calcular_metricas_projetadas(dados_atuais)

    # Gerar análise
    funil.adicionar_dados(**st.session_state['collected_data'])
    prompt_analise = gerar_prompt_analise(dados_atuais, dados_projetados)
    resposta_bruta = analise_chain.responder(prompt_analise)
    resposta_limpa = clean_text(resposta_bruta)

    # Divide o texto em seções
    secoes = re.split(r'\n\n(?=\w+:)', resposta_limpa)
    
    # Remove seções duplicadas
    secoes = list(dict.fromkeys(secoes))
    
    # Exibe cada seção formatada
    for secao in secoes:
        if ':' in secao:
            titulo, conteudo = secao.split(':', 1)
            st.write(f"### {titulo.strip()}")
            paragrafos = conteudo.strip().split('\n\n')
            for paragrafo in paragrafos:
                st.write(paragrafo)
        else:
            st.write(secao.strip())

    # Criar e exibir gráficos
    fig_funil, fig_valores = criar_graficos(dados_atuais, dados_projetados)
    
    st.write("### Comparação Visual")
    st.plotly_chart(fig_funil)
    st.plotly_chart(fig_valores)

    st.write("### Conclusão")
    st.write("Com base nessa análise, podemos ver claramente o potencial de melhoria em seu funil de vendas. "
             "A implementação de nossa solução de IA pode ajudar a otimizar cada etapa do processo, "
             "resultando em um aumento significativo nas conversões e no valor gerado.")

    # Adicionar botão para o WhatsApp
    whatsapp_link = "https://wa.me/552127559449"
    if st.button("Entre em contato via WhatsApp"):
        js = f"window.open('{whatsapp_link}')"
        html = f'<img src onerror="({js})()">'
        div = Div(text=html)
        st.bokeh_chart(div)

# Fim do script
