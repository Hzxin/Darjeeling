# -*- coding: utf-8 -*-
__all__ = ('CoveragePyCollector', 'CoveragePyCollectorConfig')

from typing import Any, ClassVar, Dict, Mapping, Optional, Set
import json
import typing

import attr

from .collector import CoverageCollector, CoverageCollectorConfig
from ..core import FileLineSet

if typing.TYPE_CHECKING:
    from ..container import ProgramContainer
    from ..environment import Environment
    from ..program import ProgramDescription


@attr.s(frozen=True)
class CoveragePyCollectorConfig(CoverageCollectorConfig):
    NAME: ClassVar[str] = 'coverage.py'

    @classmethod
    def from_dict(cls,
                  dict_: Mapping[str, Any],
                  dir_: Optional[str] = None
                  ) -> 'CoverageCollectorConfig':
        assert dict_['type'] == cls.NAME
        return CoveragePyCollectorConfig()

    def build(self,
              environment: 'Environment',
              program: 'ProgramDescription'
              ) -> 'CoverageCollector':
        return CoveragePyCollector(program=program)


@attr.s(frozen=True, slots=True, auto_attribs=True)
class CoveragePyCollector(CoverageCollector):
    program: 'ProgramDescription'

    def _read_report_json(self, json_: Mapping[str, Any]) -> FileLineSet:
        filename_to_lines: Dict[str, Set[int]] = {}
        filename_to_json_report = json_['files']
        for filename, file_json in filename_to_json_report.items():
            filename_to_lines[filename] = set(file_json['executed_lines'])
        return FileLineSet(filename_to_lines)

    def _read_report_text(self, text: str) -> FileLineSet:
        json_ = json.loads(text)
        return self._read_report_json(json_)

    def _extract(self, container: 'ProgramContainer') -> FileLineSet:
        files = container.filesystem
        shell = container.shell
        temporary_filename = files.mktemp()
        pyenv_python_path = '/opt/pyenv/versions/temp/bin/python'
        # Check pyenv path
        check_bm_cmd = "test -e /opt/pyenv/versions/temp"
        pyenv_outcome =  shell.run(check_bm_cmd,
                                      cwd=self.program.source_directory,
                                      stdout=True,
                                      stderr=True)
        if pyenv_outcome.returncode == 0:
            # Omit system deps/files
            command = (f'{pyenv_python_path} -m coverage json -o {temporary_filename} --omit="tests/*,test/*,/opt/pyenv/*" && coverage erase')
        else:
            command = (f'coverage json -o {temporary_filename} --omit="tests/*" && coverage erase')
        shell.check_output(command, cwd=self.program.source_directory)
        report_text = files.read(temporary_filename)
        return self._read_report_text(report_text)
