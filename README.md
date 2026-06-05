# Dashboard Neves Distribuidora

Dashboard profissional em Python + Streamlit para acompanhar vendas, clientes, clientes inativos, curva ABC de produtos, curva ABC de clientes e médias de compra.

## Arquivos usados

Os arquivos foram copiados para a pasta `data/`:

- `data/todas vendas 05.06.csv`
- `data/Listagem de cliente livramento.pdf`

## Como rodar

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Páginas do dashboard

- Visão geral
- Clientes
- Clientes para reativar
- Curva ABC de produtos
- Curva ABC de clientes
- Produtos por cliente
- O que o cliente mais compra em média
- Exportação

## Regras aplicadas

- Valores com vírgula são tratados como decimal.
- `DATA VENDA` é convertida para data corretamente.
- A data base para clientes ativos/inativos é `05/06/2026`.
- Classificação de clientes:
  - Ativo: comprou nos últimos 30 dias
  - Atenção: 31 a 60 dias sem comprar
  - Inativo: 61 a 90 dias sem comprar
  - Perdido: mais de 90 dias sem comprar
- Curva ABC:
  - A: até 80% do faturamento acumulado
  - B: de 80% até 95%
  - C: acima de 95%

## PDF de clientes

O sistema tenta extrair telefone e última compra do PDF de Livramento usando `pdfplumber`, com fallback para `pypdf`/`PyPDF2` quando disponível. Como PDFs podem variar bastante no formato, quando não houver correspondência segura o dashboard mantém o cliente sem telefone, sem impedir o restante das análises.
