"""
SpiderLan :: Link Budget Engine
Standards: ITU-R S.465, ITU-R P.618-13, ITU-R P.676-12
"""

import math
from dataclasses import dataclass
from enum import Enum

BOLTZMANN_DBW = -228.6


class Waveform(Enum):
    BPSK   = ("BPSK",   1, 10.5)
    QPSK   = ("QPSK",   2,  9.6)
    OQPSK  = ("OQPSK",  2,  9.6)
    PSK8   = ("8PSK",   3, 13.0)
    APSK16 = ("16APSK", 4, 16.5)
    APSK32 = ("32APSK", 5, 19.5)
    def bits_per_symbol(self): return self.value[1]
    def req_eb_n0(self):       return self.value[2]
    def label(self):           return self.value[0]


class FECCode(Enum):
    NONE      = ("None",       1.000,  0.0)
    TURBO_1_2 = ("Turbo 1/2", 0.500, -4.5)
    TURBO_3_4 = ("Turbo 3/4", 0.750, -2.2)
    LDPC_1_2  = ("LDPC 1/2",  0.500, -4.8)
    LDPC_3_4  = ("LDPC 3/4",  0.750, -2.5)
    LDPC_5_6  = ("LDPC 5/6",  0.833, -1.8)
    CONV_1_2  = ("Conv 1/2",  0.500, -3.0)
    def rate(self):        return self.value[1]
    def coding_gain(self): return self.value[2]
    def label(self):       return self.value[0]


@dataclass
class TransmitterParams:
    power_w: float; antenna_gain_dbi: float
    line_loss_db: float = 1.0; pointing_loss_db: float = 0.3
    @property
    def power_dbw(self): return 10*math.log10(max(self.power_w,1e-9))
    @property
    def eirp_dbw(self): return self.power_dbw+self.antenna_gain_dbi-self.line_loss_db-self.pointing_loss_db


@dataclass
class ReceiverParams:
    antenna_gain_dbi: float; system_noise_temp_k: float
    line_loss_db: float = 0.5; pointing_loss_db: float = 0.3
    @property
    def g_over_t_db(self):
        return (self.antenna_gain_dbi-self.line_loss_db-self.pointing_loss_db
                -10*math.log10(max(self.system_noise_temp_k,1.0)))


def fspl(distance_km, freq_ghz):
    return 20*math.log10(distance_km)+20*math.log10(freq_ghz)+92.45

def rain_loss(freq_ghz, elevation_deg, rain_rate_mm_hr=20.0):
    if freq_ghz < 1: return 0.0
    table = [(2.9,0.0000352,0.880),(7,0.000138,0.923),(10,0.00101,1.276),
             (12,0.00188,1.217),(15,0.00367,1.154),(20,0.00751,1.099),
             (25,0.01240,1.061),(30,0.01870,1.021),(40,0.03510,0.939),(100,0.0691,0.873)]
    k,alpha = next(((k,a) for f,k,a in table if freq_ghz<=f),(0.0691,0.873))
    gamma = k*(rain_rate_mm_hr**alpha)
    el    = math.radians(max(elevation_deg,5.0))
    l_s   = 3.9/math.sin(el)
    r001  = 1/(1+0.78*math.sqrt(l_s*gamma/freq_ghz)-0.38*(1-math.exp(-2*l_s)))
    return gamma*l_s*r001

def atm_loss(freq_ghz, elevation_deg):
    el = math.radians(max(elevation_deg,5.0))
    z  = (0.03+0.0001*freq_ghz if freq_ghz<15 else
          0.03+0.005*(freq_ghz-15) if freq_ghz<22.3 else
          0.18+0.01*(freq_ghz-22.3) if freq_ghz<25 else
          0.05+0.004*(freq_ghz-25) if freq_ghz<31.4 else
          0.1+0.003*freq_ghz)
    return z/math.sin(el)


