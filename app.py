
import time
from datetime import datetime, timedelta

import pandas as pd
import requests
import streamlit as st

# ============================================================
# APP
# ============================================================

st.set_page_config(
    page_title="Pokémon Card Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

POKETRACE_BASE = "https://api.poketrace.com/v1"
RAREBIT_BASE = "https://api.rarebit.app/api"
PRICECHARTING_BASE = "https://www.pricecharting.com"

# Hard pre-filter for raw cards. US source prices are USD.
HARD_MIN_RAW_PRICE = 1.00

st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
      :root { --ink: #e8edf2; --muted: #9aa7b4; --accent: #d49a5b; --accent-soft: #2c231c; --paper: #0b1117; --panel: #141c25; --panel-raised: #1a2530; }
      html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; color: var(--ink); }
      [data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"] * { color: var(--ink); }
      h1, h2, h3, [data-testid="stMarkdownContainer"] h1, [data-testid="stMarkdownContainer"] h2, [data-testid="stMarkdownContainer"] h3 { font-family: 'Space Grotesk', sans-serif; letter-spacing: -0.035em; color: var(--ink) !important; }
      [data-testid="stAppViewContainer"] { background: radial-gradient(circle at 78% -10%, #1f2a35 0, transparent 32rem), var(--paper); }
      .block-container {
        padding-top: 2.5rem;
        padding-bottom: 4rem;
        max-width: 1420px;
      }
      [data-testid="stMetric"] { background: var(--panel); border: 1px solid #263442; border-radius: 1rem; padding: .9rem 1rem; box-shadow: 0 18px 40px rgba(0,0,0,.18); }
      [data-testid="stMetricLabel"], [data-testid="stCaptionContainer"] { color: var(--muted) !important; }
      [data-testid="stMetricValue"] { font-family: 'Space Grotesk', sans-serif; font-size: 1.5rem; color: var(--ink) !important; font-variant-numeric: tabular-nums; }
      div[data-testid="stDataFrame"] { font-size: .82rem; border: 1px solid #263442; border-radius: 1rem; overflow: hidden; }
      .stTabs [data-baseweb="tab"] {
        padding: .65rem 1rem;
        font-weight: 600;
      }
      .stTabs [data-baseweb="tab"] p, .stTabs [data-baseweb="tab"] div { color: var(--muted) !important; }
      .stTabs [aria-selected="true"] p, .stTabs [aria-selected="true"] div { color: var(--accent) !important; }
      .stTabs [data-baseweb="tab-highlight"] { background: var(--accent); }
      .stButton > button { border-radius: .75rem; min-height: 2.7rem; font-weight: 600; transition: transform .3s cubic-bezier(.32,.72,0,1), box-shadow .3s cubic-bezier(.32,.72,0,1); background: var(--panel-raised); border: 1px solid #30404f; color: var(--ink); }
      .stButton > button[kind="primary"] { background: var(--accent); border-color: var(--accent); color: #17120e; }
      .stButton > button[kind="primary"]:hover { background: #e1ab70; border-color: #e1ab70; }
      .stButton > button:hover { transform: translateY(-2px); box-shadow: 0 10px 22px rgba(0,0,0,.22); }
      [data-testid="stSidebar"] { background: #101820; border-right: 1px solid #263442; }
      [data-testid="stSidebar"] label, [data-testid="stSidebar"] label p, [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: var(--ink) !important; }
      [data-testid="stSidebar"] input, [data-testid="stSidebar"] [role="combobox"] { color: var(--ink) !important; background: var(--panel) !important; border-color: #30404f !important; }
      [data-testid="stAlert"] { background: var(--panel) !important; border: 1px solid #30404f; }
      [data-testid="stAlert"] p, [data-testid="stAlert"] span { color: var(--ink) !important; }
      .eyebrow { color: var(--accent) !important; font-size: .72rem; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; margin-bottom: .4rem; }
      .hero { background: linear-gradient(135deg, #17212b, #111921); border: 1px solid #2b3a48; border-radius: 1.5rem; padding: 2rem 2.2rem; margin-bottom: 1.4rem; box-shadow: 0 24px 55px rgba(0,0,0,.22); }
      .hero h1 { color: var(--ink) !important; }
      .hero p { color: var(--muted) !important; max-width: 48rem; margin-bottom: 0; }
      .callout { background: var(--panel); border: 1px solid #30404f; border-left: 4px solid var(--accent); border-radius: .9rem; padding: 1rem 1.1rem; color: var(--muted) !important; }
      [data-testid="stSelectbox"] [data-baseweb="select"] > div, [data-testid="stNumberInput"] input { background: var(--panel) !important; color: var(--ink) !important; border-color: #30404f !important; }
      [data-testid="stSelectbox"] svg { fill: var(--muted) !important; }
      hr { border-color: #263442 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# API KEY MANAGEMENT
# ============================================================

PROVIDERS = {
    "PokeTrace": {
        "secret": "POKETRACE_API_KEY",
        "session": "api_poketrace",
        "used": True,
    },
    "RareBit": {
        "secret": "RAREBIT_API_KEY",
        "session": "api_rarebit",
        "used": False,
    },
    "PriceCharting": {
        "secret": "PRICECHARTING_TOKEN",
        "session": "api_pricecharting",
        "used": True,
    },
    "CardmarketAPI": {
        "secret": "CARDMARKETAPI_KEY",
        "session": "api_cardmarketapi",
        "used": False,
    },
}


def secret_value(name):
    try:
        value = st.secrets.get(name, "")
        return str(value).strip() if value else ""
    except Exception:
        return ""


def provider_key(provider):
    cfg = PROVIDERS[provider]
    override = st.session_state.get(cfg["session"], "").strip()
    if override:
        return override
    return secret_value(cfg["secret"])


def provider_key_source(provider):
    cfg = PROVIDERS[provider]
    if st.session_state.get(cfg["session"], "").strip():
        return "session"
    if secret_value(cfg["secret"]):
        return "Streamlit Secrets"
    return None


# ============================================================
# HTTP HELPERS
# ============================================================

def safe_json(response):
    try:
        return response.json()
    except Exception:
        return {}


def poketrace_get(path, key, params=None):
    response = requests.get(
        f"{POKETRACE_BASE}{path}",
        headers={
            "X-API-Key": key,
            "User-Agent": "PokemonCardScanner/0.4",
        },
        params=params or {},
        timeout=35,
    )

    if response.status_code >= 400:
        payload = safe_json(response)
        msg = (
            payload.get("message")
            or payload.get("error")
            or payload.get("detail")
            or response.text[:250]
        )
        raise RuntimeError(f"PokeTrace {response.status_code}: {msg}")

    return response.json(), {
        "limit": response.headers.get("X-RateLimit-Limit"),
        "remaining": response.headers.get("X-RateLimit-Remaining"),
    }


@st.cache_data(ttl=300, show_spinner=False)
def poketrace_auth_info(key):
    payload, headers = poketrace_get("/auth/info", key)
    return payload, headers


def get_plan_info(key):
    payload, headers = poketrace_auth_info(key)
    data = payload.get("data") or {}
    user = data.get("user") or {}

    return {
        "plan": str(user.get("plan") or "Unknown"),
        "remaining": user.get("remaining", headers.get("remaining")),
        "limit": user.get("limit", headers.get("limit")),
        "resetsAt": user.get("resetsAt"),
    }


def plan_has_history(plan):
    return str(plan).lower() in {"pro", "growth", "scale"}


def free_plan_delay(plan):
    return 2.1 if str(plan).lower() == "free" else 0.36


# ============================================================
# CARD PARSING
# ============================================================

def safe_num(value):
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def pct_change(newer, older):
    newer = safe_num(newer)
    older = safe_num(older)
    if newer is None or older in (None, 0):
        return None
    return (newer - older) / older * 100


def parse_us_card(card):
    prices = card.get("prices") or {}
    tcg = (prices.get("tcgplayer") or {}).get("NEAR_MINT") or {}
    ebay = (prices.get("ebay") or {}).get("NEAR_MINT") or {}
    set_data = card.get("set") or {}
    refs = card.get("refs") or {}

    tcg_avg = safe_num(tcg.get("avg"))
    tcg_low = safe_num(tcg.get("low"))
    tcg_avg1 = safe_num(tcg.get("avg1d"))
    tcg_avg7 = safe_num(tcg.get("avg7d"))
    tcg_avg30 = safe_num(tcg.get("avg30d"))

    return {
        "id": str(card.get("id") or ""),
        "Kortti": card.get("name") or "",
        "Numero": card.get("cardNumber") or "",
        "Setti": set_data.get("name") or "",
        "Set slug": set_data.get("slug") or "",
        "Variant": card.get("variant") or "",
        "Rarity": card.get("rarity") or "",
        "TCG NM": tcg_avg,
        "TCG low": tcg_low,
        "TCG cumulative saleCount proxy": int(tcg.get("saleCount") or 0),
        "TCG approx": bool(tcg.get("approxSaleCount", False)),
        "TCG 1d avg": tcg_avg1,
        "TCG 7d avg": tcg_avg7,
        "TCG 30d avg": tcg_avg30,
        "7d vs 30d %": pct_change(tcg_avg7, tcg_avg30),
        "1d vs 7d %": pct_change(tcg_avg1, tcg_avg7),
        "eBay NM": safe_num(ebay.get("avg")),
        "eBay low": safe_num(ebay.get("low")),
        "eBay cumulative saleCount proxy": int(ebay.get("saleCount") or 0),
        "eBay approx": bool(ebay.get("approxSaleCount", True)),
        "TCGplayer ID": refs.get("tcgplayerId"),
        "Last updated": card.get("lastUpdated"),
    }


def add_market_comparison(df):
    """Add transparent cross-source price fields for the manual EU handoff."""
    if df.empty:
        return df

    work = df.copy()
    tcg = pd.to_numeric(work.get("TCG NM"), errors="coerce")
    if "eBay sold avg 30d" not in work:
        work["eBay sold avg 30d"] = pd.NA
    ebay = pd.to_numeric(work["eBay sold avg 30d"], errors="coerce")
    work["Price sources"] = (
        tcg.notna().astype(int) + ebay.notna().astype(int)
    ).map({0: "Ei hintaa", 1: "1 lähde", 2: "2 lähdettä"})
    work["US reference"] = pd.concat([tcg, ebay], axis=1).median(axis=1, skipna=True)
    work["TCG vs eBay sold %"] = (
        (tcg - ebay) / ebay.replace(0, pd.NA) * 100
    ).round(1)
    work["TCG below eBay sold"] = (tcg < ebay).where(
        tcg.notna() & ebay.notna()
    )
    return work


def card_matches_price(row, min_price, max_price):
    price = row.get("TCG NM")
    if price is None:
        return False

    # Stage 1: always reject sub-$1 raw cards before they enter the
    # candidate pool or become eligible for any later/history API calls.
    effective_min = max(float(min_price), HARD_MIN_RAW_PRICE)

    return effective_min <= price <= max_price



# ============================================================
# SET CATALOG / BROAD COVERAGE
# ============================================================

@st.cache_data(ttl=86400, show_spinner=False)
def load_all_sets(key, game, plan):
    """Load the set catalog once and cache it for a day."""
    rows = []
    cursor = None

    # Use conservative page size. /sets supports cursor pagination.
    while True:
        params = {
            "game": game,
            "limit": 50,
        }
        if cursor:
            params["cursor"] = cursor

        payload, _ = poketrace_get("/sets", key, params)
        data = payload.get("data") or []
        rows.extend(data)

        pagination = payload.get("pagination") or {}
        cursor = pagination.get("nextCursor")
        has_more = bool(pagination.get("hasMore")) and bool(cursor)

        if not has_more:
            break

        time.sleep(free_plan_delay(plan))

        # Hard safety stop.
        if len(rows) > 2000:
            break

    sets_df = pd.DataFrame(
        [
            {
                "slug": row.get("slug"),
                "name": row.get("name"),
                "releaseDate": row.get("releaseDate"),
                "cardCount": row.get("cardCount"),
            }
            for row in rows
            if row.get("slug")
        ]
    )

    if sets_df.empty:
        return sets_df

    sets_df["releaseDateParsed"] = pd.to_datetime(
        sets_df["releaseDate"], errors="coerce"
    )

    return sets_df.sort_values(
        ["releaseDateParsed", "name"],
        ascending=[False, True],
        na_position="last",
    ).reset_index(drop=True)


def balanced_set_batch(sets_df, batch_size, round_no, mode):
    """
    Return a varied batch of sets.

    Balanced mode immediately spreads the requests over the full release
    timeline instead of taking Base Set, Base Set 2, ... consecutively.
    """
    if sets_df.empty:
        return sets_df

    work = sets_df.copy().reset_index(drop=True)
    n = len(work)
    batch_size = max(1, min(int(batch_size), n))

    if mode == "Uusimmat":
        start = (round_no * batch_size) % n
        idx = [(start + i) % n for i in range(batch_size)]
        return work.iloc[idx].reset_index(drop=True)

    if mode == "Vanhimmat":
        work = work.iloc[::-1].reset_index(drop=True)
        start = (round_no * batch_size) % n
        idx = [(start + i) % n for i in range(batch_size)]
        return work.iloc[idx].reset_index(drop=True)

    # "Tasaisesti kaikki"
    # Divide the entire chronology into batch_size lanes. Each successive
    # round advances one position inside every lane.
    idx = []
    for lane in range(batch_size):
        start = int(lane * n / batch_size)
        end = int((lane + 1) * n / batch_size)
        lane_len = max(1, end - start)
        pos = start + (round_no % lane_len)
        if pos < n:
            idx.append(pos)

    # Keep unique positions while preserving order.
    seen = set()
    unique_idx = []
    for i in idx:
        if i not in seen:
            unique_idx.append(i)
            seen.add(i)

    return work.iloc[unique_idx].reset_index(drop=True)


def fetch_cards_from_set(
    key,
    set_slug,
    game,
    variant,
    cursor=None,
):
    params = {
        "market": "US",
        "game": game,
        "product_type": "single",
        "set": set_slug,
        "limit": 20,
    }

    if variant != "Kaikki":
        params["variant"] = variant

    if cursor:
        params["cursor"] = cursor

    payload, headers = poketrace_get("/cards", key, params)
    pagination = payload.get("pagination") or {}

    return (
        payload.get("data") or [],
        pagination.get("nextCursor"),
        bool(pagination.get("hasMore")),
        headers,
    )


def scan_across_sets(
    key,
    plan,
    sets_df,
    sets_per_scan,
    min_price,
    max_price,
    game,
    variant,
    coverage_mode,
    reset=False,
):
    """
    Scan one page from several different sets per run.

    This is intentionally different from global /cards cursor pagination,
    which begins with the oldest catalog records and therefore produced
    Base Set / Base Set 2 repeatedly.
    """
    if reset:
        st.session_state["broad_pool"] = []
        st.session_state["broad_round"] = 0
        st.session_state["broad_scanned_cards"] = 0
        st.session_state["broad_scanned_sets"] = []
        st.session_state["set_cursors"] = {}

    pool = list(st.session_state.get("broad_pool", []))
    round_no = int(st.session_state.get("broad_round", 0))
    scanned_cards = int(st.session_state.get("broad_scanned_cards", 0))
    scanned_sets = list(st.session_state.get("broad_scanned_sets", []))
    set_cursors = dict(st.session_state.get("set_cursors", {}))

    existing_ids = {r.get("id") for r in pool if r.get("id")}

    batch = balanced_set_batch(
        sets_df,
        sets_per_scan,
        round_no,
        coverage_mode,
    )

    progress = st.progress(0)
    status = st.empty()

    for i, (_, set_row) in enumerate(batch.iterrows(), start=1):
        slug = str(set_row["slug"])
        set_name = str(set_row["name"])

        status.caption(
            f"{i}/{len(batch)} • {set_name} • löydetty hintaan {len(pool)}"
        )

        cursor = set_cursors.get(slug)

        cards, next_cursor, has_more, _ = fetch_cards_from_set(
            key=key,
            set_slug=slug,
            game=game,
            variant=variant,
            cursor=cursor,
        )

        for card in cards:
            parsed = parse_us_card(card)
            if parsed["id"] and parsed["id"] not in existing_ids:
                if card_matches_price(parsed, min_price, max_price):
                    pool.append(parsed)
                    existing_ids.add(parsed["id"])

        scanned_cards += len(cards)
        scanned_sets.append(set_name)

        # Keep a per-set cursor. If the set ends, restart at page 1 next time
        # only after other sets have had their turns.
        if has_more and next_cursor:
            set_cursors[slug] = next_cursor
        else:
            set_cursors.pop(slug, None)

        progress.progress(i / len(batch))

        if i < len(batch):
            time.sleep(free_plan_delay(plan))

    st.session_state["broad_pool"] = pool
    st.session_state["broad_round"] = round_no + 1
    st.session_state["broad_scanned_cards"] = scanned_cards
    st.session_state["broad_scanned_sets"] = scanned_sets[-200:]
    st.session_state["set_cursors"] = set_cursors

    progress.empty()
    status.empty()

    return pd.DataFrame(pool), batch


# ============================================================
# DIRECT POKETRACE SCAN
# ============================================================

def scan_poketrace_pages(
    key,
    plan,
    pages,
    min_price,
    max_price,
    game,
    variant,
    reset=False,
):
    if reset:
        st.session_state["pt_cursor"] = None
        st.session_state["pt_has_more"] = True
        st.session_state["pt_scanned_cards"] = 0
        st.session_state["pt_pool"] = []

    cursor = st.session_state.get("pt_cursor")
    has_more = st.session_state.get("pt_has_more", True)
    scanned_cards = int(st.session_state.get("pt_scanned_cards", 0))
    pool = list(st.session_state.get("pt_pool", []))

    existing_ids = {row["id"] for row in pool if row.get("id")}

    progress = st.progress(0)
    status = st.empty()

    last_headers = {}

    for page_no in range(pages):
        if not has_more:
            break

        params = {
            "market": "US",
            "game": game,
            "product_type": "single",
            "limit": 20,
        }

        if cursor:
            params["cursor"] = cursor

        if variant != "Kaikki":
            params["variant"] = variant

        status.caption(
            f"Sivu {page_no + 1}/{pages} • skannattu {scanned_cards} korttia"
        )

        payload, last_headers = poketrace_get("/cards", key, params)

        cards = payload.get("data") or []
        pagination = payload.get("pagination") or {}

        for card in cards:
            row = parse_us_card(card)
            if row["id"] and row["id"] not in existing_ids:
                if card_matches_price(row, min_price, max_price):
                    pool.append(row)
                    existing_ids.add(row["id"])

        scanned_cards += len(cards)
        cursor = pagination.get("nextCursor")
        has_more = bool(pagination.get("hasMore")) and bool(cursor)

        st.session_state["pt_cursor"] = cursor
        st.session_state["pt_has_more"] = has_more
        st.session_state["pt_scanned_cards"] = scanned_cards
        st.session_state["pt_pool"] = pool

        progress.progress((page_no + 1) / pages)

        # Respect the current account's burst tier.
        if page_no < pages - 1 and has_more:
            time.sleep(free_plan_delay(plan))

    progress.empty()
    status.empty()

    return pd.DataFrame(pool), last_headers


# ============================================================
# HISTORY FOR PRO+
# ============================================================

def history_window_api_period(period):
    if period == "7d":
        return "7d", 7
    if period == "14d":
        # API has no 14d enum. Fetch 30d and crop locally.
        return "30d", 30
    return "30d", 30


def history_crop(rows, period):
    if period != "14d":
        return rows

    parsed = []
    for row in rows:
        try:
            date = datetime.strptime(str(row.get("date")), "%Y-%m-%d").date()
            parsed.append((date, row))
        except Exception:
            continue

    if not parsed:
        return rows

    newest = max(date for date, _ in parsed)
    cutoff = newest - timedelta(days=13)
    return [row for date, row in parsed if date >= cutoff]


def get_period_sales(key, card_id, period):
    api_period, limit = history_window_api_period(period)
    payload, _ = poketrace_get(
        f"/cards/{card_id}/prices/NEAR_MINT/history",
        key,
        {"period": api_period, "limit": limit},
    )

    rows = history_crop(payload.get("data") or [], period)

    tcg_rows = [
        row
        for row in rows
        if str(row.get("source", "")).lower() == "tcgplayer"
    ]
    ebay_rows = [
        row
        for row in rows
        if str(row.get("source", "")).lower() == "ebay"
    ]

    tcg_sold = sum(int(row.get("saleCount") or 0) for row in tcg_rows)
    ebay_sold = sum(int(row.get("saleCount") or 0) for row in ebay_rows)

    def sale_price(row):
        for field in ("salePrice", "soldPrice", "price"):
            value = safe_num(row.get(field))
            if value is not None:
                return value
        return None

    ebay_sale_prices = [
        price for price in (sale_price(row) for row in ebay_rows)
        if price is not None
    ]

    return {
        "tcg": tcg_sold,
        "ebay": ebay_sold,
        "ebay_sold_avg": (
            sum(ebay_sale_prices) / len(ebay_sale_prices)
            if ebay_sale_prices
            else None
        ),
    }


def enrich_period_sales(key, df, period, max_rows, plan):
    if df.empty:
        return df

    work = df.sort_values(
        ["7d vs 30d %", "TCG 30d avg"],
        ascending=[False, False],
        na_position="last",
    ).head(max_rows).copy()

    tcg_values = []
    ebay_values = []
    ebay_sold_prices = []
    errors = []

    progress = st.progress(0)
    status = st.empty()

    for i, (_, row) in enumerate(work.iterrows(), start=1):
        status.caption(f"{i}/{len(work)} • {row['Kortti']} • {row['Setti']}")
        try:
            sold = get_period_sales(key, row["id"], period)
            tcg_values.append(sold["tcg"])
            ebay_values.append(sold["ebay"])
            ebay_sold_prices.append(sold["ebay_sold_avg"])
        except requests.RequestException as exc:
            tcg_values.append(None)
            ebay_values.append(None)
            ebay_sold_prices.append(None)
            errors.append(f"{row['Kortti']}: verkkopyyntö epäonnistui ({exc})")
        except (KeyError, TypeError, ValueError, RuntimeError) as exc:
            tcg_values.append(None)
            ebay_values.append(None)
            ebay_sold_prices.append(None)
            errors.append(f"{row['Kortti']}: historiadataa ei voitu lukea ({exc})")

        progress.progress(i / len(work))

        if str(plan).lower() == "pro":
            time.sleep(0.34)

    progress.empty()
    status.empty()

    work[f"Myyty {period} TCG"] = tcg_values
    work[f"Myyty {period} eBay"] = ebay_values
    work[f"eBay sold avg {period}"] = ebay_sold_prices
    work["_history_errors"] = [errors if i == 0 else [] for i in range(len(work))]

    work = work.sort_values(
        [f"Myyty {period} TCG", "7d vs 30d %"],
        ascending=[False, False],
        na_position="last",
    ).reset_index(drop=True)

    return work


def build_signal_table(df, period="30d"):
    """Rank candidates without pretending cumulative sales are a time window."""
    if df.empty:
        return df

    work = df.copy()
    sales_col = f"Myyty {period} TCG"
    if sales_col in work:
        sales = pd.to_numeric(work[sales_col], errors="coerce")
        work["TCG 30d data"] = "Toteutunut jakso"
    else:
        sales = pd.Series(0, index=work.index, dtype="float64")
        work["TCG 30d data"] = "Ei haettu"

    momentum = pd.to_numeric(work.get("7d vs 30d %"), errors="coerce").fillna(0)
    price = pd.to_numeric(work.get("TCG NM"), errors="coerce").fillna(0)
    sales_score = (sales.fillna(0).clip(lower=0) ** 0.5) * 12
    momentum_score = momentum.clip(lower=-100, upper=200) * 0.35
    price_score = pd.to_numeric(work.get("1d vs 7d %"), errors="coerce").fillna(0).clip(-50, 100) * 0.15
    work["Signal score"] = (sales_score + momentum_score + price_score).round(1)
    work["Signal"] = "Seurattava"
    early = (momentum >= 20) & (price_score < 8) & (sales.fillna(0) >= 5)
    work.loc[early, "Signal"] = "Early trend"
    strong = (sales.fillna(0) >= 15) & (momentum >= 10)
    work.loc[strong, "Signal"] = "Vahva kysyntä"
    return work.sort_values(
        ["Signal score", "7d vs 30d %"],
        ascending=[False, False],
        na_position="last",
    ).reset_index(drop=True)


# ============================================================
# PRICECHARTING OPTIONAL SEARCH
# ============================================================

def pricecharting_get(path, token, params):
    response = requests.get(
        f"{PRICECHARTING_BASE}{path}",
        params={"t": token, **params},
        headers={"User-Agent": "PokemonCardScanner/0.4"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") == "error":
        raise RuntimeError(
            payload.get("error-message") or "PriceCharting API error"
        )
    return payload


# ============================================================
# TOP UI
# ============================================================

st.markdown(
    """
    <section class="hero">
      <div class="eyebrow">Market intelligence · raw only</div>
      <h1>US market signal scanner</h1>
      <p>Vertaa USA:n TCGplayer-hintaa toteutuneisiin eBay-myyntihintoihin, vahvista 30 päivän myyntiliike ja vie parhaat 50 korttia käsin tehtävään EU-tarkistukseen.</p>
    </section>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.subheader("1 · Seulonnan rajat")

    col1, col2 = st.columns(2)
    min_price = col1.number_input(
        "Min US$",
        min_value=HARD_MIN_RAW_PRICE,
        value=5.0,
        step=1.0,
        help="PokeTrace palauttaa USA:n hinnat dollareina. Tämä ei ole Cardmarket-hinta.",
    )
    max_price = col2.number_input(
        "Max US$", min_value=0.0, value=20.0, step=1.0
    )

    language = st.selectbox(
        "Kortit",
        ["English", "Japanese"],
        index=0,
    )

    game = "pokemon" if language == "English" else "pokemon-japanese"

    variant = st.selectbox(
        "Variant",
        [
            "Kaikki",
            "Normal",
            "Holofoil",
            "Reverse_Holofoil",
            "1st_Edition",
            "1st_Edition_Holofoil",
            "Unlimited",
            "Unlimited_Holofoil",
        ],
        index=0,
    )

    coverage_mode = st.selectbox(
        "Settikattavuus",
        ["Tasaisesti kaikki", "Uusimmat", "Vanhimmat"],
        index=0,
        help=(
            "Tasaisesti kaikki poimii jokaisella ajolla settejä eri kohdista "
            "Pokémonin julkaisuhistoriaa, eikä aloita aina Base Setistä."
        ),
    )

    sets_per_scan = st.selectbox(
        "Settejä / skannaus",
        [5, 10, 15, 20],
        index=1,
        help=(
            "Jokaisesta valitusta setistä haetaan yksi sivu, enintään 20 korttia. "
            "Free-planilla 10 settiä kestää noin 20 sekuntia."
        ),
    )

    min_30d_sales = st.number_input(
        "Min. TCGplayer-myynti / 30d",
        min_value=0,
        value=50,
        step=10,
        help="Käytetään vasta, kun oikea päiväkohtainen TCGplayer-historia on haettu.",
    )
    show_top = st.selectbox("Näytä tuloksia", [20, 50, 100], index=1)

    st.info(
        "USA-seulonta käyttää TCGplayer Near Mint -hintaa. eBay näkyy vertailuna "
        "vain silloin, kun historiasta löytyy toteutuneen myynnin hinta."
    )

    st.divider()
    st.caption("Raw / English / Near Mint on tämän skannerin vertailustandardi.")


# ============================================================
# TABS
# ============================================================

tab_scan, tab_history, tab_pc, tab_keys = st.tabs(
    [
        "01 · Löydä signaali",
        "02 · Vahvista 30d",
        "03 · Hintavertailu",
        "04 · Datalähteet",
    ]
)


# ============================================================
# SCANNER
# ============================================================

with tab_scan:
    st.subheader("Löydä USA:n varhainen kysyntä")
    st.markdown(
        '<div class="callout"><strong>Työvaihe 1:</strong> skannaa USA:n kortit. '
        'TCGplayer on päävertailu; eBay toimii toisena lähteenä vain toteutuneilla myynneillä. '
        'Vahvista sen jälkeen TCGplayerin oikea 30 päivän myyntimäärä.</div>',
        unsafe_allow_html=True,
    )
    pt_key = provider_key("PokeTrace")

    if not pt_key:
        st.error(
            "PokeTrace API-avain puuttuu. Lisää se välilehdellä "
            "**🔑 API-yhteydet** tai Streamlit Secretsiin."
        )
    else:
        try:
            plan_info = get_plan_info(pt_key)
            plan = plan_info["plan"]
        except Exception as exc:
            st.error(f"PokeTrace-yhteys ei toimi: {exc}")
            plan_info = {
                "plan": "Unknown",
                "remaining": "–",
                "limit": "–",
            }
            plan = "Unknown"

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Plan", plan_info["plan"])
        c2.metric("API jäljellä", plan_info["remaining"] or "–")
        c3.metric(
            "Kortteja tarkistettu",
            st.session_state.get("broad_scanned_cards", 0),
        )
        c4.metric(
            "Hintaan osuvia",
            len(st.session_state.get("broad_pool", [])),
        )
        c5.metric("Hard floor", f"${HARD_MIN_RAW_PRICE:.2f}")

        try:
            with st.spinner("Ladataan settikatalogi..."):
                sets_df = load_all_sets(pt_key, game, plan)
        except Exception as exc:
            sets_df = pd.DataFrame()
            st.error(f"Settien lataus epäonnistui: {exc}")

        if not sets_df.empty:
            st.caption(
                f"PokeTrace-katalogissa löytyi **{len(sets_df)} {language}-settiä**. "
                "Scanneri hakee niistä eri settejä rinnakkain eikä kulje "
                "globaalin katalogin alusta."
            )

            b1, b2, b3 = st.columns(3)

            start_scan = b1.button(
                "🔄 Uusi laaja skannaus",
                type="primary",
                use_container_width=True,
            )
            continue_scan = b2.button(
                "▶ Jatka eri setteihin",
                use_container_width=True,
            )
            clear_scan = b3.button(
                "Tyhjennä tulokset",
                use_container_width=True,
            )

            if clear_scan:
                for key in [
                    "broad_pool",
                    "broad_round",
                    "broad_scanned_cards",
                    "broad_scanned_sets",
                    "set_cursors",
                    "period_result",
                ]:
                    st.session_state.pop(key, None)
                st.rerun()

            if max_price < min_price:
                st.error("Max-hinnan pitää olla vähintään Min-hinta.")
            elif start_scan or continue_scan:
                try:
                    if start_scan:
                        st.session_state.pop("period_result", None)
                        st.session_state.pop("period_label", None)
                    with st.spinner("Skannataan eri settejä..."):
                        pool_df, batch = scan_across_sets(
                            key=pt_key,
                            plan=plan,
                            sets_df=sets_df,
                            sets_per_scan=sets_per_scan,
                            min_price=min_price,
                            max_price=max_price,
                            game=game,
                            variant=variant,
                            coverage_mode=coverage_mode,
                            reset=start_scan,
                        )

                    if not batch.empty:
                        st.success(
                            "Tällä kierroksella tarkistetut setit: "
                            + ", ".join(batch["name"].astype(str).tolist())
                        )
                except Exception as exc:
                    st.error(str(exc))

        pool = pd.DataFrame(st.session_state.get("broad_pool", []))

        if pool.empty:
            st.info(
                "Paina **Uusi laaja skannaus**. Oletus `Tasaisesti kaikki` "
                "hakee saman tien eri aikakausien settejä."
            )
        else:
            action, explanation = st.columns([1, 2])
            enrich_clicked = action.button(
                "Vahvista TCGplayer 30d",
                type="primary",
                use_container_width=True,
                help="Hakee valituille ehdokkaille päiväkohtaiset TCGplayer-myyntirivit.",
            )
            explanation.caption(
                "Vahvistus kuluttaa history-API-kutsuja. Se on tarkoituksella erillinen vaihe, "
                "jotta koko korttikatalogia ei haeta kalliilla historiakutsuilla."
            )

            if enrich_clicked:
                if not plan_has_history(plan):
                    st.warning(
                        f"Nykyinen PokeTrace-plan on {plan}. Oikea TCGplayer 30d -myynti "
                        "vaatii Pro+-historian; kumulatiivista saleCountia ei käytetä korvikkeena."
                    )
                else:
                    try:
                        with st.spinner("Haetaan TCGplayerin toteutunut 30 päivän myynti..."):
                            st.session_state["period_result"] = enrich_period_sales(
                                pt_key, pool, "30d", min(show_top, 50), plan
                            )
                    except (requests.RequestException, RuntimeError, ValueError) as exc:
                        st.error(f"30 päivän vahvistus epäonnistui: {exc}")

            verified = st.session_state.get("period_result")
            if (
                isinstance(verified, pd.DataFrame)
                and not verified.empty
                and "Myyty 30d TCG" in verified.columns
            ):
                pool = verified
                st.success(
                    "Ranking käyttää nyt toteutunutta TCGplayer 30d -myyntiä. "
                    "EU-hinta ei ole vielä mukana, joten tämä ei yksin ole arbitraasisignaali."
                )
            ranked = add_market_comparison(build_signal_table(pool))
            if "Myyty 30d TCG" in ranked.columns:
                verified_sales = pd.to_numeric(
                    ranked["Myyty 30d TCG"], errors="coerce"
                )
                ranked["30d sales pass"] = verified_sales >= min_30d_sales
                ranked = ranked[ranked["30d sales pass"]].copy()
                if ranked.empty:
                    st.warning(
                        f"Yksikään vahvistettu ehdokas ei täyttänyt vähintään "
                        f"{min_30d_sales} TCGplayer-myyntiä / 30 päivää."
                    )
            else:
                ranked["30d sales pass"] = pd.NA
            ranked = ranked.head(show_top).reset_index(drop=True)

            display_columns = [
                "Kortti",
                "Setti",
                "Numero",
                "Variant",
                "TCG NM",
                "eBay sold avg 30d",
                "US reference",
                "TCG vs eBay sold %",
                "Price sources",
                "Signal",
                "Signal score",
                "TCG 30d data",
                "TCG 7d avg",
                "TCG 30d avg",
                "7d vs 30d %",
            ]
            if "Myyty 30d TCG" in ranked.columns:
                display_columns.insert(8, "Myyty 30d TCG")
            display = ranked[display_columns].copy()

            if "Myyty 30d TCG" not in ranked:
                st.warning(
                    "30 päivän myyntimäärää ei näytetä ennen kuin päiväkohtainen "
                    "TCGplayer-historia on haettu. Paina ensin **Vahvista TCGplayer 30d**."
                )
            else:
                exact = int(pd.to_numeric(ranked["Myyty 30d TCG"], errors="coerce").notna().sum())
                st.caption(f"Vahvistettuja 30d-myyntilukuja: {exact}/{len(ranked)}. Seuraava vaihe on EU-hinnan haku.")

            st.dataframe(
                display,
                use_container_width=True,
                hide_index=True,
                height=min(720, 40 + len(display) * 29),
                column_config={
                    "Kortti": st.column_config.TextColumn(width="medium"),
                    "Setti": st.column_config.TextColumn(width="medium"),
                    "Numero": st.column_config.TextColumn(width="small"),
                    "Variant": st.column_config.TextColumn(width="small"),
                    "Signal": st.column_config.TextColumn("Thesis", width="small"),
                    "Signal score": st.column_config.NumberColumn("Score", format="%.1f", width="small"),
                    "TCG 30d data": st.column_config.TextColumn("Datan taso", width="small"),
                    "Myyty 30d TCG": st.column_config.NumberColumn(
                        "Myyty 30d", format="%d", width="small"
                    ),
                    "TCG NM": st.column_config.NumberColumn(
                        "TCG NM", format="$%.2f", width="small"
                    ),
                    "eBay sold avg 30d": st.column_config.NumberColumn(
                        "eBay sold avg 30d", format="$%.2f", width="small"
                    ),
                    "US reference": st.column_config.NumberColumn(
                        "US ref.", format="$%.2f", width="small"
                    ),
                    "TCG vs eBay sold %": st.column_config.NumberColumn(
                        "TCG/eBay sold Δ", format="%+.1f%%", width="small"
                    ),
                    "Price sources": st.column_config.TextColumn(
                        "Hintalähteet", width="small"
                    ),
                    "TCG 7d avg": st.column_config.NumberColumn(
                        "7d avg", format="$%.2f", width="small"
                    ),
                    "TCG 30d avg": st.column_config.NumberColumn(
                        "30d avg", format="$%.2f", width="small"
                    ),
                    "7d vs 30d %": st.column_config.NumberColumn(
                        "Δ 7d/30d", format="%+.1f%%", width="small"
                    ),
                },
            )

            eu_review = ranked.head(50).copy()
            st.download_button(
                "Lataa Top 50 EU-manuaalilistaksi",
                eu_review.to_csv(index=False).encode("utf-8-sig"),
                file_name="pokemon_top50_us_candidates_for_eu_review.csv",
                mime="text/csv",
                use_container_width=True,
            )

            st.markdown("#### EU-manuaalitarkistus")
            st.info(
                "Avaa ladattu CSV ja tarkista enintään 50 korttia Cardmarketista käsin. "
                "Kirjaa jokaiselle EU-hinta, aktiivisten NM-listausten määrä, kieli, printti "
                "ja toimituskulut. USA-hintaeroa ei pidä tulkita voitoksi ennen näitä tarkistuksia."
            )



# ============================================================
# TRUE PERIOD SALES (PRO+)
# ============================================================

with tab_history:
    pt_key = provider_key("PokeTrace")
    pool = pd.DataFrame(st.session_state.get("broad_pool", []))

    st.subheader("Todelliset myynnit valitulta ajalta")

    if not pt_key:
        st.warning("PokeTrace API-avain puuttuu.")
    elif pool.empty:
        st.info("Skannaa ensin kortteja Scanner-välilehdellä.")
    else:
        try:
            info = get_plan_info(pt_key)
            plan = info["plan"]
        except Exception as exc:
            st.error(str(exc))
            plan = "Unknown"

        period = st.radio(
            "Jakso",
            ["7d", "14d", "30d"],
            horizontal=True,
            index=2,
        )

        history_count = st.selectbox(
            "Kuinka monelle candidatelle lasketaan history",
            [10, 20, 30, 50],
            index=1,
        )

        if plan_has_history(plan):
            st.success(
                f"PokeTrace {plan}: history käytettävissä. "
                "`saleCount` summataan päiväkohtaisista TCGplayer-riveistä."
            )

            if st.button(
                f"Laske Myyty {period}",
                type="primary",
                use_container_width=True,
            ):
                with st.spinner("Haetaan päiväkohtaiset myyntimäärät..."):
                    result = enrich_period_sales(
                        pt_key,
                        pool,
                        period,
                        min(history_count, len(pool)),
                        plan,
                    )
                st.session_state["period_result"] = result
                st.session_state["period_label"] = period

            result = st.session_state.get("period_result", pd.DataFrame())

            if not result.empty:
                result_period = st.session_state.get("period_label", period)
                tcg_col = f"Myyty {result_period} TCG"
                ebay_col = f"Myyty {result_period} eBay"
                history_errors = [
                    message
                    for messages in result.get("_history_errors", [])
                    for message in messages
                ]
                if history_errors:
                    st.warning(
                        f"{len(history_errors)} kortin historiapyyntö epäonnistui. "
                        "Tyhjä myyntimäärä ei tarkoita nollaa myyntiä."
                    )
                    with st.expander("Näytä virheet"):
                        st.write("\n".join(history_errors))

                display = result[
                    [
                        "Kortti",
                        "Setti",
                        "Numero",
                        "TCG NM",
                        tcg_col,
                        ebay_col,
                        "TCG 7d avg",
                        "TCG 30d avg",
                        "7d vs 30d %",
                    ]
                ]

                st.dataframe(
                    display,
                    use_container_width=True,
                    hide_index=True,
                    height=min(720, 40 + len(display) * 29),
                    column_config={
                        "TCG NM": st.column_config.NumberColumn(
                            format="$%.2f", width="small"
                        ),
                        tcg_col: st.column_config.NumberColumn(
                            "Myyty TCG", format="%d", width="small"
                        ),
                        ebay_col: st.column_config.NumberColumn(
                            "Myyty eBay", format="%d", width="small"
                        ),
                        "TCG 7d avg": st.column_config.NumberColumn(
                            "7d avg", format="$%.2f", width="small"
                        ),
                        "TCG 30d avg": st.column_config.NumberColumn(
                            "30d avg", format="$%.2f", width="small"
                        ),
                        "7d vs 30d %": st.column_config.NumberColumn(
                            "Δ 7d/30d", format="%+.1f%%", width="small"
                        ),
                    },
                )
        else:
            st.warning(
                f"Nykyinen PokeTrace-plan on **{plan}**. "
                "Price history on Pro+ -ominaisuus, joten Free-avaimella "
                "emme voi rehellisesti laskea `Myyty 7/14/30d` -lukua. "
                "Scanner-välilehti käyttää sillä välin lähteen oikeaa "
                "kumulatiivista saleCount-arvoa."
            )


# ============================================================
# PRICECHARTING
# ============================================================

with tab_pc:
    pc_token = provider_key("PriceCharting")

    st.subheader("USA-hintojen ristiinvertailu")
    st.markdown(
        '<div class="callout"><strong>Arbitraasi ei ole todistettu</strong>, ennen kuin sama '
        'kortti, printti, kieli ja Near Mint -kunto löytyy EU-lähteestä. PriceCharting toimii '
        'tässä tukevana hintataso- ja vuosivolyymin lähteenä, ei Cardmarketin korvikkeena.</div>',
        unsafe_allow_html=True,
    )
    st.write("")
    st.markdown("#### Datalähteiden tila")
    eu_status = pd.DataFrame(
        [
            {
                "Lähde": "TCGplayer / PokeTrace",
                "Rooli": "USA NM hinta + 30d toteutunut myynti",
                "Tila": "Käytössä" if pt_key else "API-avain puuttuu",
            },
            {
                "Lähde": "CardmarketAPI",
                "Rooli": "EU EN/NM/raw hinta ja tarjonta",
                "Tila": "Ei kytketty tähän versioon",
            },
            {
                "Lähde": "RareBit",
                "Rooli": "EU-historia ja varianttikohtainen vertailu",
                "Tila": "Ei kytketty tähän versioon",
            },
            {
                "Lähde": "PriceCharting",
                "Rooli": "Loose-price + yearly sales volume",
                "Tila": "Käytössä" if pc_token else "Valinnainen token",
            },
        ]
    )
    st.dataframe(eu_status, use_container_width=True, hide_index=True)
    st.caption(
        "Tätä ei käytetä 7/14/30d myyntimäärän lähteenä. "
        "Integraatio on valmiina yksittäisten tuotteiden hakuun."
    )

    if not pc_token:
        st.info(
            "PriceCharting-tokenia ei ole lisätty. Voit lisätä sen "
            "**API-yhteydet**-välilehdeltä."
        )
    else:
        query = st.text_input(
            "Hae PriceChartingista",
            placeholder="esim. Charizard Base Set",
        )

        if st.button(
            "Hae",
            disabled=not bool(query.strip()),
            use_container_width=True,
        ):
            try:
                payload = pricecharting_get(
                    "/api/products",
                    pc_token,
                    {"q": query.strip()},
                )
                products = payload.get("products") or []
                table = pd.DataFrame(
                    [
                        {
                            "Nimi": p.get("product-name"),
                            "Setti": p.get("console-name"),
                            "ID": p.get("id"),
                        }
                        for p in products[:20]
                    ]
                )
                st.dataframe(table, use_container_width=True, hide_index=True)
            except Exception as exc:
                st.error(str(exc))


# ============================================================
# CONNECTIONS / KEYS
# ============================================================

with tab_keys:
    st.subheader("API-yhteydet")
    st.caption(
        "Voit käyttää pysyviä Streamlit Secrets -avaimia tai syöttää "
        "avaimen tähän vain nykyisen selainistunnon ajaksi."
    )

    connection_rows = []

    for provider, cfg in PROVIDERS.items():
        source = provider_key_source(provider)
        connection_rows.append(
            {
                "Palvelu": provider,
                "Avain": "✓" if source else "—",
                "Lähde": source or "Ei asetettu",
                "Käytössä nyt": "Kyllä" if cfg["used"] else "Valmius myöhempään",
                "Secret name": cfg["secret"],
            }
        )

    st.dataframe(
        pd.DataFrame(connection_rows),
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("Lisää / vaihda avain tämän istunnon ajaksi", expanded=False):
        selected_provider = st.selectbox(
            "Palvelu",
            list(PROVIDERS.keys()),
        )
        cfg = PROVIDERS[selected_provider]

        session_key = st.text_input(
            f"{selected_provider} API key / token",
            type="password",
            key=f"input_{cfg['session']}",
        )

        a, b = st.columns(2)

        if a.button("Käytä istunnossa", use_container_width=True):
            st.session_state[cfg["session"]] = session_key.strip()
            st.success(
                f"{selected_provider}-avain asetettu vain tähän selainistuntoon."
            )
            st.rerun()

        if b.button("Poista istuntoavain", use_container_width=True):
            st.session_state.pop(cfg["session"], None)
            st.rerun()

    st.markdown("#### Pysyvät avaimet Streamlitissä")
    st.write(
        "Streamlit → **Manage app → Settings → Secrets**. "
        "Voit lisätä kaikki avaimet samaan Secrets-tiedostoon:"
    )

    st.code(
        """POKETRACE_API_KEY = "..."
RAREBIT_API_KEY = "..."
PRICECHARTING_TOKEN = "..."
CARDMARKETAPI_KEY = "..."
""",
        language="toml",
    )

    st.info(
        "Avaimia ei pidä kirjoittaa app.py-tiedostoon eikä committaa GitHubiin."
    )

    if provider_key("PokeTrace"):
        if st.button("Testaa PokeTrace-yhteys", use_container_width=True):
            try:
                poketrace_auth_info.clear()
                info = get_plan_info(provider_key("PokeTrace"))
                st.success(
                    f"Yhteys toimii • Plan: {info['plan']} • "
                    f"Remaining: {info['remaining']} / {info['limit']}"
                )
            except Exception as exc:
                st.error(str(exc))


st.divider()
st.caption(
    "v0.5 • US market screening + verified TCGplayer 30d • raw / ungraded only"
)
