import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import datetime

# Attempt to load ClickHouse Client
try:
    from src.clickhouse_client import get_client
except ImportError:
    st.error("Could not import clickhouse_client. Make sure you are running from the analytics root.")
    st.stop()

client = get_client()

# ─── Page Config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Address UI v2 — Analysis Dashboard",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Data Fetching Core ──────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def fetch_versions():
    query = "SELECT DISTINCT app_version FROM default.events_raw WHERE dt >= '2026-03-01' AND platform = 'Android' AND app_version != '' AND app_version IS NOT NULL LIMIT 500"
    res = client.execute_query(query)
    if res:
         return sorted(list(set([str(r['app_version']) for r in res if r.get('app_version')])))
    return []

def get_base_conditions(start_date, end_date, selected_versions):
    sd = start_date.strftime("%Y-%m-%d")
    ed = end_date.strftime("%Y-%m-%d")
    cond = f"dt >= '{sd}' AND dt <= '{ed}' AND platform = 'Android'"
    if selected_versions:
        v_list = "', '".join(selected_versions)
        cond += f" AND app_version IN ('{v_list}')"
    return cond

@st.cache_data(show_spinner="Running Conversion Query...")
def fetch_conversions(start_date, end_date, selected_versions):
    cond = get_base_conditions(start_date, end_date, selected_versions)
    query = f"""
    SELECT
        new_address_experience,
        count(session_id) as total_sessions,
        sum(has_add) as total_add_address,
        sum(has_confirm) as confirm_sessions,
        sum(has_confirm_to_save) as save_after_confirm_sessions,
        sum(has_add_to_save) as save_after_add_sessions,
        sum(nudge_shown) as nudge_sessions,
        sum(has_confirm_after_nudge) as confirm_after_nudge_sessions,
        sum(has_save_after_nudge) as save_after_nudge_sessions
    FROM (
        SELECT 
            session_id,
            anyIf(JSONExtractString(metadata, 'new_address_experience'), event_name = 'app_open' AND JSONHas(metadata, 'new_address_experience')=1 AND JSONExtractString(metadata, 'new_address_experience') NOT IN ('', 'not_set')) as new_address_experience,
            
            max(if(event_name = 'add_address_clicked' AND JSONExtractString(metadata, 'add_address') = 'cartFragment' AND JSONExtractString(metadata, 'address') = '0', 1, 0)) as has_add,
            
            sequenceMatch('(?1)(?t>=0)(?2)')(event_timestamp, 
                event_name = 'add_address_clicked' AND JSONExtractString(metadata, 'add_address') = 'cartFragment' AND JSONExtractString(metadata, 'address') = '0', 
                event_name = 'confirm_location' AND JSONExtractString(metadata, 'source') = 'cart'
            ) as has_confirm,
            
            sequenceMatch('(?1)(?t>=0)(?2)(?t>=0)(?3)')(event_timestamp, 
                event_name = 'add_address_clicked' AND JSONExtractString(metadata, 'add_address') = 'cartFragment' AND JSONExtractString(metadata, 'address') = '0', 
                event_name = 'confirm_location' AND JSONExtractString(metadata, 'source') = 'cart', 
                event_name = 'save_address_clicked' AND JSONExtractString(metadata, 'source') = 'add_address'
            ) as has_confirm_to_save,

            sequenceMatch('(?1)(?t>=0)(?2)')(event_timestamp,
                event_name = 'add_address_clicked' AND JSONExtractString(metadata, 'add_address') = 'cartFragment' AND JSONExtractString(metadata, 'address') = '0', 
                event_name = 'save_address_clicked' AND JSONExtractString(metadata, 'source') = 'add_address'
            ) as has_add_to_save,

            max(if(event_name = 'map_support_nudge_shown', 1, 0)) as nudge_shown,
            
            sequenceMatch('(?1)(?t>=0)(?2)')(event_timestamp, 
                event_name = 'map_support_nudge_shown', 
                event_name = 'confirm_location' AND JSONExtractString(metadata, 'source') = 'cart'
            ) as has_confirm_after_nudge,

            sequenceMatch('(?1)(?t>=0)(?2)')(event_timestamp, 
                event_name = 'map_support_nudge_shown', 
                event_name = 'save_address_clicked' AND JSONExtractString(metadata, 'source') = 'add_address'
            ) as has_save_after_nudge
            
        FROM default.events_raw
        WHERE {cond}
        GROUP BY session_id
        HAVING new_address_experience != ''
    )
    GROUP BY new_address_experience
    """
    res = client.execute_query(query)
    df = pd.DataFrame(res) if res else pd.DataFrame()
    if not df.empty:
        for col in df.columns:
            if col != 'new_address_experience':
                df[col] = pd.to_numeric(df[col], errors='coerce')
    return df

@st.cache_data(show_spinner="Fetching Accuracy Stats...")
def fetch_accuracy(start_date, end_date, selected_versions):
    cond = get_base_conditions(start_date, end_date, selected_versions)
    query = f"""
    SELECT
        count(if(conf_acc < 100 AND conf_acc != 0 AND best_acc = 0, 1, NULL)) as fetched_best_early,
        count(if(best_acc != 0, 1, NULL)) as fetched_better_later,
        avg(if(conf_acc != 0 AND best_acc != 0, conf_acc - best_acc, NULL)) as avg_improvement,
        quantile(0.95)(if(conf_acc != 0 AND best_acc != 0, conf_acc - best_acc, NULL)) as p95_improvement,
        avg(if(conf_acc != 0, conf_acc, NULL)) as avg_confirmed_accuracy,
        quantile(0.95)(if(conf_acc != 0, conf_acc, NULL)) as p95_confirmed_accuracy,
        avg(if(best_acc != 0, best_acc, NULL)) as avg_best_accuracy,
        quantile(0.95)(if(best_acc != 0, best_acc, NULL)) as p95_best_accuracy
    FROM (
        SELECT
            session_id,
            anyIf(JSONExtractString(metadata, 'new_address_experience'), event_name = 'app_open' AND JSONHas(metadata, 'new_address_experience')=1) as new_address_experience,
            anyIf(toFloat64OrZero(JSONExtractString(metadata, 'confirmed_location_accuracy')), event_name = 'save_address_clicked' AND JSONHas(metadata, 'confirmed_location_accuracy')=1 AND JSONExtractString(metadata, 'confirmed_location_accuracy') != '') as conf_acc,
            anyIf(toFloat64OrZero(JSONExtractString(metadata, 'best_location_accuracy')), event_name = 'save_address_clicked' AND JSONHas(metadata, 'best_location_accuracy')=1 AND JSONExtractString(metadata, 'best_location_accuracy') != '') as best_acc
        FROM default.events_raw
        WHERE {cond}
        GROUP BY session_id
        HAVING new_address_experience = 'true' AND conf_acc != 0
    )
    """
    res = client.execute_query(query)
    return res[0] if (res and len(res) > 0) else {}

