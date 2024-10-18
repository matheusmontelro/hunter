# funil_vendas.py
import pandas as pd

class FunilVendas:
    def __init__(self):
        self.data = pd.DataFrame(columns=[
            'Mês', 'Leads', 'Agendamentos', 'Comparecimentos', 
            'Vendas', 'Valor Vendido', 'Valor de Orçamentos', 
            'Investimento em Tráfego', 'Ticket Médio'
        ])

    def adicionar_dados(self, mes, leads, agendamentos, comparecimentos, vendas, valor_vendido, valor_orcamentos, investimento_trafego):
        ticket_medio = valor_vendido / vendas if vendas > 0 else 0
        nova_linha = pd.DataFrame([{
            'Mês': mes,
            'Leads': leads,
            'Agendamentos': agendamentos,
            'Comparecimentos': comparecimentos,
            'Vendas': vendas,
            'Valor Vendido': valor_vendido,
            'Valor de Orçamentos': valor_orcamentos,
            'Investimento em Tráfego': investimento_trafego,
            'Ticket Médio': ticket_medio
        }])

        # Verificar se self.data está vazio
        if self.data.empty:
            self.data = nova_linha
        else:
            self.data = pd.concat([self.data, nova_linha], ignore_index=True)

    def obter_estatisticas(self):
        return self.data.describe()
