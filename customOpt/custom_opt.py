import logging
import typing as t
from dataclasses import dataclass
from abc import ABCMeta, abstractmethod
from operator import index
from typing import Optional
import numpy as np
import torch
from botorch.acquisition import (
    LogExpectedImprovement,
    ExpectedImprovement,
    PosteriorStandardDeviation,
    UpperConfidenceBound,
    qNegIntegratedPosteriorVariance,
)
from botorch.fit import fit_gpytorch_mll
from botorch.models import SingleTaskGP
from botorch.models.transforms import Normalize, Standardize
from botorch.optim import optimize_acqf

from cernml import coi
from cernml import optimizers as opt
from cernml.coi import Constraint

from gpytorch.mlls import ExactMarginalLogLikelihood
from scipy.stats.qmc import LatinHypercube


logger = logging.getLogger(__name__)


@dataclass
class AcquisitionSelector:
    UCB: bool = True
    EI: bool = False
    QNIPV: bool = False
    PE: bool = False
    CEI: bool = False


class BaseOptimizer(
    opt.Optimizer,
    coi.Configurable,
    metaclass=ABCMeta,
):
    @abstractmethod
    def make_solve_func(self, bounds: opt.Bounds, constraints: t.Sequence[Constraint]) -> opt.Solve:
        """Create a new solve function.

        Subclasses of `Optimizer` should override this method. Users can
        call this method directly, or use the convenience wrapper
        `~cernml.optimizers.make_solve_func()`.

        Args:
            bounds: A named tuple of the lower and upper bound of the
                search space. Both are 1D arrays of the same length *N*.
            constraints: A list of soft constraints that the optimizer
                should uphold. See `~scipy.optimize.LinearConstraint`
                and `~scipy.optimize.NonlinearConstraint` for details.
        """

    @abstractmethod
    def get_config(self) -> coi.Config:
        """Return a declaration of configurable parameters."""

    @abstractmethod
    def apply_config(self, values: coi.ConfigValues) -> None:
        """Apply the configuration values to the optimizer."""


