
import io
import re
import time
import unicodedata
from urllib.parse import quote_plus

import pandas as pd
import requests
import streamlit as st

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------

st.set_page_config(
    page_title="Pokémon Card Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

TCG_PERIOD_LABEL = "1.–30.8.2026"

TCG_TOP_LOW_URL = (
    "https://8946057.fs1.hubspotusercontent-na1.net/hubfs/8946057/"
    "Seller%20Marketing%20-%20CSVs/Seller%20Marketing%20-%20Top%20Selling%20CSVs/"
    "PKMN%20Top%20Selling%20Singles%20%241-%2450%20-%20August%202026.csv"
)

TCG_TOP_HIGH_URL = (
    "https://8946057.fs1.hubspotusercontent-na1.net/hubfs/8946057/"
    "Seller%20Marketing%20-%20CSVs/Seller%20Marketing%20-%20Top%20Selling%20CSVs/"
    "PKMN%20Top%20Selling%20Singles%20%2450%2B%20-%20August%202026.csv"
)

TCG_TRENDS_URL = (
    "https://8946057.fs1.hubspotusercontent-na1.net/hubfs/8946057/"
    "Seller%20Marketing%20-%20CSVs/Seller%20Marketing%20-%20Price%20Trends%20CSVs/"
    "Pok%C3%A9mon%20Price%20Trends%20Report%20-%20August%202026.csv"
)

PRICECHARTING_BASE = "https://www.pricecharting.com"


# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------

def normalize_text(value):
    value = "" if value is None else str(value)
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = value.lower().strip()
    value = re.sub(r"[\s_\-]+", " ", value)
    value = re.sub(r"[^a-z0-9%$€+#/ ]+", "", value)
    return value.strip()


def normalize_key(value):
    value = normalize_text(value)
    value = re.sub(r"[^a-z0-9]+", "", value)
    return value


def detect_column(columns, candidates):
    normalized = {col: normalize_text(col) for col in columns}

    # exact first
    for candidate in candidates:
        c = normalize_text(candidate)
        for original, norm in normalized.items():
            if norm == c:
                return original

    # then contains
    for candidate in candidates:
        c = normalize_text(candidate)
        for original, norm in normalized.items():
            if c in norm:
                return original

    return None


def money_to_float(series):
    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace("€", "", regex=False)
        .str.replace("USD", "", regex=False)
        .str.replace("EUR", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors="coerce")


def numeric_to_float(series):
    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.extract(r"(-?\d+(?:\.\d+)?)", expand=False)
    )
    return pd.to_numeric(cleaned, errors="coerce")


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_csv(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 CardScanner/0.2"
        )
    }
    response = requests.get(url, headers=headers, timeout=35, allow_redirects=True)
    response.raise_for_status()

    first_bytes = response.content[:500].lower()
    if b"<html" in first_bytes or b"<!doctype" in first_bytes:
        raise ValueError("Lähde palautti HTML-sivun CSV-tiedoston sijasta.")

    # utf-8-sig handles BOM if present.
    return pd.read_csv(io.BytesIO(response.content), encoding="utf-8-sig")


def load_top_selling(min_price, max_price, low_url, high_url):
    frames = []
    errors = []

    if min_price < 50:
        try:
            df = fetch_csv(low_url).copy()
            df["_bucket"] = "$1–49.99"
            frames.append(df)
        except Exception as exc:
            errors.append(f"$1–49.99 raportti: {exc}")

    if max_price >= 50:
        try:
            df = fetch_csv(high_url).copy()
            df["_bucket"] = "$50+"
            frames.append(df)
        except Exception as exc:
            errors.append(f"$50+ raportti: {exc}")

    if not frames:
        return None, errors

    return pd.concat(frames, ignore_index=True, sort=False), errors


