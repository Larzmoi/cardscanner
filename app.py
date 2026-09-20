
import io
import re

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Pokémon Trend Scanner", page_icon="📈", layout="wide")

st.title("Pokémon Trend Scanner")
st.caption("Ensimmäinen versio: TCGplayerin toteutuneisiin myynteihin perustuva kuukausittainen Top Selling -data.")

LATEST_PERIOD = "2026-08"
LATEST_LABEL = "1.–30.8.2026"
DEFAULT_LOW_URL = (
    "https://8946057.fs1.hubspotusercontent-na1.net/hubfs/8946057/"
    "Seller%20Marketing%20-%20CSVs/Seller%20Marketing%20-%20Top%20Selling%20CSVs/"
    "PKMN%20Top%20Selling%20Singles%20%241-%2450%20-%20August%202026.csv"
)
DEFAULT_HIGH_URL = (
    "https://8946057.fs1.hubspotusercontent-na1.net/hubfs/8946057/"
    "Seller%20Marketing%20-%20CSVs/Seller%20Marketing%20-%20Top%20Selling%20CSVs/"
    "PKMN%20Top%20Selling%20Singles%20%2450%2B%20-%20August%202026.csv"
)

def normalize_col(s):
    s = str(s).strip().lower()
    s = re.sub(r"[\s_\-]+", " ", s)
    s = re.sub(r"[^a-z0-9 $€%]+", "", s)
    return s.strip()

def detect_column(columns, kind):
    candidates = {
        "name": ["product name", "card name", "name", "product", "card"],
        "set": ["set name", "set", "expansion", "group name"],
        "price": ["average sale price", "avg sale price", "average price", "avg price", "sale price", "price"],
        "sold": ["copies sold", "units sold", "quantity sold", "total sold", "sold quantity", "sales", "sold", "units"],
        "url": ["url", "product url", "tcgplayer url", "link"],
        "number": ["card number", "number", "collector number"],
    }
    normalized = {c: normalize_col(c) for c in columns}
    for target in candidates[kind]:
        for original, norm in normalized.items():
            if norm == target:
                return original
    for target in candidates[kind]:
        for original, norm in normalized.items():
            if target in norm:
                return original
    return None

def parse_money(series):
    return pd.to_numeric(
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace("€", "", regex=False)
        .str.replace("USD", "", regex=False)
        .str.replace("EUR", "", regex=False)
        .str.strip(),
        errors="coerce",
    )

def parse_int(series):
    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.extract(r"(-?\d+(?:\.\d+)?)", expand=False)
    )
    return pd.to_numeric(cleaned, errors="coerce")

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_csv(url):
    headers = {"User-Agent": "Mozilla/5.0 PokemonTrendScanner/0.1"}
    r = requests.get(url, timeout=30, headers=headers, allow_redirects=True)
    r.raise_for_status()
    content_type = (r.headers.get("content-type") or "").lower()
    if "html" in content_type and "<html" in r.text[:500].lower():
        raise ValueError("URL palautti HTML-sivun eikä CSV-tiedostoa.")
    return pd.read_csv(io.BytesIO(r.content))

def load_remote_sources(min_price, max_price, low_url, high_url):
    frames = []
    errors = []

    if min_price < 50:
        try:
            df = fetch_csv(low_url)
            df["_source_bucket"] = "$1–$49.99"
            frames.append(df)
        except Exception as e:
            errors.append(f"$1–$49.99 CSV: {e}")

    if max_price >= 50:
        try:
            df = fetch_csv(high_url)
            df["_source_bucket"] = "$50+"
            frames.append(df)
        except Exception as e:
            errors.append(f"$50+ CSV: {e}")

    if not frames:
        return None, errors
    return pd.concat(frames, ignore_index=True, sort=False), errors

def build_result(df, name_col, set_col, price_col, sold_col, number_col=None, url_col=None):
    out = pd.DataFrame()
    out["Kortti"] = df[name_col].astype(str)
    out["Setti"] = df[set_col].astype(str) if set_col else ""
    if number_col:
        out["Numero"] = df[number_col].astype(str)
    out["Keskim. myyntihinta"] = parse_money(df[price_col])
    out["Myyty kpl"] = parse_int(df[sold_col])
    if url_col:
        out["Linkki"] = df[url_col].astype(str)
    if "_source_bucket" in df.columns:
        out["Lähdehinta"] = df["_source_bucket"].astype(str)
    return out.dropna(subset=["Keskim. myyntihinta", "Myyty kpl"])

with st.sidebar:
    st.header("Suodattimet")
    c1, c2 = st.columns(2)
    min_price = c1.number_input("Min $", min_value=0.0, value=5.0, step=1.0)
    max_price = c2.number_input("Max $", min_value=0.0, value=20.0, step=1.0)
    top_n = st.slider("Näytä enintään", 10, 100, 50, 10)

    st.divider()
    st.subheader("Aikajakso")
    st.write(f"**{LATEST_LABEL}**")
    st.caption("V1 käyttää TCGplayerin valmista kuukausiraporttia. Se ei ole liukuva 30 päivää.")

    st.divider()
    source_mode = st.radio("Lähde", ["TCGplayer – automaattinen", "Lataa oma CSV"], index=0)

