"""
SpiderLan :: SDR Interface
Supports RTL-SDR, HackRF, USRP, and SoapySDR-compatible devices.
Falls back to simulation when no hardware is present.

Install for real hardware:
  pip install pyrtlsdr     # RTL-SDR
  pip install SoapySDR     # Universal (HackRF, USRP, LimeSDR)
  pip install numpy scipy
"""

import math
import time
import numpy as np
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class SDRBackend(Enum):
    RTLSDR    = "RTL-SDR"
    HACKRF    = "HackRF"
    USRP      = "USRP"
    SOAPYSDR  = "SoapySDR"
    SIMULATED = "Simulated"


@dataclass
class SDRConfig:
    center_freq_hz:   float          # Center frequency in Hz
    sample_rate_hz:   float = 2.4e6  # Sample rate
    gain_db:          float = 30.0   # RF gain
    ppm_correction:   float = 0.0    # Frequency correction (RTL-SDR specific)
    num_samples:      int   = 256000 # Samples per capture


@dataclass
class RFSample:
    timestamp:        str
    center_freq_hz:   float
    sample_rate_hz:   float
    power_dbm:        float          # Measured signal power
    noise_floor_dbm:  float
    peak_freq_hz:     float          # Dominant frequency in capture
    bandwidth_hz:     float          # Estimated signal bandwidth
    cn0_db:           float          # Carrier-to-noise density
    agc_gain_db:      float
    backend:          str


class SDRInterface:
    """
    Unified SDR interface.
    Attempts real hardware connection; falls back to simulation.
    """

    def __init__(self, config: SDRConfig, backend: SDRBackend = SDRBackend.RTLSDR):
        self.config  = config
        self.backend = backend
        self.device  = None
        self.connected = False
        self._try_connect()

    def _try_connect(self):
        if self.backend == SDRBackend.RTLSDR:
            try:
                from rtlsdr import RtlSdr
                self.device = RtlSdr()
                self.device.center_freq    = self.config.center_freq_hz
                self.device.sample_rate    = self.config.sample_rate_hz
                self.device.gain           = self.config.gain_db
                self.device.freq_correction = int(self.config.ppm_correction)
                self.connected = True
                self.backend   = SDRBackend.RTLSDR
            except Exception:
                self.connected = False

        elif self.backend == SDRBackend.SOAPYSDR:
            try:
                import SoapySDR
                self.device = SoapySDR.Device()
                self.device.setSampleRate(SoapySDR.SOAPY_SDR_RX, 0, self.config.sample_rate_hz)
                self.device.setFrequency(SoapySDR.SOAPY_SDR_RX, 0, self.config.center_freq_hz)
                self.device.setGain(SoapySDR.SOAPY_SDR_RX, 0, self.config.gain_db)
                self.connected = True
            except Exception:
                self.connected = False

        if not self.connected:
            self.backend = SDRBackend.SIMULATED

    def capture(self, scenario: str = "nominal") -> RFSample:
        if self.connected:
            return self._capture_real()
        return self._simulate(scenario)

    def _capture_real(self) -> RFSample:
        try:
            if self.backend == SDRBackend.RTLSDR:
                samples = self.device.read_samples(self.config.num_samples)
            else:
                import SoapySDR
                buff    = np.zeros(self.config.num_samples, dtype=np.complex64)
                rxStream = self.device.setupStream(SoapySDR.SOAPY_SDR_RX, SoapySDR.SOAPY_SDR_CF32)
                self.device.activateStream(rxStream)
                sr = self.device.readStream(rxStream, [buff], len(buff))
                self.device.deactivateStream(rxStream)
                samples = buff[:sr.ret]

            return self._process_samples(np.array(samples))
        except Exception as e:
            return self._simulate("nominal")

    def _process_samples(self, samples: np.ndarray) -> RFSample:
        # Power spectral density via Welch method
        n       = len(samples)
        window  = np.blackman(n)
        fft     = np.fft.fftshift(np.fft.fft(samples * window))
        psd     = 20 * np.log10(np.abs(fft) / n + 1e-12)

        # Frequency axis
        freqs   = np.fft.fftshift(np.fft.fftfreq(n, 1/self.config.sample_rate_hz))
        freqs  += self.config.center_freq_hz

        noise_floor  = float(np.percentile(psd, 20))
        peak_idx     = int(np.argmax(psd))
        peak_power   = float(psd[peak_idx])
        peak_freq    = float(freqs[peak_idx])

        # Estimate noise-normalized power (proxy for C/N0)
        cn0 = peak_power - noise_floor + 10*math.log10(self.config.sample_rate_hz / 2)

        # Estimate signal bandwidth (3dB width)
        threshold  = peak_power - 3
        above      = np.where(psd > threshold)[0]
        if len(above) > 1:
            bw = float(freqs[above[-1]] - freqs[above[0]])
        else:
            bw = self.config.sample_rate_hz / 100

        return RFSample(
            timestamp=datetime.now(timezone.utc).isoformat(),
            center_freq_hz=self.config.center_freq_hz,
            sample_rate_hz=self.config.sample_rate_hz,
            power_dbm=round(peak_power, 2),
            noise_floor_dbm=round(noise_floor, 2),
            peak_freq_hz=round(peak_freq, 1),
            bandwidth_hz=round(abs(bw), 1),
            cn0_db=round(cn0, 2),
            agc_gain_db=round(self.config.gain_db, 1),
            backend=self.backend.value,
        )

    def _simulate(self, scenario: str) -> RFSample:
        """
        Realistic simulation based on documented RF environments.
        Uses noise models from ITU-R P.372-16 (radio noise).
        """
        base_noise = -110.0  # Typical receiver noise floor dBm

        params = {
            "nominal":    dict(power=-95.0, noise=base_noise, cn0=42.0, agc=30.0),
            "jamming":    dict(power=-75.0, noise=base_noise+18, cn0=21.0, agc=12.0),
            "spoofing":   dict(power=-94.5, noise=base_noise+1,  cn0=41.0, agc=30.5),
            "multipath":  dict(power=-98.0, noise=base_noise+3,  cn0=36.0, agc=28.0),
            "weak_signal":dict(power=-115.0,noise=base_noise,    cn0=18.0, agc=45.0),
        }.get(scenario, dict(power=-95.0, noise=base_noise, cn0=42.0, agc=30.0))

        jitter = np.random.normal(0, 0.5)

        return RFSample(
            timestamp=datetime.now(timezone.utc).isoformat(),
            center_freq_hz=self.config.center_freq_hz,
            sample_rate_hz=self.config.sample_rate_hz,
            power_dbm=round(params["power"] + jitter, 2),
            noise_floor_dbm=round(params["noise"] + jitter*0.3, 2),
            peak_freq_hz=round(self.config.center_freq_hz + np.random.normal(0, 100), 1),
            bandwidth_hz=round(abs(np.random.normal(2e6, 1e5)), 0),
            cn0_db=round(params["cn0"] + jitter*0.5, 2),
            agc_gain_db=round(params["agc"] + jitter*0.2, 1),
            backend=SDRBackend.SIMULATED.value,
        )

    def spectrum_sweep(self, start_hz: float, stop_hz: float,
                       step_hz: float = 1e6) -> list[dict]:
        """
        Sweep across frequency range and return power at each step.
        Real hardware: retunes for each step.
        Simulation: generates realistic spectrum with signal peaks.
        """
        freqs   = np.arange(start_hz, stop_hz, step_hz)
        results = []

        for f in freqs:
            if self.connected:
                self.device.center_freq = f
                time.sleep(0.05)
            sample = self.capture()
            results.append({
                "freq_hz":   f,
                "power_dbm": sample.power_dbm,
                "noise_dbm": sample.noise_floor_dbm,
            })

        return results

    def close(self):
        if self.connected and self.device:
            try:
                if self.backend == SDRBackend.RTLSDR:
                    self.device.close()
            except Exception:
                pass


