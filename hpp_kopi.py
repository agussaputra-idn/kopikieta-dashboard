import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from google.oauth2 import service_account
import google.generativeai as genai
from PIL import Image

# 1. KONFIGURASI HALAMAN
st.set_page_config(page_title="Kopi Kieta Business Suite", page_icon="☕", layout="wide")

# --- KONFIGURASI AI & GOOGLE SHEETS ---
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model_ai = genai.GenerativeModel('gemini-1.5-flash')

def get_gsheet_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_info = st.secrets["gcp_service_account"]
    cleaned_key = creds_info["private_key"].replace("\\n", "\n").strip()
    creds = service_account.Credentials.from_service_account_info(
        {
            "type": creds_info["type"],
            "project_id": creds_info["project_id"],
            "private_key_id": creds_info["private_key_id"],
            "private_key": cleaned_key,
            "client_email": creds_info["client_email"],
            "client_id": creds_info["client_id"],
            "auth_uri": creds_info["auth_uri"],
            "token_uri": creds_info["token_uri"],
            "auth_provider_x509_cert_url": creds_info["auth_provider_x509_cert_url"],
            "client_x509_cert_url": creds_info["client_x509_cert_url"],
        },
        scopes=scope
    )
    return gspread.authorize(creds)

def load_data(sheet_name):
    try:
        client = get_gsheet_client()
        sheet = client.open("Database Kopi Kieta").worksheet(sheet_name)
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        if not df.empty and 'Tanggal' in df.columns:
            df['Tanggal'] = pd.to_datetime(df['Tanggal'], errors='coerce')
        return df
    except Exception:
        if sheet_name == "Penjualan":
            return pd.DataFrame(columns=["Tanggal", "Menu", "Kategori", "Jumlah", "Omzet"])
        return pd.DataFrame(columns=["Tanggal", "Item", "Kategori", "Jumlah", "Total Harga"])

def save_to_gsheets(sheet_name, new_data_list):
    try:
        client = get_gsheet_client()
        sheet = client.open("Database Kopi Kieta").worksheet(sheet_name)
        sheet.append_rows(new_data_list)
        return True
    except Exception as e:
        st.error(f"Gagal simpan ke {sheet_name}: {e}")
        return False

def sync_to_gsheets(sheet_name, df):
    try:
        client = get_gsheet_client()
        sheet = client.open("Database Kopi Kieta").worksheet(sheet_name)
        sheet.clear()
        df_sync = df.copy()
        if 'Tanggal' in df_sync.columns:
            df_sync['Tanggal'] = df_sync['Tanggal'].astype(str)
        data_to_sync = [df_sync.columns.values.tolist()] + df_sync.values.tolist()
        sheet.update(range_name='A1', values=data_to_sync)
        return True
    except Exception as e:
        st.error(f"Gagal sinkronisasi: {e}")
        return False

# --- DATABASE MENU ---
MENU_COFFEE = {"Brown Sugar": 13000, "Butterscotch": 13000, "Caramel": 13000, "Hazelnut": 13000, "Vanilla": 13000}
MENU_NON_COFFEE = {"Chocolate Latte": 13000, "Redvelvet Latte": 13000, "Mango Latte": 13000, "Matcha Latte": 13000}
MENU_TOAST = {"Original": 12000, "Chocolate": 12000, "Strawberry": 12000, "Blueberry": 12000}

# --- BARU: SISIPKAN DI SINI ---
MASTER_HARGA_BELI = {
    "Kopi": 250000, "Susu UHT": 25000, "Susu SKM": 30000, 
    "Krimer": 72000, "Bubuk Non-Coffee": 64000, "Gula Aren": 32000, 
    "Gula Pasir": 18000, "Syrup": 76000, "Es Batu": 16000, "Air Galon": 4000,
    "Cup Gelas": 700, "Lid/Sealer": 200, "Sedotan": 0, "Kantong Plastik": 0
}

# Daftar list yang dipakai selectbox tetap dibiarkan
LIST_BAHAN_BAKU = ["Kopi", "Susu UHT", "Susu SKM", "Krimer", "Bubuk Non-Coffee", "Gula Aren", "Gula Pasir", "Syrup", "Es Batu", "Air Galon"]
LIST_PACKAGING = ["Cup Gelas", "Lid/Sealer", "Sedotan", "Kantong Plastik"]