def parse_top_selling(df):
    cols = list(df.columns)

    name_col = detect_column(
        cols, ["product name", "card name", "name", "product", "card"]
    )
    set_col = detect_column(
        cols, ["set name", "set", "expansion", "group name"]
    )
    price_col = detect_column(
        cols,
        [
            "average sale price",
            "avg sale price",
            "average sold price",
            "average price",
            "avg price",
            "sale price",
        ],
    )
    sold_col = detect_column(
        cols,
        [
            "copies sold",
            "units sold",
            "quantity sold",
            "total sold",
            "sold quantity",
            "sales volume",
            "sales",
            "sold",
            "units",
        ],
    )
    rank_col = detect_column(cols, ["rank", "ranking", "position"])

    if not name_col or not price_col:
        return None, {
            "error": "Kortin nimeä tai keskimääräistä myyntihintaa ei tunnistettu.",
            "columns": cols,
        }

    out = pd.DataFrame()
    out["Kortti"] = df[name_col].astype(str)
    out["Setti"] = df[set_col].astype(str) if set_col else ""
    out["Keskim. myyntihinta"] = money_to_float(df[price_col])

    if sold_col:
        out["Myyty kpl"] = numeric_to_float(df[sold_col])
    else:
        out["Myyty kpl"] = pd.NA

    if rank_col:
        out["Raportin sijoitus"] = numeric_to_float(df[rank_col])
    else:
        # TCGplayer CSV is already ordered by sales volume.
        # Preserve source order if an explicit rank/count column is absent.
        out["Raportin sijoitus"] = range(1, len(out) + 1)

    if "_bucket" in df.columns:
        out["Hintaluokan lähde"] = df["_bucket"].astype(str)

    out = out.dropna(subset=["Keskim. myyntihinta"]).reset_index(drop=True)
    return out, {"sold_column": sold_col, "rank_column": rank_col}


def parse_price_trends(df):
    cols = list(df.columns)

    name_col = detect_column(
        cols, ["product name", "card name", "name", "product", "card"]
    )
    set_col = detect_column(
        cols, ["set name", "set", "expansion", "group name"]
    )
    current_col = detect_column(
        cols,
        [
            "current market price",
            "new market price",
            "ending market price",
            "current price",
            "market price",
        ],
    )
    increase_col = detect_column(
        cols,
        [
            "price increase",
            "increase",
            "market price increase",
            "dollar increase",
            "change amount",
            "price change",
            "change",
        ],
    )
    percent_col = detect_column(
        cols,
        [
            "percent increase",
            "percentage increase",
            "percent change",
            "percentage change",
            "% increase",
            "% change",
        ],
    )
    old_col = detect_column(
        cols,
        [
            "starting market price",
            "previous market price",
            "old market price",
            "market price 30 days ago",
            "starting price",
            "previous price",
        ],
    )
    sales_col = detect_column(
        cols,
        [
            "copies sold",
            "units sold",
            "sales",
            "sale count",
            "sales count",
            "quantity sold",
        ],
    )

    if not name_col:
        return None, {"error": "Kortin nimeä ei tunnistettu.", "columns": cols}

    out = pd.DataFrame()
    out["Kortti"] = df[name_col].astype(str)
    out["Setti"] = df[set_col].astype(str) if set_col else ""

    if current_col:
        out["Nykyinen market-hinta"] = money_to_float(df[current_col])
    else:
        out["Nykyinen market-hinta"] = pd.NA

    if increase_col:
        out["Muutos $"] = money_to_float(df[increase_col])
    else:
        out["Muutos $"] = pd.NA

    if old_col:
        out["Hinta jakson alussa"] = money_to_float(df[old_col])
    else:
        out["Hinta jakson alussa"] = pd.NA

    if percent_col:
        pct = money_to_float(df[percent_col])
        # If values look like fractions (0.25), convert to percentage points.
        valid = pct.dropna()
        if len(valid) and valid.abs().median() <= 2:
            pct = pct * 100
        out["Muutos %"] = pct
    else:
        out["Muutos %"] = pd.NA

    if sales_col:
        out["Myyty kpl 30d"] = numeric_to_float(df[sales_col])
    else:
        out["Myyty kpl 30d"] = pd.NA

    # Derive missing starting price / percent change when possible.
    current = pd.to_numeric(out["Nykyinen market-hinta"], errors="coerce")
    change = pd.to_numeric(out["Muutos $"], errors="coerce")
    old = pd.to_numeric(out["Hinta jakson alussa"], errors="coerce")
    pct = pd.to_numeric(out["Muutos %"], errors="coerce")

    derived_old = current - change
    out["Hinta jakson alussa"] = old.fillna(derived_old)

    old2 = pd.to_numeric(out["Hinta jakson alussa"], errors="coerce")
    derived_pct = (change / old2.replace(0, pd.NA)) * 100
    out["Muutos %"] = pct.fillna(derived_pct)

    out = out.reset_index(drop=True)

    return out, {
        "current_column": current_col,
        "increase_column": increase_col,
        "percent_column": percent_col,
        "old_column": old_col,
        "sales_column": sales_col,
        "columns": cols,
    }


