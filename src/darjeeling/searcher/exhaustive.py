# -*- coding: utf-8 -*-
__all__ = ('ExhaustiveSearcher',)

from typing import Any, Dict, Iterable, Iterator, Optional
import typing
import os

from loguru import logger

from .base import Searcher
from .config import SearcherConfig
from ..candidate import Candidate
from ..resources import ResourceUsageTracker
from ..transformation import Transformation
from ..exceptions import SearchExhausted

if typing.TYPE_CHECKING:
    from ..problem import Problem
    from ..transformations import ProgramTransformations


class ExhaustiveSearcherConfig(SearcherConfig):
    """A configuration for exhaustive search."""
    NAME = 'exhaustive'

    def __repr__(self) -> str:
        return 'ExhaustiveSearcherConfig()'

    def __str__(self) -> str:
        return repr(self)

    @classmethod
    def from_dict(cls,
                  d: Dict[str, Any],
                  dir_: Optional[str] = None
                  ) -> 'SearcherConfig':
        return ExhaustiveSearcherConfig()

    def build(self,
              problem: 'Problem',
              resources: ResourceUsageTracker,
              transformations: 'ProgramTransformations',
              *,
              threads: int = 1,
              run_redundant_tests: bool = False,
              dump_all: bool = False,
              dir_patches: str = ""
              ) -> Searcher:
        return ExhaustiveSearcher(problem=problem,
                                  resources=resources,
                                  transformations=transformations,
                                  threads=threads,
                                  run_redundant_tests=run_redundant_tests,
                                  dump_all=dump_all,
                                  dir_patches=dir_patches)


class ExhaustiveSearcher(Searcher):
    def __init__(self,
                 problem: 'Problem',
                 resources: ResourceUsageTracker,
                 transformations: 'ProgramTransformations',
                 *,
                 threads: int = 1,
                 run_redundant_tests: bool = False,
                 dump_all: bool = False,
                 dir_patches: str = ""
                 ) -> None:
        # FIXME for now!
        self.__candidates = self.all_single_edit_patches(problem, transformations)
        super().__init__(problem=problem,
                         resources=resources,
                         threads=threads,
                         run_redundant_tests=run_redundant_tests,
                         dump_all=dump_all,
                         dir_patches=dir_patches)

    @staticmethod
    def all_single_edit_patches(problem: 'Problem',
                                transformations: Iterable[Transformation],
                                ) -> Iterator[Candidate]:
        """
        Returns an iterator over all of the single-edit patches that can be
        composed using a provided source of transformations.
        """
        logger.debug("finding all single-edit patches")
        for t in transformations:
            yield Candidate(problem, [t])
        logger.debug("exhausted all single-edit patches")

    def _generate(self) -> Candidate:
        try:
            logger.debug('generating candidate patch...')
            candidate = next(self.__candidates)
            logger.debug(f'generated candidate patch: {candidate}')
            return candidate
        except StopIteration:
            logger.debug('exhausted all candidate patches')
            raise SearchExhausted

    def run(self) -> Iterator[Candidate]:
        for _ in range(self.num_workers):
            candidate = self._generate()
            self.evaluate(candidate)
        index = 0
        for candidate, outcome in self.as_evaluated():
            index += 1
            if outcome.is_repair:
                logger.info('found plausible patch')
                self._save_patches_to_disk(candidate, index)
                yield candidate
            self.evaluate(self._generate())
    
    def _save_patches_to_disk(self, candidate, index) -> None:
        dir_patches = "/output/patches"
        os.makedirs(dir_patches, exist_ok=True)
        logger.debug("Getting patch diff")
        diff = str(candidate.to_diff())
        fn_patch = os.path.join(dir_patches, f'{index}temp.diff')
        try:
            logger.debug(f"writing patch to {fn_patch}")
            with open(fn_patch, 'w') as f:
                f.write(diff)
        except OSError:
            logger.exception(f"failed to write patch: {fn_patch}")
            raise
