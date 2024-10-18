# langchain_setup.py
from langchain_community.chat_models import ChatOpenAI  # Importação atualizada
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from funil_vendas import FunilVendas

class AnaliseFunilChain:
    def __init__(self, api_key, funil_vendas: FunilVendas):
        self.funil_vendas = funil_vendas
        self.llm = ChatOpenAI(api_key=api_key, model="gpt-4")  # Utiliza ChatOpenAI para modelos de chat
        self.template = """Você é um assistente que analisa dados do funil de vendas de clínicas odontológicas. 
Com base nos seguintes dados:

{dados_funil}

Responda à seguinte pergunta do usuário de forma clara e concisa:

Pergunta: {pergunta}"""

        self.prompt = PromptTemplate(
            input_variables=["dados_funil", "pergunta"],
            template=self.template
        )
        self.chain = LLMChain(llm=self.llm, prompt=self.prompt)

    def responder(self, pergunta):
        dados = self.funil_vendas.data.to_string()
        resposta = self.chain.run({
            "dados_funil": dados,
            "pergunta": pergunta
        })
        return resposta