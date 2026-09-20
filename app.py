import math
import time
from datetime import datetime, timedelta

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title='Pokémon Trend Scanner', page_icon='📈', layout='wide')

POKETRACE_BASE = 'https://api.poketrace.com/v1'
HARD_MIN_PRICE = 1.0

PROVIDERS = {
    'PokeTrace': ('POKETRACE_API_KEY', 'session_poketrace'),
    'RareBit': ('RAREBIT_API_KEY', 'session_rarebit'),
    'PriceCharting': ('PRICECHARTING_TOKEN', 'session_pricecharting'),
    'CardmarketAPI': ('CARDMARKETAPI_KEY', 'session_cardmarketapi'),
}

st.markdown('''
<style>
.block-container {padding-top:1rem; padding-bottom:1rem; max-width:1500px;}
[data-testid="stMetric"] {padding:.2rem .5rem;}
[data-testid="stMetricValue"] {font-size:1.25rem;}
div[data-testid="stDataFrame"] {font-size:.80rem;}
.stTabs [data-baseweb="tab"] {padding-top:.35rem; padding-bottom:.35rem;}
</style>
''', unsafe_allow_html=True)


def get_secret(name):
    try:
        value = st.secrets.get(name, '')
        return str(value).strip() if value else ''
    except Exception:
        return ''


def get_provider_key(provider):
    secret_name, session_name = PROVIDERS[provider]
    return st.session_state.get(session_name, '').strip() or get_secret(secret_name)


def key_source(provider):
    secret_name, session_name = PROVIDERS[provider]
    if st.session_state.get(session_name, '').strip():
        return 'Istunto'
    if get_secret(secret_name):
        return 'Streamlit Secrets'
    return 'Ei asetettu'


def pt_get(path, key, params=None):
    r = requests.get(
        f'{POKETRACE_BASE}{path}',
        headers={'X-API-Key': key, 'User-Agent': 'PokemonTrendScanner/0.5'},
        params=params or {},
        timeout=35,
    )
    if r.status_code >= 400:
        try:
            payload = r.json()
            msg = payload.get('message') or payload.get('error') or payload
        except Exception:
            msg = r.text[:250]
        raise RuntimeError(f'PokeTrace {r.status_code}: {msg}')
    return r.json()


@st.cache_data(ttl=300, show_spinner=False)
def auth_info(key):
    return pt_get('/auth/info', key)


def get_plan(key):
    payload = auth_info(key)
    user = (payload.get('data') or {}).get('user') or {}
    return {
        'plan': str(user.get('plan') or 'Unknown'),
        'remaining': user.get('remaining', '–'),
        'limit': user.get('limit', '–'),
    }


def delay_for_plan(plan):
    return 2.1 if str(plan).lower() == 'free' else 0.35


@st.cache_data(ttl=86400, show_spinner=False)
def get_sets(key, plan):
    rows = []
    cursor = None
    while True:
        params = {'game': 'pokemon', 'limit': 50}
        if cursor:
            params['cursor'] = cursor
        payload = pt_get('/sets', key, params)
        rows.extend(payload.get('data') or [])
        pagination = payload.get('pagination') or {}
        cursor = pagination.get('nextCursor')
        if not pagination.get('hasMore') or not cursor:
            break
        time.sleep(delay_for_plan(plan))
        if len(rows) > 2000:
            break

    df = pd.DataFrame([
        {'slug': r.get('slug'), 'name': r.get('name'), 'releaseDate': r.get('releaseDate')}
        for r in rows if r.get('slug')
    ])
    if df.empty:
        return df
    df['date'] = pd.to_datetime(df['releaseDate'], errors='coerce')
    return df.sort_values('date', ascending=False, na_position='last').reset_index(drop=True)


