import numpy as np
import pyda_japc
import pyda
from isolde_offline_optimizer.utils.utils_pjlsa import set_scalar

_japc_provider = pyda_japc.JapcProvider()

pyda_client = pyda.SimpleClient(provider=_japc_provider)

def _is_valid_beam_scanner(bsc_addr) -> None:
    """Starts the beam scanner"""
    bsc_addr = bsc_addr.replace("Acquisition", "StartMotor#startMotor")
    set_scalar(bsc_addr, 1)

def _get_bsc_sensitivity(bsc_addr, selector):
    bsc_addr = bsc_addr.replace("Acquisition", "Setting")
    event = pyda_client.get(endpoint=bsc_addr, context=selector)
    return event.data["sensitivity"]

def constraint_in_ws(mu, sig):
    con = (np.abs(mu) + sig) - 17
    if con > 17:
        con = 17
    elif con < -17:
        con = -17
    return con

def constraint_size(sig):
    con = sig - 10
    if con > 0:
        con = 0
    elif con < -10:
        con = -10
    return con