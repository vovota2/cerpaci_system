import os
import streamlit as st
import numpy as np
import plotly.graph_objects as go
import pandas as pd
from scipy.optimize import fsolve
from scipy.interpolate import PchipInterpolator

st.set_page_config(page_title="Charakteristika systému - Tým 2", layout="wide")
st.title("💧 Návrh čerpacího systému pro dopravu vody")
st.markdown("### Charakteristika potrubí a určení provozního bodu")

DEFAULTS = {
    "t_provoz": 16,
    "Ls": 40.0,
    "Lv": 2500.0,
    "Ds_val": 250,
    "Dv_val": 200,
    "zv": 0.5,
    "zout_typ": "Ostrohranný výtok (ξ = 1.1)",
    "p90": 6,
    "p45": 10,
    "p30": 4,
    "aktivni_reseni": None
}


@st.cache_data
def nacti_motory():
    # OPRAVA: Program bude hledat Excel vždy přesně v té složce, kde leží tento soubor app.py
    aktualni_slozka = os.path.dirname(os.path.abspath(__file__))
    cesta = os.path.join(aktualni_slozka, "motory.xlsx")
    
    if not os.path.exists(cesta):
        # Pokud ho nenajde, napíše nám přesně na webu, kam se koukal
        st.error(f"❌ Soubor s motory NEBYL NALEZEN! Program ho hledal přesně zde: {cesta}")
        return pd.DataFrame()

    try:
        # OPRAVA: Ošetření chyby při samotném čtení
        df = pd.read_excel(cesta)
    except Exception as e:
        st.error(f"❌ Soubor byl nalezen, ale nejde přečíst (chybí pravděpodobně knihovna 'openpyxl'): {e}")
        return pd.DataFrame()

    df = df.rename(columns={
        "power": "Pn_kW",
        "rpm": "Otacky",
        "voltage": "Napeti",
        "price": "Cena",
        "manufacturer": "Vyrobce",
        "efficiency": "Ucinnost"
    })

    for col in ["Pn_kW", "Otacky", "Cena"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["Pn_kW", "Otacky"]).copy()

    if "Vyrobce" not in df.columns:
        df["Vyrobce"] = "Motor"

    if "Napeti" not in df.columns:
        df["Napeti"] = "-"

    if "Ucinnost" not in df.columns:
        df["Ucinnost"] = "-"

    df["Vyrobce"] = df["Vyrobce"].astype(str).str.strip()
    df["Napeti"] = df["Napeti"].astype(str).str.strip()
    df["Ucinnost"] = df["Ucinnost"].astype(str).str.strip()

    df["Nazev"] = (
        df["Vyrobce"]
        + " "
        + df["Pn_kW"].astype(int).astype(str)
        + " kW / "
        + df["Otacky"].astype(int).astype(str)
        + " ot/min"
    )

    return df


def vyber_motoru(P_pump_kw, rpm_pump, df_motory, rezerva=0.15):
    """
    Výběr motoru s rezervou
    """
    if P_pump_kw is None or rpm_pump is None or df_motory.empty:
        return None

    kandidati = df_motory.copy()

    for col in ["Pn_kW", "Otacky", "Cena"]:
        if col in kandidati.columns:
            kandidati[col] = pd.to_numeric(kandidati[col], errors="coerce")

    kandidati = kandidati.dropna(subset=["Pn_kW", "Otacky"]).copy()
    if kandidati.empty:
        return None

    P_pozadovane = float(P_pump_kw) * (1 + rezerva)

    kandidati = kandidati[kandidati["Pn_kW"] >= P_pozadovane].copy()
    if kandidati.empty:
        return None

    kandidati["Rozdil_otacek"] = (kandidati["Otacky"] - rpm_pump).abs()

    sort_cols = ["Rozdil_otacek", "Pn_kW"]
    if "Cena" in kandidati.columns:
        sort_cols.append("Cena")

    kandidati = kandidati.sort_values(sort_cols)

    vybrany = kandidati.iloc[0].copy()
    vybrany["P_pozadovane"] = P_pozadovane
    vybrany["Rezerva_pct"] = rezerva * 100
    vybrany["Prebytek_kW"] = vybrany["Pn_kW"] - P_pozadovane

    return vybrany


def reset_do_zakladu():
    for key, val in DEFAULTS.items():
        st.session_state[key] = val


def toggle_reseni_1():
    if st.session_state.get("aktivni_reseni") == "R1":
        reset_do_zakladu()
    else:
        st.session_state.Ds_val = 350
        st.session_state.Dv_val = 300
        st.session_state.aktivni_reseni = "R1"


def toggle_reseni_2():
    if st.session_state.get("aktivni_reseni") == "R2":
        reset_do_zakladu()
    else:
        st.session_state.Ds_val = 400
        st.session_state.Dv_val = 350
        st.session_state.aktivni_reseni = "R2"


if "t_provoz" not in st.session_state:
    reset_do_zakladu()

df_motory = nacti_motory()

Q_den_m3 = 7500.0
H_g = 90.0
h_saci_vyska = 5.0
k_m = 1.5 / 1000.0
g = 9.81
ny = 1.004e-6

