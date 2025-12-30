import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import yfinance as yf
import re
import datetime

# ----------------- PAGE CONFIG -----------------
st.set_page_config(
    page_title="Large Cap Index PEG Analyzer",
    layout="wide",
    page_icon="📊"
)

st.title("📊 Large Cap Index Valuation Dashboard")
st.markdown(
    "Analyze **Forward PE, TTM PE and Forward PEG** of Large Cap indices in real-time."
)

st.divider()

# ----------------- LOAD URL LIST -----------------
@st.cache_data
def load_urls():
    with open("url_list.txt", "r") as f:
        return [line.strip() for line in f.readlines()]

url_list = load_urls()

# ----------------- HELPER FUNCTIONS -----------------
def get_text_from_groww(i):
    response = requests.get(url_list[i])
    soup = BeautifulSoup(response.content, "html.parser")
    return soup.title.string, soup.get_text()

def get_number_of_holdings(text):
    start_index = int(text.find(")NameSectorInstrumentAssets"))
    i, digits = 1, 0
    while text[start_index - i] != "(":
        digits += 1
        i += 1

    holdings = int(text[start_index - digits:start_index])
    return start_index, holdings

def get_text_holdings(text):
    start, count = get_number_of_holdings(text)
    start += 26
    percent_count, i, s = 0, 1, ""

    while percent_count < count:
        s += text[start + i]
        if text[start + i] == "%":
            percent_count += 1
        i += 1
    return s

def get_holdings_df(text):
    raw_text = get_text_holdings(text)
    rows = []

    pattern = re.compile(
        r"(?P<Stock>.*?)(?P<Sector>Consumer\ Discretionary|Consumer\ Staples|Capital\ Goods|"
        r"Metals\ \&\ Mining|Financial|Healthcare|Technology|Automobile|Construction|"
        r"Chemicals|Energy|Insurance|Communication|Textiles|Services)"
        r"(?P<Type>Equity).*?(?P<Weightage>\d+\.\d+)%",
        re.VERBOSE
    )

    for m in pattern.finditer(raw_text):
        rows.append({
            "Stock": m.group("Stock").strip(),
            "Sector": m.group("Sector"),
            "Weightage": float(m.group("Weightage"))
        })

    return pd.DataFrame(rows)

def get_nse_ticker(name):
    try:
        search = yf.Search(name, max_results=5)
        for q in search.quotes:
            if q.get("exchange") in ["NSI", "NSE"]:
                return q.get("symbol")
    except:
        pass
    return None

def calculate_ratios(stock_name, cache):
    if stock_name in cache:
        return cache[stock_name]

    try:
        ticker = get_nse_ticker(stock_name)
        if not ticker:
            return 0

        stock = yf.Ticker(ticker)
        info = stock.info

        pe = info.get("trailingPE", 0)
        fpe = info.get("forwardPE", 0)
        eps = info.get("trailingEps", 0)
        feps = info.get("forwardEps", 0)

        if eps == 0:
            return 0

        growth = ((feps - eps) / eps) * 100
        peg = pe / growth if growth > 0 else 0

        cache[stock_name] = peg
        return peg
    except:
        return 0

# ----------------- MAIN COMPUTATION -----------------
if st.button("🚀 Run Analysis"):

    progress = st.progress(0)
    status = st.empty()

    Ratios = {}
    df = pd.DataFrame(columns=["Fund Name", "Forward PEG"])

    largeCapIndices = [i for i, u in enumerate(url_list) if "large" in u.lower()]

    for idx, i in enumerate(largeCapIndices):
        status.text(f"Processing fund {idx + 1}/{len(largeCapIndices)}")
        title, text = get_text_from_groww(i)
        holdings = get_holdings_df(text)

        peg_sum, weight_sum = 0, 0

        for _, row in holdings.iterrows():
            peg = calculate_ratios(row["Stock"], Ratios)
            peg_sum += peg * row["Weightage"]
            weight_sum += row["Weightage"]

        final_peg = peg_sum / weight_sum if weight_sum else 0
        df.loc[len(df)] = [title, round(final_peg, 2)]

        progress.progress((idx + 1) / len(largeCapIndices))

    avg_peg = df["Forward PEG"].mean()
    df.loc[len(df)] = ["Average PEG", round(avg_peg, 2)]

    status.success("✅ Analysis Complete")

    st.divider()

    # ----------------- DISPLAY -----------------
    st.subheader("📈 Large Cap PEG Summary")

    