def merge_candidates(top_df, trend_df):
    if top_df is None or trend_df is None:
        return pd.DataFrame()

    left = top_df.copy()
    right = trend_df.copy()

    left["_name"] = left["Kortti"].map(normalize_key)
    left["_set"] = left["Setti"].map(normalize_key)
    right["_name"] = right["Kortti"].map(normalize_key)
    right["_set"] = right["Setti"].map(normalize_key)

    # First try exact card + set.
    merged = left.merge(
        right,
        on=["_name", "_set"],
        how="inner",
        suffixes=("_sold", "_trend"),
    )

    if merged.empty:
        # Fallback to name only if source set naming differs.
        merged = left.merge(
            right.drop_duplicates("_name"),
            on=["_name"],
            how="inner",
            suffixes=("_sold", "_trend"),
        )

    if merged.empty:
        return merged

    result = pd.DataFrame()
    result["Kortti"] = merged.get("Kortti_sold", merged.get("Kortti_trend"))
    result["Setti"] = merged.get("Setti_sold", merged.get("Setti_trend"))
    result["Keskim. sold-hinta"] = merged.get("Keskim. myyntihinta")
    result["Myyty kpl"] = merged.get("Myyty kpl")
    result["Myyntisijoitus"] = merged.get("Raportin sijoitus")
    result["30d market-hinta"] = merged.get("Nykyinen market-hinta")
    result["30d muutos $"] = merged.get("Muutos $")
    result["30d muutos %"] = merged.get("Muutos %")
    result["Myyty kpl 30d (trend report)"] = merged.get("Myyty kpl 30d")

    # Rank primarily by actual sales count if it exists, otherwise TCG report rank.
    sold_numeric = pd.to_numeric(result["Myyty kpl"], errors="coerce")
    rank_numeric = pd.to_numeric(result["Myyntisijoitus"], errors="coerce")
    change_numeric = pd.to_numeric(result["30d muutos %"], errors="coerce").fillna(0)

    if sold_numeric.notna().any():
        result["_score_primary"] = sold_numeric.fillna(0)
        result = result.sort_values(
            ["_score_primary", "30d muutos %"],
            ascending=[False, False],
        )
    else:
        result["_score_primary"] = -rank_numeric.fillna(999999)
        result = result.sort_values(
            ["Myyntisijoitus", "30d muutos %"],
            ascending=[True, False],
        )

    return result.drop(columns=["_score_primary"], errors="ignore").reset_index(drop=True)


def get_secret(name):
    try:
        return str(st.secrets.get(name, "")).strip()
    except Exception:
        return ""


def pricecharting_request(path, token, params):
    if not token:
        raise ValueError("PriceCharting API token puuttuu.")

    query = {"t": token, **params}
    response = requests.get(
        f"{PRICECHARTING_BASE}{path}",
        params=query,
        timeout=30,
        headers={"User-Agent": "PokemonCardScanner/0.2"},
    )
    response.raise_for_status()
    data = response.json()

    if data.get("status") == "error":
        raise ValueError(data.get("error-message", "PriceCharting API error"))

    return data


def pc_search(token, query):
    return pricecharting_request("/api/products", token, {"q": query})


def pc_product(token, product_id):
    return pricecharting_request("/api/product", token, {"id": product_id})


def cents_to_dollars(value):
    try:
        return float(value) / 100
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------
# HEADER / SIDEBAR
# ------------------------------------------------------------

st.title("Pokémon Card Scanner")
st.caption("Raw-korttien myynti- ja hintatrendien seulonta.")

