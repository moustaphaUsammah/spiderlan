"""
SpiderLan :: Military Presets & Documented Incidents
MIL-STD-188 waveforms, real satellite system parameters,
and documented RF/satellite security incidents.
"""

# ── MIL-STD Waveform Presets ─────────────────────────────────────────────────
# Reference: MIL-STD-188-181C (JTIDS), MIL-STD-188-183 (MUOS), MIL-STD-188-165A

MIL_WAVEFORMS = {
    "Link 16 (JTIDS/MIDS)": {
        "freq_ghz":        0.969,
        "bandwidth_mhz":   3.0,
        "spread_type":     "FHSS",
        "data_rate_kbps":  238.0,
        "waveform":        "QPSK",
        "fec":             "NONE",
        "description":     "NATO tactical data link. FHSS across 51 channels in L-band. "
                           "Used by fighter aircraft, naval vessels, AWACS.",
        "standard":        "MIL-STD-188-181C",
    },
    "MUOS (Mobile UHF SATCOM)": {
        "freq_ghz":        0.3,
        "bandwidth_mhz":   5.0,
        "spread_type":     "DSSS",
        "data_rate_kbps":  64.0,
        "waveform":        "QPSK",
        "fec":             "CONV_1_2",
        "description":     "Mobile User Objective System. UHF SATCOM for US military. "
                           "WCDMA waveform. 5 GEO satellites.",
        "standard":        "MIL-STD-188-183",
    },
    "AEHF (EHF Milstar)": {
        "freq_ghz":        44.0,
        "bandwidth_mhz":   500.0,
        "spread_type":     "HYBRID",
        "data_rate_kbps":  8192.0,
        "waveform":        "8PSK",
        "fec":             "TURBO_3_4",
        "description":     "Advanced Extremely High Frequency. Nuclear-survivable SATCOM. "
                           "EHF uplink, SHF downlink. Jam-resistant.",
        "standard":        "MIL-STD-188-165A",
    },
    "INMARSAT BGAN (Tactical)": {
        "freq_ghz":        1.6,
        "bandwidth_mhz":   0.2,
        "spread_type":     "NONE",
        "data_rate_kbps":  492.0,
        "waveform":        "QPSK",
        "fec":             "TURBO_3_4",
        "description":     "L-band GEO SATCOM. Used by military expeditionary forces. "
                           "No spreading — vulnerable to jamming.",
        "standard":        "INMARSAT ISD",
    },
    "Starlink (User Terminal)": {
        "freq_ghz":        14.0,
        "bandwidth_mhz":   250.0,
        "spread_type":     "NONE",
        "data_rate_kbps":  100000.0,
        "waveform":        "16APSK",
        "fec":             "LDPC_3_4",
        "description":     "Ku-band phased array uplink. Used by Ukrainian military 2022+. "
                           "Susceptible to broadband jamming. No uplink authentication documented.",
        "standard":        "Starlink ICD v2.1",
    },
    "Iridium (L-band)": {
        "freq_ghz":        1.621,
        "bandwidth_mhz":   0.031,
        "spread_type":     "TDMA",
        "data_rate_kbps":  2.4,
        "waveform":        "QPSK",
        "fec":             "CONV_1_2",
        "description":     "Low data rate L-band LEO SATCOM. 66 satellites. "
                           "Used for military push-to-talk, GMDSS. Narrow beam.",
        "standard":        "Iridium SBD Protocol",
    },
    "VSAT (Ku-band SCPC)": {
        "freq_ghz":        14.25,
        "bandwidth_mhz":   36.0,
        "spread_type":     "NONE",
        "data_rate_kbps":  2000.0,
        "waveform":        "QPSK",
        "fec":             "LDPC_1_2",
        "description":     "Commercial Ku-band VSAT. Widely used by military contractors, "
                           "ships, forward bases. Often unencrypted. High intercept risk.",
        "standard":        "DVB-S2",
    },
}

# ── Real Satellite System Link Budget Presets ─────────────────────────────────

SATELLITE_SYSTEM_PRESETS = {
    "Starlink Gen2 (GEO equivalent calc)": {
        "tx_power_w":        100.0,
        "tx_gain_dbi":       30.0,
        "tx_loss_db":        1.0,
        "rx_gain_dbi":       35.0,
        "rx_noise_temp_k":   200.0,
        "freq_ghz":          14.0,
        "distance_km":       550.0,
        "elevation_deg":     50.0,
        "data_rate_kbps":    100000.0,
        "rain_rate_mm_hr":   20.0,
    },
    "GEO INMARSAT (L-band)": {
        "tx_power_w":        40.0,
        "tx_gain_dbi":       8.0,
        "tx_loss_db":        0.5,
        "rx_gain_dbi":       20.0,
        "rx_noise_temp_k":   150.0,
        "freq_ghz":          1.6,
        "distance_km":       35786.0,
        "elevation_deg":     30.0,
        "data_rate_kbps":    492.0,
        "rain_rate_mm_hr":   5.0,
    },
    "GEO Ku-band VSAT": {
        "tx_power_w":        2.0,
        "tx_gain_dbi":       43.0,
        "tx_loss_db":        1.0,
        "rx_gain_dbi":       50.0,
        "rx_noise_temp_k":   150.0,
        "freq_ghz":          14.25,
        "distance_km":       35786.0,
        "elevation_deg":     40.0,
        "data_rate_kbps":    2000.0,
        "rain_rate_mm_hr":   20.0,
    },
    "GPS L1 (C/A)": {
        "tx_power_w":        27.0,
        "tx_gain_dbi":       13.0,
        "tx_loss_db":        1.0,
        "rx_gain_dbi":       3.0,
        "rx_noise_temp_k":   513.0,
        "freq_ghz":          1.57542,
        "distance_km":       20200.0,
        "elevation_deg":     45.0,
        "data_rate_kbps":    0.05,
        "rain_rate_mm_hr":   5.0,
    },
    "AEHF EHF Uplink": {
        "tx_power_w":        20.0,
        "tx_gain_dbi":       50.0,
        "tx_loss_db":        1.5,
        "rx_gain_dbi":       55.0,
        "rx_noise_temp_k":   300.0,
        "freq_ghz":          44.0,
        "distance_km":       35786.0,
        "elevation_deg":     35.0,
        "data_rate_kbps":    8192.0,
        "rain_rate_mm_hr":   20.0,
    },
}

