"""
SpiderLan :: RF Attack Surface Mapper
Reference: Pavur et al. 2020, MIL-HDBK-1195, NIST SP 800-187
"""

import math
from dataclasses import dataclass
from enum import Enum


class VulnSeverity(Enum):
    LOW="LOW"; MEDIUM="MEDIUM"; HIGH="HIGH"; CRITICAL="CRITICAL"


@dataclass
class Vulnerability:
    name: str; severity: VulnSeverity; description: str
    attack_vector: str; mitigation: str; score: float


class AttackSurfaceMapper:
    def assess_uplink(self, eirp, freq_ghz, spread, auth, enc):
        vulns=[]
        if spread=="NONE":   js,ss,jd="CRITICAL",9.0,"No spreading. Vulnerable to narrowband spot jamming."
        elif spread=="DSSS": js,ss,jd="MEDIUM",  5.0,"DSSS processing gain resists narrowband jamming. Wideband noise remains effective."
        elif spread=="FHSS": js,ss,jd="MEDIUM",  4.5,"FHSS resists narrowband jamming. Partial-band jamming effective if hop pattern known."
        else:                js,ss,jd="LOW",     3.0,"Hybrid spreading offers high jam resistance."
        vulns.append(Vulnerability("Uplink Jamming",VulnSeverity[js],jd,
            "Transmit noise on uplink frequency from ground within coverage footprint.",
            "Increase processing gain. Implement adaptive null steering. Frequency agility.",ss))
        if not auth:
            vulns.append(Vulnerability("Uplink Signal Injection",VulnSeverity.CRITICAL,
                "No uplink authentication. Adversary can inject fraudulent command or data frames.",
                "Craft valid protocol frames. Transmit from within uplink coverage area.",
                "Implement TESLA or asymmetric uplink authentication (MIL-STD-188-182).",9.5))
        vulns.append(Vulnerability("Uplink Replay Attack",
            VulnSeverity.HIGH if not auth else VulnSeverity.MEDIUM,
            "Recorded uplink frames can be retransmitted to replay commands." if not auth
            else "Replay window exists if sequence numbers are not timestamp-bound.",
            "Record uplink pass. Replay within orbital window.",
            "Use time-bounded nonce tokens. Reject frames outside ±10s window.",
            7.0 if not auth else 4.0))
        if not enc:
            vulns.append(Vulnerability("Plaintext Uplink",VulnSeverity.HIGH,
                "Unencrypted uplink. Protocol structure visible to passive interceptor within sidelobe coverage.",
                "Passive interception from within uplink antenna sidelobes.",
                "Apply link-layer encryption (AES-256-GCM). Encrypt before modulation.",8.0))
        return vulns

    def assess_downlink(self, sat_alt_km, eirp_dbw, freq_ghz, enc, rx_sens_dbm=-110.0):
        vulns=[]
        rx_dbw=rx_sens_dbm-30
        max_loss=eirp_dbw-rx_dbw
        log_d=(max_loss-20*math.log10(freq_ghz)-92.45)/20
        slant=10**log_d; R=6371.0; H=sat_alt_km
        r_km=0.0
        if slant>0 and slant>H:
            r_km=round(R*math.acos(min((R+H)/slant,1.0)),1)
        desc=(f"Unencrypted downlink receivable within {r_km} km ground radius. "
              f"Standard dish sufficient. All traffic readable." if not enc else
              f"Encrypted downlink receivable within {r_km} km. "
              f"Metadata, timing, and volume analysis possible.")
        vulns.append(Vulnerability("Downlink Interception",
            VulnSeverity.CRITICAL if not enc else VulnSeverity.MEDIUM,desc,
            f"Deploy {freq_ghz:.1f} GHz dish within {r_km} km of ground track.",
            "Encrypt all downlink payload. Use beam hopping to reduce intercept window.",
            9.0 if not enc else 4.5))
        vulns.append(Vulnerability("Downlink Jamming",VulnSeverity.HIGH,
            "Ground-based jammer near receiver can suppress downlink regardless of satellite EIRP.",
            "Deploy jammer co-located with target receiver. Jam receiver front-end.",
            "High-gain directional antenna. AGC monitoring. Uplink alarm on CN0 drop.",7.5))
        return vulns

    def assess_ttc(self, ttc_freq_ghz, auth, ranging):
        vulns=[]
        vulns.append(Vulnerability("TT&C Command Injection",
            VulnSeverity.CRITICAL if not auth else VulnSeverity.MEDIUM,
            "TT&C uplink is highest-value attack surface. Unauthorized commands can affect payload, "
            "attitude control, or orbital maneuvers.",
            "Transmit crafted TT&C frames from within uplink coverage. Replay recorded passes.",
            "Mandatory authentication on all TT&C channels. Separate TT&C from payload uplink.",
            9.8 if not auth else 4.0))
        if ranging:
            vulns.append(Vulnerability("Ranging Signal Manipulation",VulnSeverity.MEDIUM,
                "Ranging transponder responses can be delayed to corrupt orbit determination.",
                "Introduce group delay in transponder path during ranging pass.",
                "Secure ranging protocol. Cross-validate with independent orbit determination.",5.5))
        return vulns

    def score(self, vulns):
        if not vulns: return {"overall_score":0,"risk_level":"NONE","vuln_count":0}
        scores=[v.score for v in vulns]
        overall=round(0.6*max(scores)+0.4*(sum(scores)/len(scores)),2)
        c=sum(1 for v in vulns if v.severity==VulnSeverity.CRITICAL)
        h=sum(1 for v in vulns if v.severity==VulnSeverity.HIGH)
        return {"overall_score":overall,"risk_level":"CRITICAL" if c>0 else ("HIGH" if h>0 else "MEDIUM"),
                "vuln_count":len(vulns),"critical_count":c,"high_count":h,
                "medium_count":sum(1 for v in vulns if v.severity==VulnSeverity.MEDIUM),
                "low_count":sum(1 for v in vulns if v.severity==VulnSeverity.LOW)}