with st.sidebar:
    st.header("Yleiset suodattimet")

    c1, c2 = st.columns(2)
    min_price = c1.number_input(
        "Min $", min_value=0.0, value=5.0, step=1.0, key="min_price"
    )
    max_price = c2.number_input(
        "Max $", min_value=0.0, value=20.0, step=1.0, key="max_price"
    )

    top_n = st.select_slider(
        "Näytä",
        options=[10, 20, 30, 50, 75, 100],
        value=50,
    )

    if max_price < min_price:
        st.error("Max-hinnan pitää olla vähintään Min-hinta.")

    st.divider()
    st.caption(f"TCGplayer-raporttien jakso: {TCG_PERIOD_LABEL}")
    st.caption(
        "Top Selling = raw-markkinan kuukausiraportti. "
        "30d Movers = TCGplayerin Near Mint -hintatrendiraportti."
    )


# ------------------------------------------------------------
# DATA LOAD
# ------------------------------------------------------------

@st.cache_data(ttl=1800, show_spinner=False)
def get_tcg_data(min_p, max_p):
    top_raw, top_errors = load_top_selling(
        min_p, max_p, TCG_TOP_LOW_URL, TCG_TOP_HIGH_URL
    )

    top_parsed = None
    top_meta = {}
    if top_raw is not None:
        top_parsed, top_meta = parse_top_selling(top_raw)

    trend_raw = None
    trend_parsed = None
    trend_meta = {}
    trend_error = None

    try:
        trend_raw = fetch_csv(TCG_TRENDS_URL)
        trend_parsed, trend_meta = parse_price_trends(trend_raw)
    except Exception as exc:
        trend_error = str(exc)

    return {
        "top_raw": top_raw,
        "top": top_parsed,
        "top_meta": top_meta,
        "top_errors": top_errors,
        "trend_raw": trend_raw,
        "trend": trend_parsed,
        "trend_meta": trend_meta,
        "trend_error": trend_error,
    }


data = get_tcg_data(min_price, max_price)


# ------------------------------------------------------------
# TABS
# ------------------------------------------------------------

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "🔥 Myydyimmät",
        "📈 30d nousijat",
        "🎯 Myynti + nousu",
        "💲 PriceCharting",
    ]
)


# ------------------------------------------------------------
# TAB 1: TOP SELLING
# ------------------------------------------------------------

with tab1:
    st.subheader("TCGplayer – myydyimmät Pokémon-kortit")
    st.caption(
        "Toteutuneiden TCGplayer-myyntien kuukausiraportti. "
        "TCGplayer ei tässä raportissa erottele conditionia tai printtiä."
    )

    for err in data["top_errors"]:
        st.warning(err)

    top = data["top"]

    if top is None:
        st.error("Top Selling -raporttia ei saatu luettua.")
        if data["top_meta"]:
            st.json(data["top_meta"])
    else:
        filtered = top[
            (top["Keskim. myyntihinta"] >= min_price)
            & (top["Keskim. myyntihinta"] <= max_price)
        ].copy()

        sold = pd.to_numeric(filtered["Myyty kpl"], errors="coerce")

        if sold.notna().any():
            filtered = filtered.sort_values(
                ["Myyty kpl", "Keskim. myyntihinta"],
                ascending=[False, True],
            )
            rank_basis = "myytyjen kappaleiden mukaan"
        else:
            filtered = filtered.sort_values("Raportin sijoitus")
            rank_basis = "TCGplayerin raportin sijoituksen mukaan"
            st.info(
                "Tässä CSV-versiossa ei ole erillistä myytyjen kappaleiden "
                "lukua, joten järjestys perustuu TCGplayerin valmiiseen "
                "myyntivolyymirankingiin."
            )

        filtered = filtered.head(top_n).reset_index(drop=True)
        filtered.insert(0, "#", range(1, len(filtered) + 1))

        st.write(f"Järjestys: **{rank_basis}**")

        metric1, metric2, metric3 = st.columns(3)
        metric1.metric("Kortteja", len(filtered))
        if sold.notna().any():
            metric2.metric(
                "Myyty yhteensä",
                int(pd.to_numeric(filtered["Myyty kpl"], errors="coerce").sum()),
            )
        else:
            metric2.metric("Raportti", "Top Selling")
        metric3.metric(
            "Mediaanihinta",
            (
                f"${filtered['Keskim. myyntihinta'].median():.2f}"
                if len(filtered)
                else "–"
            ),
        )

        display_cols = [
            c for c in [
                "#",
                "Kortti",
                "Setti",
                "Keskim. myyntihinta",
                "Myyty kpl",
                "Raportin sijoitus",
            ]
            if c in filtered.columns
        ]

        st.dataframe(
            filtered[display_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Keskim. myyntihinta": st.column_config.NumberColumn(
                    "Keskim. myyntihinta", format="$%.2f"
                ),
                "Myyty kpl": st.column_config.NumberColumn(
                    "Myyty kpl", format="%.0f"
                ),
                "Raportin sijoitus": st.column_config.NumberColumn(
                    "TCG-rank", format="%.0f"
                ),
            },
        )

        st.download_button(
            "Lataa tämä lista CSV:nä",
            filtered.to_csv(index=False).encode("utf-8-sig"),
            file_name="tcgplayer_top_sold_filtered.csv",
            mime="text/csv",
            use_container_width=True,
        )

        st.session_state["latest_top_filtered"] = filtered