# ── Documented Security Incidents ─────────────────────────────────────────────

DOCUMENTED_INCIDENTS = {
    "Black Sea GPS Spoofing (2017)": {
        "date":        "2017-06-22",
        "location":    "Black Sea, near Novorossiysk, Russia",
        "lat":         44.9,
        "lon":         37.4,
        "type":        "GPS Spoofing",
        "description": (
            "Over 20 ships reported GPS positions placing them 25+ nautical miles "
            "inland at Gelendzhik Airport. AIS records confirmed simultaneous spoofing "
            "of multiple vessels. First large-scale documented maritime GPS spoofing event."
        ),
        "technical": {
            "spoofed_position_delta_m": 46300,
            "vessels_affected":         20,
            "duration_hours":           24,
            "likely_source":            "Ground-based spoofing transmitter, Russian military exercise",
        },
        "gnss_scenario": "spoofing",
        "rf_scenario":   "spoofing",
        "reference":     "C4ADS Report 2019 — Above Us Only Stars",
    },
    "Ukraine Starlink Jamming (2022)": {
        "date":        "2022-03-01",
        "location":    "Eastern Ukraine",
        "lat":         48.3,
        "lon":         37.8,
        "type":        "Satellite Uplink Jamming",
        "description": (
            "Russian forces deployed ground-based jamming targeting Starlink terminals "
            "used by Ukrainian military. SpaceX responded with software updates within "
            "hours to restore service. Demonstrated real-time EW vs commercial LEO SATCOM."
        ),
        "technical": {
            "target_system":      "Starlink Gen1/Gen2 Ku-band",
            "jamming_type":       "Broadband noise + meaconing",
            "countermeasure":     "Software beam steering update by SpaceX",
            "downtime_hours":     6,
        },
        "gnss_scenario": "nominal",
        "rf_scenario":   "jamming",
        "reference":     "Elon Musk Twitter, US DOD briefings, Wired Magazine 2022",
    },
    "VSAT Maritime Interception — Pavur (2020)": {
        "date":        "2020-01-01",
        "location":    "Global — Atlantic shipping lanes",
        "lat":         40.0,
        "lon":         -30.0,
        "type":        "Downlink Interception",
        "description": (
            "Oxford researcher James Pavur demonstrated live interception of Ku-band VSAT "
            "downlinks using a $400 dish and DVB-S2 receiver. Captured unencrypted email, "
            "HTTP traffic, and sensitive military contractor communications from vessels "
            "in the Atlantic. No active attack required — purely passive reception."
        ),
        "technical": {
            "equipment_cost_usd": 400,
            "dish_diameter_m":    0.85,
            "intercept_radius_km": 40000,
            "protocols_captured": ["HTTP", "SMTP", "FTP", "Telnet"],
            "encryption_rate_pct": 30,
        },
        "gnss_scenario": "nominal",
        "rf_scenario":   "nominal",
        "reference":     "Pavur & Martinovic, IEEE S&P 2020 — A Tale of Sea and Sky",
    },
    "GPS L1 Spoofing — Tehran (2011)": {
        "date":        "2011-12-04",
        "location":    "Iran-Afghanistan border",
        "lat":         34.5,
        "lon":         62.3,
        "type":        "GPS Spoofing + Navigation Hijack",
        "description": (
            "Iranian forces captured US RQ-170 Sentinel UAV by spoofing GPS signals. "
            "UAV believed it was approaching home base and landed in Iranian territory. "
            "First publicly acknowledged spoofing-induced vehicle capture. "
            "Demonstrated navigation warfare at operational level."
        ),
        "technical": {
            "target":             "RQ-170 Sentinel UAV",
            "attack_type":        "GPS L1 C/A spoofing",
            "position_error_km":  200,
            "effect":             "Vehicle landed at adversary location",
        },
        "gnss_scenario": "spoofing",
        "rf_scenario":   "spoofing",
        "reference":     "Christian Science Monitor 2011, GPS World 2012",
    },
    "Viasat KA-SAT Cyberattack (2022)": {
        "date":        "2022-02-24",
        "location":    "Europe — Ukraine, Germany, France",
        "lat":         50.4,
        "lon":         30.5,
        "type":        "Satellite Network Attack",
        "description": (
            "Russian actors wiped tens of thousands of KA-SAT modems across Europe "
            "on the day of the Ukraine invasion using a destructive wiper (AcidRain). "
            "Disabled Ukrainian military C2 links and knocked out 5,800 wind turbines "
            "in Germany. Combined cyber+satellite attack at strategic scale."
        ),
        "technical": {
            "modems_affected":   40000,
            "malware":           "AcidRain wiper",
            "vector":            "Management network intrusion via satellite NMS",
            "collateral_damage": "5,800 wind turbines offline across EU",
        },
        "gnss_scenario": "nominal",
        "rf_scenario":   "nominal",
        "reference":     "CISA Advisory AA22-076A, SentinelOne Research 2022",
    },
}