mapa_zeta_90 = {200: 0.424, 250: 0.418, 300: 0.414, 350: 0.411, 400: 0.409, 500: 0.405}
mapa_vytok = {
    "Ostrohranný výtok (ξ = 1.1)": 1.1,
    "Pozvolný l > 2.2d (ξ = 0.15)": 0.15,
    "S úkosem α = 20° (ξ = 0.4)": 0.4,
    "S úkosem α = 40° (ξ = 1.0)": 1.0,
    "S úkosem α = 60° (ξ = 1.15)": 1.15
}

Q_H_s_R1 = np.array([0, 400, 800]) / 3600.0
H_m_R1 = np.array([148, 140, 115])
poly_Y_pump_R1 = np.poly1d(np.polyfit(Q_H_s_R1, H_m_R1 * g, 2))

Q_Eta_s_R1 = np.array([0, 200, 400, 680, 800]) / 3600.0
Eta_pct_R1 = np.array([0, 50, 71, 80, 78])
f_Eta_R1 = PchipInterpolator(Q_Eta_s_R1, Eta_pct_R1)

Q_P_s_R1 = np.array([0, 400, 800]) / 3600.0
P_kw_R1 = np.array([105, 210, 315])
poly_P_R1 = np.poly1d(np.polyfit(Q_P_s_R1, P_kw_R1, 1))

Q_NPSH_s_R1 = np.array([200, 400, 600, 800]) / 3600.0
NPSH_m_R1 = np.array([2.2, 2.25, 2.5, 3.9])
f_NPSH_R1 = PchipInterpolator(Q_NPSH_s_R1, NPSH_m_R1)

Q_H_s_R2 = np.array([0, 300, 660]) / 3600.0
H_m_R2 = np.array([126, 119, 96])
poly_Y_pump_R2 = np.poly1d(np.polyfit(Q_H_s_R2, H_m_R2 * g, 2))

Q_Eta_s_R2 = np.array([0, 510, 660]) / 3600.0
Eta_pct_R2 = np.array([0, 80.5, 78])
f_Eta_R2 = PchipInterpolator(Q_Eta_s_R2, Eta_pct_R2)

Q_P_s_R2 = np.array([0, 300, 660]) / 3600.0
P_kw_R2 = np.array([60, 134, 220])
poly_P_R2 = np.poly1d(np.polyfit(Q_P_s_R2, P_kw_R2, 2))

Q_NPSH_s_R2 = np.array([300, 500, 660]) / 3600.0
NPSH_m_R2 = np.array([2.1, 3.7, 7.0])
f_NPSH_R2 = PchipInterpolator(Q_NPSH_s_R2, NPSH_m_R2)

st.sidebar.button("🔄 Obnovit vše", on_click=reset_do_zakladu)
st.sidebar.markdown("### Návrhová řešení")
res1_active = st.session_state.aktivni_reseni == "R1"
res2_active = st.session_state.aktivni_reseni == "R2"

col_btn1, col_btn2 = st.sidebar.columns(2)
col_btn1.button("Řešení 1", on_click=toggle_reseni_1, type="primary" if res1_active else "secondary")
col_btn2.button("Řešení 2", on_click=toggle_reseni_2, type="primary" if res2_active else "secondary")

st.sidebar.markdown("---")
t_provoz = st.sidebar.slider("Plánovaný čas [h/den]", 8, 24, key="t_provoz")
Q_target_m3_h = Q_den_m3 / t_provoz
Q_target_m3_s = Q_target_m3_h / 3600

st.sidebar.header("2. Parametry potrubí")
L_s = st.sidebar.number_input("Délka sání [m]", step=1.0, key="Ls")
L_v = st.sidebar.number_input("Délka výtlaku [m]", step=10.0, key="Lv")

prumery = list(mapa_zeta_90.keys())
D_s_mm = st.sidebar.selectbox("DN sání", options=prumery, key="Ds_val")
D_v_mm = st.sidebar.selectbox("DN výtlaku", options=prumery, key="Dv_val")
D_s, D_v = D_s_mm / 1000.0, D_v_mm / 1000.0

st.sidebar.header("3. Armatury (ζ)")
zeta_ventil = st.sidebar.number_input(
    "Regulační ventil",
    step=0.1,
    key="zv",
    help="Hodnota 0,5 odpovídá plně otevřenému šoupátku dle tabulek ve zdroji [3]."
)
typ_vytoku = st.sidebar.selectbox("Typ výtoku", options=list(mapa_vytok.keys()), key="zout_typ")
zeta_vytok = mapa_vytok[typ_vytoku]

pomer_S = 0.5
zeta_kos = ((1.707 - pomer_S) ** 2) * (1 / (pomer_S ** 2))
zeta_90_s, zeta_90_v = mapa_zeta_90[D_s_mm], mapa_zeta_90[D_v_mm]
zeta_45_v, zeta_30_v = zeta_90_v * 0.60, zeta_90_v * 0.45

col_a, col_b, col_c = st.sidebar.columns(3)
pocet_90 = col_a.number_input("90°", min_value=0, key="p90")
pocet_45 = col_b.number_input("45°", min_value=0, key="p45")
pocet_30 = col_c.number_input("30°", min_value=0, key="p30")