# ------------------------------------------------------------
# TAB 2: 30D MOVERS
# ------------------------------------------------------------

with tab2:
    st.subheader("TCGplayer – 30 päivän Near Mint -nousijat")
    st.caption(
        "TCGplayerin Price Trends -raportti: Near Mint -kortit, joilla "
        "oli raporttijaksolla vähintään 10 myyntiä."
    )

    trend = data["trend"]

    if data["trend_error"]:
        st.error(f"Price Trends -raportin haku epäonnistui: {data['trend_error']}")
        st.caption("Raportin CSV-osoitteen voi joutua päivittämään, kun TCGplayer julkaisee uuden kuukauden.")
    elif trend is None:
        st.error("Price Trends -CSV saatiin, mutta sarakkeita ei pystytty tunnistamaan.")
        st.json(data["trend_meta"])
        if data["trend_raw"] is not None:
            st.dataframe(data["trend_raw"].head(30), use_container_width=True)
    else:
        current_price = pd.to_numeric(
            trend["Nykyinen market-hinta"], errors="coerce"
        )

        if current_price.notna().any():
            trend_filtered = trend[
                (current_price >= min_price) & (current_price <= max_price)
            ].copy()
        else:
            trend_filtered = trend.copy()
            st.warning(
                "Nykyistä market-hintaa ei tunnistettu CSV:stä, joten "
                "hintasuodatinta ei voitu käyttää tähän näkymään."
            )

        change_pct = pd.to_numeric(trend_filtered["Muutos %"], errors="coerce")
        change_dollars = pd.to_numeric(trend_filtered["Muutos $"], errors="coerce")

        if change_pct.notna().any():
            trend_filtered = trend_filtered.sort_values(
                "Muutos %", ascending=False
            )
        elif change_dollars.notna().any():
            trend_filtered = trend_filtered.sort_values(
                "Muutos $", ascending=False
            )

        trend_filtered = trend_filtered.head(top_n).reset_index(drop=True)
        trend_filtered.insert(0, "#", range(1, len(trend_filtered) + 1))

        m1, m2, m3 = st.columns(3)
        m1.metric("Kortteja", len(trend_filtered))

        median_change = pd.to_numeric(
            trend_filtered["Muutos %"], errors="coerce"
        ).median()
        m2.metric(
            "Mediaani 30d muutos",
            f"{median_change:+.1f}%" if pd.notna(median_change) else "–",
        )

        median_price = pd.to_numeric(
            trend_filtered["Nykyinen market-hinta"], errors="coerce"
        ).median()
        m3.metric(
            "Mediaani market-hinta",
            f"${median_price:.2f}" if pd.notna(median_price) else "–",
        )

        display_cols = [
            c for c in [
                "#",
                "Kortti",
                "Setti",
                "Hinta jakson alussa",
                "Nykyinen market-hinta",
                "Muutos $",
                "Muutos %",
                "Myyty kpl 30d",
            ]
            if c in trend_filtered.columns
        ]

        st.dataframe(
            trend_filtered[display_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Hinta jakson alussa": st.column_config.NumberColumn(format="$%.2f"),
                "Nykyinen market-hinta": st.column_config.NumberColumn(format="$%.2f"),
                "Muutos $": st.column_config.NumberColumn(format="$%+.2f"),
                "Muutos %": st.column_config.NumberColumn(format="%+.1f%%"),
                "Myyty kpl 30d": st.column_config.NumberColumn(format="%.0f"),
            },
        )

        st.download_button(
            "Lataa nousijat CSV:nä",
            trend_filtered.to_csv(index=False).encode("utf-8-sig"),
            file_name="tcgplayer_30d_movers_filtered.csv",
            mime="text/csv",
            use_container_width=True,
        )

        with st.expander("CSV-tunnistus / debug"):
            st.json(data["trend_meta"])

        st.session_state["latest_trend_filtered"] = trend_filtered


