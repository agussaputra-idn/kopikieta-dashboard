import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
# Kita ganti library auth-nya ke yang lebih stabil
from google.oauth2 import service_account
import google.generativeai as genai
from PIL import Image

# 1. KONFIGURASI HALAMAN
st.set_page_config(page_title="Kopi Kieta Business Suite", page_icon="☕", layout="wide")

# --- KONFIGURASI AI & GOOGLE SHEETS ---
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model_ai = genai.GenerativeModel('gemini-1.5-flash')

from google.oauth2 import service_account

def get_gsheet_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_info = st.secrets["gcp_service_account"]
    
    # Membersihkan karakter \n jika ada, dan menghapus spasi liar
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

# --- DATABASE MENU & DAFTAR BAHAN ---
MENU_COFFEE = ["Brown Sugar", "Butterscotch", "Caramel", "Hazelnut", "Vanilla"]
MENU_NON_COFFEE = ["Chocolate Latte", "Redvelvet Latte", "Mango Latte", "Matcha Latte"]
MENU_TOAST = ["Original", "Chocolate", "Strawberry", "Blueberry"]
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
                h_kopi = st.number_input("Kopi (Rp/kg)", min_value=0, value=150000)
                h_susu = st.number_input("Susu UHT (Rp/L)", min_value=0, value=25000)
                h_skm = st.number_input("Susu SKM (Rp/kg)", min_value=0, value=20000)
                h_krimer = st.number_input("Krimer (Rp/kg)", min_value=0, value=72000)
                h_bubuk = st.number_input("Bubuk (Rp/kg)", min_value=0, value=65000)
            with c2:
                h_g_aren = st.number_input("Gula Aren (Rp/L)", min_value=0, value=74000)
                h_g_pasir = st.number_input("Gula Pasir (Rp/kg)", min_value=0, value=18000)
                h_syrup = st.number_input("Syrup (Rp/750ml)", min_value=0, value=95000)
                h_es = st.number_input("Es Batu (Rp/10kg)", min_value=0, value=16000)
                h_air = st.number_input("Air (Rp/19L)", min_value=0, value=18000)
        with st.expander("📦 KATEGORI PACKAGING", expanded=False):
            p1, p2 = st.columns(2)
            # Menghilangkan batas maksimal (max_value)
            h_cup = p1.number_input("Cup (Rp/pcs)", min_value=0, value=800)
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
                try: res = model_ai.generate_content([f"Rincikan jumlah terjual: {', '.join(MENU_COFFEE + MENU_NON_COFFEE + MENU_TOAST)}.", Image.open(foto)]); st.info(f"Hasil AI: {res.text}")
                except Exception as e: st.error(e)
        with st.form("form_jual", clear_on_submit=True):
            tgl_j = st.date_input("Tanggal Transaksi", datetime.now())
            with st.expander("☕ VARIAN COFFEE", expanded=True):
                q_c = {m: st.number_input(f"{m}", min_value=0, key=f"c_{m}") for m in MENU_COFFEE}
            with st.expander("🥤 VARIAN NON-COFFEE", expanded=False):
                q_nc = {m: st.number_input(f"{m}", min_value=0, key=f"nc_{m}") for m in MENU_NON_COFFEE}
            with st.expander("🍞 VARIAN TOAST", expanded=False):
                q_t = {m: st.number_input(f"{m}", min_value=0, key=f"t_{m}") for m in MENU_TOAST}
            with st.expander("➕ LAINNYA", expanded=False):
                n_l = st.text_input("Nama Produk"); q_l = st.number_input("Qty", 0); h_l = st.number_input("Harga", 0)
            if st.form_submit_button("Simpan Baru"):
                rows = [[str(tgl_j), m, cat, q, q * h_jual_fix] for cat, d in [("Coffee", q_c), ("Non-Coffee", q_nc), ("Toast", q_t)] for m, q in d.items() if q > 0]
                if q_l > 0: rows.append([str(tgl_j), n_l, "Lain-lain", q_l, q_l * h_l])
                if rows and save_to_gsheets("Penjualan", rows):
                    st.session_state.data_penjualan = load_data("Penjualan"); st.success("✅ Tersimpan!")
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
# TAB 3: PEMBELIAN (TAMBAH KATEGORI LAIN-LAIN)
# ==========================================
with tab3:
    st.subheader("🛒 Pembelian (Modal)")
    col_b1, col_b2 = st.columns([1, 2])
    with col_b1:
        with st.form("form_beli", clear_on_submit=True):
            tgl_b = st.date_input("Tanggal Belanja", datetime.now())
            with st.expander("🥤 BAHAN BAKU", expanded=True):
                i_bb = st.selectbox("Bahan", ["-- Pilih --"] + LIST_BAHAN_BAKU)
                h_bb, q_bb = st.number_input("Hrg Satuan", 0, key="hb"), st.number_input("Qty", 0, key="qb")
            with st.expander("📦 PACKAGING", expanded=False):
                i_pk = st.selectbox("Pack", ["-- Pilih --"] + LIST_PACKAGING)
                h_pk, q_pk = st.number_input("Hrg Satuan ", 0, key="hp"), st.number_input("Qty ", 0, key="qp")
            
            # --- MENU TAMBAHAN: LAIN-LAIN ---
            with st.expander("⚙️ LAIN-LAIN / BIAYA TAMBAHAN", expanded=False):
                i_ll = st.text_input("Nama Pengeluaran (Contoh: Parkir/Galon)")
                h_ll = st.number_input("Total Biaya (Rp)", 0, key="hl")
                q_ll = 1 # Default 1 untuk pengeluaran biaya

            if st.form_submit_button("Simpan Belanja"):
                rows_b = []
                if i_bb != "-- Pilih --" and q_bb > 0: rows_b.append([str(tgl_b), i_bb, "Bahan Baku", q_bb, h_bb * q_bb])
                if i_pk != "-- Pilih --" and q_pk > 0: rows_b.append([str(tgl_b), i_pk, "Packaging", q_pk, h_pk * q_pk])
                if i_ll and h_ll > 0: rows_b.append([str(tgl_b), i_ll, "Lain-lain", q_ll, h_ll])
                
                if rows_b and save_to_gsheets("Pembelian", rows_b):
                    st.session_state.data_pembelian = load_data("Pembelian"); st.success("✅ Dicatat!")
        
        st.divider()
        t_res_b = st.date_input("Reset", datetime.now(), key="res_b")
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
                if sync_to_gsheets("Pembelian", ed_b): st.session_state.data_pembelian = ed_b; st.rerun()
            
            omzet = st.session_state.data_penjualan['Omzet'].sum() if not st.session_state.data_penjualan.empty else 0
            belanja = ed_b['Total Harga'].astype(float).sum() if not ed_b.empty else 0
            st.divider()
            m1, m2, m3 = st.columns(3)
            m1.metric("OMZET", f"Rp {omzet:,.0f}")
            m2.metric("BELANJA", f"Rp {belanja:,.0f}")
            m3.metric("LABA KOTOR", f"Rp {omzet - belanja:,.0f}")
