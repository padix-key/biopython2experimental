# This source code is part of the Biotite package and is distributed
# under the 3-Clause BSD License. Please see 'LICENSE.rst' for further
# information.

from typing import Callable
from enum import IntEnum
from abc import abstractmethod


def requires_state(app_state: int) -> Callable[[Callable], Callable]: ...


class AppState(IntEnum):
    CREATED = 1
    RUNNING = 2
    FINISHED = 4
    JOINED = 8
    CANCELLED = 16


class Application:
    def __init__(self) -> None: ...
    def start(self) -> None: ...
    def join(self, timeout: float = None) -> None: ...
    def cancel(self) -> None: ...
    def get_app_state(self) -> AppState: ...
    @abstractmethod
    def run(self) -> None: ...
    @abstractmethod
    def is_finished(self) -> bool: ...
    @abstractmethod
    def wait_interval(self) -> float: ...
    @abstractmethod
    def evaluate(self) -> None: ...
    def clean_up(self) -> None: ...