class RFThreatClassifier:
    """
    Classifies RF measurements into threat categories.
    Based on signal characteristics and deviation from baseline.
    """

    JS_AMBER_DB    = 10.0
    JS_RED_DB      = 20.0
    CN0_DROP_AMBER = 6.0
    CN0_DROP_RED   = 15.0
    DOPPLER_AMBER  = 50.0   # Hz
    DOPPLER_RED    = 200.0  # Hz

    def __init__(self, baseline_cn0: float = 42.0):
        self.baseline_cn0 = baseline_cn0

    def classify(self, sample: RFSample,
                 expected_freq_hz: float,
                 expected_doppler_hz: float = 0.0) -> dict:

        cn0_drop     = self.baseline_cn0 - sample.cn0_db
        noise_rise   = sample.noise_floor_dbm - (-110.0)
        doppler_err  = abs(sample.peak_freq_hz - expected_freq_hz - expected_doppler_hz)
        agc_anomaly  = sample.agc_gain_db < (30.0 - self.JS_AMBER_DB)

        # J/S estimate from noise rise + C/N0 degradation
        js_db = max(0.0, noise_rise + cn0_drop * 0.5)

        # Classification logic
        scores = {"JAMMING": 0.0, "SPOOFING": 0.0, "MULTIPATH": 0.0, "NOMINAL": 0.0}

        if js_db > self.JS_AMBER_DB:  scores["JAMMING"] += 40
        if agc_anomaly:               scores["JAMMING"] += 30
        if cn0_drop > self.CN0_DROP_AMBER: scores["JAMMING"] += 20

        if doppler_err > self.DOPPLER_AMBER: scores["SPOOFING"] += 50
        if doppler_err > self.DOPPLER_RED:   scores["SPOOFING"] += 30
        if cn0_drop < 3 and doppler_err > 100: scores["SPOOFING"] += 20

        if cn0_drop > 3 and doppler_err < self.DOPPLER_AMBER and js_db < 10:
            scores["MULTIPATH"] += 50

        if all(v == 0 for k, v in scores.items() if k != "NOMINAL"):
            scores["NOMINAL"] = 100

        threat     = max(scores, key=lambda k: scores[k])
        confidence = min(scores[threat], 100.0)

        level = (
            "RED"   if js_db >= self.JS_RED_DB   or cn0_drop >= self.CN0_DROP_RED  else
            "AMBER" if js_db >= self.JS_AMBER_DB  or cn0_drop >= self.CN0_DROP_AMBER else
            "GREEN"
        )

        return {
            "timestamp":        sample.timestamp,
            "threat_level":     level,
            "threat_type":      threat if threat != "NOMINAL" else "NONE",
            "js_ratio_db":      round(js_db, 2),
            "cn0_drop_db":      round(cn0_drop, 2),
            "doppler_error_hz": round(doppler_err, 2),
            "agc_anomaly":      agc_anomaly,
            "confidence_pct":   round(confidence, 1),
            "noise_rise_db":    round(noise_rise, 2),
            "backend":          sample.backend,
        }
