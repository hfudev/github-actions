from abc import ABCMeta, abstractmethod

from schema import Optional, Or
from six import string_types

import idf_component_tools as tools
from idf_component_tools.manifest import ComponentWithVersions

from ..errors import SourceError

try:
    from typing import TYPE_CHECKING, Callable, Dict, List, Union

    if TYPE_CHECKING:
        from ..manifest import SolvedComponent
except ImportError:
    pass


class BaseSource(object):
    __metaclass__ = ABCMeta
    NAME = 'base'

    def __init__(self, source_details=None):  # type: (dict) -> None
        self._source_details = source_details or {}
        self._hash_key = None

        unknown_keys = [key for key in self._source_details.keys() if key not in self.known_keys()]
        if unknown_keys:
            raise SourceError('Unknown keys in dependency details: %s' % ', '.join(unknown_keys))

    def _hash_values(self):
        return (self.name, self.hash_key)

    def __eq__(self, other):
        return (self._hash_values() == other._hash_values() and self.name == other.name)

    def __hash__(self):
        return hash(self._hash_values())

    def __repr__(self):  # type: () -> str
        return '{}()'.format(type(self).__name__)

    @staticmethod
    def fromdict(name, details):  # type: (str, Dict) -> BaseSource
        '''Build component source by dct'''
        for source_class in tools.sources.KNOWN_SOURCES:
            source = source_class.build_if_me(name, details)

            if source:
                return source
            else:
                continue

        raise SourceError('Unknown source for component: %s' % name)

    @staticmethod
    def is_me(name, details):  # type: (str, Dict) -> bool
        return False

    @classmethod
    def required_keys(cls):
        return []

    @classmethod
    def optional_keys(cls):
        return []

    @classmethod
    def known_keys(cls):  # type: () -> List[str]
        """List of known details key"""
        return ['version', 'public'] + cls.required_keys() + cls.optional_keys()

    @classmethod
    def schema(cls):  # type: () -> Dict
        """Schema for lock file"""
        source_schema = {'type': cls.NAME}  # type: Dict[str, Union[str, Callable]]

        for key in cls.required_keys():
            source_schema[key] = Or(*string_types)

        for key in cls.optional_keys():
            source_schema[Optional(key)] = Or(*string_types)

        return source_schema

    @classmethod
    def build_if_me(cls, name, details):
        """Returns source if details are matched, otherwise returns None"""
        return cls(details) if cls.is_me(name, details) else None

    @property
    def source_details(self):
        return self._source_details

    @property
    def name(self):
        return self.NAME

    @property
    def hash_key(self):
        """Hash key is used for comparison sources initialised with different settings"""
        return 'Base'

    @property
    def component_hash_required(self):  # type: () -> bool
        """Returns True if component's hash have to present and be validated"""
        return False

    @property
    def downloadable(self):  # type: () -> bool
        """Returns True if components have to be fetched"""
        return False

    @property
    def meta(self):  # type: () -> bool
        """Returns True for meta components. Meta components are not included in the build directly"""
        return False

    def normalized_name(self, name):  # type: (str) -> str
        return name

    @abstractmethod
    def versions(
            self,
            name,  # type: str
            details=None,  # type: Union[Dict, None]
            spec='*',  # type: str
    ):
        # type: (...) -> ComponentWithVersions
        """List of versions for given spec"""

    @abstractmethod
    def download(self, component, download_path):  # type: (SolvedComponent, str) -> List[str]
        """
        Fetch required component version from the source
        Returns list of absolute paths to directories with component on local filesystem
        """

    @abstractmethod
    def serialize(self):  # type: () -> Dict
        """
        Return fields to describe source to be saved in lock file
        """