# 2. CUSTOM CSS
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    [data-testid="stMetricValue"] { font-size: 28px; color: #00FF00 !important; }
    [data-testid="stMetricLabel"] { font-size: 14px; color: #ffffff !important; opacity: 1; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #3e4255; }
    </style>
    """, unsafe_allow_html=True)

# 3. INITIALIZE DATA
if 'data_penjualan' not in st.session_state:
    st.session_state.data_penjualan = load_data("Penjualan")
if 'data_pembelian' not in st.session_state:
    st.session_state.data_pembelian = load_data("Pembelian")

st.title("☕ Kopi Kieta Business Suite")

# 4. SIDEBAR
st.sidebar.header("🏢 Biaya Operasional")
sewa = st.sidebar.number_input("Sewa Tempat", value=700000)
gaji = st.sidebar.number_input("Gaji Karyawan", value=1200000)
listrik = st.sidebar.number_input("Listrik & Maint", value=0)
target_qty = st.sidebar.number_input("Target Vol (Cup)", value=500)
total_opex = sewa + gaji + listrik
opex_per_cup = total_opex / target_qty if target_qty > 0 else 0

tab1, tab2, tab3 = st.tabs(["🎯 HPP & Simulasi Profit", "📈 Penjualan & AI Reader", "🛒 Pembelian (Modal)"])

# ==========================================
# TAB 1: KALKULATOR HPP
# ==========================================
with tab1:
    col_input, col_result = st.columns([2, 1])
    with col_input:
        st.subheader("🛒 Master Harga & Racikan")
        with st.expander("🥤 KATEGORI BAHAN BAKU", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                h_kopi = st.number_input("Kopi (Rp/kg)", min_value=0, value=250000)
                h_susu = st.number_input("Susu UHT (Rp/L)", min_value=0, value=25000)
                h_skm = st.number_input("Susu SKM (Rp/kg)", min_value=0, value=30000)
                h_krimer = st.number_input("Krimer (Rp/kg)", min_value=0, value=72000)
                h_bubuk = st.number_input("Bubuk (Rp/kg)", min_value=0, value=65000)
            with c2:
                h_g_aren = st.number_input("Gula Aren (Rp/L)", min_value=0, value=32000)
                h_g_pasir = st.number_input("Gula Pasir (Rp/kg)", min_value=0, value=18000)
                h_syrup = st.number_input("Syrup (Rp/750ml)", min_value=0, value=76000)
                h_es = st.number_input("Es Batu (Rp/10kg)", min_value=0, value=16000)
                h_air = st.number_input("Air (Rp/19L)", min_value=0, value=4000)
        with st.expander("📦 KATEGORI PACKAGING", expanded=False):
            p1, p2 = st.columns(2)
            h_cup = p1.number_input("Cup (Rp/pcs)", min_value=0, value=700)
            h_lid = p1.number_input("Lid (Rp/pcs)", min_value=0, value=200)
            h_sedotan = p2.number_input("Sedotan (Rp/pcs)", min_value=0, value=150)
            h_plastik = p2.number_input("Plastik (Rp/pcs)", min_value=0, value=200)

        with st.expander("🧪 RACIKAN PER CUP", expanded=True):
            r1, r2, r3 = st.columns(3)
            with r1: 
                g_kopi = st.number_input("Kopi (gr)", min_value=0, value=18)
                m_susu = st.number_input("Susu (ml)", min_value=0, value=100)
                m_skm = st.number_input("SKM (gr)", min_value=0, value=20)
                g_krimer = st.number_input("Krimer (gr)", min_value=0, value=10)
            with r2: 
                ml_g_a = st.number_input("G. Aren (ml)", min_value=0, value=20)
                g_g_p = st.number_input("G. Pasir (gr)", min_value=0, value=0)
                ml_syrup = st.number_input("Syrup (ml)", min_value=0, value=10)
                g_bubuk = st.number_input("Bubuk (gr)", min_value=0, value=0)
            with r3: 
                m_es = st.number_input("Es (gr)", min_value=0, value=150)
                m_air = st.number_input("Air (ml)", min_value=0, value=50)
                h_lain = st.number_input("Lain", min_value=0, value=0)
                m_target = st.number_input("Margin %", min_value=0, value=30)

    with col_result:
        st.subheader("📊 Analisis Profit")
        cost_cup = (g_kopi*h_kopi/1000) + (m_susu*h_susu/1000) + (m_skm*h_skm/1000) + (g_krimer*h_krimer/1000) + (ml_g_a*h_g_aren/1000) + (g_g_p*h_g_pasir/1000) + (ml_syrup*h_syrup/750) + (g_bubuk*h_bubuk/1000) + (m_es*h_es/10000) + (m_air*h_air/19000) + (h_cup+h_lid+h_sedotan+h_plastik) + h_lain
        harga_rek = cost_cup / (1 - (m_target / 100)) if m_target < 100 else cost_cup * 2
        st.info(f"Saran: Rp {harga_rek:,.0f}")
        h_jual_fix = st.number_input("SET JUAL (Rp)", 0.0, value=float(round(harga_rek, -2)))
        periode_sim = st.selectbox("Simulasi Laba:", ["Per Cup", "Per Bulan", "Per Tahun"])
        profit_cup = h_jual_fix - cost_cup - opex_per_cup
        if periode_sim == "Per Cup": val_p = profit_cup
        elif periode_sim == "Per Bulan": val_p = profit_cup * target_qty
        else: val_p = profit_cup * target_qty * 12
        st.metric("HPP/CUP", f"Rp {cost_cup:,.0f}")
        st.metric(f"PROFIT ({periode_sim.upper()})", f"Rp {val_p:,.0f}")
        st.metric("PERSENTASE", f"{((h_jual_fix - cost_cup)/h_jual_fix*100):.1f}%" if h_jual_fix > 0 else "0%")

# ==========================================
# TAB 2: PENJUALAN
# ==========================================
with tab2:
    st.subheader("📝 Penjualan & AI Reader")
    col_e, col_v = st.columns([1, 2])
    with col_e:
        foto = st.file_uploader("Upload Foto", type=['jpg','png','jpeg'])
        if foto and st.button("🚀 AI Baca Foto"):
            with st.spinner("Analisis..."):
                try: 
                    res = model_ai.generate_content([f"Rincikan jumlah terjual: {', '.join(MENU_COFFEE.keys())}.", Image.open(foto)])
                    st.info(f"Hasil AI: {res.text}")
                except Exception as e: st.error(e)

        with st.form("form_jual", clear_on_submit=True):
            tgl_j = st.date_input("Tanggal Transaksi", datetime.now())
            
            def render_menu_inputs(menu_dict, key_prefix):
                data_input = {}
                for m, h_std in menu_dict.items():
                    col_nm, col_qty, col_prc = st.columns([2, 1, 1.5])
                    col_nm.markdown(f"<div style='padding-top:10px;'>{m}</div>", unsafe_allow_html=True)
                    qty = col_qty.number_input("Qty", min_value=0, step=1, key=f"q_{key_prefix}_{m}", label_visibility="collapsed")
                    price = col_prc.number_input("Harga", min_value=0, value=h_std, step=500, key=f"p_{key_prefix}_{m}", label_visibility="collapsed")
                    if qty > 0:
                        data_input[m] = {"qty": qty, "price": price}
                return data_input

            with st.expander("☕ VARIAN COFFEE", expanded=True):
                res_c = render_menu_inputs(MENU_COFFEE, "c")
            with st.expander("🥤 VARIAN NON-COFFEE", expanded=False):
                res_nc = render_menu_inputs(MENU_NON_COFFEE, "nc")
            with st.expander("🍞 VARIAN TOAST", expanded=False):
                res_t = render_menu_inputs(MENU_TOAST, "t")
            with st.expander("➕ LAINNYA", expanded=False):
                cl1, cl2, cl3 = st.columns([2, 1, 1.5])
                n_l = cl1.text_input("Nama Produk", placeholder="Menu Lain...")
                q_l = cl2.number_input("Qty ", min_value=0)
                h_l = cl3.number_input("Harga ", min_value=0)

            if st.form_submit_button("Simpan Baru"):
                rows = []
                for cat, res in [("Coffee", res_c), ("Non-Coffee", res_nc), ("Toast", res_t)]:
                    for m, val in res.items():
                        rows.append([str(tgl_j), m, cat, val['qty'], val['qty'] * val['price']])
                if q_l > 0 and n_l:
                    rows.append([str(tgl_j), n_l, "Lain-lain", q_l, q_l * h_l])
                
                if rows and save_to_gsheets("Penjualan", rows):
                    st.session_state.data_penjualan = load_data("Penjualan")
                    st.success("✅ Tersimpan!")
                    st.rerun()

        st.divider()
        t_res_j = st.date_input("Reset", datetime.now(), key="res_j")
        if st.button("Hapus Data Penjualan Tanggal Ini", type="secondary"):
            df_n = st.session_state.data_penjualan
            df_new = df_n[df_n['Tanggal'].dt.date != t_res_j]
            if sync_to_gsheets("Penjualan", df_new):
                st.session_state.data_penjualan = df_new; st.rerun()

    with col_v:
        st.write("### Data Penjualan")
        df_p = st.session_state.data_penjualan
        if not df_p.empty:
            ed_j = st.data_editor(df_p, num_rows="dynamic", use_container_width=True, key="ed_j")
            if st.button("💾 Sinkronkan Edit Penjualan"):
                if sync_to_gsheets("Penjualan", ed_j): st.session_state.data_penjualan = ed_j; st.rerun()
            st.plotly_chart(px.bar(ed_j, x="Menu", y="Jumlah", color="Kategori", title="Tren Penjualan"), use_container_width=True)

# ==========================================
# TAB 3: PEMBELIAN
# ==========================================
with tab3:
    st.subheader("🛒 Pembelian (Modal)")
    col_b1, col_b2 = st.columns([1.2, 2])
    
    with col_b1:
        with st.form("form_beli_baru", clear_on_submit=True):
            tgl_b = st.date_input("Tanggal Belanja", datetime.now())
            
            def render_beli_inputs(items_list, key_prefix):
                data_beli = {}
                for item in items_list:
                    # Ambil harga default dari master, kalau tidak ada set 0
                    h_default = MASTER_HARGA_BELI.get(item, 0)
                    c_nm, c_qty, c_prc = st.columns([2, 1, 1.5])
                    c_nm.markdown(f"<div style='padding-top:10px;'>{item}</div>", unsafe_allow_html=True)
                    qty = c_qty.number_input("Qty", min_value=0.0, step=0.1, key=f"bq_{key_prefix}_{item}", label_visibility="collapsed")
                    price = c_prc.number_input("Harga", min_value=0, value=h_default, step=500, key=f"bp_{key_prefix}_{item}", label_visibility="collapsed")
                    if qty > 0:
                        data_beli[item] = {"qty": qty, "price": price}
                return data_beli

            with st.expander("🥤 BAHAN BAKU", expanded=True):
                res_bb = render_beli_inputs(LIST_BAHAN_BAKU, "bb")
                
            with st.expander("📦 PACKAGING", expanded=False):
                res_pk = render_beli_inputs(LIST_PACKAGING, "pk")
            
            with st.expander("⚙️ LAIN-LAIN / BIAYA TAMBAHAN", expanded=False):
                cl1, cl2, cl3 = st.columns([2, 1, 1.5])
                i_ll = cl1.text_input("Nama Pengeluaran", placeholder="Contoh: Listrik/Parkir")
                q_ll = cl2.number_input("Qty ", min_value=0, value=1)
                h_ll = cl3.number_input("Total Biaya", min_value=0)

            if st.form_submit_button("Simpan Belanja"):
                rows_b = []
                # Proses Bahan Baku & Packaging
                for cat, res in [("Bahan Baku", res_bb), ("Packaging", res_pk)]:
                    for item, val in res.items():
                        rows_b.append([str(tgl_b), item, cat, val['qty'], int(val['qty'] * val['price'])])
                
                # Proses Lain-lain
                if i_ll and h_ll > 0:
                    rows_b.append([str(tgl_b), i_ll, "Lain-lain", q_ll, h_ll])
                
                if rows_b and save_to_gsheets("Pembelian", rows_b):
                    st.session_state.data_pembelian = load_data("Pembelian")
                    st.success("✅ Belanja Dicatat!")
                    st.rerun()

        st.divider()
        t_res_b = st.date_input("Reset Data", datetime.now(), key="res_b")
        if st.button("Hapus Data Pembelian Tanggal Ini", type="secondary"):
            df_nb = st.session_state.data_pembelian
            df_newb = df_nb[df_nb['Tanggal'].dt.date != t_res_b]
            if sync_to_gsheets("Pembelian", df_newb):
                st.session_state.data_pembelian = df_newb; st.rerun()

    with col_b2:
        st.write("### Data Pembelian")
        df_b = st.session_state.data_pembelian
        if not df_b.empty:
            ed_b = st.data_editor(df_b, num_rows="dynamic", use_container_width=True, key="ed_b")
            if st.button("💾 Sinkronkan Edit Pembelian"):
                if sync_to_gsheets("Pembelian", ed_b): 
                    st.session_state.data_pembelian = ed_b
                    st.rerun()
            
            # Summary Metrics
            omzet = st.session_state.data_penjualan['Omzet'].sum() if not st.session_state.data_penjualan.empty else 0
            belanja = ed_b['Total Harga'].astype(float).sum() if not ed_b.empty else 0
            st.divider()
            m1, m2, m3 = st.columns(3)
            m1.metric("OMZET", f"Rp {omzet:,.0f}")
            m2.metric("BELANJA", f"Rp {belanja:,.0f}")
            m3.metric("LABA KOTOR", f"Rp {omzet - belanja:,.0f}")
