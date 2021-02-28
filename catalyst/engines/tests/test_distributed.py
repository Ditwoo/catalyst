# flake8: noqa

from typing import Any, Dict, List
import logging
import os
from tempfile import TemporaryDirectory

from pytest import mark
import torch
from torch.utils.data import DataLoader

from catalyst.callbacks import CheckpointCallback, CriterionCallback, OptimizerCallback
from catalyst.core.callback import Callback, CallbackOrder
from catalyst.core.runner import IRunner
from catalyst.runners.config import SupervisedConfigRunner
from catalyst.engines import DistributedDataParallelEngine
from catalyst.engines.device import DeviceEngine
from catalyst.loggers import ConsoleLogger, CSVLogger
from catalyst.settings import IS_CUDA_AVAILABLE, NUM_CUDA_DEVICES

from .misc import DummyDataset, DummyModel, LossMinimizationCallback, WorldSizeCheckCallback

logger = logging.getLogger(__name__)

if NUM_CUDA_DEVICES > 1:
    os.environ["MKL_SERVICE_FORCE_INTEL"] = "1"


class CustomExperiment(IRunner):
    def __init__(self, logdir):
        super().__init__()
        self._logdir = logdir

    def get_engine(self):
        return DistributedDataParallelEngine()

    def get_callbacks(self, stage: str) -> Dict[str, Callback]:
        return {
            "criterion": CriterionCallback(metric_key="loss", input_key="logits", target_key="targets"),
            "optimizer": OptimizerCallback(metric_key="loss"),
            # "scheduler": dl.SchedulerCallback(loader_key="valid", metric_key="loss"),
            # "checkpoint": dl.CheckpointCallback(
            #     self._logdir, loader_key="valid", metric_key="loss", minimize=True, save_n_best=3
            # ),
            # "check": DeviceCheckCallback(),
            "check2": LossMinimizationCallback("loss", logger=logger),
            "check_world_size": WorldSizeCheckCallback(NUM_CUDA_DEVICES, logger=logger),
        }

    @property
    def stages(self) -> "Iterable[str]":
        return ["train"]

    def get_stage_len(self, stage: str) -> int:
        return 10

    def get_loaders(self, stage: str, epoch: int = None) -> Dict[str, Any]:
        dataset = DummyDataset(6)
        loader = DataLoader(dataset, batch_size=4)
        return {"train": loader, "valid": loader}

    def get_model(self, stage: str):
        return DummyModel(4, 2)

    def get_criterion(self, stage: str):
        return torch.nn.MSELoss()

    def get_optimizer(self, model, stage: str):
        return torch.optim.Adam(model.parameters())

    def get_scheduler(self, optimizer, stage: str):
        return None

    def get_trial(self):
        return None

    def get_loggers(self):
        return {"console": ConsoleLogger(), "csv": CSVLogger(logdir=self._logdir)}

    def handle_batch(self, batch):
        x, y = batch
        logits = self.model(x)

        self.batch = {"features": x, "targets": y, "logits": logits}


@mark.skipif(
    not IS_CUDA_AVAILABLE and NUM_CUDA_DEVICES < 2, reason="Number of CUDA devices is less than 2",
)
def test_ddp_engine():
    with TemporaryDirectory() as logdir:
        runner = CustomExperiment(logdir)
        runner.run()


class MyConfigRunner(SupervisedConfigRunner):
    _dataset = DummyDataset(6)

    def get_datasets(self, *args, **kwargs):
        return {"train": self._dataset, "valid": self._dataset}


# @mark.skip("Config experiment is in development phase!")
@mark.skipif(
    not IS_CUDA_AVAILABLE and NUM_CUDA_DEVICES < 2, reason="Number of CUDA devices is less than 2",
)
def test_config_ddp_engine():
    device = "ddp"
    with TemporaryDirectory() as logdir:
        runner = MyConfigRunner(
            config={
                "args": {"logdir": logdir},
                "model": {"_target_": "DummyModel", "in_features": 4, "out_features": 2},
                "engine": {"engine": device},
                "args": {"logdir": logdir},
                "stages": {
                    "stage1": {
                        "num_epochs": 10,
                        "loaders": {"batch_size": 4, "num_workers": 0},
                        "criterion": {"_target_": "MSELoss"},
                        "optimizer": {"_target_": "Adam", "lr": 1e-3},
                        "callbacks": {
                            "criterion": {
                                "_target_": "CriterionCallback",
                                "metric_key": "loss",
                                "input_key": "logits",
                                "target_key": "targets",
                            },
                            "optimizer": {"_target_": "OptimizerCallback", "metric_key": "loss"},
                            # "test_device": {"_target_": "DeviceCheckCallback", "assert_device": device},
                            "test_loss_minimization": {"_target_": "LossMinimizationCallback", "key": "loss"},
                            "check_world_size": {
                                "_target_": "WorldSizeCheckCallback",
                                "assert_world_size": NUM_CUDA_DEVICES,
                            },
                        },
                    },
                },
            }
        )
        runner.run()