@st.cache_data(show_spinner="Fetching Marker Moves...")
def fetch_marker_moves(start_date, end_date, selected_versions):
    cond = get_base_conditions(start_date, end_date, selected_versions)
    query = f"""
    SELECT
        new_address_experience,
        has_confirmed,
        count(session_id) as total_sessions,
        avg(moves_all) as avg_marker_moves
    FROM (
        SELECT 
            session_id,
            anyIf(JSONExtractString(metadata, 'new_address_experience'), event_name = 'app_open' AND JSONHas(metadata, 'new_address_experience')=1 AND JSONExtractString(metadata, 'new_address_experience') NOT IN ('', 'not_set')) as new_address_experience,
            
            minIf(event_timestamp, event_name = 'add_address_clicked' AND JSONExtractString(metadata, 'add_address') = 'cartFragment' AND JSONExtractString(metadata, 'address') = '0') as t_add_address,
            minIf(event_timestamp, event_name = 'confirm_location') as t_confirm,
            
            sum(if(event_name = 'location_marker_moved', 1, 0)) as moves_all,
            
            if(t_confirm > t_add_address AND t_add_address > 0, 1, 0) as has_confirmed
        FROM default.events_raw
        WHERE {cond}
        GROUP BY session_id
        HAVING t_add_address > 0 AND new_address_experience != ''
    )
    GROUP BY new_address_experience, has_confirmed
    """
    res = client.execute_query(query)
    df = pd.DataFrame(res) if res else pd.DataFrame()
    if not df.empty:
        for col in ['has_confirmed', 'total_sessions', 'avg_marker_moves']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df

@st.cache_data(show_spinner="Fetching Nudge Matrix...")
def fetch_support_matrix(start_date, end_date, selected_versions):
    cond = get_base_conditions(start_date, end_date, selected_versions)
    query = f"""
    SELECT
        reason,
        action,
        count() as nudges_shown,
        sum(if(t_confirm > toDateTime('1970-01-01 00:00:00') AND t_confirm > t_nudge, 1, 0)) as confirmed_sessions,
        sum(if(t_save > toDateTime('1970-01-01 00:00:00') AND t_save > t_nudge, 1, 0)) as saved_sessions
    FROM (
        SELECT
            session_id,
            anyIf(JSONExtractString(metadata, 'reason'), event_name = 'map_support_nudge_shown') as reason,
            anyIf(JSONExtractString(metadata, 'action'), event_name = 'map_support_nudge_shown') as action,
            minIf(event_timestamp, event_name = 'map_support_nudge_shown') as t_nudge,
            minIf(event_timestamp, event_name = 'confirm_location') as t_confirm,
            minIf(event_timestamp, event_name = 'save_address_clicked') as t_save
        FROM default.events_raw
        WHERE {cond}
        GROUP BY session_id
        HAVING reason != ''
    )
    GROUP BY reason, action
    ORDER BY reason, action
    """
    res = client.execute_query(query)
    df = pd.DataFrame(res) if res else pd.DataFrame()
    if not df.empty:
        for col in ['nudges_shown', 'confirmed_sessions', 'saved_sessions']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df

@st.cache_data(show_spinner="Fetching Search Impact...")
def fetch_search_impact(start_date, end_date, selected_versions):
    cond = get_base_conditions(start_date, end_date, selected_versions)
    query = f"""
    SELECT
        source,
        count() as searches,
        sum(if(t_save > toDateTime('1970-01-01 00:00:00') AND t_save > t_search, 1, 0)) as saves
    FROM (
        SELECT
            session_id,
            anyIf(JSONExtractString(metadata, 'source'), event_name = 'map_search_bar') as source,
            minIf(event_timestamp, event_name = 'map_search_bar') as t_search,
            minIf(event_timestamp, event_name = 'save_address_clicked') as t_save
        FROM default.events_raw
        WHERE {cond}
        GROUP BY session_id
        HAVING source != ''
    )
    GROUP BY source
    """
    res = client.execute_query(query)
    df = pd.DataFrame(res) if res else pd.DataFrame()
    if not df.empty:
        for col in ['searches', 'saves']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df




@st.cache_data(show_spinner="Fetching Delivery Impact...")
def fetch_delivery_impact(start_date, end_date, selected_versions):
    cond = get_base_conditions(start_date, end_date, selected_versions)
    sd = start_date.strftime('%Y-%m-%d 00:00:00')
    
    query = f'''
    WITH AddressSessions AS (
        SELECT 
            session_id, user_id,
            minIf(event_timestamp, event_name = 'save_address_clicked' AND JSONExtractString(metadata, 'source') = 'add_address') as t_save_address
        FROM default.events_raw
        WHERE {cond}
        GROUP BY session_id, user_id
        HAVING user_id != 0
           AND max(if(event_name = 'add_address_clicked' AND JSONExtractString(metadata, 'add_address') = 'cartFragment' AND JSONExtractString(metadata, 'address') = '0', 1, 0)) = 1
           AND sequenceMatch('(?1)(?t>=0)(?2)(?t>=0)(?3)')(event_timestamp, 
                event_name = 'add_address_clicked' AND JSONExtractString(metadata, 'add_address') = 'cartFragment' AND JSONExtractString(metadata, 'address') = '0', 
                event_name = 'confirm_location' AND JSONExtractString(metadata, 'source') = 'cart', 
                event_name = 'save_address_clicked' AND JSONExtractString(metadata, 'source') = 'add_address'
           ) = 1
    ),
    UserVariants AS (
        SELECT user_id, 
               anyIf(JSONExtractString(metadata, 'new_address_experience'), event_name = 'app_open' AND JSONHas(metadata, 'new_address_experience')=1 AND JSONExtractString(metadata, 'new_address_experience') NOT IN ('', 'not_set')) as variant
        FROM default.events_raw
        WHERE {cond}
        GROUP BY user_id
        HAVING variant != ''
    ),
    UserFirstAddress AS (
        SELECT a.user_id, 
               v.variant as variant, 
               argMin(a.session_id, a.t_save_address) as session_id,
               min(a.t_save_address) as t_save_address
        FROM AddressSessions a
        JOIN UserVariants v ON a.user_id = v.user_id
        GROUP BY a.user_id, v.variant
    ),
    SessionPermissions AS (
        SELECT session_id,
               max(if(event_name = 'location_permission_granted', 1, 0)) as loc_perm_granted,
               max(if(event_name = 'location_permission_denied', 1, 0)) as loc_perm_denied,
               max(if(event_name = 'gps_permission_granted', 1, 0)) as gps_perm_granted,
               max(if(event_name = 'gps_permission_denied', 1, 0)) as gps_perm_denied,
               max(if(event_name = 'get_current_location_clicked', 1, 0)) as get_current_loc_clicked
        FROM default.events_raw
        WHERE {cond}
        GROUP BY session_id
    ),
    MatchedOrders AS (
        SELECT 
            a.variant as variant,
            JSONExtractString(o.metadata, 'del_picked_at') as picked_at_str,
            JSONExtractString(o.metadata, 'delivered_at') as delivered_at_str,
            toFloat64OrNull(JSONExtractString(o.metadata, 'placement_del_distance')) as placement_del_distance,
            JSONExtractString(o.metadata, 'order_id') as order_id,
            o.timestamp as order_delivered_timestamp,
            sp.loc_perm_granted,
            sp.loc_perm_denied,
            sp.gps_perm_granted,
            sp.gps_perm_denied,
            sp.get_current_loc_clicked,
            row_number() OVER (PARTITION BY a.user_id ORDER BY o.timestamp ASC) as rn
        FROM UserFirstAddress a
        JOIN SessionPermissions sp ON a.session_id = sp.session_id
        JOIN mixpanel.events_tracking_buffer o ON toUInt64OrZero(toString(a.user_id)) = toUInt64OrZero(toString(o.user_id))
        WHERE o.event_name = 'OrderDelivered'
          AND JSONExtractString(o.metadata, 'order_count') = '1'
          AND toUInt64(o.timestamp) >= toUInt64(toUnixTimestamp(toDateTime('{sd}'))) * 1000
          AND toUInt64(o.timestamp) >= toUInt64(a.t_save_address)
          AND toUInt64(o.timestamp) <= toUInt64(a.t_save_address) + 86400000 
    ),
    FirstOrders AS (
        SELECT * FROM MatchedOrders WHERE rn = 1
    ),
    OrderReach AS (
        SELECT 
            JSONExtractString(metadata, 'order_id') as order_id,
            min(timestamp) as reached_timestamp
        FROM mixpanel.events_tracking_buffer
        WHERE event_name = 'ReachedDestination'
          AND JSONExtractString(metadata, 'order_count') = '1'
          AND timestamp >= toUnixTimestamp(toDateTime('{sd}')) * 1000
        GROUP BY order_id
    )
    SELECT f.*, r.reached_timestamp 
    FROM FirstOrders f
    LEFT JOIN OrderReach r ON f.order_id = r.order_id AND f.order_id != ''
    '''
    res = client.execute_query(query)
    df = pd.DataFrame(res) if res else pd.DataFrame()
    if df.empty: return df

    df['picked_at'] = pd.to_datetime(df['picked_at_str'], errors='coerce')
    df['delivered_at'] = pd.to_datetime(df['delivered_at_str'], errors='coerce')
    df['reached_at'] = pd.to_datetime(pd.to_numeric(df['reached_timestamp'], errors='coerce'), unit='ms') + pd.Timedelta(hours=5, minutes=30)
    df['order_delivered_at'] = pd.to_datetime(pd.to_numeric(df['order_delivered_timestamp'], errors='coerce'), unit='ms') + pd.Timedelta(hours=5, minutes=30)
    
    df['delivery_time_sec'] = (df['delivered_at'] - df['picked_at']).dt.total_seconds()
    df['ride_time_sec'] = (df['reached_at'] - df['picked_at']).dt.total_seconds()
    df['handover_time_sec'] = (df['order_delivered_at'] - df['reached_at']).dt.total_seconds()
    df['placement_del_distance'] = pd.to_numeric(df['placement_del_distance'], errors='coerce')
    
    valid_df = df[
        (df['delivery_time_sec'].isna() | (df['delivery_time_sec'] <= 3600)) & 
        (df['ride_time_sec'].isna() | (df['ride_time_sec'] <= 3600)) &
        (df['handover_time_sec'].isna() | (df['handover_time_sec'] <= 3600))
    ].copy()
    return valid_df

