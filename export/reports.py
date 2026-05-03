"""
SpiderLan :: Export Engine
STANAG 4586 (UAV interoperability), STIX 2.1 (threat intelligence),
and structured JSON assessment reports.
"""

import json
import uuid
from datetime import datetime, timezone


def export_stanag_4586(assessment: dict, platform_id: str = "SPIDERLAN-01") -> dict:
    """
    STANAG 4586 — NATO STANAG for UAV control systems.
    Used for interoperability between UAV ground control stations
    and C2 systems. Relevant for navigation and RF status reporting.
    """
    ts = datetime.now(timezone.utc).isoformat()

    gnss = assessment.get("gnss_integrity", {})
    rf   = assessment.get("rf_assessment",  {})
    surf = assessment.get("attack_surface", {})

    return {
        "stanag_version":    "4586 Ed.3",
        "message_type":      "CUCS_REPORT",
        "platform_id":       platform_id,
        "timestamp_utc":     ts,
        "data_link_status": {
            "link_margin_db":    assessment.get("link_budget", {}).get("link_margin_db"),
            "link_status":       assessment.get("link_budget", {}).get("status"),
            "uplink_freq_ghz":   assessment.get("link_budget", {}).get("freq_ghz"),
            "jam_margin_db":     assessment.get("anti_jam",   {}).get("jam_margin_db"),
            "jamming_detected":  rf.get("threat_level") in ("AMBER","RED"),
        },
        "navigation_status": {
            "gnss_integrity":    gnss.get("status"),
            "hpl_m":             gnss.get("hpl_m"),
            "vpl_m":             gnss.get("vpl_m"),
            "raim_passed":       gnss.get("raim_passed"),
            "fde_active":        gnss.get("fde_triggered"),
            "excluded_prns":     gnss.get("excluded_prns", []),
            "starlink_delta_m":  gnss.get("starlink_check", {}).get("delta_m"),
        },
        "threat_summary": {
            "rf_threat_level":   rf.get("threat_level", "UNKNOWN"),
            "threat_type":       rf.get("threat_type",  "NONE"),
            "attack_risk":       surf.get("risk_level", "UNKNOWN"),
            "critical_vulns":    surf.get("critical_count", 0),
        },
    }


def export_stix_bundle(assessment: dict,
                       incident_title: str,
                       analyst: str) -> dict:
    """
    STIX 2.1 bundle.
    Standard format for sharing threat intelligence (OASIS CTI TC).
    Accepted by: MISP, OpenCTI, IBM QRadar, Splunk SIEM.
    """
    ts  = datetime.now(timezone.utc).isoformat()
    bid = f"bundle--{uuid.uuid4()}"

    identity = {
        "type":           "identity",
        "spec_version":   "2.1",
        "id":             f"identity--{uuid.uuid4()}",
        "name":           "SpiderLan",
        "identity_class": "system",
        "created":        ts,
        "modified":       ts,
    }

    incident = {
        "type":            "incident",
        "spec_version":    "2.1",
        "id":              f"incident--{uuid.uuid4()}",
        "name":            incident_title,
        "created":         ts,
        "modified":        ts,
        "created_by_ref":  identity["id"],
        "description":     f"SpiderLan assessment. Analyst: {analyst}.",
        "labels":          ["satellite", "rf-security", "navigation-warfare"],
        "extensions": {
            "extension-definition--spiderlan-v1": {
                "extension_type":    "property-extension",
                "link_margin_db":    assessment.get("link_budget",   {}).get("link_margin_db"),
                "gnss_status":       assessment.get("gnss_integrity",{}).get("status"),
                "attack_risk":       assessment.get("attack_surface",{}).get("risk_level"),
                "rf_threat_level":   assessment.get("rf_assessment", {}).get("threat_level"),
            }
        }
    }

    indicators = []

    # RF threat indicator
    rf = assessment.get("rf_assessment", {})
    if rf.get("threat_type") not in (None, "NONE", "NOMINAL"):
        indicators.append({
            "type":            "indicator",
            "spec_version":    "2.1",
            "id":              f"indicator--{uuid.uuid4()}",
            "name":            f"RF {rf['threat_type']} — {rf.get('threat_level','')}",
            "created":         ts,
            "modified":        ts,
            "pattern":         f"[x-rf:threat_type = '{rf['threat_type']}']",
            "pattern_type":    "stix",
            "valid_from":      ts,
            "indicator_types": ["malicious-activity"],
            "labels":          ["rf", "satellite", rf["threat_type"].lower()],
            "extensions": {
                "extension-definition--spiderlan-v1": {
                    "extension_type":    "property-extension",
                    "js_ratio_db":       rf.get("js_ratio_db"),
                    "cn0_drop_db":       rf.get("cn0_drop_db"),
                    "doppler_error_hz":  rf.get("doppler_error_hz"),
                    "confidence_pct":    rf.get("confidence_pct"),
                }
            }
        })

    # Attack surface findings
    for f in assessment.get("attack_surface", {}).get("findings", []):
        if f.get("severity") in ("CRITICAL", "HIGH"):
            indicators.append({
                "type":            "indicator",
                "spec_version":    "2.1",
                "id":              f"indicator--{uuid.uuid4()}",
                "name":            f"[{f['severity']}] {f['name']}",
                "created":         ts,
                "modified":        ts,
                "pattern":         f"[x-sat-vuln:name = '{f['name']}']",
                "pattern_type":    "stix",
                "valid_from":      ts,
                "indicator_types": ["malicious-activity"],
                "labels":          ["satellite", "vulnerability", f["severity"].lower()],
                "extensions": {
                    "extension-definition--spiderlan-v1": {
                        "extension_type":       "property-extension",
                        "exploitability_score": f.get("score"),
                        "mitigation":           f.get("mitigation"),
                    }
                }
            })

    return {
        "type":         "bundle",
        "id":           bid,
        "spec_version": "2.1",
        "objects":      [identity, incident] + indicators,
    }


def export_full_report(assessment: dict, analyst: str, title: str) -> dict:
    """Structured JSON report suitable for defense client delivery."""
    return {
        "report_metadata": {
            "title":        title,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "analyst":      analyst,
            "tool":         "SpiderLan v1.0",
            "standards":    ["ITU-R S.465", "ITU-R P.618-13", "RTCA DO-229E",
                             "MIL-STD-188-181C", "STIX 2.1", "STANAG 4586 Ed.3"],
        },
        "executive_summary": {
            "link_status":       assessment.get("link_budget",   {}).get("status"),
            "link_margin_db":    assessment.get("link_budget",   {}).get("link_margin_db"),
            "gnss_integrity":    assessment.get("gnss_integrity",{}).get("status"),
            "attack_risk":       assessment.get("attack_surface",{}).get("risk_level"),
            "critical_findings": assessment.get("attack_surface",{}).get("critical_count", 0),
            "rf_threat":         assessment.get("rf_assessment", {}).get("threat_level", "UNKNOWN"),
        },
        "link_budget":    assessment.get("link_budget"),
        "anti_jam":       assessment.get("anti_jam"),
        "gnss_integrity": assessment.get("gnss_integrity"),
        "rf_assessment":  assessment.get("rf_assessment"),
        "attack_surface": assessment.get("attack_surface"),
        "stanag_4586":    export_stanag_4586(assessment),
    }
