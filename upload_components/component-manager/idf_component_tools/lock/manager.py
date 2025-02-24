import os
from collections import OrderedDict
from io import open

from schema import And, Optional, Or, Schema, SchemaError
from six import string_types
from yaml import Dumper, YAMLError
from yaml import dump as dump_yaml
from yaml import safe_load

import idf_component_tools as tools

from ..errors import LockError
from ..manifest import SolvedManifest

FORMAT_VERSION = '1.0.0'

EMPTY_LOCK = {
    'manifest_hash': None,
    'version': FORMAT_VERSION,
}

HASH_SCHEMA = Or(And(Or(*string_types), lambda h: len(h) == 64), None)

LOCK_SCHEMA = Schema(
    {
        Optional('dependencies'): {
            Optional(Or(*string_types)): {
                'source': Or(*[source.schema() for source in tools.sources.KNOWN_SOURCES]),
                'version': Or(*string_types),
                Optional('component_hash'): HASH_SCHEMA,
            }
        },
        'manifest_hash': HASH_SCHEMA,
        'version': And(Or(*string_types), len),
    })


def _ordered_dict_representer(dumper, data):  # type: (Dumper, OrderedDict) -> Dumper
    return dumper.represent_data(dict(data))


Dumper.add_representer(OrderedDict, _ordered_dict_representer)


class LockManager:
    def __init__(self, path):
        self._path = path

    def exists(self):
        return os.path.isfile(self._path)

    def dump(self, solution):  # type: (SolvedManifest) -> None
        """Writes updated lockfile to disk"""

        try:
            with open(self._path, mode='w', encoding='utf-8') as f:
                # inject format version
                solution_dict = solution.serialize()
                solution_dict['version'] = FORMAT_VERSION
                lock = LOCK_SCHEMA.validate(solution_dict)
                dump_yaml(data=lock, stream=f, encoding='utf-8', allow_unicode=True, Dumper=Dumper)
        except SchemaError as e:
            raise LockError('Lock format is not valid:\n%s' % str(e))

    def load(self):  # type: () -> SolvedManifest
        if not self.exists():
            return SolvedManifest.fromdict(EMPTY_LOCK)

        with open(self._path, mode='r', encoding='utf-8') as f:
            try:
                content = f.read()

                if not content:
                    return SolvedManifest.fromdict(EMPTY_LOCK)

                lock = LOCK_SCHEMA.validate(safe_load(content))

                version = lock.pop('version')
                if version != FORMAT_VERSION:
                    raise LockError(
                        'Cannot parse components lock file.'
                        'Lock file format version is %s, while only %s is supported' % (version, FORMAT_VERSION))

                return SolvedManifest.fromdict(lock)
            except (YAMLError, SchemaError):
                raise LockError(
                    (
                        'Cannot parse components lock file. Please check that\n\t%s\nis a valid lock YAML file.\n'
                        'You can delete corrupted lock file and it will be recreated on next run. '
                        'Some components may be updated in this case.') % self._path)
