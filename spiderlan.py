"""
SpiderLan
Satellite RF Security & Navigation Integrity Platform
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import json, math, random
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import folium
from streamlit_folium import st_folium
from datetime import datetime, timezone, timedelta

from core.link_budget import (
    LinkBudgetCalculator, TransmitterParams, ReceiverParams,
    AntiJamAnalyzer, EavesdropGeometry, Waveform, FECCode
)
from core.gnss_integrity import RAIMMonitor, SatObs, NavSolution, Constellation, IntegrityStatus
from core.catalog import (
    CELESTRAK_GROUPS, fetch_tle_group, fetch_custom_tle,
    sat_position_now, ground_track, contact_windows, elevation_azimuth
)
from core.sdr_interface import SDRInterface, SDRConfig, SDRBackend, RFThreatClassifier
from offensive.attack_surface import AttackSurfaceMapper, VulnSeverity
from data.presets import MIL_WAVEFORMS, SATELLITE_SYSTEM_PRESETS, DOCUMENTED_INCIDENTS
from export.reports import export_full_report, export_stix_bundle, export_stanag_4586

st.set_page_config(page_title="SpiderLan", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
html,body,*{font-family:'Share Tech Mono','Courier New',monospace!important}
.stApp{background:#050905;color:#9ab89a}
section[data-testid="stSidebar"]{background:#060b06;border-right:1px solid #172917}
.stTabs [data-baseweb="tab-list"]{background:#070d07;border-bottom:1px solid #172917;gap:0}
.stTabs [data-baseweb="tab"]{background:#070d07;color:#3d6b3d;border:1px solid #172917;
  border-bottom:none;border-radius:0;padding:8px 18px;font-size:11px;letter-spacing:1px}
.stTabs [aria-selected="true"]{background:#0b140b!important;color:#2eff2e!important;border-top:2px solid #2eff2e!important}
.stButton>button{background:#0b140b;color:#2eff2e;border:1px solid #224422;
  border-radius:0;padding:9px 0;font-size:11px;letter-spacing:2px;width:100%}
.stButton>button:hover{background:#142814}
.stSelectbox label,.stSlider label,.stNumberInput label,.stTextInput label,
.stCheckbox label,.stTextArea label,.stMultiSelect label{color:#3d6b3d!important;font-size:11px!important;letter-spacing:1px}
div[data-testid="stMetric"]{background:#080e08;border:1px solid #172917;padding:10px 14px}
div[data-testid="stMetric"] label{color:#3d6b3d!important;font-size:10px!important;letter-spacing:2px}
div[data-testid="stMetric"] div{color:#2eff2e!important;font-size:20px!important}
.hdr{border-bottom:1px solid #172917;padding-bottom:12px;margin-bottom:18px;
  display:flex;justify-content:space-between;align-items:flex-end}
.hdr-name{color:#2eff2e;font-size:21px;letter-spacing:7px}
.hdr-sub{color:#3d6b3d;font-size:10px;letter-spacing:3px;margin-top:3px}
.hdr-ts{color:#1f4a1f;font-size:11px}
.kpibox{background:#080e08;border:1px solid #172917;padding:12px 16px}
.kpilbl{color:#2d5a2d;font-size:9px;letter-spacing:3px;text-transform:uppercase}
.kpival{font-size:21px;font-weight:700;margin-top:4px}
.kpival.g{color:#2eff2e}.kpival.a{color:#ffaa00}.kpival.r{color:#ff3030}
.row{padding:8px 12px;border-left:3px solid #172917;margin:3px 0;background:#070d07;font-size:11px}
.row.r{border-left-color:#992020;background:#0e0707}
.row.a{border-left-color:#997700;background:#0e0c07}
.actbox{background:#070d07;border:1px solid #172917;padding:10px 14px;font-size:11px;color:#4a8a4a;margin-top:8px}
.sh{color:#3d6b3d;font-size:10px;letter-spacing:4px;text-transform:uppercase;
  border-bottom:1px solid #172917;padding-bottom:6px;margin:18px 0 12px}
.vbox{background:#070d07;border:1px solid #172917;padding:12px 16px;margin:6px 0}
.vbox.c{border-left:3px solid #ff3030}.vbox.h{border-left:3px solid #ff7700}
.vbox.m{border-left:3px solid #ffaa00}.vbox.l{border-left:3px solid #2eff2e}
.vname{color:#9ab89a;font-size:13px;font-weight:700}
.vdesc{color:#5a8a5a;font-size:11px;margin-top:4px}
.vmit{color:#3d6b3d;font-size:11px;margin-top:4px}
.incident-box{background:#070d07;border:1px solid #172917;border-left:3px solid #ff3030;
  padding:14px 16px;margin:8px 0;font-size:11px}
.sdr-live{background:#070d07;border:1px solid #2eff2e;padding:8px 14px;font-size:11px;color:#2eff2e}
#MainMenu,footer,header{visibility:hidden}.stDeployButton{display:none}
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
def ss(k, v):
    if k not in st.session_state: st.session_state[k]=v

ss("satellites",  [])
ss("tle_loaded",  False)
ss("tle_group",   "Starlink")
ss("gnss_history",[])
ss("last_gnss",   None)
ss("raim",        RAIMMonitor(40.0,50.0))
ss("lb_result",   None)
ss("aj_result",   None)
ss("vulns",       [])
ss("surf_score",  {})
ss("sdr",         None)
ss("rf_history",  [])
ss("last_rf",     None)
ss("assessment",  {})

def dfig(h=380):
    return dict(paper_bgcolor="#050905",plot_bgcolor="#050905",
        font=dict(color="#9ab89a",family="Share Tech Mono,Courier New",size=11),
        xaxis=dict(gridcolor="#0d170d",linecolor="#172917",zerolinecolor="#172917"),
        yaxis=dict(gridcolor="#0d170d",linecolor="#172917",zerolinecolor="#172917"),
        margin=dict(l=50,r=20,t=30,b=40),height=h)

def kpi(col,label,val,cls="g"):
    col.markdown(f'<div class="kpibox"><div class="kpilbl">{label}</div>'
                 f'<div class="kpival {cls}">{val}</div></div>',unsafe_allow_html=True)

def sh(t): st.markdown(f'<div class="sh">{t}</div>',unsafe_allow_html=True)

def scls(s): return {"CRITICAL":"c","HIGH":"h","MEDIUM":"m","LOW":"l"}.get(s,"l")
def scol(s): return {"CRITICAL":"#ff3030","HIGH":"#ff7700","MEDIUM":"#ffaa00","LOW":"#2eff2e"}.get(s,"#fff")
def lcls(s): return "r" if s in ("FAULT","WARNING","OPEN","CRITICAL") else ("a" if s in ("CAUTION","MARGINAL","HIGH") else "g")

# ── Header ────────────────────────────────────────────────────────────────────
ts_now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
lb=st.session_state.lb_result; lg=st.session_state.last_gnss
sv=st.session_state.surf_score; lr=st.session_state.last_rf

st.markdown(f"""
<div class="hdr">
  <div><div class="hdr-name">SPIDERLAN</div>
  <div class="hdr-sub">SATELLITE RF SECURITY & NAVIGATION INTEGRITY PLATFORM</div></div>
  <div class="hdr-ts">{ts_now} UTC</div>