def get_lambda(Q_m3_s, D):
    if Q_m3_s <= 0:
        return 0
    v = (4 * Q_m3_s) / (np.pi * D**2)
    Re = (v * D) / ny
    return 0.25 / (np.log10((k_m / (3.7 * D)) + (5.74 / (Re**0.9))))**2


def vypocet_ztrat_sani(Q_m3_s):
    if Q_m3_s <= 0:
        return 0
    lam_s = get_lambda(Q_m3_s, D_s)
    v_s = (4 * Q_m3_s) / (np.pi * D_s**2)
    return (lam_s * (L_s / D_s) + zeta_kos + zeta_90_s) * (v_s**2 / (2 * g))


def vypocet_Y_sys(Q_m3_s):
    if Q_m3_s <= 0:
        return H_g * g
    h_zs = vypocet_ztrat_sani(Q_m3_s)
    lam_v = get_lambda(Q_m3_s, D_v)
    v_v = (4 * Q_m3_s) / (np.pi * D_v**2)
    sz_v = zeta_ventil + zeta_vytok + (pocet_90 * zeta_90_v) + (pocet_45 * zeta_45_v) + (pocet_30 * zeta_30_v)
    h_zv = (lam_v * (L_v / D_v) + sz_v) * (v_v**2 / (2 * g))
    return (H_g + h_zs + h_zv) * g


Q_op_m3_s = None
Y_op_jkg = None
poly_Y_active = None
f_NPSH_active = None
f_Eta_active = None
poly_P_active = None
pump_max_q = 800
npsh_min_q = 200
vybrany_motor = None
rpm_pump_active = None
nazev_cerpadla = None

if st.session_state.aktivni_reseni == "R1":
    poly_Y_active, f_NPSH_active = poly_Y_pump_R1, f_NPSH_R1
    f_Eta_active, poly_P_active = f_Eta_R1, poly_P_R1
    pump_max_q, npsh_min_q = 800, 200
    rpm_pump_active = 1488
    nazev_cerpadla = "KSB Omega 200-670 B"
    Q_op_m3_s = fsolve(lambda q: vypocet_Y_sys(q) - poly_Y_active(q), Q_target_m3_s)[0]
    Y_op_jkg = vypocet_Y_sys(Q_op_m3_s)

    P_motor_potreba = float(poly_P_active(Q_op_m3_s))
    vybrany_motor = vyber_motoru(
        P_pump_kw=P_motor_potreba,
        rpm_pump=rpm_pump_active,
        df_motory=df_motory,
        rezerva=0.15
    )

elif st.session_state.aktivni_reseni == "R2":
    poly_Y_active, f_NPSH_active = poly_Y_pump_R2, f_NPSH_R2
    f_Eta_active, poly_P_active = f_Eta_R2, poly_P_R2
    pump_max_q, npsh_min_q = 660, 300
    rpm_pump_active = 1486
    nazev_cerpadla = "KSB Omega 150-605 B"
    Q_op_m3_s = fsolve(lambda q: vypocet_Y_sys(q) - poly_Y_active(q), Q_target_m3_s)[0]
    Y_op_jkg = vypocet_Y_sys(Q_op_m3_s)

    P_motor_potreba = float(poly_P_active(Q_op_m3_s))
    vybrany_motor = vyber_motoru(
        P_pump_kw=P_motor_potreba,
        rpm_pump=rpm_pump_active,
        df_motory=df_motory,
        rezerva=0.15
    )

st.sidebar.markdown("---")
st.sidebar.markdown("**ℹ️ Vypočtené součinitele ztrát (ζ) a tření (λ):**")
c_z1, c_z2 = st.sidebar.columns(2)
c_z1.metric(
    "Sací koš (ζ)",
    f"{zeta_kos:.3f}",
    help="Vypočteno empirickým vzorcem pro sací koš s mřížkou (poměr průřezů S=0.5) dle zdroje [1]."
)
c_z2.metric(
    "Výtok (ζ)",
    f"{zeta_vytok:.3f}",
    help="Hodnota odpovídající geometrii výtoku do nádrže, odečteno ze zdroje [3]."
)
c_z1.metric(
    "Koleno 90° sání (ζ)",
    f"{zeta_90_s:.3f}",
    help="Hodnota vypočtena vlastním Excelem (z předmětu IMP) na základě rovnic ze zdroje [2]."
)
c_z2.metric(
    "Koleno 90° výtlak (ζ)",
    f"{zeta_90_v:.3f}",
    help="Hodnota vypočtena vlastním Excelem (z předmětu IMP) na základě rovnic ze zdroje [2]."
)
c_z1.metric(
    "Koleno 45° (ζ)",
    f"{zeta_45_v:.3f}",
    help="Vypočteno jako 60 % tlakové ztráty 90° kolena dle doporučení zdroje [3]."
)
c_z2.metric(
    "Koleno 30° (ζ)",
    f"{zeta_30_v:.3f}",
    help="Vypočteno jako 45 % tlakové ztráty 90° kolena dle doporučení zdroje [3]."
)

