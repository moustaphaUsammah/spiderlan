"""
SpiderLan :: GNSS Integrity Monitor
Standards: RTCA DO-229E, ICAO Annex 10, IS-GPS-200N
"""

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime, timezone


class IntegrityStatus(Enum):
    OK="OK"; CAUTION="CAUTION"; WARNING="WARNING"; FAULT="FAULT"

class Constellation(Enum):
    GPS="GPS"; GLONASS="GLONASS"; GALILEO="GALILEO"
    BEIDOU="BEIDOU"; STARLINK="STARLINK_PNT"


@dataclass
class SatObs:
    prn: int; constellation: Constellation
    elevation_deg: float; azimuth_deg: float
    pseudorange_m: float; cn0_db: float
    residual_m: float=0.0; excluded: bool=False


@dataclass
class NavSolution:
    timestamp: str; lat_deg: float; lon_deg: float; alt_m: float
    hdop: float; vdop: float
    hpl_m: float=0.0; vpl_m: float=0.0
    hal_m: float=40.0; val_m: float=50.0
    n_sats: int=0; status: IntegrityStatus=IntegrityStatus.OK
    excluded_prns: list=field(default_factory=list)
    starlink_delta_m: Optional[float]=None


class RAIMMonitor:
    SIGMA_URA=2.0; SIGMA_TROP=0.5; SIGMA_MP=0.3; SIGMA_NOISE=0.15
    CHI2={4:16.27,5:20.52,6:22.46,7:24.32,8:26.12,9:27.88,10:29.59,12:32.91,14:36.12}
    K_H=6.0; K_V=5.33

    def __init__(self, hal=40.0, val=50.0):
        self.hal=hal; self.val=val; self.history=[]

    def _sigma(self, el_deg):
        el = math.radians(max(el_deg, 5.0))
        return math.sqrt(self.SIGMA_URA**2 + self.SIGMA_TROP**2/math.sin(el)**2
                         + self.SIGMA_MP**2 + self.SIGMA_NOISE**2)

    def _residuals(self, obs):
        for o in obs:
            if o.residual_m == 0.0:
                o.residual_m = round(self._sigma(o.elevation_deg)*0.1, 3)
        return [o.residual_m for o in obs]

    def _chi2(self, res, obs):
        n = len(res)
        if n < 5: return 0.0, False
        ssr = sum((r/self._sigma(o.elevation_deg))**2 for r,o in zip(res,obs))
        thr = self.CHI2.get(n-4, 26.12)
        return round(ssr,3), ssr<thr

    def _fde(self, obs, res):
        sigmas  = [self._sigma(o.elevation_deg) for o in obs]
        nres    = [abs(r/s) for r,s in zip(res,sigmas)]
        idx     = max(range(len(nres)), key=lambda i: nres[i])
        prn     = obs[idx].prn
        rem_r   = [r for i,r in enumerate(res) if i!=idx]
        rem_o   = [o for i,o in enumerate(obs)  if i!=idx]
        _,ok    = self._chi2(rem_r, rem_o)
        return [prn], ok

    def _hpl_vpl(self, obs, sol):
        active  = [o for o in obs if not o.excluded]
        if not active: return 999.0,999.0
        avg_s   = sum(self._sigma(o.elevation_deg) for o in active)/len(active)
        return round(self.K_H*avg_s*max(sol.hdop,1.0),2), round(self.K_V*avg_s*max(sol.vdop,1.0),2)

    def run(self, obs, sol, starlink_pos=None):
        res       = self._residuals(obs)
        ssr, ok   = self._chi2(res, obs)
        excl=[]; fde_ok=False
        if not ok:
            excl, fde_ok = self._fde(obs, res)
            for o in obs:
                if o.prn in excl: o.excluded=True
        hpl,vpl = self._hpl_vpl(obs, sol)
        if not ok and not fde_ok: status=IntegrityStatus.FAULT
        elif hpl>self.hal or vpl>self.val: status=IntegrityStatus.WARNING
        elif hpl>self.hal*0.75 or vpl>self.val*0.75: status=IntegrityStatus.CAUTION
        else: status=IntegrityStatus.OK
        stk={"available":False}
        stk_delta=None
        if starlink_pos:
            R=6371000.0
            lat1=math.radians(sol.lat_deg); lat2=math.radians(starlink_pos["lat"])
            dlat=lat2-lat1; dlon=math.radians(starlink_pos["lon"]-sol.lon_deg)
            a=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
            stk_delta=round(R*2*math.asin(math.sqrt(max(a,0))),2)
            consistent=stk_delta<50.0
            stk={"available":True,"delta_m":stk_delta,"consistent":consistent}
            if stk_delta>100 and status==IntegrityStatus.OK:
                status=IntegrityStatus.CAUTION
        sol.hpl_m=hpl; sol.vpl_m=vpl; sol.status=status
        sol.excluded_prns=excl; sol.starlink_delta_m=stk_delta
        result={"timestamp":datetime.now(timezone.utc).isoformat(),"status":status.value,
                "hpl_m":hpl,"vpl_m":vpl,"hal_m":self.hal,"val_m":self.val,
                "raim_passed":ok,"chi2_statistic":ssr,"fde_triggered":not ok,
                "excluded_prns":excl,"n_sats":len(obs),"starlink_check":stk}
        self.history.append(result)
        return result