class BayesianModel:
    """
    Bayesian statistical model for finding the best next point to evaluate the objective function.
    It contains the Gaussian Process (GP) for modeling the objective function and the likelihood.
    Contains as well the implementation of the acquisition function to know where to sample next depending on the criterion.
    """

    Q: int = 1  # Number of points to query at a time
    NUM_RESTARTS: int = 5  # Number of restarts for the optimizer
    RAW_SAMPLES: int = 5  # Number of random samples for the optimizer

    def __init__(
        self,
        train_x: torch.Tensor,
        train_y: torch.Tensor,
        train_f: torch.Tensor,
        bounds: torch.Tensor,
        acquisition: str,
        beta: float,
        train_c: Optional[torch.Tensor] = None,
        taus: Optional[list[float]] = None,

    ) -> None:
        self.train_x = train_x
        self.train_y = train_y
        self.train_c = train_c
        self.train_f = train_f
        self.taus = taus
        self._bounds = bounds
        self._acquisition = acquisition
        self._beta = beta

    def get_candidate(self) -> torch.Tensor:
        """
        Optimize the acquisition function and return the next candidate point.
        The task is always a maximization task.
        """
        model = self.build_gp_model(train_x=self.train_x, train_y=self.train_y)
        fit_gpytorch_mll(ExactMarginalLogLikelihood(model.likelihood, model))

        if self._acquisition == "CEI":
            if self.train_c is None or self.taus is None:
                raise ValueError("CEI selected but no constraints or thresholds provided.")

            # Fit constraint models
            constraint_models = []
            for i in range(self.train_c.shape[1]):
                c_model = self.build_gp_model(
                    train_x=self.train_x,
                    train_y=self.train_c[:, i].unsqueeze(-1),
                )
                fit_gpytorch_mll(ExactMarginalLogLikelihood(c_model.likelihood, c_model))
                constraint_models.append(c_model)

            class ConstrainedEI(UpperConfidenceBound):#ExpectedImprovement
                #def __init__(self,model, best_f, maximize=True):
                #    super().__init__
                def forward(inner_self, X):
                    EI = super(ConstrainedEI, inner_self).forward(X)
                    constraint_probs = []
                    for i, gpr in enumerate(constraint_models):
                        gpr.eval()
                        with torch.no_grad():
                            post = gpr.posterior(X)
                            mu, sigma = post.mean, post.variance.sqrt()
                            prob = torch.distributions.Normal(mu, sigma).cdf(
                                torch.tensor([self.taus[i]])
                            )
                            constraint_probs.append(prob.view(-1))
                    total_prob = torch.ones_like(EI)
                    for p in constraint_probs:
                        total_prob *= p
                    return EI * total_prob

            if self.train_f.numel() == 0:
                self.train_f = np.array([[1.0]]).reshape(-1,1)
                self.train_f = torch.tensor(self.train_f, dtype=torch.float64)
            acq_fun = ConstrainedEI(model, beta=self._beta, maximize=False)#best_f=self.train_f.min()

        elif self._acquisition == "UCB":
                acq_fun = UpperConfidenceBound(model, beta=self._beta, maximize=True)
        elif self._acquisition == "EI":
            acq_fun = LogExpectedImprovement(model, best_f=self.train_y.min(), maximize=True)
        elif self._acquisition == "qNIPV":
            acq_fun = qNegIntegratedPosteriorVariance(model, X_baseline=self.train_x, maximize=True)
        elif self._acquisition == "PE":
            acq_fun = PosteriorStandardDeviation(model, maximize=True)
        else:
            msg = f"Invalid acquisition function: {self._acquisition}"
            raise ValueError(msg)

        candidate, _ = optimize_acqf(
            acq_function=acq_fun,
            bounds=self._bounds,
            q=self.Q,
            num_restarts=self.NUM_RESTARTS,
            raw_samples=self.RAW_SAMPLES,
        )
        return candidate

    # M.S.: adding train_x and train_y as arguments
    def build_gp_model(self, train_x, train_y) -> SingleTaskGP:
        """Build GP model with integrated scalers for in- and output."""
        outcome_transform = Standardize(m=1)
        outcome_transform.train()

        n_params = self._bounds.size(1)
        gp_model = SingleTaskGP(
            train_X=train_x,
            train_Y=train_y,
            input_transform=Normalize(d=n_params, bounds=self._bounds),
            outcome_transform=outcome_transform,
        )
        mll = ExactMarginalLogLikelihood(gp_model.likelihood, gp_model)
        fit_gpytorch_mll(mll)
        return gp_model

    def get_predictions(self, gp_model: SingleTaskGP, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Get predictions from GP model (mean and stddev)."""
        with torch.no_grad():
            posterior = gp_model.posterior(x)
            pred_mean = torch.tensor(posterior.mean)
            pred_stddev = torch.tensor(posterior.variance.sqrt())
        return pred_mean, pred_stddev


class BayesianOptimizer(BaseOptimizer):
    logger = logging.getLogger(__name__)

    # M.S.: Pass the env_cls argument which points to the COI environment
    #       class.
    def __init__(self) -> None:
        super().__init__()
        self._beta: float = 2.0
        self._n_init_samples: int = 1
        self._n_iterations: int = 5
        self._acqu_f: str = "CEI"

    def get_config(self) -> coi.Config:
        config = coi.Config()
        config.add("beta", self._beta, range=(0.1, 20), label="Beta value for UCB acquisition function")
        config.add("n_init_samples", self._n_init_samples, range=(1, 100), label="Number of initial samples")
        config.add("n_iterations", self._n_iterations, range=(1, 10000), label="Number of iterations")
        config.add(
            "acquisition_function",
            self._acqu_f,
            choices=["UCB", "EI", "qNIPV", "PE", "CEI"],
            label="Acquisition function",
        )
        return config

    def apply_config(self, values: coi.ConfigValues) -> None:
        self._beta = values.beta
        self._n_init_samples = values.n_init_samples
        self._n_iterations = values.n_iterations
        self._acqu_f = values.acquisition_function

    def make_solve_func(
        self, bounds: tuple[np.ndarray, np.ndarray], constraints: t.Sequence[coi.Constraint]
    ) -> opt.Solve:
        # Initialize the Bayesian model
        n_params = bounds[0].shape[0]
        lower_bounds = -np.ones(n_params)
        upper_bounds = np.ones(n_params)
        param_bounds = torch.tensor(np.vstack([lower_bounds, upper_bounds]), dtype=torch.float64)

        def solve(objective: opt.Objective, initial: np.ndarray) -> opt.OptimizeResult:
            # Sample the initial n_initial_samples points
            print("Number of initial combinations", n_params)
            lh_sampler = LatinHypercube(d=n_params)

            # Order: deh1, deh2, dev1, dev2, qp30, qp40, qp50
            #samples = np.array([[0.0, 0.08, 0.0, 0.8, 0.1221, 0.0729, 0.6462]])#good starting beam 0.0, 0.036, 0.559, 0.53, 0.226, 0.087, 0.607
            samples: np.ndarray = lh_sampler.random(n=self._n_init_samples)  # Samples in [0, 1]
            #samples: np.ndarray = lh_sampler.random(n=1)  #
            x_init = 2.0 * samples - 1.0  # Scale to [-1, 1] (coi env bounds)

            # Compute the objective for all the respective initial points
            y_init = np.zeros([self._n_init_samples])
            print("initial y_init", y_init)
            y_feas_init = np.array([])
            x_trainf = np.array([[]])
            print("initial parameters", x_init)
            valid_index = []
            constraints_init = []
            for i in range(self._n_init_samples):
                obj_val, info_dict = objective(x_init[i, :])
                #train_X or everything with X is for the deflection plates and quads voltages
                #y_train or everything related to y is the objectvie you are maximizing (for current is the FC measurement)
                #check iof there is a new FC_constant
                y_init[i] = obj_val
                # if new scale constant fc_scale
                #   y_init = y_init*fc_scale/fc_scale_old
                print("obj_val, info_dict: ", obj_val, info_dict)
                # M.S.: atm. just passing random array of floats hence, cannot
                #       call on x_init[i, :]. What is the actual form of a
                #       constraint - a callable?
                #       N.B.: call constraints_values since otherwise might run into
                #       issues with the originally defined constraints variable
                #       in this scope.
                constraints_values = info_dict["constraints"] #replace with info_dict[key]
                constraints_init.append(np.float_(constraints_values))
                if (np.array(constraints_init[i])  <= info_dict["taus"]).all():
                    valid_index.append(i)
                if len(constraints_values) != len(constraints_values):
                    raise ValueError(
                        "Length of constraints array does not correspond to "
                        "number of constraints defined in optimizer."
                    )
                print(f'solve -- {constraints_values=}')

            # Build initial model on init data
            print("I just finish initializing")
            train_x = torch.tensor(x_init, dtype=torch.float64)
            y_init = y_init.reshape(-1, 1)
            y_feas_init = y_init[valid_index]
            y_feas_init = y_feas_init.reshape(-1, 1)
            x_trainf = x_init[valid_index]
            #x_trainf = x_trainf.reshape(1,-1)
            train_y = torch.tensor(y_init, dtype=torch.float64)
            trainx_f =  torch.tensor(x_trainf, dtype=torch.float64)
            train_f = torch.tensor(y_feas_init, dtype=torch.float64)
            train_c = torch.tensor(constraints_init, dtype=torch.float64)
            '''print("train_x: ", train_x)
            print("train_y: ", train_y)
            print("train_c: ", train_c)
            print("train_f: ", train_f)'''

            for _i in range(self._n_iterations):
                model = BayesianModel(
                    train_x=train_x,
                    train_y=train_y,
                    train_f=train_f,
                    bounds=param_bounds,
                    acquisition=self._acqu_f,
                    beta=self._beta,
                    train_c=train_c if len(info_dict["constraints"]) > 0 else None,
                    taus=info_dict["taus"] if len(info_dict["constraints"]) > 0 else None,
                )
                next_x = model.get_candidate()
                next_x = np.clip(next_x, a_min=lower_bounds, a_max=upper_bounds)
                print("next x", next_x)
                obj_val, info_dict = objective(next_x.flatten().numpy())
                constraints_values = info_dict["constraints"]
                new_y = torch.tensor([obj_val], dtype=torch.float64).unsqueeze(-1)
                new_c = torch.tensor([constraints_values], dtype=torch.float64)
                #print(new_c)
                print([constraints_values] )
                is_feas = False
                if ([constraints_values]  <= info_dict["taus"]).all():
                    train_f = torch.cat([train_f, new_y], dim=0)
                    trainx_f = torch.cat([trainx_f, next_x], dim=0)
                    is_feas = True
                print("Feasible solution? ", is_feas)
                print("train_feas", trainx_f, train_f)
                train_x = torch.cat([train_x, next_x], dim=0)
                train_y = torch.cat([train_y, new_y], dim=0)
                train_c = torch.cat([train_c, new_c], dim=0)
                # if new scale constant fc_scale
                # train_f  = train_f *fc_scale/fc_scale_old
                # train_y  = train_y *fc_scale/fc_scale_old


            if train_f.numpy().size != 0:
                argmin = np.argmin(train_f)
                x_opt = trainx_f[argmin, :]
                y_opt = train_f[argmin]
                print("Optimal solution (original): ", x_opt, y_opt)
                obj_val, info_dict = objective(x_opt.flatten().numpy())
                print("Optimal solution (new): ", x_opt, obj_val)
                next_x = x_opt
                new_y = obj_val
            else:
                print("Non optimal solution that fulfill the constraints was found ")

            return opt.OptimizeResult(
                x=next_x.flatten().numpy(), #x_opt.numpy()
                fun=float(new_y), #y_opt
                success=True,
                message="",
                nit=self._n_iterations,
                nfev=self._n_init_samples + self._n_iterations,
            )



        return solve