</div>""",unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("CONFIGURATION")
    st.markdown("---")
    analyst   = st.text_input("Analyst ID","OPS-001")
    operation = st.selectbox("Operation",["ASSESSMENT","MONITORING","FORENSICS"])
    st.markdown("---")
    st.markdown("SATELLITE FEED")
    grp = st.selectbox("Constellation Group", list(CELESTRAK_GROUPS.keys()))
    lim = st.slider("Max Satellites", 5, 100, 30)
    if st.button("LOAD TLEs"):
        with st.spinner(f"Fetching {grp}..."):
            st.session_state.satellites = fetch_tle_group(grp, lim)
            st.session_state.tle_loaded = True
            st.session_state.tle_group  = grp
        st.success(f"{len(st.session_state.satellites)} satellites loaded")
    custom_tle = st.text_area("Paste Custom TLEs (3-line format)", height=80)
    if st.button("LOAD CUSTOM TLEs") and custom_tle:
        sats = fetch_custom_tle(custom_tle)
        st.session_state.satellites = sats
        st.session_state.tle_loaded = True
        st.success(f"{len(sats)} custom satellites loaded")
    st.markdown("---")
    gs_lat = st.number_input("Ground Station Lat", value=30.06, format="%.4f")
    gs_lon = st.number_input("Ground Station Lon", value=31.24, format="%.4f")
    el_mask= st.slider("Elevation Mask (deg)", 5, 30, 10)
    st.markdown("---")
    st.markdown("SDR HARDWARE")
    sdr_backend = st.selectbox("SDR Device",["Simulated","RTL-SDR","HackRF","USRP","SoapySDR"])
    sdr_freq    = st.number_input("Center Freq (MHz)", 100.0, 6000.0, 1575.42)
    sdr_gain    = st.number_input("RF Gain (dB)", 0.0, 60.0, 30.0)
    if st.button("CONNECT SDR"):
        backend_map = {"RTL-SDR":SDRBackend.RTLSDR,"HackRF":SDRBackend.HACKRF,
                       "USRP":SDRBackend.USRP,"SoapySDR":SDRBackend.SOAPYSDR,
                       "Simulated":SDRBackend.SIMULATED}
        cfg = SDRConfig(center_freq_hz=sdr_freq*1e6, gain_db=sdr_gain)
        st.session_state.sdr = SDRInterface(cfg, backend_map[sdr_backend])
        b = st.session_state.sdr.backend.value
        st.success(f"Connected: {b}")

# ── KPI Bar ───────────────────────────────────────────────────────────────────
gnss_s = lg["status"]             if lg else "---"
lb_s   = lb["status"]             if lb else "---"
margin = f'{lb["link_margin_db"]}dB' if lb else "---"
risk   = sv.get("risk_level","---")
rf_lvl = lr["threat_level"]       if lr else "---"

k1,k2,k3,k4,k5 = st.columns(5)
kpi(k1,"GNSS",       gnss_s, lcls(gnss_s))
kpi(k2,"LINK",       lb_s,   lcls(lb_s))
kpi(k3,"MARGIN",     margin, lcls(lb_s))
kpi(k4,"ATK RISK",   risk,   lcls(risk))
kpi(k5,"RF THREAT",  rf_lvl, lcls(rf_lvl))
st.markdown("<br>",unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
t1,t2,t3,t4,t5,t6,t7 = st.tabs([
    "TACTICAL MAP","LINK BUDGET","GNSS INTEGRITY",
    "RF MONITOR","ATTACK SURFACE","INCIDENTS","EXPORT"
])

# ══════════════════════════════════════════════════════
# TAB 1 — TACTICAL MAP
# ══════════════════════════════════════════════════════
with t1:
    sh("SATELLITE TACTICAL MAP — " + st.session_state.tle_group)
    mc1,mc2 = st.columns([3,1])
    with mc2:
        if st.session_state.tle_loaded:
            selected   = st.multiselect("Select",
                [s[0] for s in st.session_state.satellites],
                default=[s[0] for s in st.session_state.satellites[:6]])
            show_track = st.checkbox("Ground Tracks",True)
            show_cov   = st.checkbox("Coverage Circles",False)
            show_wins  = st.checkbox("Contact Windows",False)
        else:
            st.info("Load a satellite group from the sidebar.")
            selected=[]
    with mc1:
        m=folium.Map(location=[20,10],zoom_start=2,
            tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",attr="CartoDB")
        folium.CircleMarker([gs_lat,gs_lon],radius=7,color="#2eff2e",
            fill=True,fill_color="#2eff2e",fill_opacity=1.0,
            tooltip=f"Ground Station  {gs_lat:.4f}N  {gs_lon:.4f}E").add_to(m)
        rows=[]
        for name,tle1,tle2 in st.session_state.satellites:
            if name not in selected: continue
            try:
                pos=sat_position_now(name,tle1,tle2)
                lat,lon,alt=pos["lat"],pos["lon"],pos["alt_km"]
                if show_track:
                    track=ground_track(name,tle1,tle2)
                    seg,segs=[],[]
                    for i,(la,lo) in enumerate(track):
                        if i>0 and abs(lo-track[i-1][1])>180: segs.append(seg);seg=[]
                        seg.append([la,lo])
                    segs.append(seg)
                    for s in segs:
                        if len(s)>1: folium.PolyLine(s,color="#1a4a1a",weight=1,opacity=0.45).add_to(m)
                if show_cov:
                    R=6371; cov=math.sqrt(alt*(2*R+alt))*0.8
                    folium.Circle([lat,lon],radius=cov*1000,color="#0d2a0d",
                        fill=True,fill_color="#0d1a0d",fill_opacity=0.06,weight=0.5).add_to(m)
                folium.CircleMarker([lat,lon],radius=4,color="#2eff2e",
                    fill=True,fill_color="#2eff2e",fill_opacity=0.9,
                    tooltip=f"{name}  Alt:{alt:.0f}km  {lat:.2f}N {lon:.2f}E").add_to(m)
                ea=elevation_azimuth(name,tle1,tle2,gs_lat,gs_lon)
                rows.append({"Satellite":name,"Lat":lat,"Lon":lon,"Alt(km)":alt,
                             "El(deg)":ea["elevation_deg"],"Az(deg)":ea["azimuth_deg"],
                             "Range(km)":ea["range_km"],"Visible":ea["visible"]})
            except Exception:
                rows.append({"Satellite":name,"Lat":"ERR","Lon":"ERR","Alt(km)":"ERR",
                             "El(deg)":"ERR","Az(deg)":"ERR","Range(km)":"ERR","Visible":False})
        st_folium(m,height=490,use_container_width=True)
    if rows:
        sh("CONSTELLATION TABLE")
        df=pd.DataFrame(rows)
        st.dataframe(df,use_container_width=True,hide_index=True)
    if show_wins and selected and st.session_state.tle_loaded:
        sh(f"CONTACT WINDOWS — NEXT 24h  |  GS: {gs_lat:.2f}N {gs_lon:.2f}E  |  EL MASK: {el_mask}deg")
        all_w=[]
        for name,tle1,tle2 in st.session_state.satellites:
            if name not in selected[:5]: continue
            for w in contact_windows(name,tle1,tle2,gs_lat,gs_lon,el_mask,24):
                w["Satellite"]=name; all_w.append(w)
        if all_w:
            df_w=pd.DataFrame(all_w)[["Satellite","aos","los","duration_s","max_el_deg"]]
            df_w.columns=["Satellite","AOS (UTC)","LOS (UTC)","Duration(s)","Max El(deg)"]
            st.dataframe(df_w,use_container_width=True,hide_index=True)

# ══════════════════════════════════════════════════════
# TAB 2 — LINK BUDGET
# ══════════════════════════════════════════════════════
with t2:
    sh("LINK BUDGET CALCULATOR")
    preset_name = st.selectbox("System Preset",
        ["Custom"] + list(SATELLITE_SYSTEM_PRESETS.keys()))
    preset = SATELLITE_SYSTEM_PRESETS.get(preset_name, {})
    wf_preset = st.selectbox("Waveform Preset (MIL-STD)",
        ["Custom"] + list(MIL_WAVEFORMS.keys()))
    if wf_preset != "Custom":
        wp=MIL_WAVEFORMS[wf_preset]
        st.markdown(f'<div class="actbox">{wp["description"]}<br>'
                    f'Standard: {wp["standard"]}</div>',unsafe_allow_html=True)

    lc1,lc2=st.columns(2)
    with lc1:
        st.markdown("**TRANSMITTER**")
        tx_p  = st.number_input("Tx Power (W)",   1.0,10000.0, preset.get("tx_power_w",100.0),  step=10.0)
        tx_g  = st.number_input("Tx Gain (dBi)",  0.0,70.0,    preset.get("tx_gain_dbi",43.0))
        tx_ll = st.number_input("Tx Line Loss",    0.0,5.0,     preset.get("tx_loss_db",1.0))
        tx_pl = st.number_input("Tx Pointing Loss",0.0,3.0,     0.3)
        st.markdown("**PATH**")
        f_ghz = st.number_input("Frequency (GHz)",1.0,50.0,    preset.get("freq_ghz",14.0))
        d_km  = st.number_input("Slant Range (km)",300.0,42000.0,preset.get("distance_km",35786.0))
        el_d  = st.number_input("Elevation (deg)", 5.0,90.0,   preset.get("elevation_deg",40.0))
        rain  = st.number_input("Rain Rate (mm/hr)",0.0,150.0, preset.get("rain_rate_mm_hr",20.0),
                                help="20=moderate, 50=heavy, 100=tropical")
    with lc2:
        st.markdown("**RECEIVER**")
        rx_g  = st.number_input("Rx Gain (dBi)",   0.0,70.0,   preset.get("rx_gain_dbi",50.0))
        rx_t  = st.number_input("Noise Temp (K)",   20.0,1000.0,preset.get("rx_noise_temp_k",150.0))
        rx_ll = st.number_input("Rx Line Loss",     0.0,3.0,    0.5)
        rx_pl = st.number_input("Rx Pointing Loss", 0.0,3.0,    0.3)
        st.markdown("**WAVEFORM & FEC**")
        if wf_preset!="Custom":
            wp=MIL_WAVEFORMS[wf_preset]
            wf_name  = {"BPSK":"BPSK","QPSK":"QPSK","8PSK":"8PSK","16APSK":"16APSK","32APSK":"32APSK"}.get(wp["waveform"],"QPSK")
            fec_name = {"NONE":"None","CONV_1_2":"Conv 1/2","LDPC_1_2":"LDPC 1/2",
                        "LDPC_3_4":"LDPC 3/4","TURBO_1_2":"Turbo 1/2","TURBO_3_4":"Turbo 3/4"}.get(wp["fec"],"None")
            dr       = wp["data_rate_kbps"]
        else:
            wf_name  = st.selectbox("Waveform",  [w.label()  for w in Waveform])
            fec_name = st.selectbox("FEC",        [f.label()  for f in FECCode])
            dr       = st.number_input("Data Rate (kbps)",1.0,1e6,1000.0)
        if wf_preset!="Custom":
            st.markdown(f"Waveform: `{wf_name}`  FEC: `{fec_name}`  Rate: `{dr} kbps`")

    if st.button("COMPUTE LINK BUDGET"):
        wf  = next(w for w in Waveform  if w.label()==wf_name)
        fec = next(f for f in FECCode   if f.label()==fec_name)
        tx  = TransmitterParams(tx_p,tx_g,tx_ll,tx_pl)
        rx  = ReceiverParams(rx_g,rx_t,rx_ll,rx_pl)
        res = LinkBudgetCalculator(tx,rx,f_ghz,d_km,el_d,dr,wf,fec,rain).compute()
        st.session_state.lb_result=res
        st.session_state.assessment["link_budget"]=res
        st.rerun()

    if lb:
        sh("RESULTS")
        r1,r2,r3,r4=st.columns(4)
        mc=lcls(lb["status"])
        kpi(r1,"LINK STATUS",  lb["status"],          mc)
        kpi(r2,"MARGIN",       f'{lb["link_margin_db"]}dB', mc)
        kpi(r3,"C/N0",         f'{lb["cn0_dbhz"]}dBHz',"g")
        kpi(r4,"Eb/N0",        f'{lb["eb_n0_db"]}dB',  "g")
        st.markdown("<br>",unsafe_allow_html=True)
        labels=["EIRP","FSPL","Rain Loss","Atm Loss","G/T","C/N0"]
        values=[lb["eirp_dbw"],-lb["fspl_db"],-lb["rain_loss_db"],
                -lb["atm_loss_db"],lb["g_over_t_db"],lb["cn0_dbhz"]]
        fig=go.Figure(go.Bar(x=labels,y=values,
            marker_color=["#2eff2e" if v>0 else "#ff3030" for v in values],
            text=[f"{v:+.1f}" for v in values],textposition="outside",
            textfont=dict(size=10,color="#9ab89a")))
        fig.update_layout(**dfig(300),showlegend=False,yaxis_title="dB / dBHz / dBW")
        st.plotly_chart(fig,use_container_width=True)
        st.dataframe(pd.DataFrame([{"Parameter":k.replace("_"," ").upper(),"Value":v}
                     for k,v in lb.items()]),use_container_width=True,hide_index=True)

    sh("ANTI-JAM MARGIN ANALYZER")
    aj1,aj2=st.columns(2)
    with aj1:
        spread  = st.selectbox("Spread Spectrum",["DSSS","FHSS","HYBRID","NONE"])
        bw_mhz  = st.number_input("Signal BW (MHz)",0.1,500.0,
                    MIL_WAVEFORMS[wf_preset]["bandwidth_mhz"] if wf_preset!="Custom" else 20.0)
        aj_dr   = st.number_input("Data Rate (kbps)",1.0,100000.0,100.0,key="aj_dr")
        rx_nf   = st.number_input("Rx Noise Figure (dB)",0.0,20.0,3.0)
        req_snr = st.number_input("Required SNR (dB)",-10.0,30.0,6.0)
    with aj2:
        j_eirp  = st.number_input("Jammer EIRP (dBW)",-10.0,80.0,30.0)
        s_eirp  = st.number_input("Signal EIRP (dBW)",-10.0,80.0,50.0)
        pl_aj   = st.number_input("Path Loss (dB)",100.0,250.0,205.0)
    if st.button("COMPUTE ANTI-JAM"):
        aj=AntiJamAnalyzer(spread,bw_mhz,aj_dr,rx_nf,req_snr)
        res=aj.compute(j_eirp,s_eirp,pl_aj)
        st.session_state.aj_result=res
        st.session_state.assessment["anti_jam"]=res
        st.rerun()
    if st.session_state.aj_result:
        aj=st.session_state.aj_result; e=aj["jamming_effectiveness"]
        ec=lcls(e)
        a1,a2,a3,a4=st.columns(4)
        kpi(a1,"EFFECTIVENESS",   e,                         ec)
        kpi(a2,"PROC GAIN",       f'{aj["processing_gain_db"]}dB',"g")
        kpi(a3,"J/S RATIO",       f'{aj["js_ratio_db"]}dB',  "r" if aj["js_ratio_db"]>0 else "g")
        kpi(a4,"JAM MARGIN",      f'{aj["jam_margin_db"]}dB',"g" if aj["jam_margin_db"]>0 else "r")

# ══════════════════════════════════════════════════════
# TAB 3 — GNSS INTEGRITY
# ══════════════════════════════════════════════════════
with t3:
    sh("GNSS INTEGRITY MONITOR — RAIM / FDE / STARLINK CROSS-CHECK")
    gc1,gc2=st.columns([1,2])
    with gc1:
        n_sats  = st.slider("Visible Satellites",4,14,8)
        gscen   = st.selectbox("Fault Scenario",["nominal","faulty_sv","spoofing","poor_geometry"])
        use_stk = st.checkbox("Starlink Cross-Check",True)
        hal_i   = st.number_input("HAL (m)",10.0,500.0,40.0)
        val_i   = st.number_input("VAL (m)",10.0,500.0,50.0)
        run_g   = st.button("RUN RAIM CHECK")
        if lg:
            s=lg["status"]
            sc={"FAULT":"#ff3030","WARNING":"#ff7700","CAUTION":"#ffaa00","OK":"#2eff2e"}.get(s,"#fff")
            st.markdown(f'<span style="color:{sc};font-size:18px;font-weight:700">{s}</span>',unsafe_allow_html=True)
            st.markdown(f"HPL: `{lg['hpl_m']}m` / HAL: `{lg['hal_m']}m`")
            st.markdown(f"VPL: `{lg['vpl_m']}m` / VAL: `{lg['val_m']}m`")
            st.markdown(f"Satellites: `{lg['n_sats']}` | Chi2: `{lg['chi2_statistic']}`")
            if lg.get("fde_triggered"):
                st.error(f"FDE ACTIVE — Excluded PRN: {lg['excluded_prns']}")
            sc2=lg.get("starlink_check",{})
            if sc2.get("available"):
                d=sc2.get("delta_m",0); ok=sc2.get("consistent")
                st.markdown(f"Starlink delta: `{d:.1f}m` — {'CONSISTENT' if ok else 'INCONSISTENT'}")
    with gc2:
        gh=st.session_state.gnss_history
        if gh:
            df_g=pd.DataFrame(gh[-50:])
            fig_g=make_subplots(rows=2,cols=1,shared_xaxes=True,
                subplot_titles=["PROTECTION LEVELS (m)","STARLINK CROSS-CHECK DELTA (m)"],vertical_spacing=0.1)
            fig_g.add_trace(go.Scatter(y=df_g["hpl_m"],name="HPL",line=dict(color="#2eff2e",width=1.5)),row=1,col=1)
            fig_g.add_trace(go.Scatter(y=df_g["vpl_m"],name="VPL",line=dict(color="#ffaa00",width=1.5)),row=1,col=1)
            fig_g.add_hline(y=hal_i,line_dash="dash",line_color="#ff3030",row=1,col=1)
            deltas=[r.get("starlink_check",{}).get("delta_m",0) for r in gh[-50:]]
            fig_g.add_trace(go.Scatter(y=deltas,name="Delta",line=dict(color="#4a9aff",width=1.5),
                fill="tozeroy",fillcolor="rgba(74,154,255,0.04)"),row=2,col=1)
            fig_g.add_hline(y=50,line_dash="dash",line_color="#ffaa00",row=2,col=1)
            fig_g.update_layout(**dfig(380),legend=dict(bgcolor="#050905",font=dict(color="#9ab89a")))
            fig_g.update_annotations(font=dict(color="#3d6b3d",size=10))
            st.plotly_chart(fig_g,use_container_width=True)
        else:
            st.info("Run RAIM check to display integrity telemetry.")
    if gh:
        sh("GNSS SKY PLOT")
        n_sv=gh[-1].get("n_sats",8); excl=gh[-1].get("excluded_prns",[])
        els=[random.uniform(10,85) for _ in range(n_sv)]
        azs=[random.uniform(0,360) for _ in range(n_sv)]
        prns=[f"G{i+1:02d}" for i in range(n_sv)]
        r_v=[1-e/90 for e in els]
        cols=["#ff3030" if (i+1) in excl else "#2eff2e" for i in range(n_sv)]
        fig_s=go.Figure(go.Scatterpolar(r=r_v,theta=azs,mode="markers+text",
            marker=dict(size=14,color=cols,line=dict(color="#050905",width=1)),
            text=prns,textfont=dict(size=8,color="#050905"),textposition="middle center"))
        fig_s.update_layout(**dfig(340),
            polar=dict(bgcolor="#050905",
                radialaxis=dict(tickvals=[0,.33,.67,1],ticktext=["90","60","30","0"],
                    gridcolor="#0d170d",linecolor="#172917",tickfont=dict(color="#3d6b3d",size=9)),
                angularaxis=dict(direction="clockwise",gridcolor="#0d170d",linecolor="#172917",
                    tickfont=dict(color="#3d6b3d",size=9),
                    tickmode="array",tickvals=[0,90,180,270],ticktext=["N","E","S","W"])))
        st.plotly_chart(fig_s,use_container_width=True)
    if run_g:
        obs=[]
        for i in range(n_sats):
            el=random.uniform(10,85); res=0.0
            if gscen=="faulty_sv" and i==0: res=random.uniform(15,30)
            elif gscen=="spoofing":          res=random.uniform(5,12)
            elif gscen=="poor_geometry":     el=random.uniform(5,20)
            obs.append(SatObs(prn=i+1,constellation=Constellation.GPS,
                elevation_deg=el,azimuth_deg=random.uniform(0,360),
                pseudorange_m=20_200_000+random.uniform(-1000,1000),
                cn0_db=random.uniform(35,50),residual_m=res))
        hdop=1.2 if gscen=="nominal" else 2.8; vdop=2.0 if gscen=="nominal" else 4.5
        sol=NavSolution(timestamp=datetime.now(timezone.utc).isoformat(),
            lat_deg=gs_lat,lon_deg=gs_lon,alt_m=50.0,hdop=hdop,vdop=vdop,
            hal_m=hal_i,val_m=val_i,n_sats=n_sats)
        stk={"lat":gs_lat+(0.0005 if gscen=="spoofing" else random.uniform(-0.0001,0.0001)),
             "lon":gs_lon+random.uniform(-0.0001,0.0001)} if use_stk else None
        rec=RAIMMonitor(hal_i,val_i).run(obs,sol,stk)
        rec["n_sats"]=n_sats
        st.session_state.gnss_history.append(rec)
        st.session_state.last_gnss=rec
        st.session_state.assessment["gnss_integrity"]=rec
        st.rerun()

# ══════════════════════════════════════════════════════
# TAB 4 — RF MONITOR (SDR)
# ══════════════════════════════════════════════════════
with t4:
    sh("RF SIGNAL MONITOR — SDR INTERFACE")
    sdr=st.session_state.sdr
    if sdr:
        st.markdown(f'<div class="sdr-live">CONNECTED: {sdr.backend.value} | '
                    f'CENTER: {sdr.config.center_freq_hz/1e6:.3f} MHz | '
                    f'SR: {sdr.config.sample_rate_hz/1e6:.1f} MSPS</div>',unsafe_allow_html=True)
    else:
        st.info("Connect an SDR device from the sidebar. Simulated mode available without hardware.")

    rc1,rc2=st.columns([1,2])
    with rc1:
        scenario=st.selectbox("Scenario",["nominal","jamming","spoofing","multipath","weak_signal"])
        n_s=st.slider("Burst Captures",1,20,5)
        exp_freq=st.number_input("Expected Peak Freq (MHz)",100.0,6000.0,1575.42)
        exp_dop =st.number_input("Expected Doppler (Hz)",-5000.0,5000.0,0.0)
        run_rf  =st.button("CAPTURE & CLASSIFY")
        if lr:
            lvl=lr["threat_level"]
            lc2_={"RED":"#ff3030","AMBER":"#ffaa00","GREEN":"#2eff2e"}.get(lvl,"#fff")
            st.markdown(f'<span style="color:{lc2_};font-size:18px;font-weight:700">{lvl}</span>',unsafe_allow_html=True)
            st.markdown(f"Type: `{lr['threat_type']}` | Conf: `{lr['confidence_pct']}%`")
            st.markdown(f"J/S: `{lr['js_ratio_db']}dB` | C/N0 Drop: `{lr['cn0_drop_db']}dB`")
            st.markdown(f"Backend: `{lr['backend']}`")
    with rc2:
        rh=st.session_state.rf_history
        if rh:
            df_r=pd.DataFrame(rh[-50:])
            fig_r=make_subplots(rows=3,cols=1,shared_xaxes=True,
                subplot_titles=["J/S RATIO (dB)","C/N0 DROP (dB)","DOPPLER ERROR (Hz)"],
                vertical_spacing=0.1)
            fig_r.add_trace(go.Scatter(y=df_r["js_ratio_db"],mode="lines+markers",
                line=dict(color="#2eff2e",width=1.5),marker=dict(size=3),name="J/S"),row=1,col=1)
            fig_r.add_hline(y=10,line_dash="dash",line_color="#ffaa00",row=1,col=1)
            fig_r.add_hline(y=20,line_dash="dash",line_color="#ff3030",row=1,col=1)
            fig_r.add_trace(go.Scatter(y=df_r["cn0_drop_db"],mode="lines+markers",
                line=dict(color="#ffaa00",width=1.5),marker=dict(size=3),name="C/N0"),row=2,col=1)
            fig_r.add_trace(go.Scatter(y=df_r["doppler_error_hz"],mode="lines+markers",
                line=dict(color="#ff6666",width=1.5),marker=dict(size=3),name="Doppler"),row=3,col=1)
            fig_r.update_layout(**dfig(400),showlegend=False)
            fig_r.update_annotations(font=dict(color="#3d6b3d",size=10))
            st.plotly_chart(fig_r,use_container_width=True)
        else:
            st.info("Run a capture to display RF telemetry.")

    # Spectrum waterfall
    if rh:
        sh("RF SPECTRUM WATERFALL")
        freqs=np.linspace(exp_freq*1e6-1.2e6,exp_freq*1e6+1.2e6,200)/1e6
        wfall=[]
        for h in rh[-30:]:
            noise=np.random.normal(-110,2,200)
            pi=np.argmin(np.abs(freqs-exp_freq))
            noise[max(0,pi-5):pi+5]+=25-h.get("cn0_drop_db",0)
            if h.get("threat_type")=="JAMMING": noise+=h.get("js_ratio_db",0)*0.5
            wfall.append(noise)
        fig_wf=go.Figure(go.Heatmap(z=wfall,x=freqs,
            colorscale=[[0,"#050905"],[0.3,"#0d3a0d"],[0.6,"#1a7a1a"],[0.85,"#ffaa00"],[1,"#ff3030"]],
            showscale=True,colorbar=dict(title="dBm",tickfont=dict(color="#9ab89a"))))
        fig_wf.update_layout(**dfig(230),xaxis_title="Frequency (MHz)",yaxis_title="Time")
        st.plotly_chart(fig_wf,use_container_width=True)

    sh("THREAT LOG")
    for h in reversed(rh[-12:]):
        lvl=h["threat_level"]
        rc_={"RED":"r","AMBER":"a"}.get(lvl,"")
        col={"RED":"#ff3030","AMBER":"#ffaa00"}.get(lvl,"#2eff2e")
        st.markdown(f'<div class="row {rc_}"><span style="color:#3d6b3d">{h["timestamp"]}</span> &nbsp;'
                    f'<span style="color:{col};font-weight:700">{lvl}</span> | '
                    f'{h["threat_type"]} | J/S:{h["js_ratio_db"]}dB | '
                    f'Conf:{h["confidence_pct"]}% | {h["backend"]}</div>',unsafe_allow_html=True)

    if run_rf:
        if not sdr:
            cfg=SDRConfig(center_freq_hz=exp_freq*1e6,gain_db=30.0)
            st.session_state.sdr=SDRInterface(cfg,SDRBackend.SIMULATED)
            sdr=st.session_state.sdr
        clf=RFThreatClassifier()
        for _ in range(n_s):
            sample=sdr.capture(scenario)
            rec=clf.classify(sample,exp_freq*1e6,exp_dop)
            st.session_state.rf_history.append(rec)
            st.session_state.last_rf=rec
        st.session_state.assessment["rf_assessment"]=st.session_state.last_rf
        st.rerun()

# ══════════════════════════════════════════════════════
# TAB 5 — ATTACK SURFACE
# ══════════════════════════════════════════════════════
with t5:
    sh("RF ATTACK SURFACE ASSESSMENT")
    as1,as2=st.columns(2)
    with as1:
        st.markdown("**UPLINK**")
        ul_eirp  = st.number_input("Uplink EIRP (dBW)",0.0,90.0,55.0)
        ul_freq  = st.number_input("Uplink Freq (GHz)",1.0,50.0,14.0)
        ul_spread= st.selectbox("Uplink Spread",["NONE","DSSS","FHSS","HYBRID"])
        ul_auth  = st.checkbox("Uplink Auth Enabled",False)
        ul_enc   = st.checkbox("Uplink Encryption",False)
        st.markdown("**TT&C**")
        ttc_freq = st.number_input("TT&C Freq (GHz)",1.0,50.0,2.025)
        ttc_rng  = st.checkbox("Ranging Enabled",True)
    with as2:
        st.markdown("**DOWNLINK**")
        dl_alt   = st.number_input("Satellite Alt (km)",160.0,36000.0,550.0)
        dl_eirp  = st.number_input("Downlink EIRP (dBW)",0.0,80.0,47.0)
        dl_freq  = st.number_input("Downlink Freq (GHz)",1.0,50.0,11.7)
        dl_enc   = st.checkbox("Downlink Encryption",False)
        rx_sens  = st.number_input("Adversary Rx Sens (dBm)",-140.0,-60.0,-110.0)
    if st.button("RUN ATTACK SURFACE ASSESSMENT"):
        m=AttackSurfaceMapper()
        vulns=m.assess_uplink(ul_eirp,ul_freq,ul_spread,ul_auth,ul_enc)
        vulns+=m.assess_downlink(dl_alt,dl_eirp,dl_freq,dl_enc,rx_sens)
        vulns+=m.assess_ttc(ttc_freq,ul_auth,ttc_rng)
        score=m.score(vulns)
        st.session_state.vulns=vulns
        st.session_state.surf_score=score
        st.session_state.assessment["attack_surface"]={
            **score,
            "findings":[{"name":v.name,"severity":v.severity.value,
                         "score":v.score,"description":v.description,
                         "attack_vector":v.attack_vector,"mitigation":v.mitigation}
                        for v in vulns]
        }
        st.rerun()
    vs=st.session_state.vulns; ss2=st.session_state.surf_score
    if vs:
        sh("RESULTS")
        s1,s2,s3,s4=st.columns(4)
        kpi(s1,"RISK",         ss2.get("risk_level","---"),lcls(ss2.get("risk_level","")))
        kpi(s2,"SCORE",        f'{ss2.get("overall_score",0)}/10',"r")
        kpi(s3,"TOTAL VULNS",  ss2.get("vuln_count",0),"a")
        kpi(s4,"CRITICAL",     ss2.get("critical_count",0),"r")
        st.markdown("<br>",unsafe_allow_html=True)
        sh("VULNERABILITY FINDINGS")
        for v in sorted(vs,key=lambda x:x.score,reverse=True):
            cls=scls(v.severity.value); col=scol(v.severity.value)
            st.markdown(f"""