class LinkBudgetCalculator:
    def __init__(self, tx, rx, freq_ghz, distance_km, elevation_deg,
                 data_rate_kbps, waveform, fec, rain_rate=20.0):
        self.tx=tx; self.rx=rx; self.freq_ghz=freq_ghz
        self.distance_km=distance_km; self.elevation_deg=elevation_deg
        self.data_rate_kbps=data_rate_kbps; self.waveform=waveform
        self.fec=fec; self.rain_rate=rain_rate

    def compute(self):
        eirp       = self.tx.eirp_dbw
        path_loss  = (fspl(self.distance_km, self.freq_ghz)
                      + rain_loss(self.freq_ghz, self.elevation_deg, self.rain_rate)
                      + atm_loss(self.freq_ghz, self.elevation_deg))
        g_t        = self.rx.g_over_t_db
        cn0        = eirp - path_loss + g_t - BOLTZMANN_DBW
        rb_hz      = self.data_rate_kbps*1000/self.fec.rate()
        eb_n0      = cn0 - 10*math.log10(rb_hz)
        req_eb_n0  = self.waveform.req_eb_n0() + self.fec.coding_gain()
        margin     = eb_n0 - req_eb_n0
        rl = rain_loss(self.freq_ghz, self.elevation_deg, self.rain_rate)
        al = atm_loss(self.freq_ghz, self.elevation_deg)
        return {
            "eirp_dbw":           round(eirp,2),
            "fspl_db":            round(fspl(self.distance_km,self.freq_ghz),2),
            "rain_loss_db":       round(rl,2),
            "atm_loss_db":        round(al,2),
            "total_path_loss_db": round(path_loss,2),
            "g_over_t_db":        round(g_t,2),
            "cn0_dbhz":           round(cn0,2),
            "eb_n0_db":           round(eb_n0,2),
            "req_eb_n0_db":       round(req_eb_n0,2),
            "link_margin_db":     round(margin,2),
            "symbol_rate_ksps":   round(self.data_rate_kbps/self.fec.rate()/self.waveform.bits_per_symbol(),2),
            "status":             "CLOSED" if margin>=0 else "OPEN",
            "margin_quality":     "ADEQUATE" if margin>=3 else ("MARGINAL" if margin>=0 else "INSUFFICIENT"),
        }


class AntiJamAnalyzer:
    def __init__(self, spread_type, signal_bw_mhz, data_rate_kbps, rx_nf_db, req_snr_db):
        self.spread_type=spread_type; self.bw_mhz=signal_bw_mhz
        self.dr_kbps=data_rate_kbps; self.nf=rx_nf_db; self.req_snr=req_snr_db

    def compute(self, jammer_eirp_dbw, signal_eirp_dbw, path_loss_db):
        if self.spread_type=="DSSS":
            pg = 10*math.log10((self.bw_mhz*1e6)/(self.dr_kbps*1e3))
        elif self.spread_type=="FHSS":
            pg = 10*math.log10(max(self.bw_mhz/(self.dr_kbps/1000),1))
        elif self.spread_type=="HYBRID":
            pg = 10*math.log10((self.bw_mhz*1e6)/(self.dr_kbps*1e3))+3.0
        else:
            pg = 0.0
        js = (jammer_eirp_dbw-path_loss_db)-(signal_eirp_dbw-path_loss_db)
        js_eff = js - pg
        jam_margin = pg - self.req_snr - js
        eff = ("LINK DISRUPTED" if js_eff>=10 else "EFFECTIVE" if js_eff>=0
               else "MARGINAL" if js_eff>=-10 else "INEFFECTIVE")
        return {
            "processing_gain_db":    round(pg,2),
            "js_ratio_db":           round(js,2),
            "js_after_pg_db":        round(js_eff,2),
            "jam_margin_db":         round(jam_margin,2),
            "jamming_effectiveness": eff,
            "spread_type":           self.spread_type,
        }


class EavesdropGeometry:
    def __init__(self, sat_alt_km, eirp_dbw, rx_sensitivity_dbm=-110.0, freq_ghz=11.7):
        self.alt=sat_alt_km; self.eirp=eirp_dbw
        self.rx_sens=rx_sensitivity_dbm-30; self.freq=freq_ghz

    def intercept_radius_km(self):
        max_loss = self.eirp - self.rx_sens
        log_d    = (max_loss - 20*math.log10(self.freq) - 92.45)/20
        slant    = 10**log_d
        R        = 6371.0
        if slant <= 0 or slant < self.alt: return 0.0
        cos_n = min((R+self.alt)/slant, 1.0)
        return round(R*math.acos(cos_n), 1)

    def intercept_area_km2(self):
        r = self.intercept_radius_km()
        return round(math.pi*r**2, 0)