# ------------------------------------------------------------
# TAB 3: COMBINED
# ------------------------------------------------------------

with tab3:
    st.subheader("Kortit, jotka ovat sekä myytyjä että nousussa")
    st.caption(
        "Ristiintaulukoi TCGplayerin Top Selling -raportin ja "
        "30 päivän Near Mint Price Trends -raportin."
    )

    top_all = data["top"]
    trend_all = data["trend"]

    if top_all is None or trend_all is None:
        st.info("Yhdistelmä tarvitsee molemmat TCGplayer-raportit.")
    else:
        # Apply selected price range before merge.
        top_filtered = top_all[
            (top_all["Keskim. myyntihinta"] >= min_price)
            & (top_all["Keskim. myyntihinta"] <= max_price)
        ].copy()

        trend_price = pd.to_numeric(
            trend_all["Nykyinen market-hinta"], errors="coerce"
        )
        if trend_price.notna().any():
            trend_filtered_all = trend_all[
                (trend_price >= min_price) & (trend_price <= max_price)
            ].copy()
        else:
            trend_filtered_all = trend_all.copy()

        combined = merge_candidates(top_filtered, trend_filtered_all)

        if combined.empty:
            st.info(
                "Tällä hintahaarukalla samoja kortteja ei löytynyt molemmista "
                "raporteista. Kokeile leveämpää hintahaarukkaa."
            )
        else:
            combined = combined.head(top_n).copy()
            combined.insert(0, "#", range(1, len(combined) + 1))

            st.success(
                f"Löytyi {len(combined)} korttia, jotka esiintyvät sekä "
                "Top Selling- että 30d Price Trends -datassa."
            )

            st.dataframe(
                combined,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Keskim. sold-hinta": st.column_config.NumberColumn(format="$%.2f"),
                    "Myyty kpl": st.column_config.NumberColumn(format="%.0f"),
                    "Myyntisijoitus": st.column_config.NumberColumn(format="%.0f"),
                    "30d market-hinta": st.column_config.NumberColumn(format="$%.2f"),
                    "30d muutos $": st.column_config.NumberColumn(format="$%+.2f"),
                    "30d muutos %": st.column_config.NumberColumn(format="%+.1f%%"),
                    "Myyty kpl 30d (trend report)": st.column_config.NumberColumn(format="%.0f"),
                },
            )

            st.download_button(
                "Lataa yhdistelmä CSV:nä",
                combined.to_csv(index=False).encode("utf-8-sig"),
                file_name="tcgplayer_sold_plus_movers.csv",
                mime="text/csv",
                use_container_width=True,
            )

            st.session_state["latest_combined"] = combined


# ------------------------------------------------------------
# TAB 4: PRICECHARTING
# ------------------------------------------------------------

