from dataclasses import dataclass
import numpy as np
import typing as t

@dataclass
class ParamConfig:
    """Configuration for a single parameter in the optimization.

    Attributes:
        enabled: Whether this parameter is enabled for optimization
        addr: parameter address
        scale: Scaling factor for parameter values
        tolerance: Tolerance for parameter convergence
        units: units of parameter value
    """

    enabled: bool
    addr: str
    scale: float
    tolerance: float
    units: str
    bounds: t.Tuple = (-np.inf, np.inf)
