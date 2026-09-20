
import io
import re
import time
import unicodedata
from datetime import datetime, timedelta

import pandas as pd
import requests
import streamlit as st

# ============================================================
# CONFIG
# ============================================================

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

POKETRACE_BASE = "https://api.poketrace.com/v1"
PRICECHARTING_BASE = "https://www.pricecharting.com"

# Compact layout.
st.markdown(
    """
    <style>
      .block-container {
        padding-top: 1.3rem;
        padding-bottom: 1.5rem;
        max-width: 1500px;
      }
      h1 { margin-bottom: .15rem; }
      [data-testid="stMetric"] {
        padding: .35rem .65rem;
      }
      [data-testid="stMetricValue"] {
        font-size: 1.45rem;
      }
      div[data-testid="stDataFrame"] {
        font-size: 0.82rem;
      }
      .stTabs [data-baseweb="tab"] {
        padding-top: .45rem;
        padding-bottom: .45rem;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# GENERIC HELPERS
# ============================================================

def normalize_text(value):
    value = "" if value is None else str(value)
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = value.lower().strip()
    value = re.sub(r"[\s_\-]+", " ", value)
    value = re.sub(r"[^a-z0-9%$€+#/ ]+", "", value)
    return value.strip()


def normalize_key(value):
    return re.sub(r"[^a-z0-9]+", "", normalize_text(value))


def detect_column(columns, candidates):
    normalized = {col: normalize_text(col) for col in columns}
    for candidate in candidates:
        c = normalize_text(candidate)
        for original, norm in normalized.items():
            if norm == c:
                return original
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


def get_secret(name):
    try:
        return str(st.secrets.get(name, "")).strip()
    except Exception:
        return ""


def extract_card_number(text):
    if not text:
        return ""
    m = re.search(r"(\d+[A-Za-z]?/\d+[A-Za-z]?)", str(text))
    return m.group(1) if m else ""


def clean_card_name_for_search(text):
    text = str(text or "")
    text = re.sub(r"\s*-\s*\d+[A-Za-z]?/\d+[A-Za-z]?\s*$", "", text)
    text = re.sub(r"\s+\d+[A-Za-z]?/\d+[A-Za-z]?\s*$", "", text)
    return text.strip()


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_csv(url):
    r = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 CardScanner/0.3"},
        timeout=35,
        allow_redirects=True,
    )
    r.raise_for_status()
    if b"<html" in r.content[:500].lower():
        raise ValueError("CSV-osoite palautti HTML-sivun.")
    return pd.read_csv(io.BytesIO(r.content), encoding="utf-8-sig")


# ============================================================
# TCGPLAYER MONTHLY CANDIDATES
# ============================================================

def load_top_selling(min_price, max_price):
    frames = []

    if min_price < 50:
        df = fetch_csv(TCG_TOP_LOW_URL).copy()
        df["_bucket"] = "$1–49.99"
        frames.append(df)

    if max_price >= 50:
        df = fetch_csv(TCG_TOP_HIGH_URL).copy()
        df["_bucket"] = "$50+"
        frames.append(df)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True, sort=False)


def parse_top_selling(df):
    if df.empty:
        return df

    cols = list(df.columns)

    name_col = detect_column(cols, ["product name", "card name", "name", "product"])
    set_col = detect_column(cols, ["set name", "set", "expansion", "group name"])
    price_col = detect_column(
        cols,
        ["average sale price", "avg sale price", "average price", "sale price", "price"],
    )

    if not name_col or not price_col:
        raise ValueError(f"TCGplayer CSV:n sarakkeita ei tunnistettu: {cols}")

    out = pd.DataFrame()
    out["Kortti"] = df[name_col].astype(str)
    out["Setti"] = df[set_col].astype(str) if set_col else ""
    out["TCG raporttihinta"] = money_to_float(df[price_col])
    out["TCG candidate rank"] = range(1, len(out) + 1)
    out["Korttinumero"] = out["Kortti"].map(extract_card_number)
    out["Hakunimi"] = out["Kortti"].map(clean_card_name_for_search)
    return out


@st.cache_data(ttl=1800, show_spinner=False)
def load_candidates(min_price, max_price):
    raw = load_top_selling(min_price, max_price)
    parsed = parse_top_selling(raw)
    if parsed.empty:
        return parsed
    return parsed[
        (parsed["TCG raporttihinta"] >= min_price)
        & (parsed["TCG raporttihinta"] <= max_price)
    ].reset_index(drop=True)


# ============================================================
# TCGPLAYER PRICE TRENDS
# ============================================================

def parse_price_trends(df):
    cols = list(df.columns)

    name_col = detect_column(cols, ["product name", "card name", "name", "product"])
    set_col = detect_column(cols, ["set name", "set", "expansion", "group name"])
    old_col = detect_column(
        cols,
        [
            "market price 30 days ago",
            "market price 30d ago",
            "starting market price",
            "previous market price",
        ],
    )
    current_col = detect_column(
        cols,
        [
            "current market price",
            "market price today",
            "market price now",
            "new market price",
            "ending market price",
        ],
    )
    increase_col = detect_column(
        cols,
        ["price increase", "market price increase", "dollar increase", "price change"],
    )
    pct_col = detect_column(
        cols,
        ["percent increase", "percentage increase", "percent change", "percentage change"],
    )

    if not name_col:
        raise ValueError("Price Trends: kortin nimeä ei tunnistettu.")

    out = pd.DataFrame()
    out["Kortti"] = df[name_col].astype(str)
    out["Setti"] = df[set_col].astype(str) if set_col else ""

    old = money_to_float(df[old_col]) if old_col else pd.Series(pd.NA, index=df.index)
    change = money_to_float(df[increase_col]) if increase_col else pd.Series(pd.NA, index=df.index)
    current = money_to_float(df[current_col]) if current_col else pd.Series(pd.NA, index=df.index)

    old = pd.to_numeric(old, errors="coerce")
    change = pd.to_numeric(change, errors="coerce")
    current = pd.to_numeric(current, errors="coerce")

    current = current.fillna(old + change)
    old = old.fillna(current - change)
    change = change.fillna(current - old)

    if pct_col:
        pct = pd.to_numeric(money_to_float(df[pct_col]), errors="coerce")
        valid = pct.dropna()
        if len(valid) and valid.abs().median() <= 2:
            pct *= 100
    else:
        pct = pd.Series(pd.NA, index=df.index)

    pct = pct.fillna((change / old.replace(0, pd.NA)) * 100)

    out["30d alussa"] = old
    out["30d nyt"] = current
    out["30d $"] = change
    out["30d %"] = pct

    invalid = (out["30d alussa"] < 0) | (out["30d nyt"] < 0)
    out.loc[invalid, ["30d alussa", "30d nyt", "30d $", "30d %"]] = pd.NA
    return out


@st.cache_data(ttl=1800, show_spinner=False)
def load_price_trends():
    return parse_price_trends(fetch_csv(TCG_TRENDS_URL))


# ============================================================
# POKETRACE
# ============================================================

def poketrace_get(path, key, params=None):
    r = requests.get(
        f"{POKETRACE_BASE}{path}",
        headers={
            "X-API-Key": key,
            "User-Agent": "PokemonCardScanner/0.3",
        },
        params=params or {},
        timeout=30,
    )
    if r.status_code >= 400:
        try:
            msg = r.json().get("message") or r.json().get("error")
        except Exception:
            msg = r.text[:300]
        raise RuntimeError(f"PokeTrace {r.status_code}: {msg}")
    return r.json()


@st.cache_data(ttl=600, show_spinner=False)
def poketrace_auth_info(key):
    return poketrace_get("/auth/info", key)


@st.cache_data(ttl=1800, show_spinner=False)
def poketrace_search(key, search, card_number=""):
    params = {
        "market": "US",
        "game": "pokemon",
        "product_type": "single",
        "search": search,
        "limit": 20,
    }
    if card_number:
        params["card_number"] = card_number
    return poketrace_get("/cards", key, params)


def score_match(candidate_name, candidate_set, candidate_number, card):
    score = 0
    name = str(card.get("name", ""))
    set_name = str((card.get("set") or {}).get("name", ""))
    number = str(card.get("cardNumber", ""))

    if normalize_key(name) == normalize_key(candidate_name):
        score += 6
    elif normalize_key(candidate_name) in normalize_key(name) or normalize_key(name) in normalize_key(candidate_name):
        score += 3

    if candidate_set and normalize_key(set_name) == normalize_key(candidate_set):
        score += 6
    elif candidate_set and (
        normalize_key(candidate_set) in normalize_key(set_name)
        or normalize_key(set_name) in normalize_key(candidate_set)
    ):
        score += 2

    if candidate_number and normalize_key(number) == normalize_key(candidate_number):
        score += 5

    return score


@st.cache_data(ttl=1800, show_spinner=False)
def map_candidate_to_poketrace(key, card_name, set_name, card_number):
    query_name = clean_card_name_for_search(card_name)
    payload = poketrace_search(key, query_name, card_number)
    cards = payload.get("data", []) or []

    if not cards and card_number:
        payload = poketrace_search(key, query_name, "")
        cards = payload.get("data", []) or []

    if not cards:
        return None

    scored = sorted(
        [(score_match(query_name, set_name, card_number, c), c) for c in cards],
        key=lambda x: x[0],
        reverse=True,
    )

    best_score, best = scored[0]
    if best_score < 3:
        return None
    return best


@st.cache_data(ttl=1800, show_spinner=False)
def poketrace_history(key, card_id, period):
    api_period = "30d" if period == "14d" else period
    limit = 30 if api_period == "30d" else 10
    return poketrace_get(
        f"/cards/{card_id}/prices/NEAR_MINT/history",
        key,
        {"period": api_period, "limit": limit},
    )


def period_history_rows(history_payload, wanted_period):
    rows = history_payload.get("data", []) or []
    if wanted_period != "14d":
        return rows

    dated = []
    for row in rows:
        try:
            d = datetime.strptime(str(row.get("date")), "%Y-%m-%d").date()
            dated.append((d, row))
        except Exception:
            pass

    if not dated:
        return rows

    max_date = max(d for d, _ in dated)
    cutoff = max_date - timedelta(days=13)
    return [row for d, row in dated if d >= cutoff]


def summarize_poketrace_card(card, history_rows):
    prices = card.get("prices") or {}
    tcg = (prices.get("tcgplayer") or {}).get("NEAR_MINT") or {}
    ebay = (prices.get("ebay") or {}).get("NEAR_MINT") or {}

    tcg_rows = [r for r in history_rows if str(r.get("source", "")).lower() == "tcgplayer"]
    ebay_rows = [r for r in history_rows if str(r.get("source", "")).lower() == "ebay"]

    tcg_sold = sum(float(r.get("saleCount") or 0) for r in tcg_rows)
    ebay_sold = sum(float(r.get("saleCount") or 0) for r in ebay_rows)

    # Prefer rolling average from most recent history row, otherwise current avg.
    tcg_rows_sorted = sorted(tcg_rows, key=lambda r: str(r.get("date", "")), reverse=True)
    latest = tcg_rows_sorted[0] if tcg_rows_sorted else {}

    return {
        "PokeTrace ID": card.get("id"),
        "Variant": card.get("variant") or "",
        "TCG NM": tcg.get("avg"),
        "TCG low": tcg.get("low"),
        "TCG myyty": int(tcg_sold),
        "eBay raw myyty": int(ebay_sold),
        "avg7d": latest.get("avg7d"),
        "avg30d": latest.get("avg30d"),
        "Päivitetty": card.get("lastUpdated"),
    }


def build_live_sales_scan(candidates, key, period, max_cards):
    rows = []
    progress = st.progress(0)
    status = st.empty()

    subset = candidates.head(max_cards).copy()

    for i, (_, candidate) in enumerate(subset.iterrows(), start=1):
        status.caption(
            f"{i}/{len(subset)} • {candidate['Kortti']} • {candidate['Setti']}"
        )

        try:
            card = map_candidate_to_poketrace(
                key,
                candidate["Kortti"],
                candidate["Setti"],
                candidate["Korttinumero"],
            )
            if not card:
                progress.progress(i / len(subset))
                continue

            history = poketrace_history(key, str(card["id"]), period)
            history_rows = period_history_rows(history, period)
            live = summarize_poketrace_card(card, history_rows)

            rows.append(
                {
                    "Kortti": candidate["Kortti"],
                    "Setti": candidate["Setti"],
                    "Variant": live["Variant"],
                    f"Myyty {period} TCG": live["TCG myyty"],
                    f"Myyty {period} eBay": live["eBay raw myyty"],
                    "TCG NM": live["TCG NM"],
                    "TCG low": live["TCG low"],
                    "7d avg": live["avg7d"],
                    "30d avg": live["avg30d"],
                    "PokeTrace ID": live["PokeTrace ID"],
                }
            )
        except Exception as exc:
            # History access is Pro+. Stop immediately on access-plan failure.
            msg = str(exc)
            if "403" in msg or "Pro" in msg or "plan" in msg.lower():
                progress.empty()
                status.empty()
                raise RuntimeError(
                    "PokeTrace history ei ole käytettävissä tällä API-tasolla. "
                    "7/14/30 päivän tarkat myyntimäärät vaativat PokeTrace Pro -historian."
                ) from exc

        progress.progress(i / len(subset))

    progress.empty()
    status.empty()

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows)
    sold_col = f"Myyty {period} TCG"
    result = result.sort_values(
        [sold_col, "TCG NM"],
        ascending=[False, True],
    ).reset_index(drop=True)
    return result


# ============================================================
# PRICECHARTING (OPTIONAL)
# ============================================================

def pc_request(path, token, params):
    r = requests.get(
        f"{PRICECHARTING_BASE}{path}",
        params={"t": token, **params},
        timeout=30,
        headers={"User-Agent": "PokemonCardScanner/0.3"},
    )
    r.raise_for_status()
    payload = r.json()
    if payload.get("status") == "error":
        raise RuntimeError(payload.get("error-message", "PriceCharting API error"))
    return payload


# ============================================================
# SIDEBAR
# ============================================================

st.title("Pokémon Card Scanner")
st.caption("Raw / ungraded Pokémon -korttien myynti- ja hintatrendit.")

with st.sidebar:
    st.subheader("Scanner")

    c1, c2 = st.columns(2)
    min_price = c1.number_input("Min $", min_value=0.0, value=5.0, step=1.0)
    max_price = c2.number_input("Max $", min_value=0.0, value=20.0, step=1.0)

    period = st.segmented_control(
        "Myyntijakso",
        options=["7d", "14d", "30d"],
        default="30d",
    )

    top_n = st.selectbox("Näytä Top", [10, 20, 30, 50], index=3)

    st.caption(
        "TCGplayerin kuukausiraporttia käytetään ensin candidate-listana. "
        "PokeTrace-history antaa varsinaisen 7/14/30d myyntimäärän."
    )

    search_clicked = st.button(
        "🔎 Hae kortit",
        type="primary",
        use_container_width=True,
    )

    st.divider()
    poketrace_key = get_secret("POKETRACE_API_KEY")
    if poketrace_key:
        st.success("PokeTrace API-avain käytössä")
    else:
        st.warning("PokeTrace API-avain puuttuu")

    st.caption(f"TCG candidate report: {TCG_PERIOD_LABEL}")


# ============================================================
# LOAD CANDIDATES
# ============================================================

if search_clicked:
    if max_price < min_price:
        st.sidebar.error("Max-hinnan pitää olla vähintään Min-hinta.")
    else:
        with st.spinner("Haetaan TCGplayer candidate-lista..."):
            try:
                st.session_state["candidates"] = load_candidates(min_price, max_price)
                st.session_state["loaded_range"] = (min_price, max_price)
            except Exception as exc:
                st.error(f"TCGplayer-datan haku epäonnistui: {exc}")

candidates = st.session_state.get("candidates", pd.DataFrame())


# ============================================================
# TABS
# ============================================================

tab_scan, tab_movers, tab_pc, tab_status = st.tabs(
    ["🔥 Myyntiskanneri", "📈 30d nousijat", "💲 PriceCharting", "⚙️ Data"]
)


# ============================================================
# MAIN SALES SCANNER
# ============================================================

with tab_scan:
    st.subheader("Myydyimmät raw-kortit")

    if candidates.empty:
        st.info("Valitse hintahaarukka ja paina **🔎 Hae kortit**.")
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric("Candidate-kortteja", len(candidates))
        m2.metric("Hintahaarukka", f"${min_price:.0f}–${max_price:.0f}")
        m3.metric("Jakso", period)

        if not poketrace_key:
            st.warning(
                "Tarkat 7/14/30d kappalemäärät tarvitsevat PokeTrace-historyn. "
                "Lisää `POKETRACE_API_KEY` Streamlit Secretsiin."
            )

            fallback = candidates.head(top_n)[
                ["Kortti", "Setti", "TCG raporttihinta"]
            ].copy()

            st.dataframe(
                fallback,
                use_container_width=True,
                hide_index=True,
                height=min(620, 38 + 31 * len(fallback)),
                column_config={
                    "TCG raporttihinta": st.column_config.NumberColumn(
                        "TCG avg", format="$%.2f", width="small"
                    ),
                    "Kortti": st.column_config.TextColumn(width="medium"),
                    "Setti": st.column_config.TextColumn(width="medium"),
                },
            )
        else:
            scan_limit = min(top_n, len(candidates))

            st.caption(
                f"Skannataan enintään {scan_limit} TCGplayerin kuukausiraportin "
                "vahvinta candidatea ja järjestetään ne PokeTrace-historyn "
                f"todellisen {period}-myyntimäärän mukaan."
            )

            if st.button(
                f"▶ Laske myydyt {period}",
                use_container_width=True,
                type="secondary",
            ):
                try:
                    with st.spinner("Haetaan myyntihistoriaa..."):
                        result = build_live_sales_scan(
                            candidates,
                            poketrace_key,
                            period,
                            scan_limit,
                        )
                    st.session_state["live_result"] = result
                    st.session_state["live_period"] = period
                except Exception as exc:
                    st.error(str(exc))

            result = st.session_state.get("live_result", pd.DataFrame())

            if not result.empty:
                sold_col = f"Myyty {st.session_state.get('live_period', period)} TCG"
                ebay_col = f"Myyty {st.session_state.get('live_period', period)} eBay"

                metric_a, metric_b, metric_c = st.columns(3)
                metric_a.metric("Kortteja", len(result))
                metric_b.metric(
                    "TCG myyty yhteensä",
                    f"{int(result[sold_col].sum()):,}".replace(",", " "),
                )
                metric_c.metric(
                    "Top-kortin myynnit",
                    int(result.iloc[0][sold_col]),
                )

                display = result[
                    [
                        "Kortti",
                        "Setti",
                        sold_col,
                        "TCG NM",
                        "7d avg",
                        "30d avg",
                        ebay_col,
                        "Variant",
                    ]
                ].copy()

                st.dataframe(
                    display,
                    use_container_width=True,
                    hide_index=True,
                    height=min(680, 40 + 30 * len(display)),
                    column_config={
                        sold_col: st.column_config.NumberColumn(
                            sold_col.replace(" TCG", ""),
                            format="%d",
                            width="small",
                        ),
                        ebay_col: st.column_config.NumberColumn(
                            "eBay raw", format="%d", width="small"
                        ),
                        "TCG NM": st.column_config.NumberColumn(
                            "TCG NM", format="$%.2f", width="small"
                        ),
                        "7d avg": st.column_config.NumberColumn(
                            "7d avg", format="$%.2f", width="small"
                        ),
                        "30d avg": st.column_config.NumberColumn(
                            "30d avg", format="$%.2f", width="small"
                        ),
                        "Kortti": st.column_config.TextColumn(width="medium"),
                        "Setti": st.column_config.TextColumn(width="medium"),
                        "Variant": st.column_config.TextColumn(width="small"),
                    },
                )

                st.download_button(
                    "Lataa CSV",
                    result.to_csv(index=False).encode("utf-8-sig"),
                    file_name=f"pokemon_raw_sold_{st.session_state.get('live_period', period)}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )


# ============================================================
# MOVERS
# ============================================================

with tab_movers:
    st.subheader("TCGplayer 30d Near Mint -nousijat")

    try:
        movers = load_price_trends().copy()
        current = pd.to_numeric(movers["30d nyt"], errors="coerce")
        movers = movers[
            (current >= min_price) & (current <= max_price)
        ].copy()
        movers = movers.sort_values("30d %", ascending=False).head(top_n)

        compact = movers[
            ["Kortti", "Setti", "30d alussa", "30d nyt", "30d $", "30d %"]
        ]

        st.dataframe(
            compact,
            use_container_width=True,
            hide_index=True,
            height=min(680, 40 + 30 * len(compact)),
            column_config={
                "30d alussa": st.column_config.NumberColumn(
                    "30d ago", format="$%.2f", width="small"
                ),
                "30d nyt": st.column_config.NumberColumn(
                    "Nyt", format="$%.2f", width="small"
                ),
                "30d $": st.column_config.NumberColumn(
                    "Δ $", format="$%+.2f", width="small"
                ),
                "30d %": st.column_config.NumberColumn(
                    "Δ %", format="%+.1f%%", width="small"
                ),
                "Kortti": st.column_config.TextColumn(width="medium"),
                "Setti": st.column_config.TextColumn(width="medium"),
            },
        )
    except Exception as exc:
        st.error(f"30d movers -dataa ei saatu: {exc}")


# ============================================================
# PRICECHARTING
# ============================================================

with tab_pc:
    st.subheader("PriceCharting")
    st.caption(
        "Valinnainen toinen raw-hintalähde. Ei käytetä 7/14/30d "
        "myyntimäärän lähteenä."
    )

    pc_token = get_secret("PRICECHARTING_TOKEN")
    if not pc_token:
        pc_token = st.text_input("PriceCharting token", type="password")

    pc_query = st.text_input("Korttihaku", placeholder="esim. Charizard 4 Base Set")

    if st.button(
        "Hae PriceChartingista",
        disabled=not bool(pc_token and pc_query.strip()),
    ):
        try:
            data = pc_request("/api/products", pc_token, {"q": pc_query.strip()})
            products = data.get("products", [])
            st.session_state["pc_products"] = products
        except Exception as exc:
            st.error(str(exc))

    products = st.session_state.get("pc_products", [])
    if products:
        rows = []
        for p in products[:20]:
            rows.append(
                {
                    "Nimi": p.get("product-name"),
                    "Setti": p.get("console-name"),
                    "ID": p.get("id"),
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ============================================================
# DATA STATUS
# ============================================================

with tab_status:
    st.subheader("Datalähteet")

    rows = [
        {
            "Lähde": "TCGplayer Top Selling",
            "Käyttö": "Candidate-lista",
            "Jakso": "Kuukausi",
            "Tarkka sold count": "Ei julkisessa CSV:ssä",
        },
        {
            "Lähde": "PokeTrace TCGplayer history",
            "Käyttö": "Raw/NM myyntimäärä",
            "Jakso": "7 / 14 / 30d",
            "Tarkka sold count": "Kyllä, history saleCount",
        },
        {
            "Lähde": "PokeTrace eBay",
            "Käyttö": "Raw sold vertailu",
            "Jakso": "7 / 14 / 30d",
            "Tarkka sold count": "Observed / eBay voi olla approximate",
        },
        {
            "Lähde": "PriceCharting",
            "Käyttö": "Raw nykyhinta + likviditeetti",
            "Jakso": "Nykyinen / vuosivolyymi",
            "Tarkka sold count": "Ei 7/30d",
        },
    ]

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if poketrace_key:
        try:
            info = poketrace_auth_info(poketrace_key)
            user = (info.get("data") or {}).get("user") or {}
            st.write(
                f"**PokeTrace plan:** {user.get('plan', 'Unknown')}  \n"
                f"**Remaining:** {user.get('remaining', '–')} / {user.get('limit', '–')}"
            )
        except Exception as exc:
            st.warning(f"PokeTrace auth-info ei onnistunut: {exc}")

    st.code(
        'POKETRACE_API_KEY = "oma_avain"\n'
        'PRICECHARTING_TOKEN = "oma_token"',
        language="toml",
    )
    st.caption("Lisää avaimet Streamlit → App settings → Secrets. Älä committaa niitä GitHubiin.")


st.divider()
st.caption(
    "v0.3 • Raw only • TCG rank ei ole enää päämittari. "
    "Tavoite: todelliset 7/14/30d myyntimäärät."
)