def safe_float(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def pct(new, old):
    new = safe_float(new)
    old = safe_float(old)
    if new is None or old in (None, 0):
        return None
    return (new - old) / old * 100


def parse_card(card):
    # Strict safety: only English Pokémon singles.
    if str(card.get('game', '')).lower() != 'pokemon':
        return None
    if str(card.get('productType', '')).lower() != 'single':
        return None

    prices = card.get('prices') or {}
    tcg = (prices.get('tcgplayer') or {}).get('NEAR_MINT') or {}
    ebay = (prices.get('ebay') or {}).get('NEAR_MINT') or {}
    set_data = card.get('set') or {}

    price = safe_float(tcg.get('avg'))
    avg1 = safe_float(tcg.get('avg1d'))
    avg7 = safe_float(tcg.get('avg7d'))
    avg30 = safe_float(tcg.get('avg30d'))

    return {
        'id': str(card.get('id') or ''),
        'Kortti': str(card.get('name') or ''),
        'Setti': str(set_data.get('name') or ''),
        'Numero': str(card.get('cardNumber') or ''),
        'Variant': str(card.get('variant') or ''),
        'Rarity': str(card.get('rarity') or ''),
        'TCG NM': price,
        'TCG 1d': avg1,
        'TCG 7d': avg7,
        'TCG 30d': avg30,
        '7d/30d %': pct(avg7, avg30),
        '1d/7d %': pct(avg1, avg7),
        'Hist. sales': int(tcg.get('saleCount') or 0),
        'eBay sales': int(ebay.get('saleCount') or 0),
    }


def candidate_passes(row, min_price, max_price, exclude_energy, min_momentum, max_short_drop, min_liquidity):
    price = row.get('TCG NM')
    if price is None:
        return False
    if not (max(HARD_MIN_PRICE, float(min_price)) <= price <= max_price):
        return False
    if exclude_energy and 'energy' in row.get('Kortti', '').lower():
        return False

    mom = row.get('7d/30d %')
    short = row.get('1d/7d %')

    # Do not rank falling/high-volume cards as growth candidates.
    if mom is None or mom < min_momentum:
        return False
    if short is not None and short < max_short_drop:
        return False

    # Only confirmation, never the main score.
    if int(row.get('Hist. sales') or 0) < min_liquidity:
        return False
    return True


def trend_score(row):
    momentum = max(-50.0, min(100.0, float(row.get('7d/30d %') or 0)))
    short = max(-30.0, min(50.0, float(row.get('1d/7d %') or 0)))
    sales = max(0, int(row.get('Hist. sales') or 0))
    liquidity_bonus = min(8.0, math.log10(sales + 1) * 2.5)
    return round(momentum * 0.8 + short * 0.15 + liquidity_bonus, 1)


def set_batch(sets_df, count, round_no, mode):
    if sets_df.empty:
        return sets_df
    n = len(sets_df)
    count = min(count, n)

    if mode == 'Uusimmat':
        start = (round_no * count) % n
        return sets_df.iloc[[(start + i) % n for i in range(count)]]

    # Spread immediately across the entire release history.
    idx = []
    for lane in range(count):
        start = int(lane * n / count)
        end = int((lane + 1) * n / count)
        width = max(1, end - start)
        idx.append(start + (round_no % width))
    idx = list(dict.fromkeys(i for i in idx if i < n))
    return sets_df.iloc[idx]


def scan_sets(key, plan, sets_df, set_count, min_price, max_price, exclude_energy,
              min_momentum, max_short_drop, min_liquidity, mode, reset, signature):
    if reset:
        st.session_state['trend_pool'] = []
        st.session_state['trend_round'] = 0
        st.session_state['trend_scanned'] = 0
        st.session_state['trend_signature'] = signature

    pool = list(st.session_state.get('trend_pool', []))
    round_no = int(st.session_state.get('trend_round', 0))
    scanned = int(st.session_state.get('trend_scanned', 0))
    seen = {r['id'] for r in pool if r.get('id')}
    batch = set_batch(sets_df, set_count, round_no, mode)

    progress = st.progress(0)
    status = st.empty()

    for i, (_, s) in enumerate(batch.iterrows(), start=1):
        status.caption(f'{i}/{len(batch)} • {s["name"]}')
        payload = pt_get('/cards', key, {
            'market': 'US',
            'game': 'pokemon',
            'product_type': 'single',
            'set': s['slug'],
            'limit': 20,
        })

        for card in payload.get('data') or []:
            scanned += 1
            row = parse_card(card)
            if row is None:
                continue
            if row['id'] in seen:
                continue
            if candidate_passes(row, min_price, max_price, exclude_energy, min_momentum,
                                max_short_drop, min_liquidity):
                row['Trend score'] = trend_score(row)
                pool.append(row)
                seen.add(row['id'])

        progress.progress(i / len(batch))
        if i < len(batch):
            time.sleep(delay_for_plan(plan))

    st.session_state['trend_pool'] = pool
    st.session_state['trend_round'] = round_no + 1
    st.session_state['trend_scanned'] = scanned
    st.session_state['trend_signature'] = signature
    progress.empty()
    status.empty()
    return pd.DataFrame(pool), batch


def has_history(plan):
    return str(plan).lower() in {'pro', 'growth', 'scale'}


def fetch_history(key, card_id):
    payload = pt_get(
        f'/cards/{card_id}/prices/NEAR_MINT/history',
        key,
        {'period': '30d', 'limit': 30},
    )
    return payload.get('data') or []


def recent_sales_metrics(rows):
    parsed = []
    for r in rows:
        if str(r.get('source', '')).lower() != 'tcgplayer':
            continue
        try:
            d = datetime.strptime(str(r.get('date')), '%Y-%m-%d').date()
        except Exception:
            continue
        parsed.append((d, int(r.get('saleCount') or 0)))

    if not parsed:
        return {}

    newest = max(d for d, _ in parsed)

    def total(start_back, end_back):
        start = newest - timedelta(days=end_back)
        end = newest - timedelta(days=start_back)
        return sum(v for d, v in parsed if start <= d <= end)

    sold7 = total(0, 6)
    prev7 = total(7, 13)
    sold14 = total(0, 13)
    sold30 = total(0, 29)
    accel = None if prev7 == 0 else (sold7 - prev7) / prev7 * 100

    return {
        'Myyty 7d': sold7,
        'Edelliset 7d': prev7,
        'Myyty 14d': sold14,
        'Myyty 30d': sold30,
        'Sales acceleration %': accel,
    }


def enrich_recent_sales(key, df, count, plan):
    work = df.head(count).copy()
    metrics = []
    progress = st.progress(0)
    status = st.empty()

    for i, (_, row) in enumerate(work.iterrows(), start=1):
        status.caption(f'{i}/{len(work)} • {row["Kortti"]}')
        try:
            metrics.append(recent_sales_metrics(fetch_history(key, row['id'])))
        except Exception:
            metrics.append({})
        progress.progress(i / len(work))
        time.sleep(delay_for_plan(plan))

    progress.empty()
    status.empty()

    for col in ['Myyty 7d', 'Edelliset 7d', 'Myyty 14d', 'Myyty 30d', 'Sales acceleration %']:
        work[col] = [m.get(col) for m in metrics]

    return work.sort_values(
        ['Sales acceleration %', 'Myyty 7d', '7d/30d %'],
        ascending=[False, False, False],
        na_position='last',
    ).reset_index(drop=True)


st.title('Pokémon Trend Scanner')
st.caption('Halvat raw Pokémon -kortit • positiivinen momentum • panic-sale suodatus')

pt_key = get_provider_key('PokeTrace')

with st.sidebar:
    st.subheader('Candidate-filtterit')
    c1, c2 = st.columns(2)
    min_price = c1.number_input('Min $', min_value=HARD_MIN_PRICE, value=1.0, step=1.0)
    max_price = c2.number_input('Max $', min_value=HARD_MIN_PRICE, value=30.0, step=1.0)

    exclude_energy = st.checkbox('Sulje Energy-kortit pois', value=True)
    min_momentum = st.slider('Min 7d vs 30d hintamomentum', 0, 50, 3, 1, format='%d%%')
    max_short_drop = st.slider('Sallittu 1d vs 7d pudotus', -30, 0, -10, 1, format='%d%%')
    min_liquidity = st.number_input('Min historiallinen saleCount', min_value=0, value=5, step=1,
                                    help='Vain likviditeetin vahvistus, ei viimeisen 30d myyntimäärä.')
    coverage = st.selectbox('Settikattavuus', ['Tasaisesti kaikki', 'Uusimmat'])
    sets_per_scan = st.selectbox('Settejä / kierros', [5, 10, 15, 20], index=1)
    show_top = st.selectbox('Näytä Top', [20, 50, 100], index=1)

candidate_tab, sales_tab, api_tab = st.tabs(['🎯 Trend candidates', '🔥 Oikea 7/14/30d sales', '🔑 API:t'])

with candidate_tab:
    if not pt_key:
        st.error('Lisää PokeTrace API-avain API:t-välilehdellä.')
    else:
        try:
            plan_info = get_plan(pt_key)
            plan = plan_info['plan']
            sets_df = get_sets(pt_key, plan)
        except Exception as exc:
            st.error(str(exc))
            plan_info = {'plan': 'Unknown', 'remaining': '–'}
            plan = 'Unknown'
            sets_df = pd.DataFrame()

        signature = (min_price, max_price, exclude_energy, min_momentum, max_short_drop,
                     min_liquidity, coverage)

        if st.session_state.get('trend_signature') not in (None, signature):
            st.warning('Filtterit muuttuivat. Aloita Uusi skannaus, ettei vanha pool sekoitu mukaan.')

        a, b, c = st.columns(3)
        start = a.button('🔄 Uusi skannaus', type='primary', use_container_width=True)
        more = b.button('▶ Lisää settejä', use_container_width=True)
        clear = c.button('Tyhjennä', use_container_width=True)

        if clear:
            for k in ['trend_pool', 'trend_round', 'trend_scanned', 'trend_signature', 'recent_result']:
                st.session_state.pop(k, None)
            st.rerun()

        if start or more:
            if max_price < min_price:
                st.error('Max-hinnan pitää olla vähintään Min-hinta.')
            elif sets_df.empty:
                st.error('Settikatalogia ei saatu.')
            else:
                try:
                    _, batch = scan_sets(
                        pt_key, plan, sets_df, sets_per_scan, min_price, max_price,
                        exclude_energy, min_momentum, max_short_drop, int(min_liquidity),
                        coverage, start, signature,
                    )
                    st.success('Tarkistetut setit: ' + ', '.join(batch['name'].astype(str).tolist()))
                except Exception as exc:
                    st.error(str(exc))

        pool = pd.DataFrame(st.session_state.get('trend_pool', []))

        if pool.empty:
            st.info('Scanneri näyttää vain positiivisen 7d/30d hintamomentumin kortit eikä rankkaa pelkkää myyntimäärää.')
        else:
            pool = pool.sort_values(['Trend score', '7d/30d %', 'Hist. sales'], ascending=[False, False, False]).head(show_top)

            m1, m2, m3, m4 = st.columns(4)
            m1.metric('Tarkistettu', st.session_state.get('trend_scanned', 0))
            m2.metric('Candidates', len(st.session_state.get('trend_pool', [])))
            m3.metric('Plan', plan_info.get('plan', '–'))
            m4.metric('API jäljellä', plan_info.get('remaining', '–'))

            display = pool[['Kortti', 'Setti', 'Numero', 'Rarity', 'TCG NM', 'TCG 7d', 'TCG 30d',
                            '7d/30d %', '1d/7d %', 'Hist. sales', 'Trend score']]

            st.dataframe(
                display,
                use_container_width=True,
                hide_index=True,
                height=min(720, 40 + 29 * len(display)),
                column_config={
                    'TCG NM': st.column_config.NumberColumn(format='$%.2f'),
                    'TCG 7d': st.column_config.NumberColumn('7d avg', format='$%.2f'),
                    'TCG 30d': st.column_config.NumberColumn('30d avg', format='$%.2f'),
                    '7d/30d %': st.column_config.NumberColumn('7d↗30d', format='%+.1f%%'),
                    '1d/7d %': st.column_config.NumberColumn('1d↗7d', format='%+.1f%%'),
                    'Hist. sales': st.column_config.NumberColumn(format='%d'),
                    'Trend score': st.column_config.NumberColumn(format='%.1f'),
                },
            )
            st.caption('Trend score on seulontamittari, ei hinnannousuennuste. Free-planissa saleCount on kumulatiivinen ja toimii vain likviditeetin vahvistuksena.')

with sales_tab:
    if not pt_key:
        st.warning('PokeTrace API-avain puuttuu.')
    else:
        try:
            plan = get_plan(pt_key)['plan']
        except Exception as exc:
            st.error(str(exc))
            plan = 'Unknown'

        pool = pd.DataFrame(st.session_state.get('trend_pool', []))
        if pool.empty:
            st.info('Tee ensin candidate-skannaus.')
        elif not has_history(plan):
            st.warning(f'PokeTrace-plan on {plan}. Tarkka päiväkohtainen saleCount-history on Pro+, joten Free-tilassa emme näytä tekaistuja Myyty 7d/30d -lukuja.')
        else:
            count = st.selectbox('Analysoi candidateja', [10, 20, 30, 50], index=1)
            if st.button('Laske myyntien kiihtyminen', type='primary', use_container_width=True):
                base = pool.sort_values(['Trend score', 'Hist. sales'], ascending=[False, False])
                st.session_state['recent_result'] = enrich_recent_sales(pt_key, base, min(count, len(base)), plan)

            result = st.session_state.get('recent_result', pd.DataFrame())
            if not result.empty:
                display = result[['Kortti', 'Setti', 'TCG NM', 'Myyty 7d', 'Edelliset 7d',
                                  'Sales acceleration %', 'Myyty 14d', 'Myyty 30d', '7d/30d %']]
                st.dataframe(display, use_container_width=True, hide_index=True,
                             column_config={
                                 'TCG NM': st.column_config.NumberColumn(format='$%.2f'),
                                 'Sales acceleration %': st.column_config.NumberColumn('Sales accel.', format='%+.1f%%'),
                                 '7d/30d %': st.column_config.NumberColumn('Price momentum', format='%+.1f%%'),
                             })

with api_tab:
    st.subheader('API-yhteydet')
    rows = []
    for provider, (secret_name, _) in PROVIDERS.items():
        rows.append({'Palvelu': provider, 'Tila': '✓' if get_provider_key(provider) else '—',
                     'Avain': key_source(provider), 'Secret': secret_name})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    provider = st.selectbox('Palvelu', list(PROVIDERS))
    secret_name, session_name = PROVIDERS[provider]
    value = st.text_input(f'{provider} avain/token', type='password')
    x, y = st.columns(2)
    if x.button('Käytä tässä istunnossa', use_container_width=True):
        st.session_state[session_name] = value.strip()
        st.rerun()
    if y.button('Poista istuntoavain', use_container_width=True):
        st.session_state.pop(session_name, None)
        st.rerun()

    st.markdown('#### Streamlit Secrets')
    st.code('POKETRACE_API_KEY = "..."\nRAREBIT_API_KEY = "..."\nPRICECHARTING_TOKEN = "..."\nCARDMARKETAPI_KEY = "..."', language='toml')
    st.caption('Älä committaa oikeita API-avaimia GitHubiin.')

st.divider()
st.caption('v0.5 reset • Pokémon only • raw/NM • positive-momentum candidates')
