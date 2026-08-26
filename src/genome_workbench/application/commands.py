"""Undo/redo command objects and stack. Pure Python — no Qt dependency, so it
is fully unit-testable and can be wrapped by a QUndoCommand adapter in the UI
layer without duplicating logic.
"""

from __future__ import annotations

from typing import Protocol

from genome_workbench.domain.models import Feature
from genome_workbench.infrastructure.persistence.sqlite_repository import ProjectRepository


class Command(Protocol):
    description: str

    def do(self) -> None: ...
    def undo(self) -> None: ...


class FeatureCreateCommand:
    description = "Create feature"

    def __init__(self, repo: ProjectRepository, feature: Feature) -> None:
        self._repo = repo
        self._feature = feature
        self.description = f"Create {feature.type} feature"

    def do(self) -> None:
        self._repo.save_feature(self._feature)

    def undo(self) -> None:
        self._repo.delete_feature(self._feature.id)


class FeatureUpdateCommand:
    def __init__(self, repo: ProjectRepository, before: Feature, after: Feature) -> None:
        self._repo = repo
        self._before = before
        self._after = after
        self.description = f"Edit {after.type} feature"

    def do(self) -> None:
        self._repo.save_feature(self._after)

    def undo(self) -> None:
        self._repo.save_feature(self._before)


class FeatureDeleteCommand:
    def __init__(self, repo: ProjectRepository, feature: Feature) -> None:
        self._repo = repo
        self._feature = feature
        self.description = f"Delete {feature.type} feature"

    def do(self) -> None:
        self._repo.delete_feature(self._feature.id)

    def undo(self) -> None:
        self._repo.save_feature(self._feature)


class BatchCommand:
    """Groups several commands into one undo/redo step (e.g. a batch
    qualifier edit applied to many features at once) -- Ctrl+Z undoes the
    whole batch in one press, not one feature at a time."""

    def __init__(self, commands: list[Command], description: str) -> None:
        self._commands = commands
        self.description = description

    def do(self) -> None:
        for command in self._commands:
            command.do()

    def undo(self) -> None:
        for command in reversed(self._commands):
            command.undo()


class UndoStack:
    def __init__(self) -> None:
        self._undo_history: list[Command] = []
        self._redo_history: list[Command] = []

    def push(self, command: Command) -> None:
        command.do()
        self._undo_history.append(command)
        self._redo_history.clear()

    def undo(self) -> bool:
        if not self._undo_history:
            return False
        command = self._undo_history.pop()
        command.undo()
        self._redo_history.append(command)
        return True

    def redo(self) -> bool:
        if not self._redo_history:
            return False
        command = self._redo_history.pop()
        command.do()
        self._undo_history.append(command)
        return True

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_history)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_history)

    def clear(self) -> None:
        self._undo_history.clear()
        self._redo_history.clear()