st.info(
    "Tämä versio rankkaa kortit toteutuneiden TCGplayer-myyntien kappalemäärän mukaan. "
    "TCGplayerin kuukausiraportti ei erottele kuntoluokkaa tai printtiä."
)

raw_df = None
load_errors = []

if source_mode == "TCGplayer – automaattinen":
    with st.expander("TCGplayer CSV -osoitteet", expanded=False):
        st.caption("Jos TCGplayer vaihtaa raportin osoitteita, liitä uudet CSV-linkit tähän.")
        low_url = st.text_input("$1–$49.99 CSV", value=DEFAULT_LOW_URL)
        high_url = st.text_input("$50+ CSV", value=DEFAULT_HIGH_URL)

    if st.button("Hae myydyimmät kortit", type="primary", use_container_width=True):
        if max_price < min_price:
            st.error("Maksimihinnan pitää olla vähintään minimihinta.")
            st.stop()
        with st.spinner("Haetaan TCGplayerin Top Selling -raporttia..."):
            raw_df, load_errors = load_remote_sources(min_price, max_price, low_url, high_url)
        st.session_state["raw_df"] = raw_df
        st.session_state["load_errors"] = load_errors
else:
    uploaded = st.file_uploader("Valitse CSV", type=["csv"])
    if uploaded is not None:
        try:
            raw_df = pd.read_csv(uploaded)
            st.session_state["raw_df"] = raw_df
            st.session_state["load_errors"] = []
        except Exception as e:
            st.error(f"CSV:n lukeminen epäonnistui: {e}")

if "raw_df" in st.session_state and st.session_state["raw_df"] is not None:
    raw_df = st.session_state["raw_df"]
    load_errors = st.session_state.get("load_errors", [])

    for err in load_errors:
        st.warning(err)

    st.subheader("Sarakkeiden tunnistus")
    cols = list(raw_df.columns)
    detected = {
        "name": detect_column(cols, "name"),
        "set": detect_column(cols, "set"),
        "price": detect_column(cols, "price"),
        "sold": detect_column(cols, "sold"),
        "url": detect_column(cols, "url"),
        "number": detect_column(cols, "number"),
    }

    a, b, c, d = st.columns(4)
    name_col = a.selectbox("Kortin nimi", cols, index=cols.index(detected["name"]) if detected["name"] in cols else 0)
    set_options = ["—"] + cols
    set_col = b.selectbox("Setti", set_options, index=set_options.index(detected["set"]) if detected["set"] in cols else 0)
    price_col = c.selectbox("Myyntihinta", cols, index=cols.index(detected["price"]) if detected["price"] in cols else 0)
    sold_col = d.selectbox("Myyty määrä", cols, index=cols.index(detected["sold"]) if detected["sold"] in cols else 0)

    with st.expander("Lisäkentät"):
        e, f = st.columns(2)
        num_options = ["—"] + cols
        url_options = ["—"] + cols
        number_col = e.selectbox("Korttinumero", num_options, index=num_options.index(detected["number"]) if detected["number"] in cols else 0)
        url_col = f.selectbox("Tuotelinkki", url_options, index=url_options.index(detected["url"]) if detected["url"] in cols else 0)

    if st.button("Laske Top-lista", use_container_width=True):
        result = build_result(
            raw_df,
            name_col=name_col,
            set_col=None if set_col == "—" else set_col,
            price_col=price_col,
            sold_col=sold_col,
            number_col=None if number_col == "—" else number_col,
            url_col=None if url_col == "—" else url_col,
        )
        result = result[
            (result["Keskim. myyntihinta"] >= min_price)
            & (result["Keskim. myyntihinta"] <= max_price)
        ].copy()
        result = result.sort_values(["Myyty kpl", "Keskim. myyntihinta"], ascending=[False, True]).head(top_n)
        result.insert(0, "#", range(1, len(result) + 1))
        st.session_state["result"] = result

if "result" in st.session_state:
    result = st.session_state["result"]
    st.divider()
    st.subheader(f"Top {len(result)} – eniten myydyt")

    k1, k2, k3 = st.columns(3)
    k1.metric("Kortteja", len(result))
    k2.metric("Myyty yhteensä", int(result["Myyty kpl"].sum()) if len(result) else 0)
    k3.metric("Mediaanihinta", f"${result['Keskim. myyntihinta'].median():.2f}" if len(result) else "–")

    st.dataframe(
        result,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Keskim. myyntihinta": st.column_config.NumberColumn(format="$%.2f"),
            "Myyty kpl": st.column_config.NumberColumn(format="%d"),
            "Linkki": st.column_config.LinkColumn(display_text="Avaa"),
        },
    )

    csv_bytes = result.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "Lataa tulokset CSV:nä",
        csv_bytes,
        file_name=f"pokemon_top_sold_{LATEST_PERIOD}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.caption(
        "Huom: TCGplayerin Top Selling -raportti yhdistää saman kortin eri kuntoluokat ja printit. "
        "Seuraava versio voidaan tehdä 7/14/30 päivän API-datalla sekä EN/NM-rajauksella."
    )
