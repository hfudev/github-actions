"""Classes to work with manifest file"""
import re
from functools import total_ordering

import semantic_version as semver

import idf_component_tools as tools
from idf_component_tools.hash_tools import hash_object
from idf_component_tools.serialization import serializable

try:
    from collections.abc import Mapping
except ImportError:
    from collections import Mapping

try:
    from semantic_version import SimpleSpec as Spec
except ImportError:
    from semantic_version import Spec

try:
    from typing import TYPE_CHECKING, List, Optional, Union

    if TYPE_CHECKING:
        from ..sources import BaseSource
except ImportError:
    pass

COMMIT_ID_RE = re.compile(r'[0-9a-f]{40}')


@serializable
class Manifest(object):
    _serialization_properties = [
        'dependencies',
        'description',
        'files',
        'maintainers',
        'name',
        'targets',
        'url',
        'version',
    ]

    def __init__(
            self,
            dependencies=None,  # type: Optional[List[ComponentRequirement]] # Dependencies, list of component
            description=None,  # description type: Optional[str] # Human-readable
            download_url=None,  # type: Optional[str] # Direct url for tarball download
            maintainers=None,  # type: Optional[str] # List of maintainers
            manifest_hash=None,  # type: Optional[str] # Check-sum of manifest content
            name=None,  # type: Optional[str] # Component name
            targets=None,  # type: Optional[List[str]] # List of supported chips
            url=None,  # type: Optional[str] # Url of the repo
            include_files=None,  # type: Optional[List[str]]
            exclude_files=None,  # type: Optional[List[str]]
            version=None,  # type: Union[ComponentVersion, None] # Version
    ):
        # type: (...) -> None

        self.name = name or ''
        self.version = version
        self.maintainers = maintainers
        self.description = description
        self.download_url = download_url
        self.url = url

        if dependencies is None:
            dependencies = []
        self._dependencies = dependencies

        if targets is None:
            targets = []
        self.targets = targets

        if include_files is None:
            include_files = []
        if exclude_files is None:
            exclude_files = []
        self.files = {
            'include': include_files,
            'exclude': exclude_files,
        }

        self._manifest_hash = manifest_hash

    @classmethod
    def fromdict(cls, manifest_tree, name):  # type: (dict, str) -> Manifest
        """Coverts manifest dict to manifest object"""
        manifest = cls(
            name=name,
            maintainers=manifest_tree.get('maintainers'),
            url=manifest_tree.get('url'),
            description=manifest_tree.get('description'),
            targets=manifest_tree.get('targets', []),
            include_files=manifest_tree.get('files', {}).get('include'),
            exclude_files=manifest_tree.get('files', {}).get('exclude'),
        )

        version = manifest_tree.get('version')
        if version:
            manifest.version = ComponentVersion(version)

        for name, details in manifest_tree.get('dependencies', {}).items():
            if not isinstance(details, Mapping):
                details = {'version': details}

            source = tools.sources.BaseSource.fromdict(name, details)
            component = ComponentRequirement(
                name,
                source,
                version_spec=details.get('version') or '*',
                public=details.get('public'),
            )
            manifest._dependencies.append(component)

        return manifest

    @property
    def dependencies(self):
        return sorted(self._dependencies, key=lambda d: d.name)

    @property
    def manifest_hash(self):  # type: () -> str
        if self._manifest_hash:
            return self.manifest_hash

        serialized = self.serialize()  # type: ignore
        return hash_object(serialized)


@serializable
class ComponentRequirement(object):
    _serialization_properties = [
        'name',
        'public',
        'source',
        'version_spec',
    ]

    def __init__(
            self,
            name,  # type: str
            source,  # type: BaseSource
            version_spec='*',  # type: str
            public=None,  # type: Optional[bool]
    ):
        # type: (...) -> None
        self.version_spec = version_spec
        self.source = source
        self._name = name
        self.public = public

    @property
    def meta(self):
        return self.source.meta

    @property
    def name(self):
        return self.source.normalized_name(self._name)

    def __repr__(self):  # type: () -> str
        return 'ComponentRequirement("{}", {}, version_spec="{}", public={})'.format(
            self._name, self.source, self.version_spec, self.public)


@total_ordering
@serializable(like='str')
class ComponentVersion(object):
    def __init__(self, version_string, dependencies=None):  # type: (str, Optional[List[ComponentRequirement]]) -> None
        """
        version_string - can be `*`, git commit hash (hex, 160 bit) or valid semantic version string
        """

        self._version_string = version_string.strip().lower()
        self._semver = None

        # Setting flags:
        self.is_commit_id = bool(COMMIT_ID_RE.match(self._version_string))
        self.is_any = self._version_string == '*'
        self.is_semver = False

        # Checking format
        if not (self.is_any or self.is_commit_id):
            self._semver = semver.Version(self._version_string)
            self.is_semver = True

    def __eq__(self, other):
        if self.is_semver and other.is_semver:
            return self._semver == other._semver
        else:
            return self._version_string == other._version_string

    def __lt__(self, other):
        if not (self.is_semver and other.is_semver):
            raise ValueError('Can only compare semantic versions')

        return self._semver < other._semver

    def __repr__(self):
        return 'ComponentVersion("{}")'.format(self._version_string)

    def __str__(self):
        return self._version_string

    @property
    def semver(self):  # type: () -> semver.Version
        if self.is_semver:
            return self._semver
        else:
            raise TypeError('Version is not semantic')


class ComponentSpec(object):
    def __init__(self, spec_string):  # type: (str) -> None
        """
        spec_string - git commit hash (hex, 160 bit) or valid semantic version spec
        """
        self.is_commit_id = bool(COMMIT_ID_RE.match(spec_string))
        self.is_semspec = False

        if not self.is_commit_id:
            self._semver = Spec(spec_string)
            self.is_semspec = True

        self._spec_string = spec_string.strip().lower()

    def match(self, version):  # type: (ComponentVersion) -> bool
        """Check whether a Version satisfies the Spec."""
        if version.is_any:
            return True

        if self.is_commit_id:
            return self._spec_string == str(version)
        else:
            return self._semver.match(version)

    def __str__(self):
        return self._spec_string


class HashedComponentVersion(ComponentVersion):
    def __init__(self, *args, **kwargs):
        component_hash = kwargs.pop('component_hash', None)
        dependencies = kwargs.pop('dependencies', [])
        super(HashedComponentVersion, self).__init__(*args, **kwargs)

        self.component_hash = component_hash
        self.dependencies = dependencies


class ComponentWithVersions(object):
    def __init__(self, name, versions):  # type: (str, List[HashedComponentVersion]) -> None
        self.versions = versions
        self.name = name


class ProjectRequirements(object):
    '''Representation of all manifests required by project'''
    def __init__(self, manifests):  # type: (List[Manifest]) -> None
        self.manifests = manifests
        self._manifest_hash = None

    @property
    def manifest_hash(self):  # type: () -> str
        '''Lazily calculate requirements hash'''
        if self._manifest_hash:
            return self._manifest_hash

        manifest_hashes = [manifest.manifest_hash for manifest in self.manifests]
        return hash_object(manifest_hashes)