lambda_help = (
    "Délkový třecí součinitel se dynamicky mění, protože je přímo závislý na rychlosti proudění "
    "(Reynoldsově čísle). Vypočteno pomocí Swamee-Jainovy rovnice (zdroj [5]): "
    "λ = 0.25 / [log10(k/(3.7*D) + 5.74/Re^0.9)]^2"
)

st.sidebar.markdown("<br>", unsafe_allow_html=True)

if Q_op_m3_s is not None:
    lam_s_val = get_lambda(Q_op_m3_s, D_s)
    lam_v_val = get_lambda(Q_op_m3_s, D_v)
    st.sidebar.metric("Délkový třecí souč. λ (sání)", f"{lam_s_val:.4f}", help=lambda_help)
    st.sidebar.metric("Délkový třecí souč. λ (výtlak)", f"{lam_v_val:.4f}", help=lambda_help)
else:
    lam_s_1 = get_lambda(0.001, D_s)
    lam_s_2 = get_lambda(0.250, D_s)
    lam_v_1 = get_lambda(0.001, D_v)
    lam_v_2 = get_lambda(0.250, D_v)
    st.sidebar.metric(
        "Délkový třecí souč. λ (sání)",
        f"{min(lam_s_1, lam_s_2):.4f} - {max(lam_s_1, lam_s_2):.4f}",
        help=lambda_help
    )
    st.sidebar.metric(
        "Délkový třecí souč. λ (výtlak)",
        f"{min(lam_v_1, lam_v_2):.4f} - {max(lam_v_1, lam_v_2):.4f}",
        help=lambda_help
    )

if st.session_state.aktivni_reseni == "R1":
    st.info("💡 **Aktivní čerpadlo:** KSB Omega 200-670 B (1488 rpm). Zdroj katalogových dat: [4]")
elif st.session_state.aktivni_reseni == "R2":
    st.info("💡 **Aktivní čerpadlo:** KSB Omega 150-605 B (1486 rpm). Zdroj katalogových dat: [4]")

if vybrany_motor is not None:
    cena_motoru = "-"
    if "Cena" in vybrany_motor and pd.notna(vybrany_motor["Cena"]):
        cena_motoru = f"{vybrany_motor['Cena']:,.0f}".replace(",", " ")

    st.info(
        f"⚙️ **Vybraný motor:** {vybrany_motor['Nazev']} | "
        f"{vybrany_motor['Pn_kW']:.0f} kW | "
        f"{int(vybrany_motor['Otacky'])} ot/min | "
        f"{vybrany_motor['Napeti']} | "
        f"{vybrany_motor['Vyrobce']} | "
        f"{vybrany_motor['Ucinnost']} | "
        f"{cena_motoru} Kč  \n"
        f"Výběr byl proveden podle nejbližších otáček k čerpadlu ({rpm_pump_active} ot/min) "
        f"a nejbližšího vyššího výkonu s rezervou 15 %. Zdroj parametrů motorů a cen: [6], [7], [8]"
    )
elif st.session_state.aktivni_reseni is not None:
    st.warning("⚠️ Pro zvolený provozní bod nebyl v databázi nalezen vhodný motor.")

Q_array = np.linspace(0.001, 0.250, 150)
Q_array_m3_h = Q_array * 3600
Y_sys_array = np.array([vypocet_Y_sys(q) for q in Q_array])
Y_target_sys = vypocet_Y_sys(Q_target_m3_s)

layout_config = dict(
    xaxis=dict(
        range=[0, 800],
        dtick=100,
        showgrid=True,
        gridwidth=1,
        gridcolor="#dcdcdc",
        minor=dict(dtick=50, showgrid=True, gridwidth=1, gridcolor="#f0f0f0"),
        title="Q [m³/h]"
    ),
    yaxis=dict(
        showgrid=True,
        gridwidth=1,
        gridcolor="#dcdcdc",
        minor=dict(showgrid=True, gridwidth=1, gridcolor="#f0f0f0")
    ),
    template="plotly_white",
    height=400,
    margin=dict(l=20, r=20, t=60, b=20),
    title=dict(x=0, xanchor="left", font=dict(size=18))
)

fig_main = go.Figure()
fig_main.add_trace(
    go.Scatter(
        x=Q_array_m3_h,
        y=Y_sys_array,
        name=f"Soustava ({int(D_s_mm)}/{int(D_v_mm)})",
        line=dict(color="blue", width=3)
    )
)
fig_main.add_shape(
    type="line",
    x0=Q_target_m3_h,
    y0=0,
    x1=Q_target_m3_h,
    y1=Y_target_sys,
    line=dict(color="gray", width=2, dash="dash")
)
fig_main.add_trace(
    go.Scatter(
        x=[Q_target_m3_h],
        y=[Y_target_sys],
        name="Min. požadavek",
        mode="markers",
        marker=dict(color="gray", size=10)
    )
)

