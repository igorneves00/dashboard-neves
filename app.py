from __future__ import annotations

import io
import re
import unicodedata
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


BASE_DATE = pd.Timestamp("2026-06-05")
PROJECT_DIR = Path(__file__).parent
SALES_FILE = PROJECT_DIR / "todas vendas 05.06.csv"
CLIENTS_PDF = PROJECT_DIR / "Listagem de cliente livramento.pdf"

YELLOW = "#F6C400"
BLACK = "#111111"
WHITE = "#FFFFFF"
LIGHT = "#F7F7F7"


st.set_page_config(
    page_title="Neves Distribuidora | Dashboard Comercial",
    page_icon="ND",
    layout="wide",
)


CUSTOM_CSS = f"""
<style>
    :root {{
        --neves-black: {BLACK};
        --neves-yellow: {YELLOW};
        --neves-white: {WHITE};
        --neves-light: {LIGHT};
    }}

    .stApp {{
        background: #fbfbfb;
        color: var(--neves-black);
    }}

    [data-testid="stSidebar"] {{
        background: var(--neves-black);
    }}

    [data-testid="stSidebar"] * {{
        color: var(--neves-white);
    }}

    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stMultiSelect label,
    [data-testid="stSidebar"] .stDateInput label {{
        color: var(--neves-white) !important;
        font-weight: 700;
    }}

    .dashboard-title {{
        padding: 18px 22px;
        border-left: 8px solid var(--neves-yellow);
        background: var(--neves-black);
        color: var(--neves-white);
        margin-bottom: 18px;
    }}

    .dashboard-title h1 {{
        margin: 0;
        font-size: 30px;
        letter-spacing: 0;
    }}

    .dashboard-title p {{
        margin: 6px 0 0;
        color: #eeeeee;
    }}

    .metric-card {{
        background: var(--neves-white);
        border: 1px solid #e8e8e8;
        border-top: 5px solid var(--neves-yellow);
        padding: 16px 18px;
        min-height: 116px;
        box-shadow: 0 8px 22px rgba(0,0,0,0.05);
    }}

    .metric-label {{
        font-size: 13px;
        color: #595959;
        text-transform: uppercase;
        font-weight: 800;
    }}

    .metric-value {{
        font-size: 27px;
        color: var(--neves-black);
        font-weight: 900;
        margin-top: 8px;
    }}

    .section-title {{
        font-size: 20px;
        font-weight: 900;
        margin: 20px 0 10px;
        color: var(--neves-black);
    }}

    .whatsapp-box {{
        background: #fff8d7;
        border-left: 6px solid var(--neves-yellow);
        padding: 14px 16px;
        color: var(--neves-black);
        margin-top: 10px;
    }}

    div[data-testid="stMetric"] {{
        background: var(--neves-white);
        border-top: 5px solid var(--neves-yellow);
        padding: 14px;
        box-shadow: 0 8px 22px rgba(0,0,0,0.05);
    }}
</style>
"""


def normalize_text(value: object) -> str:
    text = "" if pd.isna(value) else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text.upper()).strip()


