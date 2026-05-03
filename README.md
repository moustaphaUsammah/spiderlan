# SpiderLan
## Satellite RF Security & Navigation Integrity Platform

Covers RF link analysis, GNSS integrity monitoring, satellite attack surface assessment,
and forensic reporting. Designed for satellite security research and defense applications.

---

## Install & Run

```
pip install -r requirements.txt
streamlit run spiderlan.py
```

For real SDR hardware (RTL-SDR, HackRF, USRP):
```
pip install pyrtlsdr       # RTL-SDR
pip install SoapySDR       # HackRF / USRP / LimeSDR
```

---

## Modules

| Module | Standards |
|--------|-----------|
| Link Budget | ITU-R S.465, ITU-R P.618-13, ITU-R P.676-12 |
| Anti-Jam | MIL-HDBK-1195, Adamy EW101 |
| GNSS Integrity | RTCA DO-229E, ICAO Annex 10, IS-GPS-200N |
| Attack Surface | Pavur 2020, MIL-HDBK-1195, NIST SP 800-187 |
| SDR Interface | RTL-SDR, HackRF, USRP, SoapySDR |
| Export | STIX 2.1, STANAG 4586 Ed.3, JSON |

## Satellite Groups Supported

All Celestrak groups: Starlink, GPS, GLONASS, Galileo, BeiDou,
INMARSAT, INTELSAT, SES, Iridium, Military (USA), Space Stations, GEO.
Custom TLE paste also supported.

## MIL-STD Waveform Presets

Link 16 (JTIDS/MIDS), MUOS, AEHF, INMARSAT BGAN, Starlink, Iridium, VSAT

## Documented Incidents Included

- Black Sea GPS Spoofing (2017)
- Ukraine Starlink Jamming (2022)
- VSAT Maritime Interception — Pavur (2020)
- GPS Spoofing / UAV Capture — Tehran (2011)
- Viasat KA-SAT Cyberattack (2022)

---

## References

- Pavur & Martinovic, "A Tale of Sea and Sky", IEEE S&P 2020
- C4ADS, "Above Us Only Stars", 2019
- ITU-R P.618-13, P.676-12, S.465
- RTCA DO-229E (MOPS)
- MIL-STD-188-181C, 183, 165A
- Adamy, "EW 101", Artech House 2001