if poly_Y_active is not None and Q_op_m3_s is not None:
    Q_op_m3_h = Q_op_m3_s * 3600

    mask_pump = Q_array_m3_h <= pump_max_q
    fig_main.add_trace(
        go.Scatter(
            x=Q_array_m3_h[mask_pump],
            y=poly_Y_active(Q_array[mask_pump]),
            name="Čerpadlo",
            line=dict(color="green", width=3)
        )
    )
    fig_main.add_trace(
        go.Scatter(
            x=[Q_op_m3_h],
            y=[Y_op_jkg],
            name="pracovní bod",
            mode="markers",
            marker=dict(color="red", size=12)
        )
    )
    fig_main.update_layout(title_text="H-Q Charakteristika", yaxis_title="Měrná energie Y [J/kg]", **layout_config)

    fig_eta = go.Figure()
    fig_eta.add_trace(
        go.Scatter(
            x=Q_array_m3_h[mask_pump],
            y=f_Eta_active(Q_array[mask_pump]),
            name="Účinnost",
            line=dict(color="orange", width=3)
        )
    )
    fig_eta.add_trace(
        go.Scatter(
            x=[Q_op_m3_h],
            y=[f_Eta_active(Q_op_m3_s)],
            name="pracovní bod",
            mode="markers",
            marker=dict(color="red", size=12)
        )
    )
    fig_eta.update_layout(title_text="Účinnost η [%]", **layout_config)

    fig_p = go.Figure()
    fig_p.add_trace(
        go.Scatter(
            x=Q_array_m3_h[mask_pump],
            y=poly_P_active(Q_array[mask_pump]),
            name="Příkon",
            line=dict(color="purple", width=3)
        )
    )
    fig_p.add_trace(
        go.Scatter(
            x=[Q_op_m3_h],
            y=[poly_P_active(Q_op_m3_s)],
            name="pracovní bod",
            mode="markers",
            marker=dict(color="red", size=12)
        )
    )
    fig_p.update_layout(title_text="Příkon P [kW]", **layout_config)

    fig_npsh = go.Figure()
    mask_npsh_req = (Q_array_m3_h >= npsh_min_q) & (Q_array_m3_h <= pump_max_q)
    mask_npsh_avail = Q_array_m3_h <= 800
    npsh_a = 10.1 - h_saci_vyska - np.array([vypocet_ztrat_sani(q) for q in Q_array[mask_npsh_avail]])

    fig_npsh.add_trace(
        go.Scatter(
            x=Q_array_m3_h[mask_npsh_req],
            y=f_NPSH_active(Q_array[mask_npsh_req]),
            name="NPSHr",
            line=dict(color="teal", width=3)
        )
    )
    fig_npsh.add_trace(
        go.Scatter(
            x=Q_array_m3_h[mask_npsh_avail],
            y=npsh_a,
            name="NPSHa",
            line=dict(color="red", dash="dash")
        )
    )
    if Q_op_m3_h >= npsh_min_q:
        fig_npsh.add_trace(
            go.Scatter(
                x=[Q_op_m3_h],
                y=[f_NPSH_active(Q_op_m3_s)],
                name="pracovní bod",
                mode="markers",
                marker=dict(color="red", size=12)
            )
        )
    fig_npsh.update_layout(title_text="NPSH [m]", **layout_config)

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(fig_main, use_container_width=True)
    with c2:
        st.plotly_chart(fig_eta, use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        st.plotly_chart(fig_p, use_container_width=True)
    with c4:
        st.plotly_chart(fig_npsh, use_container_width=True)

    st.info(
        f"📍 **Požadovaný provozní bod soustavy:** "
        f"Průtok = **{Q_target_m3_h:.1f} m³/h**, "
        f"Dopravní výška = **{(Y_target_sys / g):.2f} m**"
    )

else:
    fig_main.update_layout(
        title_text="Charakteristika soustavy",
        yaxis_title="Měrná energie Y [J/kg]",
        **layout_config
    )
    st.plotly_chart(fig_main, use_container_width=True)
    st.info(
        f"📍 **Požadovaný provozní bod soustavy:** "
        f"Průtok = **{Q_target_m3_h:.1f} m³/h**, "
        f"Dopravní výška = **{(Y_target_sys / g):.2f} m**"
    )

if poly_Y_active is not None and Q_op_m3_s is not None:
    st.markdown("### 📊 Parametry pracovního bodu a posouzení kavitace")

    H_op = Y_op_jkg / g
    H_z = H_op - H_g
    Eta_op = f_Eta_active(Q_op_m3_s)
    P_op = poly_P_active(Q_op_m3_s)
    npsh_r_bod = f_NPSH_active(Q_op_m3_s)
    npsh_a_bod = 10.1 - h_saci_vyska - vypocet_ztrat_sani(Q_op_m3_s)
    t_real = Q_den_m3 / Q_op_m3_h

    rows = [
        ["Skutečný průtok (Q)", f"{Q_op_m3_h:.1f}", "m³/h"],
        ["Geodetická dopravní výška (H_g)", f"{H_g:.1f}", "m"],
        ["Ztrátová výška soustavy (H_z)", f"{H_z:.2f}", "m"],
        ["Celková dopravní výška (H)", f"{H_op:.2f}", "m"],
        ["Účinnost čerpadla (η)", f"{Eta_op:.1f}", "%"],
        ["Příkon na hřídeli (P)", f"{P_op:.1f}", "kW"],
        ["Vyžadovaná kavitační rezerva (NPSHr)", f"{npsh_r_bod:.2f}", "m"],
        ["Dostupná kavitační rezerva (NPSHa)", f"{npsh_a_bod:.2f}", "m"],
        ["Skutečný čas čerpání 7500 m³", f"{t_real:.2f}", "h/den"],
        ["Přiřazený motor", str(vybrany_motor["Nazev"]) if vybrany_motor is not None else "-", ""],
        ["Jmenovitý výkon motoru", f"{vybrany_motor['Pn_kW']:.1f}" if vybrany_motor is not None else "-", "kW"],
        ["Cena motoru", f"{vybrany_motor['Cena']:,.0f}".replace(",", " ") if vybrany_motor is not None and pd.notna(vybrany_motor["Cena"]) else "-", "Kč"],
    ]

    df_results = pd.DataFrame(rows, columns=["Veličina", "Hodnota", "Jednotka"])
    st.table(df_results)

    npsh_pozadavek = npsh_r_bod + 0.5
    if npsh_a_bod >= npsh_pozadavek:
        st.success(
            f"✅ **Kavitační podmínka splněna:** Disponibilní rezerva sání vyhovuje podmínce "
            f"$\\text{{NPSH}}_a \\ge \\text{{NPSH}}_r + 0,5$ m "
            f"({npsh_a_bod:.2f} m ≥ {npsh_pozadavek:.2f} m). Čerpadlo pracuje bezpečně."
        )
    else:
        st.error(
            f"⚠️ **Pozor, hrozí kavitace:** Podmínka "
            f"$\\text{{NPSH}}_a \\ge \\text{{NPSH}}_r + 0,5$ m není splněna "
            f"({npsh_a_bod:.2f} m < {npsh_pozadavek:.2f} m)."
        )

    with st.expander("Debug výběru motoru"):
        st.write("Počet motorů v databázi:", len(df_motory))
        st.write("Příkon čerpadla v pracovním bodě [kW]:", round(float(P_op), 2))
        st.write("Požadovaný výkon motoru s rezervou 15 % [kW]:", round(float(P_op) * 1.15, 2))
        st.write("Otáčky čerpadla [ot/min]:", rpm_pump_active)
        if not df_motory.empty:
            st.write("Maximální výkon motoru v databázi [kW]:", float(df_motory["Pn_kW"].max()))
        if vybrany_motor is not None:
            st.write("Vybraný motor:", vybrany_motor["Nazev"])
            st.write("Rozdíl otáček [ot/min]:", int(abs(vybrany_motor["Otacky"] - rpm_pump_active)))
            st.write("Výkonová rezerva [kW]:", round(float(vybrany_motor["Prebytek_kW"]), 2))
        else:
            st.write("Nebyl nalezen vhodný motor.")

    # ---------------------------------
    # EKONOMICKÁ ČÁST
    
    st.markdown("### 💰 Ekonomická bilance")

    cena_el_kwh = 8500 / 1000  # 8 500 Kč/MWh -> 8.5 Kč/kWh
    cena_litina_kg = 65  # Kč/kg
    
    hmotnosti_kg_m = {200: 35, 250: 45, 300: 58, 350: 72, 400: 88, 500: 125}
    m_sani_kg = L_s * hmotnosti_kg_m.get(int(D_s_mm), 0)
    m_vytlak_kg = L_v * hmotnosti_kg_m.get(int(D_v_mm), 0)
    
    cena_potrubi_celkem = (m_sani_kg + m_vytlak_kg) * cena_litina_kg
    naklady_investice_rok = cena_potrubi_celkem * 0.10  # 10 % z ceny jako roční odpisy

    eta_motor = 0.95
    if vybrany_motor is not None and vybrany_motor["Ucinnost"] != "-":
        try:
            eta_val = float(str(vybrany_motor["Ucinnost"]).replace(",", "."))
            eta_motor = eta_val / 100 if eta_val > 1 else eta_val
        except ValueError:
            pass

    P_elektricky_kw = float(P_op) / eta_motor
    spotreba_rok_kwh = P_elektricky_kw * t_real * 365
    naklady_energie_rok = spotreba_rok_kwh * cena_el_kwh
    
    cena_motoru_val = 0
    if vybrany_motor is not None and pd.notna(vybrany_motor.get("Cena")):
        cena_motoru_val = float(vybrany_motor["Cena"])
        naklady_investice_rok += (cena_motoru_val * 0.10)

    celkove_naklady_rok = naklady_investice_rok + naklady_energie_rok
    objem_vody_rok = Q_den_m3 * 365
    merna_cena_m3 = celkove_naklady_rok / objem_vody_rok

    c_eko1, c_eko2, c_eko3 = st.columns(3)
    c_eko1.metric("Investiční roční náklady", f"{naklady_investice_rok:,.0f} Kč".replace(",", " "))
    c_eko2.metric("Náklady na energii / rok", f"{naklady_energie_rok:,.0f} Kč".replace(",", " "))
    c_eko3.metric("Celkové roční náklady", f"{celkove_naklady_rok:,.0f} Kč".replace(",", " "))
    
    st.success(f"**Výsledná měrná cena za čerpání vody:** {merna_cena_m3:.3f} Kč / m³")
    # ------------------------


# SROVNÁVACÍ ANALÝZAA PRO INVESTORA
# -----------------------
st.markdown("---")
st.markdown("### 📈 Srovnávací analýza obou řešení pro investora")


hmotnosti_kg_m = {200: 35, 250: 45, 300: 58, 350: 72, 400: 88, 500: 125}

def spocti_variantu_pro_srovnani(Ds_mm_loc, Dv_mm_loc, poly_Y_loc, poly_P_loc, f_NPSH_loc):
    Ds_loc, Dv_loc = Ds_mm_loc / 1000.0, Dv_mm_loc / 1000.0
    
    def sys_Y_loc(q):
        if q <= 0: return H_g * g
        v_s_loc = (4 * q) / (np.pi * Ds_loc**2)
        Re_s_loc = (v_s_loc * Ds_loc) / ny
        lam_s_loc = 0.25 / (np.log10((k_m / (3.7 * Ds_loc)) + (5.74 / (Re_s_loc**0.9))))**2
        h_zs_loc = (lam_s_loc * (L_s / Ds_loc) + zeta_kos + mapa_zeta_90[Ds_mm_loc]) * (v_s_loc**2 / (2 * g))
        
        v_v_loc = (4 * q) / (np.pi * Dv_loc**2)
        Re_v_loc = (v_v_loc * Dv_loc) / ny
        lam_v_loc = 0.25 / (np.log10((k_m / (3.7 * Dv_loc)) + (5.74 / (Re_v_loc**0.9))))**2
        sz_v_loc = zeta_ventil + zeta_vytok + (pocet_90 * mapa_zeta_90[Dv_mm_loc]) + (pocet_45 * mapa_zeta_90[Dv_mm_loc] * 0.60) + (pocet_30 * mapa_zeta_90[Dv_mm_loc] * 0.45)
        h_zv_loc = (lam_v_loc * (L_v / Dv_loc) + sz_v_loc) * (v_v_loc**2 / (2 * g))
        return (H_g + h_zs_loc + h_zv_loc) * g

    # Nalezení prac.. bodu
    Q_op_loc = fsolve(lambda q: sys_Y_loc(q) - poly_Y_loc(q), Q_target_m3_s)[0]
    Y_op_loc = sys_Y_loc(Q_op_loc)
    P_op_loc = poly_P_loc(Q_op_loc)
    t_real_loc = Q_den_m3 / (Q_op_loc * 3600)
    
    # Kavitace
    v_s_loc = (4 * Q_op_loc) / (np.pi * Ds_loc**2)
    Re_s_loc = (v_s_loc * Ds_loc) / ny
    lam_s_loc = 0.25 / (np.log10((k_m / (3.7 * Ds_loc)) + (5.74 / (Re_s_loc**0.9))))**2
    ztrata_sani_loc = (lam_s_loc * (L_s / Ds_loc) + zeta_kos + mapa_zeta_90[Ds_mm_loc]) * (v_s_loc**2 / (2 * g))
    npsha_loc = 10.1 - h_saci_vyska - ztrata_sani_loc
    
    # Ekonomika
    inv_potrubi = (L_s * hmotnosti_kg_m.get(Ds_mm_loc, 0) + L_v * hmotnosti_kg_m.get(Dv_mm_loc, 0)) * 65
    ene_rok = (P_op_loc / 0.95) * t_real_loc * 365 * 8.5
    total_rok = (inv_potrubi * 0.10) + ene_rok 
    merna = total_rok / (Q_den_m3 * 365)
    
    return {"Q": Q_op_loc*3600, "H": Y_op_loc/g, "P": P_op_loc, "Total": total_rok, "Merna": merna, "NPSHa": npsha_loc, "NPSHr": f_NPSH_loc(Q_op_loc)}


r1 = spocti_variantu_pro_srovnani(350, 300, poly_Y_pump_R1, poly_P_R1, f_NPSH_R1)
r2 = spocti_variantu_pro_srovnani(400, 350, poly_Y_pump_R2, poly_P_R2, f_NPSH_R2)

df_komparace = pd.DataFrame({
    "Hodnocený parametr": ["Dimenze potrubí (Sání / Výtlak)", "Pracovní průtok", "Dopravní výška", "Příkon čerpadla", "Roční náklady (bez ceny motoru)", "Měrná cena čerpání", "Kavitační rezerva (NPSHa - NPSHr)"],
    "Řešení 1 (Užší)": [f"DN 350 / 300", f"{r1['Q']:.1f} m³/h", f"{r1['H']:.1f} m", f"{r1['P']:.1f} kW", f"{r1['Total']:,.0f} Kč".replace(","," "), f"{r1['Merna']:.3f} Kč/m³", f"{r1['NPSHa']-r1['NPSHr']:.2f} m"],
    "Řešení 2 (Širší)": [f"DN 400 / 350", f"{r2['Q']:.1f} m³/h", f"{r2['H']:.1f} m", f"{r2['P']:.1f} kW", f"{r2['Total']:,.0f} Kč".replace(","," "), f"{r2['Merna']:.3f} Kč/m³", f"{r2['NPSHa']-r2['NPSHr']:.2f} m"]
})

st.table(df_komparace)

col_vitez, col_rizika = st.columns(2)
with col_vitez:
    uspora = r1['Total'] - r2['Total']
    st.success(f"💰 **Ekonomické doporučení: Volba Řešení 2** (Úspora **{uspora:,.0f} Kč** ročně)".replace(","," "))
    st.write("**Proč se vyplatí investovat do širšího potrubí?**")
    st.write("Tlakové ztráty v potrubí klesají s pátou mocninou průměru: vlivem rychlosti - z rovnice kontinuity je ve jmenovateli D na čtvrtou + vlivem délkového třecího součinitele - D na prvou ve jmenovateli. Čerpadlo tak u Řešení 2 nemusí překonávat takový hydraulický odpor sítě, díky čemuž spotřebuje o desítky kW méně elektřiny. Tato provozní úspora na energiích zaplatí zvýšenou počáteční investici do větších trubek už během prvního roku provozu.")

with col_rizika:
    st.warning("⚠️ **Možná rizika a negativa (Trade-offs):**")
    st.markdown("""
    * **Manipulace a montáž:** Potrubí v Řešení 2 je těžší, což si vyžádá nasazení těžší techniky a bude znamenat složitější dopravu a montáž a tak prodraží prvotní instalaci.
    * **Vyšší počáteční výdaj:** Jednorázový výdaj při samotné stavbě systému bude vyšší.
    * **Riziko sedimentace:** Ve větším potrubí teče voda pomaleji. Pokud by voda obsahovala hrubší kaly, může hrozit usazování (při zadaných průměrech jsme ale s rezervou v bezpečné zóně nad 1 m/s).
    """)


st.markdown("---")
st.markdown("### 💡 Odůvodnění návrhu")
if st.session_state.aktivni_reseni == "R1":
    st.write(
        "Pro **Řešení 1** jsme zvolili průměr sání DN 350 a výtlaku DN 300. "
        "Vycházeli jsme z doporučených rychlostí proudění. Na sání nám vyšla rychlost necelých 1,4 m/s, "
        "což je v normě a vyhneme se tak problémům s kavitací. Na výtlaku máme rychlost kolem 1,8 m/s. "
        "Užší trubky by znamenaly moc velký odpor, širší by zase byly moc drahé. "
        "Takhle ušetříme za materiál na 2,5 km dlouhé trase a čerpadlo ten odpor v pohodě zvládne protlačit."
    )
elif st.session_state.aktivni_reseni == "R2":
    st.write(
        "Pro **Řešení 2** jsme průměry zvětšili na DN 400 pro sání a DN 350 pro výtlak. "
        "Tím se významně sníží hydraulické ztráty v potrubí (křivka soustavy bude plošší) "
        "a teoreticky budeme moci použít slabší a energeticky úspornější čerpadlo. "
        "Rychlosti proudění klesnou, což ještě více zlepší kavitaci na sání, "
        "ale zároveň vzrostou počáteční investiční náklady na potrubí."
    )
else:
    st.write("Zatím nebylo vybráno žádné návrhové řešení. Zvolte řešení v levém panelu.")

with st.expander("Zobrazit databázi motorů"):
    if df_motory.empty:
        st.warning("Soubor motory.xlsx nebyl nalezen nebo je prázdný. Zkontrolujte nahoře chybové hlášky.")
    else:
        st.dataframe(df_motory, use_container_width=True)

st.markdown("---")
st.markdown("### Zdroje")
st.markdown("""
<div style='font-size: 0.85em; color: gray;'>
<b>[1]</b> IDELCHIK, I. E. <i>Handbook of hydraulic resistance</i>. 3rd ed. 1994.<br>
<b>[2]</b> TKACHENKO, T. a V. MILEIKOVSKYI. <i>Precise Explicit Approximations of the Colebrook-White Equation</i>. 2020.<br>
<b>[3]</b> Ústav zemědělské, potravinářské a environmentální techniky AF MENDELU. <i>Proudění tekutin, ztráty v potrubí</i> [online].<br>
<b>[4]</b> KSB EasySelect [online katalog čerpadel]. Dostupné z: https://www.ksb.com/easyselect/app/?n=ext_vst<br>
<b>[5]</b> SWAMEE, Prabhata K. a Akalank K. JAIN. <i>Explicit equations for pipe-flow problems</i>. <i>Journal of the Hydraulics Division</i>, 1976.<br>
<b>[6]</b> SEVA-TEC. <i>Cast iron electric motors – efficiency class IE3</i> [online]. Dostupné z: https://www.seva-tec.de/en/collections/cast-iron-electric-motors?filter.p.m.custom.effizienzklasse=IE+3&page=7&sort_by=price-ascending<br>
<b>[7]</b> Levné elektromotory.cz. <i>Elektromotory 134–1400 ot/min</i> [online]. Dostupné z: https://www.levne-elektromotory.cz/134-1400-otmin?order=product.price.desc<br>
<b>[8]</b> Interní tabulka motorů <i>motory.xlsx</i> [příloha projektu]; zdroj vyšetřovaných parametrů motorů: výkon, otáčky, napětí, cena, výrobce a třída účinnosti.<br>
</div>
""", unsafe_allow_html=True)