# ─── Custom CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"]  { font-family: 'Inter', sans-serif; }
.main { background: #0a0e1a; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0d1226 0%, #111827 100%); border-right: 1px solid rgba(99,102,241,0.2); }
.metric-card { background: linear-gradient(135deg, rgba(99,102,241,0.12) 0%, rgba(139,92,246,0.08) 100%); border: 1px solid rgba(99,102,241,0.25); border-radius: 16px; padding: 20px 24px; margin-bottom: 12px; }
.metric-card h3 { color: #94a3b8; font-size: 0.75rem; font-weight: 500; letter-spacing: 0.08em; text-transform: uppercase; margin: 0 0 6px 0; }
.metric-card .value { color: #f1f5f9; font-size: 2rem; font-weight: 700; line-height: 1; }
.metric-card .delta { font-size: 0.8rem; margin-top: 6px; }
.delta-up { color: #34d399; }
.delta-down { color: #f87171; }
.section-header { display: flex; align-items: center; gap: 12px; padding: 16px 0 8px 0; border-bottom: 1px solid rgba(99,102,241,0.2); margin-bottom: 20px; }
.section-header .icon { width: 36px; height: 36px; border-radius: 10px; background: linear-gradient(135deg, #6366f1, #8b5cf6); display: flex; align-items: center; justify-content: center; font-size: 1.1rem; }
.section-header h2 { color: #e2e8f0; font-size: 1.1rem; font-weight: 600; margin: 0; }
.insight-box { background: linear-gradient(135deg, rgba(52,211,153,0.08) 0%, rgba(16,185,129,0.04) 100%); border: 1px solid rgba(52,211,153,0.2); border-left: 4px solid #34d399; border-radius: 8px; padding: 14px 18px; color: #94a3b8; font-size: 0.88rem; line-height: 1.6; margin-top: 12px; }
.insight-box strong { color: #e2e8f0; }
.warn-box { background: linear-gradient(135deg, rgba(251,191,36,0.08), rgba(245,158,11,0.04)); border: 1px solid rgba(251,191,36,0.2); border-left: 4px solid #fbbf24; border-radius: 8px; padding: 14px 18px; color: #94a3b8; font-size: 0.88rem; line-height: 1.6; margin-top: 12px; }
.warn-box strong { color: #e2e8f0; }
.stPlotlyChart { border-radius: 12px; overflow: hidden; }
div[data-testid="stMetric"] { background: linear-gradient(135deg, rgba(99,102,241,0.12), rgba(139,92,246,0.08)); border: 1px solid rgba(99,102,241,0.25); border-radius: 12px; padding: 16px 20px; }
div[data-testid="stMetric"] label { color: #94a3b8 !important; font-size: 0.75rem !important; }
div[data-testid="stMetric"] [data-testid="stMetricValue"] { color: #f1f5f9 !important; font-size: 1.6rem !important; font-weight: 700 !important; }
div[data-testid="stMetric"] [data-testid="stMetricDelta"] { font-size: 0.8rem !important; }
</style>
""", unsafe_allow_html=True)

# ─── Plotly dark theme defaults ──────────────────────────────────────────────
PLOT_BG   = "rgba(13,18,38,0)"
PAPER_BG  = "rgba(13,18,38,0)"
GRID_CLR  = "rgba(99,102,241,0.12)"
FONT_CLR  = "#94a3b8"
TRUE_CLR  = "#6366f1"   # Indigo - New UI
FALSE_CLR = "#f59e0b"   # Amber  - Old UI
GREEN     = "#34d399"
PURPLE    = "#a78bfa"
ROSE      = "#fb7185"

def base_layout(**kwargs):
    return dict(
        plot_bgcolor=PLOT_BG,
        paper_bgcolor=PAPER_BG,
        font=dict(family="Inter", color=FONT_CLR, size=12),
        margin=dict(l=12, r=12, t=40, b=12),
        **kwargs
    )

# ─────────────────────────────────────────────────────────────────────────────
#  SIDEBAR / FILTERS
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:12px 0 20px 0">
        <h1 style="color:#e2e8f0;font-size:1.15rem;font-weight:700;margin:0">📍 Address UI v2</h1>
        <p style="color:#64748b;font-size:0.78rem;margin:4px 0 0 0">A/B Analysis Dashboard</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("**Filters**")
    
    # Date Filter
    date_range = st.date_input("Date Range", value=(datetime.date(2026, 3, 7), datetime.date.today()))
    start_date = date_range[0]
    end_date = date_range[1] if len(date_range) > 1 else date_range[0]

    # App Version Filter
    versions = fetch_versions()
    selected_versions = st.multiselect("App Versions", versions, default=[])
    
    # Refresh Button
    if st.button("Refresh Data", type="primary"):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.markdown("**Navigate**")
    sections = [
        "🎯 Overview",
        "📊 Funnel Conversions",
        "🎯 Accuracy Attribution",
        "🖱️ Marker Moves",
        "🔔 Support Nudge Matrix",
        "🔍 Search Bar Impact",
        "🚚 Delivery Impact"
    ]
    selected = st.radio("Navigate", sections, label_visibility="collapsed")

    st.divider()
    st.markdown("""
    <div style="background:linear-gradient(135deg,rgba(99,102,241,0.15),rgba(139,92,246,0.1));border:1px solid rgba(99,102,241,0.3);border-radius:10px;padding:12px 14px">
        <p style="color:#94a3b8;font-size:0.75rem;margin:0">
            <strong style="color:#a5b4fc">True</strong> = New UI (v2)<br>
            <strong style="color:#fcd34d">False</strong> = Old UI (v1)<br><br>
            Variants attributed via <code style="color:#94a3b8;font-size:0.72rem">app_open</code> event per session.
        </p>
    </div>
    """, unsafe_allow_html=True)


# ─── Data Extraction Logic (Helpers) ─────────────────────────────────────────

df_conv = fetch_conversions(start_date, end_date, selected_versions)
if not df_conv.empty and 'new_address_experience' in df_conv.columns:
    old_row = df_conv[df_conv['new_address_experience'] == 'false'].iloc[0] if not df_conv[df_conv['new_address_experience'] == 'false'].empty else None
    new_row = df_conv[df_conv['new_address_experience'] == 'true'].iloc[0] if not df_conv[df_conv['new_address_experience'] == 'true'].empty else None
else:
    old_row, new_row = None, None

def get_rates(row):
    if row is None or row['total_add_address'] == 0 or row['confirm_sessions'] == 0:
        return 0, 0, 0
    c1 = (row['confirm_sessions'] / row['total_add_address']) * 100
    c2 = (row['save_after_confirm_sessions'] / row['confirm_sessions']) * 100
    c3 = (row['save_after_add_sessions'] / row['total_add_address']) * 100
    return round(c1, 2), round(c2, 2), round(c3, 2)

f_pcts = list(get_rates(old_row)) if old_row is not None else [0, 0, 0]
t_pcts = list(get_rates(new_row)) if new_row is not None else [0, 0, 0]

acc_row = fetch_accuracy(start_date, end_date, selected_versions)
avg_imp = round(float(acc_row.get('avg_improvement', 0) or 0), 2)
p95_imp = round(float(acc_row.get('p95_improvement', 0) or 0), 2)
avg_conf = round(float(acc_row.get('avg_confirmed_accuracy', 0) or 0), 2)
avg_best = round(float(acc_row.get('avg_best_accuracy', 0) or 0), 2)

df_marker = fetch_marker_moves(start_date, end_date, selected_versions)
def get_avg_moves(df_m, variant, has_conf):
    if df_m.empty or 'new_address_experience' not in df_m.columns: return 0
    subset = df_m[(df_m['new_address_experience'] == variant) & (df_m['has_confirmed'] == has_conf)]
    return round(subset.iloc[0]['avg_marker_moves'], 2) if not subset.empty else 0
def get_move_sessions(df_m, variant, has_conf):
    if df_m.empty or 'new_address_experience' not in df_m.columns: return 0
    subset = df_m[(df_m['new_address_experience'] == variant) & (df_m['has_confirmed'] == has_conf)]
    return int(subset.iloc[0]['total_sessions']) if not subset.empty else 0

old_moves_conf = get_avg_moves(df_marker, 'false', 1)
new_moves_conf = get_avg_moves(df_marker, 'true', 1)

df_sbar = fetch_search_impact(start_date, end_date, selected_versions)
if not df_sbar.empty and 'saves' in df_sbar.columns and 'searches' in df_sbar.columns:
    df_sbar['Conv %'] = ((df_sbar['saves'] / df_sbar['searches']) * 100).round(2)
    tot_searches = df_sbar['searches'].sum()
    tot_saves = df_sbar['saves'].sum()
    sbar_overall = round((tot_saves / tot_searches * 100), 2) if tot_searches > 0 else 0
else:
    sbar_overall = 0
    tot_searches = 0


# ─────────────────────────────────────────────────────────────────────────────
#  OVERVIEW
# ─────────────────────────────────────────────────────────────────────────────
if selected == "🎯 Overview":
    st.markdown("""
    <div style="padding:28px 0 4px 0">
        <h1 style="color:#e2e8f0;font-size:1.9rem;font-weight:700;margin:0">Address UI v2 — Performance Analysis</h1>
        <p style="color:#64748b;font-size:0.9rem;margin:8px 0 0 0">New User Checkout Cohort · Android</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    # KPI row
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        uplift = round(t_pcts[2] - f_pcts[2], 2)
        st.metric("Overall Conv — New UI", f"{t_pcts[2]}%", f"{'+' if uplift > 0 else ''}{uplift}pp vs Old UI", delta_color="normal")
    with c2:
        st.metric("Overall Conv — Old UI", f"{f_pcts[2]}%", "Baseline")
    with c3:
        st.metric("Avg GPS Improvement", f"{avg_imp} m", "Background polling")
    with c4:
        move_delta = round(new_moves_conf - old_moves_conf, 2)
        st.metric("Avg Marker Moves (New UI ✓)", f"{new_moves_conf}", f"{move_delta} vs Old UI ✓")
    with c5:
        st.metric("Search Bar → Save", f"{sbar_overall}%", "Overall")

    st.markdown("---")

    # Funnel overview side-by-side
    st.markdown("### End-to-End Funnel Snapshot")

    col_left, col_right = st.columns(2)
    stages = ["Add Address", "Confirm Location", "Save Address"]
    false_vals = [100, f_pcts[0], f_pcts[2]]
    true_vals  = [100, t_pcts[0], t_pcts[2]]

    for col, label, vals, clr in [
        (col_left,  "False — Old UI", false_vals, FALSE_CLR),
        (col_right, "True  — New UI", true_vals,  TRUE_CLR),
    ]:
        with col:
            fig = go.Figure(go.Funnel(
                y=stages,
                x=vals,
                textinfo="value+percent initial",
                textfont=dict(color="#f1f5f9", size=13, family="Inter"),
                marker=dict(
                    color=[clr, clr, clr],
                    line=dict(width=0)
                ),
                connector=dict(line=dict(color="rgba(255,255,255,0.05)", width=1)),
                opacity=0.9,
            ))
            fig.update_layout(
                **base_layout(height=340, title=dict(text=label, font=dict(color="#e2e8f0", size=14), x=0.5)),
                xaxis=dict(visible=False),
            )
            st.plotly_chart(fig, use_container_width=True)

    # Quick insight cards
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div class="insight-box">
            💡 <strong>New UI wins on both conversion steps.</strong> Converts significantly better, reducing overall friction for users who are currently in the cart without any saved addresses.
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="warn-box">
            ⚠️ <strong>Support features are essential safety nets.</strong> Many final completions in the New UI stem from the map search bar and support nudge usage.
        </div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
#  FUNNEL CONVERSIONS
# ─────────────────────────────────────────────────────────────────────────────
elif selected == "📊 Funnel Conversions":
    st.markdown("""
    <div style="padding:20px 0 4px 0">
        <h1 style="color:#e2e8f0;font-size:1.5rem;font-weight:700;margin:0">📊 Funnel Conversions</h1>
        <p style="color:#64748b;font-size:0.85rem;margin:6px 0 0 0">New User Checkout Cohort — <code>add_address=cartFragment, address=0, source=cart/add_address</code></p>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    # Step-by-step grouped bar
    steps = ["Add → Confirm", "Confirm → Save", "Add → Save (Overall)"]
    deltas = [round(t - f, 2) for t, f in zip(t_pcts, f_pcts)]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Old UI (False)",
        x=steps, y=f_pcts,
        marker_color=FALSE_CLR,
        text=[f"{v}%" for v in f_pcts],
        textposition="outside",
        textfont=dict(color="#fcd34d", size=13),
        width=0.32,
        offset=-0.18,
    ))
    fig.add_trace(go.Bar(
        name="New UI (True)",
        x=steps, y=t_pcts,
        marker_color=TRUE_CLR,
        text=[f"{v}%" for v in t_pcts],
        textposition="outside",
        textfont=dict(color="#a5b4fc", size=13),
        width=0.32,
        offset=0.18,
    ))
    fig.update_layout(
        **base_layout(height=420),
        barmode="overlay",
        yaxis=dict(
            title="Conversion (%)", range=[0, 110],
            gridcolor=GRID_CLR, zeroline=False, tickfont=dict(color=FONT_CLR)
        ),
        xaxis=dict(gridcolor=GRID_CLR, tickfont=dict(color="#cbd5e1", size=13)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    font=dict(color=FONT_CLR)),
        title=dict(text="Step-by-Step Funnel Conversion by Variant", font=dict(color="#e2e8f0", size=14)),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Delta callouts
    c1, c2, c3 = st.columns(3)
    for col, step, delta in zip([c1, c2, c3], steps, deltas):
        with col:
            st.metric(f"Δ  {step}", f"{'+' if delta > 0 else ''}{delta}pp", "New UI uplift", delta_color="normal")

    st.divider()

    # Side-by-side funnels
    st.markdown("#### Full Funnel Visualisation")
    col_a, col_b = st.columns(2)
    for col, label, vals, clr in [
        (col_a, "Old UI (False)", [100, f_pcts[0], f_pcts[2]], FALSE_CLR),
        (col_b, "New UI (True)",  [100, t_pcts[0], t_pcts[2]], TRUE_CLR),
    ]:
        with col:
            fig2 = go.Figure(go.Funnel(
                y=["Add Address", "Confirm Location", "Save Address"],
                x=vals,
                textinfo="value+percent initial",
                textfont=dict(color="#f1f5f9", size=13),
                marker=dict(color=[clr]*3, line=dict(width=0)),
                connector=dict(line=dict(color="rgba(255,255,255,0.05)")),
            ))
            fig2.update_layout(**base_layout(height=300, title=dict(text=label, font=dict(color="#e2e8f0", size=13), x=0.5)), xaxis=dict(visible=False))
            st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # Support nudge stats
    st.markdown("#### Support Nudge Conversion (New UI Only)")
    nudge_conf_rate, nudge_save_rate = 0, 0
    if new_row is not None and new_row['nudge_sessions'] > 0:
        nudge_conf_rate = round(new_row['confirm_after_nudge_sessions'] / new_row['nudge_sessions'] * 100, 2)
        nudge_save_rate = round(new_row['save_after_nudge_sessions'] / new_row['nudge_sessions'] * 100, 2)

    col_n1, col_n2 = st.columns(2)
    with col_n1:
        st.metric("Nudge → Confirm Location", f"{nudge_conf_rate}%")
    with col_n2:
        st.metric("Nudge → Save Address", f"{nudge_save_rate}%")

    fig_nudge = go.Figure()
    fig_nudge.add_trace(go.Bar(
        x=["Nudge → Confirm", "Nudge → Save"],
        y=[nudge_conf_rate, nudge_save_rate],
        marker=dict(
            color=[PURPLE, ROSE],
            line=dict(width=0),
        ),
        text=[f"{nudge_conf_rate}%", f"{nudge_save_rate}%"],
        textposition="outside",
        textfont=dict(color="#e2e8f0", size=13),
        width=0.4,
    ))
    fig_nudge.update_layout(
        **base_layout(height=300),
        yaxis=dict(range=[0, 110], gridcolor=GRID_CLR, zeroline=False, tickfont=dict(color=FONT_CLR)),
        xaxis=dict(tickfont=dict(color="#cbd5e1", size=13)),
        title=dict(text="Support Nudge → Subsequent Action (True Variant)", font=dict(color="#e2e8f0", size=13)),
    )
    st.plotly_chart(fig_nudge, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
#  ACCURACY ATTRIBUTION
# ─────────────────────────────────────────────────────────────────────────────
elif selected == "🎯 Accuracy Attribution":
    st.markdown("""
    <div style="padding:20px 0 4px 0">
        <h1 style="color:#e2e8f0;font-size:1.5rem;font-weight:700;margin:0">🎯 Accuracy Attribution</h1>
        <p style="color:#64748b;font-size:0.85rem;margin:6px 0 0 0">Background location polling accuracy — New UI (True Variant) only</p>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    # Metrics
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Cases — Best at Confirm", f"{acc_row.get('fetched_best_early', 0)}", "conf_acc<100 & best empty")
    with c2:
        st.metric("Cases — Better Loc Later", f"{acc_row.get('fetched_better_later', 0)}", "best_acc populated")
    with c3:
        st.metric("Avg Confirmed Accuracy", f"{avg_conf} m", f"P95: {round(float(acc_row.get('p95_confirmed_accuracy',0) or 0), 2)} m")
    with c4:
        st.metric("Avg Best Accuracy", f"{avg_best} m", f"P95: {round(float(acc_row.get('p95_best_accuracy',0) or 0), 2)} m")

    st.divider()

    # Avg vs P95 grouped comparison
    fig = go.Figure()
    categories = ["Confirmed Accuracy", "Best Location Accuracy", "Improvement (Conf−Best)"]
    avgs = [avg_conf, avg_best, avg_imp]
    p95s = [round(float(acc_row.get('p95_confirmed_accuracy',0) or 0), 2), round(float(acc_row.get('p95_best_accuracy',0) or 0), 2), p95_imp]

    fig.add_trace(go.Bar(name="Average", x=categories, y=avgs,
        marker_color=TRUE_CLR, text=[f"{v} m" for v in avgs],
        textposition="outside", textfont=dict(color="#a5b4fc", size=12), width=0.28, offset=-0.15))
    fig.add_trace(go.Bar(name="P95", x=categories, y=p95s,
        marker_color=PURPLE, text=[f"{v} m" for v in p95s],
        textposition="outside", textfont=dict(color="#c4b5fd", size=12), width=0.28, offset=0.15))

    fig.update_layout(**base_layout(height=400, barmode="overlay"),
        yaxis=dict(title="Meters", gridcolor=GRID_CLR, zeroline=False, tickfont=dict(color=FONT_CLR)),
        xaxis=dict(tickfont=dict(color="#cbd5e1", size=13)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color=FONT_CLR)),
        title=dict(text="GPS Accuracy — Average vs P95", font=dict(color="#e2e8f0", size=14)),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Gauge for improvement
    st.markdown("#### Accuracy Improvement Gauge")
    col_g1, col_g2 = st.columns(2)
    max_avg_val = max(30, avg_imp * 1.5)
    max_p95_val = max(130, p95_imp * 1.5)
    for col, label, avg, max_val, clr in [
        (col_g1, "Avg Improvement (m)", avg_imp, max_avg_val, GREEN),
        (col_g2, "P95 Improvement (m)", p95_imp, max_p95_val, PURPLE),
    ]:
        with col:
            fig_g = go.Figure(go.Indicator(
                mode="gauge+number",
                value=avg,
                title={"text": label, "font": {"color": "#e2e8f0", "size": 13}},
                gauge={
                    "axis": {"range": [0, max_val], "tickcolor": FONT_CLR},
                    "bar": {"color": clr},
                    "bgcolor": "rgba(0,0,0,0)",
                    "bordercolor": "rgba(255,255,255,0.05)",
                    "steps": [{"range": [0, max_val * 0.5], "color": "rgba(255,255,255,0.04)"},
                               {"range": [max_val * 0.5, max_val], "color": "rgba(255,255,255,0.02)"}],
                },
                number={"suffix": " m", "font": {"color": "#f1f5f9", "size": 28}},
            ))
            fig_g.update_layout(**base_layout(height=260))
            st.plotly_chart(fig_g, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
#  MARKER MOVES
# ─────────────────────────────────────────────────────────────────────────────
elif selected == "🖱️ Marker Moves":
    st.markdown("""
    <div style="padding:20px 0 4px 0">
        <h1 style="color:#e2e8f0;font-size:1.5rem;font-weight:700;margin:0">🖱️ Marker Moves — Friction Analysis</h1>
        <p style="color:#64748b;font-size:0.85rem;margin:6px 0 0 0">How much do users fight the map pin before deciding to confirm or drop off?</p>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    old_moves_drop = get_avg_moves(df_marker, 'false', 0)
    new_moves_drop = get_avg_moves(df_marker, 'true', 0)
    
    old_sess_conf = get_move_sessions(df_marker, 'false', 1)
    old_sess_drop = get_move_sessions(df_marker, 'false', 0)
    new_sess_conf = get_move_sessions(df_marker, 'true', 1)
    new_sess_drop = get_move_sessions(df_marker, 'true', 0)

    old_tot = old_sess_conf + old_sess_drop
    new_tot = new_sess_conf + new_sess_drop

    old_conf_pct = round(old_sess_conf / old_tot * 100, 2) if old_tot > 0 else 0
    old_drop_pct = round(old_sess_drop / old_tot * 100, 2) if old_tot > 0 else 0
    new_conf_pct = round(new_sess_conf / new_tot * 100, 2) if new_tot > 0 else 0
    new_drop_pct = round(new_sess_drop / new_tot * 100, 2) if new_tot > 0 else 0

    # KPIs
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Confirmed Users — Old UI", f"{old_conf_pct}%", f"Avg {old_moves_conf} marker moves")
    with c2: st.metric("Confirmed Users — New UI", f"{new_conf_pct}%", f"Avg {new_moves_conf} marker moves")
    with c3: st.metric("Dropped Off — Old UI", f"{old_drop_pct}%", f"Avg {old_moves_drop} marker moves")
    with c4: st.metric("Dropped Off — New UI", f"{new_drop_pct}%", f"Avg {new_moves_drop} marker moves")

    st.divider()

    col_pie, col_bar = st.columns([1, 1.6])

    with col_pie:
        # Session distribution pies
        st.markdown("**Session Outcome Distribution**")
        fig_pies = make_subplots(
            rows=1, cols=2,
            specs=[[{"type": "domain"}, {"type": "domain"}]],
            subplot_titles=["Old UI", "New UI"],
        )
        colors_pie = [GREEN, ROSE]
        for i, (variant, confirmed_pct, dropped_pct) in enumerate([
            ("Old UI", old_conf_pct, old_drop_pct),
            ("New UI", new_conf_pct, new_drop_pct),
        ]):
            fig_pies.add_trace(go.Pie(
                labels=["Confirmed", "Dropped Off"],
                values=[confirmed_pct, dropped_pct],
                hole=0.55,
                marker=dict(colors=colors_pie, line=dict(width=2, color="rgba(13,18,38,0.8)")),
                textfont=dict(color="#e2e8f0", size=11),
                textinfo="percent",
                hovertemplate="%{label}: %{percent}<extra></extra>",
            ), row=1, col=i+1)
        fig_pies.update_layout(**base_layout(height=290), showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.15, font=dict(color=FONT_CLR)))
        for annotation in fig_pies.layout.annotations:
            annotation.font.color = "#e2e8f0"
            annotation.font.size = 12
        st.plotly_chart(fig_pies, use_container_width=True)

    with col_bar:
        # Avg marker moves comparison
        st.markdown("**Avg Marker Moves — Confirmed vs Dropped Off**")
        combo = go.Figure()
        outcomes = ["Dropped Off", "Confirmed"]
        old_moves = [old_moves_drop, old_moves_conf]
        new_moves = [new_moves_drop,  new_moves_conf]
        combo.add_trace(go.Bar(name="Old UI", x=outcomes, y=old_moves,
            marker_color=FALSE_CLR, text=[f"{v}" for v in old_moves],
            textposition="outside", textfont=dict(color="#fcd34d", size=12), width=0.3, offset=-0.16))
        combo.add_trace(go.Bar(name="New UI", x=outcomes, y=new_moves,
            marker_color=TRUE_CLR, text=[f"{v}" for v in new_moves],
            textposition="outside", textfont=dict(color="#a5b4fc", size=12), width=0.3, offset=0.16))
        combo.update_layout(**base_layout(height=290, barmode="overlay"),
            yaxis=dict(title="Avg Moves", gridcolor=GRID_CLR, zeroline=False, tickfont=dict(color=FONT_CLR)),
            xaxis=dict(tickfont=dict(color="#cbd5e1", size=13)),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color=FONT_CLR)),
        )
        st.plotly_chart(combo, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
#  SUPPORT NUDGE MATRIX
# ─────────────────────────────────────────────────────────────────────────────
elif selected == "🔔 Support Nudge Matrix":
    st.markdown("""
    <div style="padding:20px 0 4px 0">
        <h1 style="color:#e2e8f0;font-size:1.5rem;font-weight:700;margin:0">🔔 Support Nudge Matrix</h1>
        <p style="color:#64748b;font-size:0.85rem;margin:6px 0 0 0">3 trigger reasons × 3 user actions — Conversion & distribution breakdown</p>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    df_nudge = fetch_support_matrix(start_date, end_date, selected_versions)
    if not df_nudge.empty:
        df_nudge['Dist %'] = df_nudge.groupby('reason')['nudges_shown'].transform(lambda x: (x / x.sum()) * 100)
        df_nudge['Confirm %'] = (df_nudge['confirmed_sessions'] / df_nudge['nudges_shown']) * 100
        df_nudge['Save %'] = (df_nudge['saved_sessions'] / df_nudge['nudges_shown']) * 100
        df_nudge.fillna(0, inplace=True)
    else:
        st.warning("No support nudge data available for current filters.")

    if not df_nudge.empty:
        action_colors = {
            "dismiss":              "#f59e0b",
            "search_location":      "#6366f1",
            "use_current_location": "#34d399",
        }

        # ── Pie charts: action distribution within each reason ─────────────────
        st.markdown("#### Action Distribution Within Each Nudge Reason")
        reasons = df_nudge['reason'].unique()
        cols = st.columns(max(len(reasons), 1))
        for col, reason in zip(cols, reasons):
            subset = df_nudge[df_nudge["reason"] == reason]
            with col:
                fig_pie = go.Figure(go.Pie(
                    labels=subset["action"],
                    values=subset["Dist %"],
                    hole=0.52,
                    marker=dict(
                        colors=[action_colors.get(a, "#aaa") for a in subset["action"]],
                        line=dict(width=2, color="rgba(13,18,38,0.8)")
                    ),
                    textinfo="percent+label",
                    textfont=dict(color="#f1f5f9", size=10),
                    hovertemplate="%{label}: %{value:.1f}%<extra></extra>",
                ))
                fig_pie.update_layout(
                    plot_bgcolor=PLOT_BG,
                    paper_bgcolor=PAPER_BG,
                    font=dict(family="Inter", color=FONT_CLR, size=12),
                    height=260,
                    showlegend=False,
                    margin=dict(l=8, r=8, t=40, b=8),
                    title=dict(text=reason.replace("_"," ").title(), font=dict(color="#e2e8f0", size=12), x=0.5),
                )
                st.plotly_chart(fig_pie, use_container_width=True)

        st.divider()

        # ── Grouped bar: Confirm & Save conversion by reason+action ───────────
        st.markdown("#### Confirm & Save Conversion by Reason × Action")

        fig_matrix = go.Figure()
        x_labels = [f"{r.replace('_',' ')[:6]}·{a.replace('_',' ')[:4]}" for r, a in zip(df_nudge["reason"], df_nudge["action"])]

        fig_matrix.add_trace(go.Bar(
            name="Confirm Conv %",
            x=x_labels, y=df_nudge["Confirm %"].round(2),
            marker_color=PURPLE,
            text=[f"{v:.1f}%" for v in df_nudge["Confirm %"]],
            textposition="outside", textfont=dict(color="#c4b5fd", size=10),
            width=0.35, offset=-0.18,
        ))
        fig_matrix.add_trace(go.Bar(
            name="Save Conv %",
            x=x_labels, y=df_nudge["Save %"].round(2),
            marker_color=GREEN,
            text=[f"{v:.1f}%" for v in df_nudge["Save %"]],
            textposition="outside", textfont=dict(color="#6ee7b7", size=10),
            width=0.35, offset=0.18,
        ))
        fig_matrix.update_layout(
            **base_layout(height=420, barmode="overlay"),
            yaxis=dict(title="Conversion (%)", range=[0, 110], gridcolor=GRID_CLR, zeroline=False, tickfont=dict(color=FONT_CLR)),
            xaxis=dict(tickangle=-35, tickfont=dict(color="#cbd5e1", size=10)),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color=FONT_CLR)),
        )
        st.plotly_chart(fig_matrix, use_container_width=True)

        st.divider()

        # ── Data table ─────────────────────────────────────────────────────────
        st.markdown("#### Full Matrix Table")
        st.dataframe(
            df_nudge[['reason', 'action', 'nudges_shown', 'Dist %', 'Confirm %', 'Save %']].style
                .background_gradient(subset=["Dist %","Confirm %","Save %"], cmap="Blues")
                .format({"Dist %":"{:.1f}%","Confirm %":"{:.1f}%","Save %":"{:.1f}%"}),
            use_container_width=True, height=360
        )

# ─────────────────────────────────────────────────────────────────────────────
#  SEARCH BAR
# ─────────────────────────────────────────────────────────────────────────────
elif selected == "🔍 Search Bar Impact":
    st.markdown("""
    <div style="padding:20px 0 4px 0">
        <h1 style="color:#e2e8f0;font-size:1.5rem;font-weight:700;margin:0">🔍 Search Bar Impact</h1>
        <p style="color:#64748b;font-size:0.85rem;margin:6px 0 0 0">map_search_bar → save_address_clicked conversion, by trigger source</p>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    if not df_sbar.empty:
        df_sbar['Volume %'] = (df_sbar['searches'] / tot_searches * 100).round(1)

        best_source = df_sbar.loc[df_sbar['Conv %'].idxmax()]
        worst_source = df_sbar.loc[df_sbar['Conv %'].idxmin()]

        # KPIs
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("Overall Search → Save", f"{sbar_overall}%")
        with c2: st.metric("Best Source Conv", f"{best_source['Conv %']}%", best_source['source'])
        with c3: st.metric("Total Searches", f"{tot_searches:,}")
        with c4: st.metric("Worst Source Conv", f"{worst_source['Conv %']}%", worst_source['source'])

        st.divider()

        col_pie, col_bar = st.columns([1, 1.6])

        with col_pie:
            st.markdown("**Search Volume Distribution**")
            src_colors = [TRUE_CLR, FALSE_CLR, PURPLE, ROSE, GREEN]
            fig_vol = go.Figure(go.Pie(
                labels=df_sbar["source"],
                values=df_sbar["searches"],
                hole=0.55,
                marker=dict(colors=src_colors, line=dict(width=2, color="rgba(13,18,38,0.8)")),
                textinfo="percent+label",
                textfont=dict(color="#f1f5f9", size=10),
                hovertemplate="%{label}: %{value} searches (%{percent})<extra></extra>",
            ))
            fig_vol.update_layout(**base_layout(height=310, showlegend=False))
            st.plotly_chart(fig_vol, use_container_width=True)

        with col_bar:
            st.markdown("**Conversion Rate by Source**")
            fig_conv = go.Figure(go.Bar(
                x=df_sbar["source"],
                y=df_sbar["Conv %"],
                marker=dict(color=src_colors, line=dict(width=0)),
                text=[f"{v}%" for v in df_sbar["Conv %"]],
                textposition="outside",
                textfont=dict(color="#e2e8f0", size=13),
                width=0.45,
            ))
            fig_conv.update_layout(
                **base_layout(height=310),
                yaxis=dict(range=[0, 110], title="Conv %", gridcolor=GRID_CLR, zeroline=False, tickfont=dict(color=FONT_CLR)),
                xaxis=dict(tickfont=dict(color="#cbd5e1", size=11)),
            )
            st.plotly_chart(fig_conv, use_container_width=True)

        # Volume vs conv scatter
        st.markdown("#### Volume vs Conversion — Bubble View")
        fig_bubble = px.scatter(
            df_sbar,
            x="Conv %",
            y="source",
            size="searches",
            color="source",
            color_discrete_sequence=src_colors,
            text="source",
            size_max=60,
        )
        fig_bubble.update_traces(textposition="top center", textfont=dict(color="#e2e8f0", size=11))
        fig_bubble.update_layout(
            **base_layout(height=280),
            showlegend=False,
            xaxis=dict(title="Conversion %", range=[0, 100], gridcolor=GRID_CLR, zeroline=False, tickfont=dict(color=FONT_CLR)),
            yaxis=dict(gridcolor=GRID_CLR, zeroline=False, tickfont=dict(color="#cbd5e1", size=11)),
        )
        st.plotly_chart(fig_bubble, use_container_width=True)
    else:
        st.warning("No search bar data available for current filters.")

# ─────────────────────────────────────────────────────────────────────────────
#  DELIVERY IMPACT
# ─────────────────────────────────────────────────────────────────────────────
elif selected == "🚚 Delivery Impact":
    st.markdown('''
    <div style="padding:20px 0 4px 0">
        <h1 style="color:#e2e8f0;font-size:1.5rem;font-weight:700;margin:0">🚚 Delivery Impact</h1>
        <p style="color:#64748b;font-size:0.85rem;margin:6px 0 0 0">OrderDelivered Tracking Events (order_count = 1 cohort)</p>
    </div>
    ''', unsafe_allow_html=True)
    st.divider()
    
    df_del = fetch_delivery_impact(start_date, end_date, selected_versions)
    
    if not df_del.empty:
        old_del = df_del[df_del['variant'] == 'false']
        new_del = df_del[df_del['variant'] == 'true']
        
        # Calculate Aggregates
        def get_metrics(subset):
            subset = subset.dropna(subset=['delivery_time_sec', 'ride_time_sec', 'handover_time_sec'])
            if subset.empty: return 0,0,0,0,0,0
            d_p90 = subset['delivery_time_sec'].quantile(0.9) / 60
            r_avg = subset['ride_time_sec'].mean() / 60
            r_p90 = subset['ride_time_sec'].quantile(0.9) / 60
            h_avg = subset['handover_time_sec'].mean() / 60
            h_p90 = subset['handover_time_sec'].quantile(0.9) / 60
            return len(subset), d_p90, r_avg, r_p90, h_avg, h_p90
            
        old_n, old_dp90, old_ravg, old_rp90, old_havg, old_hp90 = get_metrics(old_del)
        new_n, new_dp90, new_ravg, new_rp90, new_havg, new_hp90 = get_metrics(new_del)
        
        # Distance Stats
        def get_dist_metrics(subset):
            subset = subset.dropna(subset=['placement_del_distance'])
            if subset.empty: return 0,0,0,0
            n = len(subset)
            avg = subset['placement_del_distance'].mean()
            c_high = len(subset[subset['placement_del_distance'] <= 50])
            c_inacc = len(subset[subset['placement_del_distance'] > 200])
            return avg, (c_high/n*100), (c_inacc/n*100), c_inacc
            
        old_davg, old_dhigh, old_dinacc, old_inacc_n = get_dist_metrics(old_del)
        new_davg, new_dhigh, new_dinacc, new_inacc_n = get_dist_metrics(new_del)
        
        st.markdown("#### The 3 Phases of Delivery Time")
        # Time Metrics Top Row
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("Orders Tracked", f"{new_n}", f"{new_n - old_n} vs Old UI")
        with c2: st.metric("Overall Delivery P90", f"{new_dp90:.1f}m", f"{new_dp90 - old_dp90:.1f}m vs Old UI")
        with c3: st.metric("Ride Time P90", f"{new_rp90:.1f}m", f"{new_rp90 - old_rp90:.1f}m vs Old UI", delta_color="inverse")
        with c4: st.metric("Handover P90", f"{new_hp90:.1f}m", f"{new_hp90 - old_hp90:.1f}m vs Old UI", delta_color="inverse")
        
        # Stacked Bar for Time Breakdown
        st.markdown("---")
        st.markdown("**Average Time Breakdown (Mins)**")
        fig_time = go.Figure()
        
        # Ride Time
        fig_time.add_trace(go.Bar(
            name="Ride Time", y=["Old UI", "New UI"], x=[old_ravg, new_ravg], orientation='h',
            marker=dict(color=PURPLE), text=[f"{v:.1f}m" for v in [old_ravg, new_ravg]], textposition="inside"
        ))
        # Handover Time
        fig_time.add_trace(go.Bar(
            name="Handover Time", y=["Old UI", "New UI"], x=[old_havg, new_havg], orientation='h',
            marker=dict(color=GREEN), text=[f"{v:.1f}m" for v in [old_havg, new_havg]], textposition="inside"
        ))
        fig_time.update_layout(**base_layout(height=280, barmode="stack", yaxis=dict(autorange="reversed")),
            xaxis=dict(title="Average Minutes", gridcolor=GRID_CLR, tickfont=dict(color=FONT_CLR)))
        st.plotly_chart(fig_time, use_container_width=True)
        
        st.markdown("---")
        
        # Distance Impact
        st.markdown("#### Placement vs Actual Delivery Distance")
        c1, c2, c3 = st.columns(3)
        with c1: st.metric("Average Distance (New UI)", f"{new_davg:.1f}m", f"{new_davg - old_davg:.1f}m vs Old", delta_color="inverse")
        with c2: st.metric("Highly Accurate (<50m)", f"{new_dhigh:.1f}%", f"{new_dhigh - old_dhigh:.1f}pp", delta_color="normal")
        with c3: st.metric("Inaccurate (>200m)", f"{new_dinacc:.1f}%", f"{new_dinacc - old_dinacc:.1f}pp", delta_color="inverse")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Distance Buckets
        dist_bins = ["< 50m", "50-200m", "> 200m"]
        def get_bins(subset):
            n = len(subset.dropna(subset=['placement_del_distance']))
            if n==0: return [0,0,0]
            c1 = len(subset[subset['placement_del_distance'] <= 50]) / n * 100
            c2 = len(subset[(subset['placement_del_distance'] > 50) & (subset['placement_del_distance'] <= 200)]) / n * 100
            c3 = len(subset[subset['placement_del_distance'] > 200]) / n * 100
            return [c1, c2, c3]
            
        fig_dist = go.Figure()
        fig_dist.add_trace(go.Bar(name="Old UI", x=dist_bins, y=get_bins(old_del), text=[f"{v:.1f}%" for v in get_bins(old_del)], textposition="outside", marker_color=FALSE_CLR, width=0.35, offset=-0.18))
        fig_dist.add_trace(go.Bar(name="New UI", x=dist_bins, y=get_bins(new_del), text=[f"{v:.1f}%" for v in get_bins(new_del)], textposition="outside", marker_color=TRUE_CLR, width=0.35, offset=0.18))
        fig_dist.update_layout(**base_layout(height=350, barmode="overlay"), yaxis=dict(title="% of Orders", range=[0,105], gridcolor=GRID_CLR), xaxis=dict(title="Distance Buckets"))
        st.plotly_chart(fig_dist, use_container_width=True)
        
        st.markdown("---")
        
        # Deep Dive (>200m attribution)
        st.markdown("#### Attribution for Inaccurate Orders (>200m)")
        st.markdown("Why was the pin placed so inaccurately? Looking closely at device permissions:")
        
        def attr_metrics(subset):
            inacc = subset[subset['placement_del_distance'] > 200]
            n = len(inacc)
            if n == 0: return [0,0,0,0,0]
            loc_gran = len(inacc[inacc['loc_perm_granted']==1])/n*100
            loc_deni = len(inacc[inacc['loc_perm_denied']==1])/n*100
            gps_gran = len(inacc[inacc['gps_perm_granted']==1])/n*100
            gps_deni = len(inacc[inacc['gps_perm_denied']==1])/n*100
            use_curr = len(inacc[inacc['get_current_loc_clicked']==1])/n*100
            return [loc_gran, loc_deni, gps_gran, gps_deni, use_curr]
            
        attr_labels = ["Location Granted", "Location Denied", "GPS Granted", "GPS Denied", 'Clicked "Use Current"']
        fig_attr = go.Figure()
        fig_attr.add_trace(go.Bar(name="Old UI", x=attr_labels, y=attr_metrics(old_del), marker_color=FALSE_CLR, text=[f"{v:.1f}%" for v in attr_metrics(old_del)], textposition="outside", width=0.35, offset=-0.18))
        fig_attr.add_trace(go.Bar(name="New UI", x=attr_labels, y=attr_metrics(new_del), marker_color=TRUE_CLR, text=[f"{v:.1f}%" for v in attr_metrics(new_del)], textposition="outside", width=0.35, offset=0.18))
        fig_attr.update_layout(**base_layout(height=380, barmode="overlay"), yaxis=dict(range=[0,105], title="% of Inaccurate Orders", gridcolor=GRID_CLR))
        st.plotly_chart(fig_attr, use_container_width=True)
        
        st.markdown('''
        <div class="insight-box">
            💡 <strong>Observation:</strong> Nearly 40% of the worst placements (>200m error) occurred when the user <strong>explicitly granted location permission</strong> and clicked "Use Current Location". This proves many severe cases are caused by highly inaccurate OS-level GPS fetching, which users confidently accept without verifying the pin.
        </div>''', unsafe_allow_html=True)

    else:
        st.warning("No tracking data available for the given criteria.")
