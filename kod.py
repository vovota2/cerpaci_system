import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import math

# 1. Konfigurace stránky
st.set_page_config(page_title="Návrh čerpacího systému - Tým 2", layout="wide")
st.title("💧 Návrh čerpacího systému pro dopravu vody")
st.markdown("**Tým 2:** Automatizovaný výpočetní a optimalizační model")

# 2. Definice konstant (Zadání Tým 2)
Q_den_m3 = 7500.0      # Denní objem [m3/den]
H_g = 90.0             # Geodetická výška [m]
h_s = 5.0              # Sací výška [m]
L_v = 2500.0           # Délka výtlaku [m]
L_s = 40.0             # Délka sání [m]
k_drsnost = 1.5 / 1000 # Drsnost potrubí [m]

# Výpočet jmenovitého průtoku
Q_m3_s = (Q_den_m3 / 24) / 3600 # Převod na m3/s
Q_l_s = Q_m3_s * 1000           # Převod na l/s

# 3. Postranní panel pro uživatelské vstupy (Optimalizační parametry)
st.sidebar.header("Optimalizované parametry")
D_s_mm = st.sidebar.number_input("Průměr sacího potrubí Ds [mm]", min_value=50, max_value=500, value=250, step=10)
D_v_mm = st.sidebar.number_input("Průměr výtlačného potrubí Dv [mm]", min_value=50, max_value=500, value=200, step=10)

D_s = D_s_mm / 1000 # převod na metry
D_v = D_v_mm / 1000 # převod na metry

st.sidebar.header("Odhadované součinitele ztrát (ζ)")
zeta_kos = st.sidebar.number_input("Sací koš", value=4.0)
zeta_klapka = st.sidebar.number_input("Zpětná klapka", value=2.0)
zeta_koleno_90 = st.sidebar.number_input("Koleno 90°", value=0.3)
# Zde si tým doplní další součinitele...

# 4. Základní výpočty rychlostí
v_s = Q_m3_s / (math.pi * (D_s / 2)**2)
v_v = Q_m3_s / (math.pi * (D_v / 2)**2)

# 5. Zobrazení výsledků
col1, col2 = st.columns(2)

with col1:
    st.subheader("Základní hydraulické parametry")
    st.write(f"**Požadovaný průtok (Q):** {Q_l_s:.2f} l/s ({Q_m3_s:.4f} m³/s)")
    
    # Podmíněné formátování pro rychlosti (upozornění, pokud jsou mimo doporučené meze)
    st.write(f"**Rychlost v sání (v_s):** {v_s:.2f} m/s")
    if v_s > 1.5:
        st.warning("⚠️ Rychlost v sání je příliš vysoká (doporučeno do 1.5 m/s). Zvyšte průměr sání.")
        
    st.write(f"**Rychlost ve výtlaku (v_v):** {v_v:.2f} m/s")
    if v_v > 2.5:
        st.warning("⚠️ Rychlost ve výtlaku je příliš vysoká (doporučeno do 2.5 m/s). Zvyšte průměr výtlaku.")

with col2:
    st.subheader("Výpočet tlakových ztrát")
    st.info("Zde bude implementován výpočet Reynoldsova čísla, součinitele tření λ (např. Colebrook-White) a celkové dopravní výšky čerpadla.")
    # TODO: Zde doprogramujete výpočet ztrát

# 6. Charakteristika potrubí (Příklad vykreslení)
st.subheader("Charakteristika systému")
# Pro graf vytvoříme pole průtoků od 0 do 1.5 násobku jmenovitého průtoku
q_array = np.linspace(0, Q_m3_s * 1.5, 50)
# TODO: Zde místo H_g nahradíte výpočtem skutečné křivky: H_celk = H_g + k * Q^2
h_array = H_g + (1500 * q_array**2) # <- TOTO JE JEN ILUSTRATIVNÍ ROVNICE! 

fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(q_array * 1000, h_array, label='Charakteristika potrubí', color='blue', linewidth=2)
ax.axvline(x=Q_l_s, color='red', linestyle='--', label='Požadovaný pracovní bod')
ax.set_xlabel('Průtok Q [l/s]')
ax.set_ylabel('Dopravní výška H [m]')
ax.set_title('Závislost dopravní výšky na průtoku')
ax.grid(True)
ax.legend()

st.pyplot(fig)

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
