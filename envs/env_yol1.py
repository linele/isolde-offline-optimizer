from isolde_offline_optimizer.envs.base_env import IsoldeOfflineBaseEnv
from isolde_offline_optimizer import utils as utl
from pathlib import Path

from cernml import coi

class IsoldeOfflineEnv(IsoldeOfflineBaseEnv):

    def _detector_subscriptions(self) -> dict[str, str]:
        _env_name = "IsoldeOffline1Env"
        _facility = "YOL1"
        _data_dir = Path(f"./{_facility}/")

        return {
            "FC120": "YOL1.FC120/Acquisition",
            "FC350": "YOL1.FC350/Acquisition",
        }

    def _scanner_subscriptions(self) -> dict[str, str]:
        return {
            "BS330": "YOFFL1.BSC330/Acquisition",
        }

    def _setup_parameters(self) -> dict[str, utl.ParamConfig]:
        return {
            "EINZEL": utl.ParamConfig(
                enabled=True,
                addr="yol.ht-einzel/Setting",
                scale=1000.0,
                tolerance=0.5,
                units="A",
                bounds=(9000, 20000)
            ),
            "DEFL": utl.ParamConfig(
                enabled=True,
                addr="yol.dev2/Setting",
                scale=100.0,
                tolerance=0.5,
                units="A",
                bounds=(0, 500)
            ),
            "DEH1": utl.ParamConfig(
                enabled=True,
                addr="yol.deh1/Setting",
                scale=100.0,
                tolerance=0.5,
                units="A",
                bounds=(0., 500)
            ),
            "DEH2": utl.ParamConfig(
                enabled=True,
                addr="yol.deh2/Setting",
                scale=100.0,
                tolerance=0.5,
                units="A",
                bounds=(0., 500)
            ),
            "DEV1": utl.ParamConfig(
                enabled=True,
                addr="yol.dev1/Setting",
                scale=100.0,
                tolerance=0.5,
                units="A",
                bounds=(0., 500)
            ),
            "DEV2": utl.ParamConfig(
                enabled=True,
                addr="yol.dev2/Setting",
                scale=100.0,
                tolerance=0.5,
                units="A",
                bounds=(0, 500)
            ),
            "ANODE1": utl.ParamConfig(
                enabled=True,
                addr="yol.anode1/Setting",
                scale=100.0,
                tolerance=0.5,
                units="A",
                bounds=(0, 500)
            ),
            "ANODE2": utl.ParamConfig(
                enabled=True,
                addr="yol.anode2/Setting",
                scale=100.0,
                tolerance=0.5,
                units="A",
                bounds=(0, 500)
            ),
            "ANODE3": utl.ParamConfig(
                enabled=True,
                addr="YOL.ANODE3/Setting",
                scale=100.0,
                tolerance=0.5,
                units="A",
                bounds=(0, 500)
            ),
            "YOL.MAGNET": utl.ParamConfig(
                enabled=True,
                addr="yol.magnet/Setting",
                scale=100.0,
                tolerance=0.5,
                units="A",
                bounds=(0, 500)
            ),
        }

coi.register("IsoldeOfflineEnv-v0", entry_point=IsoldeOfflineEnv)