<div class="vbox {cls}">
<div class="vname" style="color:{col}">[{v.severity.value}]  {v.name} &nbsp;
<span style="color:#3d6b3d;font-size:11px">Score: {v.score}/10</span></div>
<div class="vdesc">{v.description}</div>
<div style="color:#3d6b3d;font-size:11px;margin-top:6px">ATTACK VECTOR: {v.attack_vector}</div>
<div class="vmit">MITIGATION: {v.mitigation}</div>
</div>""",unsafe_allow_html=True)
    sh("DOWNLINK INTERCEPTION GEOMETRY")
    eg=EavesdropGeometry(dl_alt,dl_eirp,rx_sens,dl_freq)
    r_km=eg.intercept_radius_km(); a_km2=eg.intercept_area_km2()
    e1,e2=st.columns(2)
    kpi(e1,"INTERCEPT RADIUS",f"{r_km} km","r")
    kpi(e2,"INTERCEPT AREA",  f"{a_km2:,.0f} km2","r")
    st.markdown(f'<div class="actbox">Any adversary with a standard {dl_freq:.1f} GHz dish '
                f'within {r_km} km of the satellite ground track can receive this downlink. '
                f'Total intercept area: {a_km2:,.0f} km2.</div>',unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# TAB 6 — DOCUMENTED INCIDENTS
# ══════════════════════════════════════════════════════
with t6:
    sh("DOCUMENTED SATELLITE SECURITY INCIDENTS")
    st.markdown('<div class="actbox">Real-world incidents. Load as test scenarios for RAIM and RF monitor.</div>',
                unsafe_allow_html=True)

    # Incident map
    inc_m=folium.Map(location=[30,20],zoom_start=2,
        tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",attr="CartoDB")
    for name,inc in DOCUMENTED_INCIDENTS.items():
        color={"GPS Spoofing":"red","Satellite Uplink Jamming":"orange",
               "Downlink Interception":"blue","Navigation Hijack":"red",
               "Satellite Network Attack":"darkred"}.get(inc["type"],"gray")
        folium.CircleMarker([inc["lat"],inc["lon"]],radius=8,color=color,
            fill=True,fill_color=color,fill_opacity=0.8,
            tooltip=f"{name}\n{inc['date']}\n{inc['type']}").add_to(inc_m)
    st_folium(inc_m,height=350,use_container_width=True)

    for name,inc in DOCUMENTED_INCIDENTS.items():
        st.markdown(f'<div class="sh">{inc["type"].upper()}  |  {name}  |  {inc["date"]}</div>', unsafe_allow_html=True)
        if True:
            st.markdown(f"**Location:** {inc['location']}")
            st.markdown(f"**Description:** {inc['description']}")
            st.markdown("**Technical Details:**")
            for k,v in inc["technical"].items():
                st.markdown(f"- {k.replace('_',' ').title()}: `{v}`")
            st.markdown(f"**Reference:** {inc['reference']}")
            col_a,col_b=st.columns(2)
            with col_a:
                if st.button(f"Load as GNSS Scenario",key=f"g_{name}"):
                    st.session_state["inject_gnss"]=inc["gnss_scenario"]
                    st.info(f"Scenario set: {inc['gnss_scenario']}. Go to GNSS INTEGRITY tab.")
            with col_b:
                if st.button(f"Load as RF Scenario",key=f"r_{name}"):
                    st.session_state["inject_rf"]=inc["rf_scenario"]
                    st.info(f"Scenario set: {inc['rf_scenario']}. Go to RF MONITOR tab.")

# ══════════════════════════════════════════════════════
# TAB 7 — EXPORT
# ══════════════════════════════════════════════════════
with t7:
    sh("EXPORT — ASSESSMENT REPORT")
    title=st.text_input("Report Title","SpiderLan Assessment Report")
    summ =st.text_area("Summary","",height=60)
    e1,e2,e3=st.columns(3)
    assessment=st.session_state.assessment
    with e1:
        if st.button("EXPORT FULL JSON"):
            r=export_full_report(assessment,analyst,title)
            st.download_button("DOWNLOAD JSON",
                data=json.dumps(r,indent=2,default=str),
                file_name=f"spiderlan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json")
    with e2:
        if st.button("EXPORT STIX 2.1"):
            r=export_stix_bundle(assessment,title,analyst)
            st.download_button("DOWNLOAD STIX",
                data=json.dumps(r,indent=2,default=str),
                file_name=f"spiderlan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.stix.json",
                mime="application/json")
    with e3:
        if st.button("EXPORT STANAG 4586"):
            r=export_stanag_4586(assessment)
            st.download_button("DOWNLOAD STANAG",
                data=json.dumps(r,indent=2,default=str),
                file_name=f"spiderlan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.stanag.json",
                mime="application/json")
    sh("LIVE PREVIEW")
    try:
        st.json(export_full_report(assessment,analyst,title))
    except Exception as e:
        st.error(str(e))
