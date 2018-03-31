from typing import Iterable, Iterator
from timeit import default_timer as timer
import datetime
import threading

import bugzoo

from .candidate import Candidate
from .problem import Problem


__ALL__ = ['Searcher']


class Searcher(object):
    def __init__(self,
                 bugzoo: bugzoo.BugZoo,
                 problem: Problem,
                 candidates: Iterable[Candidate],
                 *,
                 threads: int = 1,
                 time_limit: Optional[timedelta] = None
                 ) -> None:
        """
        Constructs a new searcher for a given source of candidate patches.

        Parameters:
            problem: a description of the problem.
            candidates: a source of candidate patches.
            threads: the number of threads that should be made available to
                the search process.
            time_limit: an optional limit on the amount of time given to the
                searcher.
        """
        assert time_limit is None or time_limit > 0, \
            "if specified, time limit should be greater than zero."

        self.__bugzoo = bugzoo
        self.__problem = problem
        self.__candidates = candidates
        self.__time_limit = time_limit
        self.__num_threads = threads

        # records the time at which the current iteration begun
        self.__time_iteration_begun = None

        self.__lock_candidates = threading.Lock() # type: threading.Lock
        self.__counter_candidates = 0
        self.__counter_tests = 0
        self.__exhausted_candidates = False
        self.__time_running = datetime.timedelta()
        self.__error_occurred = False
        self.__next_patch = None

    @property
    def paused(self) -> bool:
        """
        Indicates whether this searcher is paused.
        """
        return self.__paused or self.exhausted

    @property
    def exhausted(self) -> bool:
        """
        Indicates whether or not the resources available to this searcher have
        been exhausted.
        """
        if self.__error_occurred:
            return True
        if self.__exhausted_candidates:
            return True
        if self.__time_limit is None:
            return False
        return self.time_running > self.time_limit

    @property
    def time_limit(self) -> Optional[datetime.timedelta]:
        """
        An optional limit on the length of time that may be spent searching
        for patches.
        """
        return self.__time_limit

    @property
    def time_running(self) -> datetime.timedelta:
        """
        The amount of time that has been spent searching for patches.
        """
        duration_iteration = timer() - self.__time_start_iteration
        return self.__time_running + duration_iteration

    def __iter__(self) -> Iterator[Candidate]:
        return self

    def __next__(self) -> Candidate:
        """
        Searches for the next acceptable patch.

        Returns:
            the next patch that passes all tests.

        Raises:
            StopIteration: if the search space or available resources have
                been exhausted.
        """
        self.__time_iteration_begun = timer()
        threads = []

        # TODO there's a bit of a bug: any patches that were read from the
        #   generator by the worker and were still stored in its
        #   `candidate` variable will be discarded. fixable by adding a
        #   buffer to `_try_next`.
        try:
            def worker(searcher: 'Searcher') -> None:
                while True:
                    if not searcher._try_next():
                        break

            for _ in range(self.__num_threads):
                t = threading.Thread(target=worker, args=(self,), daemon=True)
                threads.append(t)
                t.start()
        except:
            self.__error_occurred = True
        finally:
            # TODO this is bad -- use while instead
            for worker in workers:
                worker.join()

        duration_iteration = timer() - self.__time_start_iteration
        self.__time_running += duration_iteration

        # if we have a patch, return it
        if self.__next_patch:
            self.__next_patch = None
            return self.__next_patch

        # if not, we're done
        raise StopIteration

    def _try_next(self) -> bool:
        """
        Evaluates the next candidate patch.

        Returns:
            a boolean indicating whether the calling thread should continue to
            evaluate candidate patches.
        """
        # TODO have we run out of precious resources?
        if self.paused:
            return False

        self.__lock_candidates.acquire()
        try:
            candidate = next(self.__candidates)
        except StopIteration:
            print("exhausted all candidate patches!")
            self.__exhausted_candidates = True
            return False
        finally:
            self.__lock_candidates.release()

        print("Evaluating: {}".format(candidate))
        self.__counter_candidates += 1
        bz = self.__bugzoo
        container = bz.containers.provision(self.__problem.bug)
        try:
            patch = candidate.diff(self.__problem)
            bz.containers.patch(container, patch)

            # ensure that the patch compiles
            if not bz.containers.compile(container).successful:
                print("Failed to compile: {}".format(candidate))
                return True

            # for now, execute all tests in no particular order
            # TODO perform test ordering
            for test in self.problem.tests:
                print("Executing test: {} ({})".format(test.name, candidate))
                self.__counter_tests += 1
                outcome = bz.containers.execute(container, test)
                if not outcome.passed:
                    print("Failed test: {} ({})".format(test.name, candidate))
                    return True
                print("Passed test: {} ({})".format(test.name, candidate))

            # FIXME possible race condition if two workers report repairs at
            #   the same time?
            # if we've found a repair, pause the search
            self.__next_patch = candidate
            diff = candidate.diff(self.problem)

            # TODO make this prettier
            # report the patch
            time_repair = self.time_running.seconds / 60.0
            msg = "FOUND REPAIR [{:.2f} minutes]: {}\n{}\n{}\n{}"
            msg = msg.format(time_repair, candidate, ("=" * 80), diff, ("="*80))
            print(msg)

            return True

        finally:
            print("Evaluated: {}".format(candidate))
            if container:
                del bz.containers[container.uid]