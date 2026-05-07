from isolde_offline_optimizer.envs.base_env import IsoldeOfflineBaseEnv
from isolde_offline_optimizer import utils as utl
from pathlib import Path

from cernml import coi
import numpy as np


class IsoldeOfflineEnv(IsoldeOfflineBaseEnv):
    _env_name = "IsoldeOffline2Env"
    _facility = "YOL2"
    _data_dir = Path(f"./{_facility}/")

    def _detector_subscriptions(self) -> dict[str, str]:
        """
        -> list[str]:

        return [
            "PSB.GPS.BSFH01.UCAP/Analysis",
            "PSB.GPS.BSFV01.UCAP/Analysis",
            "BTY.BCT213/Acquisition",
        ]"""
        return {
            "FC80": "YOFFL2.SPARE1/Acquisition",
            "FC100": "YOFFL2.FC100/Acquisition",
            "FC110": "YOFFL2.FC110/Acquisition",
            "FC190": "YOFFL2.FC190/Acquisition",
        }

    def _scanner_subscriptions(self) -> dict[str, str]:
        return {
            "BS70": "YOFFL2.BSC70/Acquisition",
            "BS100": "YOFFL2.BSC100/Acquisition",
            "BS170": "YOFFL2.BSC170/Acquisition",
        }

    def _setup_parameters(self) -> dict[str, utl.ParamConfig]:
        return {
            "DEH1": utl.ParamConfig(
                enabled=True,
                addr="YOL2.DEH1/Setting",
                scale=10.0,
                tolerance=0.5,
                units="A",
                bounds=(0., 250)
            ),
            "DEH2": utl.ParamConfig(
                enabled=True,
                addr="YOL2.DEH2/Setting",
                scale=10.0,
                tolerance=0.5,
                units="A",
                bounds=(0., 250)
            ),
            "DEV1": utl.ParamConfig(
                enabled=True,
                addr="YOL2.DEV1/Setting",
                scale=5.0,
                tolerance=0.5,
                units="A",
                bounds=(0., 250)
            ),
            "DEV2": utl.ParamConfig(
                enabled=True,
                addr="YOL2.DEV2/Setting",
                scale=5.0,
                tolerance=0.5,
                units="A",
                bounds=(0., 250)
            ),
            "QS110-B": utl.ParamConfig(
                enabled=False,
                addr="YOL2.QS110-B/Setting",
                scale=10.0,
                tolerance=0.5,
                units="A",
                bounds=(750, 3000)
            ),
            "QS110-T": utl.ParamConfig(
                enabled=False,
                addr="YOL2.QS110-T/Setting",
                scale=10.0,
                tolerance=0.5,
                units="A",
                bounds=(750, 3000)
            ),
            "QS110-L": utl.ParamConfig(
                enabled=False,
                addr="YOL2.QS110-L/Setting",
                scale=5.0,
                tolerance=0.5,
                units="A",
                bounds=(750, 3000)
            ),
            "QS110-R": utl.ParamConfig(
                enabled=False,
                addr="YOL2.QS110-R/Setting",
                scale=5.0,
                tolerance=0.5,
                units="A",
                bounds=(750, 3000)
            ),
            "QP30": utl.ParamConfig(
                enabled=True,
                addr="YOL2.QP30/Setting",
                scale=10.0,
                tolerance=0.5,
                units="A",
                bounds=(750, 3000)
            ),
            "QP40": utl.ParamConfig(
                enabled=True,
                addr="YOL2.QP40/Setting",
                scale=100.0,
                tolerance=0.5,
                units="A",
                bounds=(750, 3000)
            ),
            "QP50": utl.ParamConfig(
                enabled=True,
                addr="YOL2.QP50/Setting",
                scale=5.0,
                tolerance=0.5,
                units="A",
                bounds=(750, 3000)
            ),
            "QP100": utl.ParamConfig(
                enabled=False,
                addr="YOL2.QP100/Setting",
                scale=5.0,
                tolerance=0.5,
                units="A",
                bounds=(750, 3000)
            ),
            "QP120": utl.ParamConfig(
                enabled=False,
                addr="YOL2.QP120/Setting",
                scale=5.0,
                tolerance=0.5,
                units="A",
                bounds=(750, 3000)
            ),
            "QP130": utl.ParamConfig(
                enabled=False,
                addr="YOL2.QP130/Setting",
                scale=5.0,
                tolerance=0.5,
                units="A",
                bounds=(750, 3000)
            ),
        }

coi.register("IsoldeOfflineEnv-v0", entry_point=IsoldeOfflineEnv)

