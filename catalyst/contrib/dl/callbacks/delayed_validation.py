from collections import OrderedDict
from torch.utils.data import DataLoader
from typing import Mapping


from catalyst.core import Callback, CallbackNode, CallbackOrder, State


class DelayedValidationCallback(Callback):
    """A callback to run validation with some period."""

    def __init__(self, **kwargs):
        """
        Args:
            kwargs: expected loader names and periods to run loader.
        """
        super().__init__(order=CallbackOrder.Metric)
        self.loader_periods = {}
        self.loaders: Mapping[str, DataLoader] = OrderedDict()
        for loader, period in kwargs.items():
            if not isinstance(loader, str) or not isinstance(period, (int, float)):
                continue
            self.loader_periods[loader] = period

    def on_stage_start(self, state: State) -> None:
        """Collect information about loaders.

        Arguments:
            state (State): training state
        """
        for name, loader in state.loaders.items():
            self.loaders[name] = loader

    def on_epoch_start(self, state: State) -> None:
        """Set loaders for current epoch.

        Arguments:
            state (State): training state
        """
        epoch_num = state.epoch
        # loaders to use in current epoch
        new_loaders = OrderedDict()
        for name, loader in self.loaders.items():
            if epoch_num % self.loader_periods.get(name, 1) == 0:
                new_loaders[name] = loader
        state.loaders = new_loaders