def money(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def number(value: float) -> str:
    return f"{value:,.0f}".replace(",", ".")


def percent(value: float) -> str:
    return f"{value:.2f}%".replace(".", ",")


def parse_brazilian_number(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.strip()
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.replace(r"[^0-9.\-]", "", regex=True)
    )
    return pd.to_numeric(cleaned, errors="coerce").fillna(0)


@st.cache_data(show_spinner=False)
def load_sales(path: str) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "latin1", "cp1252"):
        try:
            df = pd.read_csv(path, sep=";", encoding=encoding, dtype=str)
            break
        except UnicodeDecodeError:
            continue
    else:
        df = pd.read_csv(path, sep=";", dtype=str)
    df.columns = [col.strip() for col in df.columns]

    numeric_cols = [
        "CLIENTE",
        "VENDA",
        "COD PRODUTO",
        "QTDE",
        "VALOR UNITÁRIO",
        "VALOR TOTAL",
        "CUSTO NF",
        "CUSTO MEDIO",
        "CUSTO CHEIO",
        "CUSTO BASE",
        "DESCONTO",
        "TOTAL VENDA",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = parse_brazilian_number(df[col])

    df["DATA VENDA"] = pd.to_datetime(df["DATA VENDA"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["DATA VENDA"]).copy()

    text_cols = ["VENDEDOR", "RAZÃO SOCIAL", "STATUS", "DESCRIÇÃO", "UNIDADE", "GRUPO", "FORNECEDOR"]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()

    df["CLIENTE_ID"] = df["CLIENTE"].astype("Int64").astype(str).replace("<NA>", "")
    df["CLIENTE_NOME"] = df["RAZÃO SOCIAL"].where(df["RAZÃO SOCIAL"].ne(""), df["CLIENTE_ID"])
    df["CLIENTE_KEY"] = df["CLIENTE_NOME"].map(normalize_text)
    df["PRODUTO_KEY"] = df["DESCRIÇÃO"].map(normalize_text)
    df["MES"] = df["DATA VENDA"].dt.to_period("M").dt.to_timestamp()
    df["DATA_DIA"] = df["DATA VENDA"].dt.date
    return df


def extract_pdf_text(path: Path) -> str:
    if not path.exists():
        return ""

    try:
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:
        pass

    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        pass

    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return ""


@st.cache_data(show_spinner=False)
def load_pdf_clients(path: str) -> pd.DataFrame:
    text = extract_pdf_text(Path(path))
    if not text.strip():
        return pd.DataFrame(columns=["PDF_CLIENTE_KEY", "PDF_CLIENTE", "TELEFONE_PDF", "ULTIMA_COMPRA_PDF"])

    phone_pattern = re.compile(
        r"(?:(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?(?:9\s*)?\d{4}[-.\s]?\d{4})"
    )
    date_pattern = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
    rows = []

    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if len(line) < 4:
            continue

        phones = phone_pattern.findall(line)
        dates = date_pattern.findall(line)
        if not phones and not dates:
            continue

        clean_name = phone_pattern.sub(" ", line)
        clean_name = date_pattern.sub(" ", clean_name)
        clean_name = re.sub(r"\b(CNPJ|CPF|FONE|TELEFONE|CELULAR|ULTIMA COMPRA|ÚLTIMA COMPRA)\b", " ", clean_name, flags=re.I)
        clean_name = re.sub(r"[^A-Za-zÀ-ÿ0-9 ()&./-]", " ", clean_name)
        clean_name = re.sub(r"\s+", " ", clean_name).strip(" -")

        rows.append(
            {
                "PDF_CLIENTE_KEY": normalize_text(clean_name),
                "PDF_CLIENTE": clean_name,
                "TELEFONE_PDF": phones[0] if phones else "",
                "ULTIMA_COMPRA_PDF": pd.to_datetime(dates[-1], dayfirst=True, errors="coerce") if dates else pd.NaT,
            }
        )

    if not rows:
        return pd.DataFrame(columns=["PDF_CLIENTE_KEY", "PDF_CLIENTE", "TELEFONE_PDF", "ULTIMA_COMPRA_PDF"])

    pdf_df = pd.DataFrame(rows)
    pdf_df = pdf_df[pdf_df["PDF_CLIENTE_KEY"].str.len() > 2].copy()
    pdf_df = pdf_df.sort_values(["PDF_CLIENTE_KEY", "TELEFONE_PDF"], ascending=[True, False])
    return pdf_df.drop_duplicates("PDF_CLIENTE_KEY", keep="first")


def classify_client(days_without_buying: int) -> str:
    if days_without_buying <= 30:
        return "Ativo"
    if days_without_buying <= 60:
        return "Atenção"
    if days_without_buying <= 90:
        return "Inativo"
    return "Perdido"


def build_client_summary(df: pd.DataFrame, pdf_clients: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        df.groupby(["CLIENTE_ID", "CLIENTE_NOME", "CLIENTE_KEY"], as_index=False)
        .agg(
            TOTAL_COMPRADO=("TOTAL VENDA", "sum"),
            QTDE_COMPRAS=("VENDA", "nunique"),
            ULTIMA_COMPRA=("DATA VENDA", "max"),
            QTDE_ITENS=("QTDE", "sum"),
        )
    )
    grouped["TICKET_MEDIO"] = grouped["TOTAL_COMPRADO"] / grouped["QTDE_COMPRAS"].replace(0, pd.NA)
    grouped["DIAS_SEM_COMPRAR"] = (BASE_DATE - grouped["ULTIMA_COMPRA"].dt.normalize()).dt.days.clip(lower=0)
    grouped["CLASSIFICACAO"] = grouped["DIAS_SEM_COMPRAR"].map(classify_client)

    top_group = (
        df.groupby(["CLIENTE_KEY", "GRUPO"], as_index=False)["TOTAL VENDA"]
        .sum()
        .sort_values(["CLIENTE_KEY", "TOTAL VENDA"], ascending=[True, False])
        .drop_duplicates("CLIENTE_KEY")
        .rename(columns={"GRUPO": "GRUPO_MAIS_COMPRADO"})
    )
    top_product = (
        df.groupby(["CLIENTE_KEY", "DESCRIÇÃO"], as_index=False)["TOTAL VENDA"]
        .sum()
        .sort_values(["CLIENTE_KEY", "TOTAL VENDA"], ascending=[True, False])
        .drop_duplicates("CLIENTE_KEY")
        .rename(columns={"DESCRIÇÃO": "PRODUTO_MAIS_COMPRADO"})
    )

    grouped = grouped.merge(top_group[["CLIENTE_KEY", "GRUPO_MAIS_COMPRADO"]], on="CLIENTE_KEY", how="left")
    grouped = grouped.merge(top_product[["CLIENTE_KEY", "PRODUTO_MAIS_COMPRADO"]], on="CLIENTE_KEY", how="left")

    if not pdf_clients.empty:
        grouped = grouped.merge(pdf_clients, left_on="CLIENTE_KEY", right_on="PDF_CLIENTE_KEY", how="left")
        missing_phone = grouped["TELEFONE_PDF"].isna() | grouped["TELEFONE_PDF"].eq("")
        pdf_lookup = pdf_clients[["PDF_CLIENTE_KEY", "TELEFONE_PDF", "ULTIMA_COMPRA_PDF"]].to_dict("records")
        for idx, row in grouped.loc[missing_phone].iterrows():
            client_key = row["CLIENTE_KEY"]
            match = next(
                (
                    item
                    for item in pdf_lookup
                    if client_key
                    and item["PDF_CLIENTE_KEY"]
                    and (client_key in item["PDF_CLIENTE_KEY"] or item["PDF_CLIENTE_KEY"] in client_key)
                ),
                None,
            )
            if match:
                grouped.at[idx, "TELEFONE_PDF"] = match["TELEFONE_PDF"]
                grouped.at[idx, "ULTIMA_COMPRA_PDF"] = match["ULTIMA_COMPRA_PDF"]
        grouped["TELEFONE"] = grouped["TELEFONE_PDF"].fillna("")
        grouped["ULTIMA_COMPRA_PDF"] = pd.to_datetime(grouped["ULTIMA_COMPRA_PDF"], errors="coerce")
    else:
        grouped["TELEFONE"] = ""
        grouped["ULTIMA_COMPRA_PDF"] = pd.NaT

    grouped["SUGESTAO_WHATSAPP"] = grouped["GRUPO_MAIS_COMPRADO"].fillna("").apply(
        lambda grupo: (
            "Olá, tudo bem? Aqui é da Neves Distribuidora. Vi que já faz um tempo que você não compra "
            "com a gente e queria te mostrar algumas condições em MDF, fita de borda, ferragens e puxadores. "
            "Posso te mandar as novidades?"
            if not grupo
            else f"Olá, tudo bem? Aqui é da Neves Distribuidora. Vi que já faz um tempo que você não compra com a gente. "
            f"Temos novidades e condições especiais em {grupo.lower()}, além de MDF, fita de borda, ferragens e puxadores. "
            "Posso te mandar as opções?"
        )
    )
    return grouped.sort_values("TOTAL_COMPRADO", ascending=False)


def build_abc(df: pd.DataFrame, group_cols: list[str], value_col: str = "TOTAL VENDA") -> pd.DataFrame:
    abc = df.groupby(group_cols, as_index=False).agg(FATURAMENTO=(value_col, "sum"), QUANTIDADE=("QTDE", "sum"))
    abc = abc.sort_values("FATURAMENTO", ascending=False)
    total = abc["FATURAMENTO"].sum()
    abc["PARTICIPACAO_%"] = (abc["FATURAMENTO"] / total * 100).fillna(0) if total else 0
    abc["PARTICIPACAO_ACUMULADA_%"] = abc["PARTICIPACAO_%"].cumsum()
    abc["CLASSE"] = pd.cut(
        abc["PARTICIPACAO_ACUMULADA_%"],
        bins=[-0.001, 80, 95, float("inf")],
        labels=["A", "B", "C"],
    ).astype(str)
    return abc


def average_purchase_profile(df: pd.DataFrame) -> pd.DataFrame:
    sales_by_client = df.groupby(["CLIENTE_KEY", "CLIENTE_NOME", "VENDA"], as_index=False).agg(
        DATA_COMPRA=("DATA VENDA", "min"),
        VALOR_COMPRA=("TOTAL VENDA", "sum"),
        QTDE_COMPRA=("QTDE", "sum"),
    )
    averages = sales_by_client.groupby(["CLIENTE_KEY", "CLIENTE_NOME"], as_index=False).agg(
        MEDIA_VALOR_POR_COMPRA=("VALOR_COMPRA", "mean"),
        MEDIA_QTDE_POR_COMPRA=("QTDE_COMPRA", "mean"),
        QTDE_COMPRAS=("VENDA", "nunique"),
        ULTIMA_COMPRA=("DATA_COMPRA", "max"),
    )

    frequency = []
    for key, group in sales_by_client.sort_values("DATA_COMPRA").groupby("CLIENTE_KEY"):
        dates = group["DATA_COMPRA"].drop_duplicates().sort_values()
        mean_days = dates.diff().dt.days.dropna().mean() if len(dates) > 1 else pd.NA
        frequency.append({"CLIENTE_KEY": key, "FREQUENCIA_MEDIA_DIAS": mean_days})

    profile = averages.merge(pd.DataFrame(frequency), on="CLIENTE_KEY", how="left")
    top_group = (
        df.groupby(["CLIENTE_KEY", "GRUPO"], as_index=False)["QTDE"]
        .sum()
        .sort_values(["CLIENTE_KEY", "QTDE"], ascending=[True, False])
        .drop_duplicates("CLIENTE_KEY")
        .rename(columns={"GRUPO": "GRUPO_MAIS_COMPRADO"})
    )
    top_product = (
        df.groupby(["CLIENTE_KEY", "DESCRIÇÃO"], as_index=False)["QTDE"]
        .sum()
        .sort_values(["CLIENTE_KEY", "QTDE"], ascending=[True, False])
        .drop_duplicates("CLIENTE_KEY")
        .rename(columns={"DESCRIÇÃO": "PRODUTO_MAIS_COMPRADO"})
    )
    profile = profile.merge(top_group[["CLIENTE_KEY", "GRUPO_MAIS_COMPRADO"]], on="CLIENTE_KEY", how="left")
    profile = profile.merge(top_product[["CLIENTE_KEY", "PRODUTO_MAIS_COMPRADO"]], on="CLIENTE_KEY", how="left")
    profile["DIAS_SEM_COMPRAR"] = (BASE_DATE - profile["ULTIMA_COMPRA"].dt.normalize()).dt.days.clip(lower=0)
    return profile


def products_by_client(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(["CLIENTE_NOME", "CLIENTE_KEY", "COD PRODUTO", "DESCRIÇÃO", "GRUPO"], as_index=False)
        .agg(QUANTIDADE=("QTDE", "sum"), FATURAMENTO=("TOTAL VENDA", "sum"), COMPRAS=("VENDA", "nunique"))
        .sort_values(["CLIENTE_NOME", "FATURAMENTO"], ascending=[True, False])
    )


def build_export(
    inactive_clients: pd.DataFrame,
    abc_products: pd.DataFrame,
    abc_clients: pd.DataFrame,
    client_products: pd.DataFrame,
) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        inactive_clients.to_excel(writer, sheet_name="Clientes inativos", index=False)
        abc_products.to_excel(writer, sheet_name="ABC produtos", index=False)
        abc_clients.to_excel(writer, sheet_name="ABC clientes", index=False)
        client_products.to_excel(writer, sheet_name="Produtos por cliente", index=False)
    return output.getvalue()


def metric_card(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_table(df: pd.DataFrame) -> pd.DataFrame:
    formatted = df.copy()
    for col in formatted.columns:
        if "DATA" in col or "COMPRA" in col and pd.api.types.is_datetime64_any_dtype(formatted[col]):
            formatted[col] = formatted[col].dt.strftime("%d/%m/%Y")
    return formatted


st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
st.markdown(
    """
    <div class="dashboard-title">
        <h1>Neves Distribuidora | Dashboard Comercial</h1>
        <p>Vendas, clientes, reativação, curva ABC e médias de compra com data base em 05/06/2026.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if not SALES_FILE.exists():
    st.error(f"Arquivo de vendas não encontrado em {SALES_FILE}.")
    st.stop()

sales = load_sales(str(SALES_FILE))
pdf_clients = load_pdf_clients(str(CLIENTS_PDF))

with st.sidebar:
    st.markdown("## Filtros")
    pages = [
        "Visão geral",
        "Clientes",
        "Clientes para reativar",
        "Curva ABC de produtos",
        "Curva ABC de clientes",
        "Produtos por cliente",
        "O que o cliente mais compra em média",
        "Exportação",
    ]
    page = st.radio("Página", pages)

    min_date = sales["DATA VENDA"].min().date()
    max_date = sales["DATA VENDA"].max().date()
    date_range = st.date_input("Período", value=(min_date, max_date), min_value=min_date, max_value=max_date)

    vendedores = st.multiselect("Vendedor", sorted(sales["VENDEDOR"].dropna().unique()))
    grupos = st.multiselect("Grupo", sorted(sales["GRUPO"].dropna().unique()))
    clientes = st.multiselect("Cliente", sorted(sales["CLIENTE_NOME"].dropna().unique()))
    fornecedores = st.multiselect("Fornecedor", sorted(sales["FORNECEDOR"].dropna().unique()))

filtered = sales.copy()
if isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1]) + pd.Timedelta(days=1)
    filtered = filtered[(filtered["DATA VENDA"] >= start) & (filtered["DATA VENDA"] < end)]
if vendedores:
    filtered = filtered[filtered["VENDEDOR"].isin(vendedores)]
if grupos:
    filtered = filtered[filtered["GRUPO"].isin(grupos)]
if clientes:
    filtered = filtered[filtered["CLIENTE_NOME"].isin(clientes)]
if fornecedores:
    filtered = filtered[filtered["FORNECEDOR"].isin(fornecedores)]

if filtered.empty:
    st.warning("Nenhum dado encontrado para os filtros selecionados.")
    st.stop()

client_summary = build_client_summary(filtered, pdf_clients)
abc_products = build_abc(filtered, ["COD PRODUTO", "DESCRIÇÃO", "GRUPO"])
abc_clients = build_abc(filtered, ["CLIENTE_NOME"])
client_products = products_by_client(filtered)
avg_profile = average_purchase_profile(filtered)

plot_template = "plotly_white"
plot_colors = [YELLOW, BLACK, "#6b6b6b", "#d6a900", "#f2df78"]


if page == "Visão geral":
    total_revenue = filtered["TOTAL VENDA"].sum()
    sales_count = filtered["VENDA"].nunique()
    avg_ticket = total_revenue / sales_count if sales_count else 0
    active_clients = client_summary[client_summary["CLASSIFICACAO"].eq("Ativo")]["CLIENTE_ID"].nunique()
    products_count = filtered["COD PRODUTO"].nunique()

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        metric_card("Faturamento total", money(total_revenue))
    with col2:
        metric_card("Quantidade de vendas", number(sales_count))
    with col3:
        metric_card("Ticket médio", money(avg_ticket))
    with col4:
        metric_card("Clientes ativos", number(active_clients))
    with col5:
        metric_card("Produtos vendidos", number(products_count))

    month_revenue = filtered.groupby("MES", as_index=False)["TOTAL VENDA"].sum()
    seller_revenue = filtered.groupby("VENDEDOR", as_index=False)["TOTAL VENDA"].sum().sort_values("TOTAL VENDA", ascending=False)
    group_revenue = filtered.groupby("GRUPO", as_index=False)["TOTAL VENDA"].sum().sort_values("TOTAL VENDA", ascending=False)

    st.markdown('<div class="section-title">Faturamento por mês</div>', unsafe_allow_html=True)
    fig_month = px.line(month_revenue, x="MES", y="TOTAL VENDA", markers=True, template=plot_template)
    fig_month.update_traces(line_color=YELLOW, marker_color=BLACK, line_width=4)
    fig_month.update_layout(yaxis_title="Faturamento", xaxis_title="", hovermode="x unified")
    st.plotly_chart(fig_month, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown('<div class="section-title">Faturamento por vendedor</div>', unsafe_allow_html=True)
        fig_seller = px.bar(seller_revenue, x="TOTAL VENDA", y="VENDEDOR", orientation="h", template=plot_template, color_discrete_sequence=[YELLOW])
        fig_seller.update_layout(yaxis={"categoryorder": "total ascending"}, xaxis_title="Faturamento", yaxis_title="")
        st.plotly_chart(fig_seller, use_container_width=True)
    with col_b:
        st.markdown('<div class="section-title">Faturamento por grupo</div>', unsafe_allow_html=True)
        fig_group = px.pie(group_revenue, values="TOTAL VENDA", names="GRUPO", hole=0.45, color_discrete_sequence=plot_colors)
        st.plotly_chart(fig_group, use_container_width=True)

elif page == "Clientes":
    st.markdown('<div class="section-title">Ranking dos clientes que mais compram</div>', unsafe_allow_html=True)
    ranking = client_summary.head(30)
    fig_clients = px.bar(ranking, x="TOTAL_COMPRADO", y="CLIENTE_NOME", orientation="h", template=plot_template, color="CLASSIFICACAO", color_discrete_map={"Ativo": "#111111", "Atenção": "#F6C400", "Inativo": "#E89005", "Perdido": "#B00020"})
    fig_clients.update_layout(yaxis={"categoryorder": "total ascending"}, xaxis_title="Total comprado", yaxis_title="")
    st.plotly_chart(fig_clients, use_container_width=True)

    table = client_summary[
        [
            "CLIENTE_ID",
            "CLIENTE_NOME",
            "TOTAL_COMPRADO",
            "QTDE_COMPRAS",
            "TICKET_MEDIO",
            "ULTIMA_COMPRA",
            "DIAS_SEM_COMPRAR",
            "CLASSIFICACAO",
        ]
    ].rename(
        columns={
            "CLIENTE_ID": "Cliente",
            "CLIENTE_NOME": "Nome",
            "TOTAL_COMPRADO": "Total comprado",
            "QTDE_COMPRAS": "Quantidade de compras",
            "TICKET_MEDIO": "Ticket médio",
            "ULTIMA_COMPRA": "Última compra",
            "DIAS_SEM_COMPRAR": "Dias sem comprar",
            "CLASSIFICACAO": "Classificação",
        }
    )
    st.dataframe(table, use_container_width=True, hide_index=True)

elif page == "Clientes para reativar":
    st.markdown('<div class="section-title">Clientes que não compram há mais tempo</div>', unsafe_allow_html=True)
    inactive = client_summary[client_summary["CLASSIFICACAO"].isin(["Inativo", "Perdido"])].sort_values("DIAS_SEM_COMPRAR", ascending=False)
    table = inactive[
        [
            "CLIENTE_NOME",
            "TELEFONE",
            "ULTIMA_COMPRA",
            "ULTIMA_COMPRA_PDF",
            "DIAS_SEM_COMPRAR",
            "TOTAL_COMPRADO",
            "GRUPO_MAIS_COMPRADO",
            "PRODUTO_MAIS_COMPRADO",
            "SUGESTAO_WHATSAPP",
        ]
    ].rename(
        columns={
            "CLIENTE_NOME": "Nome do cliente",
            "TELEFONE": "Telefone",
            "ULTIMA_COMPRA": "Última compra",
            "ULTIMA_COMPRA_PDF": "Última compra no PDF",
            "DIAS_SEM_COMPRAR": "Dias sem comprar",
            "TOTAL_COMPRADO": "Total que já comprou",
            "GRUPO_MAIS_COMPRADO": "Grupo que mais comprava",
            "PRODUTO_MAIS_COMPRADO": "Produto que mais comprava",
            "SUGESTAO_WHATSAPP": "Mensagem pronta para WhatsApp",
        }
    )
    st.dataframe(table, use_container_width=True, hide_index=True)

    if not inactive.empty:
        selected = st.selectbox("Ver mensagem por cliente", inactive["CLIENTE_NOME"].tolist())
        msg = inactive.loc[inactive["CLIENTE_NOME"].eq(selected), "SUGESTAO_WHATSAPP"].iloc[0]
        st.markdown(f'<div class="whatsapp-box">{msg}</div>', unsafe_allow_html=True)

elif page == "Curva ABC de produtos":
    st.markdown('<div class="section-title">Curva ABC de produtos</div>', unsafe_allow_html=True)
    table = abc_products.rename(
        columns={
            "COD PRODUTO": "Código do produto",
            "DESCRIÇÃO": "Produto",
            "GRUPO": "Grupo",
            "QUANTIDADE": "Quantidade vendida",
            "FATURAMENTO": "Faturamento",
            "PARTICIPACAO_%": "Participação %",
            "PARTICIPACAO_ACUMULADA_%": "Participação acumulada %",
            "CLASSE": "Classe",
        }
    )
    st.dataframe(table, use_container_width=True, hide_index=True)
    fig = px.bar(abc_products.head(30), x="FATURAMENTO", y="DESCRIÇÃO", color="CLASSE", orientation="h", template=plot_template, color_discrete_map={"A": BLACK, "B": YELLOW, "C": "#777777"})
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, xaxis_title="Faturamento", yaxis_title="")
    st.plotly_chart(fig, use_container_width=True)

elif page == "Curva ABC de clientes":
    st.markdown('<div class="section-title">Curva ABC de clientes</div>', unsafe_allow_html=True)
    table = abc_clients.rename(
        columns={
            "CLIENTE_NOME": "Cliente",
            "FATURAMENTO": "Total comprado",
            "PARTICIPACAO_%": "Participação %",
            "PARTICIPACAO_ACUMULADA_%": "Participação acumulada %",
            "CLASSE": "Classe",
        }
    )
    st.dataframe(table[["Cliente", "Total comprado", "Participação %", "Participação acumulada %", "Classe"]], use_container_width=True, hide_index=True)
    fig = px.bar(abc_clients.head(30), x="FATURAMENTO", y="CLIENTE_NOME", color="CLASSE", orientation="h", template=plot_template, color_discrete_map={"A": BLACK, "B": YELLOW, "C": "#777777"})
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, xaxis_title="Total comprado", yaxis_title="")
    st.plotly_chart(fig, use_container_width=True)

elif page == "Produtos por cliente":
    selected_client = st.selectbox("Cliente", sorted(filtered["CLIENTE_NOME"].unique()))
    client_key = normalize_text(selected_client)
    client_rows = filtered[filtered["CLIENTE_KEY"].eq(client_key)]
    summary_row = client_summary[client_summary["CLIENTE_KEY"].eq(client_key)].iloc[0]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Média de compra", money(summary_row["TICKET_MEDIO"]))
    with col2:
        metric_card("Última compra", summary_row["ULTIMA_COMPRA"].strftime("%d/%m/%Y"))
    with col3:
        metric_card("Dias sem comprar", number(summary_row["DIAS_SEM_COMPRAR"]))
    with col4:
        metric_card("Status", summary_row["CLASSIFICACAO"])

    st.markdown('<div class="section-title">Produtos que ele mais compra</div>', unsafe_allow_html=True)
    top_products = client_products[client_products["CLIENTE_KEY"].eq(client_key)].head(30)
    st.dataframe(top_products[["COD PRODUTO", "DESCRIÇÃO", "GRUPO", "QUANTIDADE", "FATURAMENTO", "COMPRAS"]], use_container_width=True, hide_index=True)

    col_a, col_b = st.columns(2)
    with col_a:
        group_table = client_rows.groupby("GRUPO", as_index=False)["TOTAL VENDA"].sum().sort_values("TOTAL VENDA", ascending=False)
        fig = px.bar(group_table, x="TOTAL VENDA", y="GRUPO", orientation="h", template=plot_template, color_discrete_sequence=[YELLOW])
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, xaxis_title="Faturamento", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)
    with col_b:
        suggestions = (
            abc_products[abc_products["GRUPO"].isin(client_rows["GRUPO"].dropna().unique())]
            .loc[lambda x: ~x["DESCRIÇÃO"].isin(client_rows["DESCRIÇÃO"].unique())]
            .head(10)
        )
        st.markdown('<div class="section-title">Sugestão de produtos para oferecer</div>', unsafe_allow_html=True)
        st.dataframe(suggestions[["COD PRODUTO", "DESCRIÇÃO", "GRUPO", "FATURAMENTO", "CLASSE"]], use_container_width=True, hide_index=True)

elif page == "O que o cliente mais compra em média":
    st.markdown('<div class="section-title">Perfil médio de compra por cliente</div>', unsafe_allow_html=True)
    table = avg_profile.rename(
        columns={
            "CLIENTE_NOME": "Cliente",
            "GRUPO_MAIS_COMPRADO": "Grupo mais comprado",
            "PRODUTO_MAIS_COMPRADO": "Produto mais comprado",
            "MEDIA_VALOR_POR_COMPRA": "Média de valor por compra",
            "MEDIA_QTDE_POR_COMPRA": "Média de quantidade por compra",
            "FREQUENCIA_MEDIA_DIAS": "Frequência média de compra em dias",
        }
    )
    st.dataframe(
        table[
            [
                "Cliente",
                "Grupo mais comprado",
                "Produto mais comprado",
                "Média de valor por compra",
                "Média de quantidade por compra",
                "Frequência média de compra em dias",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

elif page == "Exportação":
    st.markdown('<div class="section-title">Exportar análises em Excel</div>', unsafe_allow_html=True)
    inactive = client_summary[client_summary["CLASSIFICACAO"].isin(["Inativo", "Perdido"])].copy()
    export_bytes = build_export(inactive, abc_products, abc_clients, client_products)
    st.download_button(
        "Baixar Excel consolidado",
        data=export_bytes,
        file_name="dashboard_neves_distribuidora.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.info("O arquivo inclui: clientes inativos, curva ABC de produtos, curva ABC de clientes e produtos mais comprados por cliente.")

with st.sidebar:
    st.markdown("---")
    st.caption(f"Linhas filtradas: {number(len(filtered))}")
    st.caption(f"Clientes no PDF vinculados: {number(client_summary['TELEFONE'].astype(bool).sum())}")
