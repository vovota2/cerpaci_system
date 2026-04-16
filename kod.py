import streamlit as st

# ... (předchozí konstanty z Týmu 2 zůstávají: Q_den = 7500, L_v = 2500, L_s = 40) ...

# --- NOVÉ KONSTANTY Z EKONOMIKY ---
CENA_EL_KWH = 8.50    # 8500 Kč/MWh je 8.5 Kč/kWh
CENA_LITINA_KG = 65.0 # Kč/kg
ODPISY_POTRUBI = 0.10 # 10 % z investice do ročních nákladů

# Tabulka hmotností (DN [mm] : kg/m)
hmotnosti_dn = {200: 35, 250: 45, 300: 58, 350: 72, 400: 88, 500: 125}

st.sidebar.header("Provozní parametry")
# Omezení dle zadání na max 16 hodin
t_provoz = st.sidebar.slider("Doba čerpání [hod/den]", min_value=8, max_value=16, value=14, step=1)

# Přepočet průtoku podle zvolené doby provozu!
Q_m3_h = 7500 / t_provoz       # m3 za hodinu
Q_m3_s = Q_m3_h / 3600         # m3 za sekundu
Q_l_s = Q_m3_s * 1000          # litry za sekundu

st.sidebar.header("Rozměry potrubí (DN)")
# Zde omezíme výběr jen na hodnoty z tabulky, aby to odpovídalo zadání
D_s_mm = st.sidebar.selectbox("Průměr sání Ds [mm]", options=list(hmotnosti_dn.keys()), index=1)
D_v_mm = st.sidebar.selectbox("Průměr výtlaku Dv [mm]", options=list(hmotnosti_dn.keys()), index=0)

# --- VÝPOČET INVESTICE DO POTRUBÍ (CAPEX) ---
celkova_delka = 2500 + 40 # L_v + L_s (Tým 2)
# Pro zjednodušení teď počítám obojí stejným průměrem pro ukázku, 
# ve finále to rozdělíte na L_s * vaha(D_s) + L_v * vaha(D_v)
vaha_sani_kg = 40 * hmotnosti_dn[D_s_mm]
vaha_vytlaku_kg = 2500 * hmotnosti_dn[D_v_mm]
celkova_vaha_kg = vaha_sani_kg + vaha_vytlaku_kg

cena_potrubi_celkem = celkova_vaha_kg * CENA_LITINA_KG
rocni_naklady_potrubi = cena_potrubi_celkem * ODPISY_POTRUBI

st.subheader("Ekonomická bilance potrubí")
st.write(f"**Celková hmotnost potrubí:** {celkova_vaha_kg:,.0f} kg".replace(',', ' '))
st.write(f"**Investice do potrubí (CAPEX):** {cena_potrubi_celkem:,.0f} Kč".replace(',', ' '))
st.write(f"**Roční odpis potrubí (do nákladů):** {rocni_naklady_potrubi:,.0f} Kč/rok".replace(',', ' '))
