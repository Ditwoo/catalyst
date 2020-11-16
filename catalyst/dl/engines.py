import torch
import torch.nn as nn
from catalyst.core.engine import IEngine
from typing import Mapping, Any


class DeviceEngine(IEngine):
    def __init__(self, device: str = "cpu"):
        self.device = device

    def process_model(self, model_fn: callable):
        model = model_fn()
        return model.to(self.device)

    def process_criterion(self, criterion_fn: callable):
        criterion = criterion_fn()
        return criterion.to(self.device)

    def process_optimizer(self, optimizer_fn: callable, model: nn.Module):
        optimizer = optimizer_fn(model.parameters())
        return optimizer

    def process_scheduler(self, scheduler_fn: callable, optimizer: nn.Module):
        scheduler = scheduler_fn(optimizer)
        return scheduler

    def handle_device(self, batch: Mapping[str, Any]):
        if isinstance(batch, torch.Tensor):
            return batch.to(self.device)
        elif isinstance(batch, (tuple, list)):
            return [self.handle_device(tensor) for tensor in batch]
        elif isinstance(batch, dict):
            return {
                key: self.handle_device(tensor)
                for key, tensor in batch.items()
            }
        return batch

    def save_checkpoint(
        self, checkpoint_content: Mapping[str, Any], file: str
    ):
        torch.save(checkpoint_content, file)

    def load_checkpoint(
        self,
        file: str,
        model: nn.Module,
        optimizer: nn.Module = None,
        criterion=None,
        scheduler=None,
    ):
        content = torch.load(file)

        if "model_state_dict" in content:
            model.load_state_dict(content["model_state_dict"])

        if "optimizer_state_dict" in content and optimizer is not None:
            optimizer.load_state_dict(content["optimizer_state_dict"])

        if "criterion_state_dict" in content and criterion is not None:
            criterion.load_state_dict(content["criterion_state_dict"])

        if "scheduler_state_dict" in content and scheduler is not None:
            scheduler.load_state_dict(content["scheduler_state_dict"])


class DistributedDeviveEngine(DeviceEngine):
    # TODO: maybe handle unpacking DataParallel to simple nn.Module

    def load_checkpoint(
        self,
        file: str,
        model: nn.DataParallel,
        optimizer: nn.Module = None,
        criterion=None,
        scheduler=None,
    ):
        content = torch.load(file)

        if "model_state_dict" in content:
            model.module.load_state_dict(content["model_state_dict"])

        if "optimizer_state_dict" in content and optimizer is not None:
            optimizer.load_state_dict(content["optimizer_state_dict"])

        if "criterion_state_dict" in content and criterion is not None:
            criterion.load_state_dict(content["criterion_state_dict"])

        if "scheduler_state_dict" in content and scheduler is not None:
            scheduler.load_state_dict(content["scheduler_state_dict"])