with tab4:
    st.subheader("PriceCharting – nykyinen raw-hinta + vuosimyynti")
    st.caption(
        "Valinnainen lisälähde. PriceCharting API vaatii maksullisen "
        "API-tokenin. Ilman tokenia muu scanneri toimii normaalisti."
    )

    secret_token = get_secret("PRICECHARTING_TOKEN")
    token = secret_token

    if secret_token:
        st.success("PRICECHARTING_TOKEN löytyi Streamlit Secrets -asetuksista.")
    else:
        token = st.text_input(
            "PriceCharting API token",
            value="",
            type="password",
            help="Tokenia ei tallenneta tämän sovelluksen tiedostoihin.",
        )

    st.info(
        "PriceChartingin `loose-price` tarkoittaa korteilla ungraded/raw-hintaa. "
        "`sales-volume` on vuosittainen myyntimäärä, ei 7/30 päivän myyntimäärä."
    )

    # Offer cards from scanner as quick search seeds.
    seed_options = []

    if "latest_combined" in st.session_state:
        for _, row in st.session_state["latest_combined"].iterrows():
            seed_options.append(
                f"{row.get('Kortti', '')} | {row.get('Setti', '')}"
            )
    elif "latest_top_filtered" in st.session_state:
        for _, row in st.session_state["latest_top_filtered"].iterrows():
            seed_options.append(
                f"{row.get('Kortti', '')} | {row.get('Setti', '')}"
            )

    query_default = ""

    if seed_options:
        selected_seed = st.selectbox(
            "Valitse scannerin kortti hakupohjaksi",
            ["— kirjoitan haun itse —"] + seed_options,
        )
        if selected_seed != "— kirjoitan haun itse —":
            card_name, set_name = selected_seed.split(" | ", 1)
            query_default = f"{card_name} {set_name}".strip()

    pc_query = st.text_input(
        "PriceCharting-haku",
        value=query_default,
        placeholder="esim. Charizard 4 Base Set",
    )

    if st.button(
        "Hae PriceChartingista",
        disabled=not bool(token and pc_query.strip()),
        use_container_width=True,
    ):
        try:
            with st.spinner("Haetaan PriceCharting-tuotteita..."):
                search_data = pc_search(token, pc_query.strip())
            products = search_data.get("products", [])

            if not products:
                st.warning("PriceCharting ei löytänyt tuotteita tällä haulla.")
                st.session_state.pop("pc_products", None)
            else:
                st.session_state["pc_products"] = products
        except Exception as exc:
            st.error(str(exc))

    products = st.session_state.get("pc_products", [])

    if products:
        labels = []
        id_by_label = {}

        for product in products:
            label = (
                f"{product.get('product-name', 'Unknown')} "
                f"— {product.get('console-name', '')} "
                f"[ID {product.get('id', '')}]"
            )
            labels.append(label)
            id_by_label[label] = str(product.get("id"))

        selected_product = st.selectbox(
            "Valitse oikea kortti",
            labels,
        )

        if st.button(
            "Näytä raw-hinta ja myyntivolyymi",
            use_container_width=True,
        ):
            try:
                # Respect PriceCharting's 1 request / second API limit.
                time.sleep(1.05)
                detail = pc_product(token, id_by_label[selected_product])

                raw_price = cents_to_dollars(detail.get("loose-price"))
                annual_volume = detail.get("sales-volume")
                annual_volume_num = None
                try:
                    annual_volume_num = int(float(annual_volume))
                except (TypeError, ValueError):
                    pass

                p1, p2, p3 = st.columns(3)
                p1.metric(
                    "PriceCharting raw",
                    f"${raw_price:.2f}" if raw_price is not None else "–",
                )
                p2.metric(
                    "Vuosimyynti",
                    f"{annual_volume_num:,}".replace(",", " ")
                    if annual_volume_num is not None
                    else "–",
                )
                p3.metric(
                    "PriceCharting ID",
                    str(detail.get("id", "–")),
                )

                st.write(
                    f"**{detail.get('product-name', '')}**  \n"
                    f"{detail.get('console-name', '')}"
                )

                raw_table = {
                    "Kenttä": [
                        "Raw / ungraded",
                        "Yearly sales volume",
                        "Release date",
                        "PriceCharting ID",
                    ],
                    "Arvo": [
                        f"${raw_price:.2f}" if raw_price is not None else "–",
                        annual_volume if annual_volume is not None else "–",
                        detail.get("release-date", "–"),
                        detail.get("id", "–"),
                    ],
                }
                st.dataframe(
                    pd.DataFrame(raw_table),
                    use_container_width=True,
                    hide_index=True,
                )

                st.caption(
                    "Graded-price-kenttiä ei käytetä tässä raw-scannerissa."
                )

            except Exception as exc:
                st.error(str(exc))

    if not token:
        st.warning(
            "PriceCharting-osio odottaa API-tokenia. Kun hankit tokenin, "
            "turvallisin tapa pilvessä on lisätä Streamlit App → Settings → "
            "Secrets: `PRICECHARTING_TOKEN = \"...\"`."
        )


# ------------------------------------------------------------
# FOOTER
# ------------------------------------------------------------

st.divider()
st.caption(
    "v0.2 • Raw trend scanner. RareBit/Cardmarket lisätään myöhemmin erillisenä "
    "EU-datalähteenä. PSA/graded-dataa ei käytetä pääscannerissa."
)
