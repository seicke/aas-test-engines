from typing import Dict, List, Union
from .exception import AasTestToolsException
from .result import AasTestResult, Level
from ._util import b64urlsafe

from fences.open_api.open_api import OpenApi, Operation
from fences.open_api.generate import SampleCache, generate_all, generate_one_valid, Request
from fences.core.util import ConfusionMatrix

import os
from yaml import load
try:
    # This one is faster but not available on all systems
    from yaml import CSafeLoader as Loader
except ImportError:
    from yaml import SafeLoader as Loader

from dataclasses import dataclass
import requests


def _stringify_path(path: List[Union[str, int]]) -> str:
    return "/".join(str(fragment) for fragment in path)


def _lookup(value: any, path: List[Union[str, int]], idx: int = 0) -> any:
    if idx >= len(path):
        return value

    fragment = path[idx]
    if isinstance(fragment, str):
        if not isinstance(value, dict):
            raise ApiTestSuiteException(f"Cannot look up {_stringify_path(path)}: should be an object")
        try:
            sub_value = value[fragment]
        except KeyError:
            raise ApiTestSuiteException(f"Cannot look up {_stringify_path(path)}: key '{fragment}' does not exist")
    elif isinstance(fragment, int):
        if not isinstance(value, list):
            raise ApiTestSuiteException(f"Cannot look up {_stringify_path(path)}: should be an array")
        try:
            sub_value = value[fragment]
        except IndexError:
            raise ApiTestSuiteException(f"Cannot look up {_stringify_path(path)}: array too short")
    return _lookup(sub_value, path, idx+1)


def _extend(data: Dict[str, List[str]]) -> dict:
    while True:
        all_resolved = True
        for key, values in data.items():
            new_values = []
            for value in values:
                try:
                    new_values.extend(data[value])
                    all_resolved = False
                except KeyError:
                    new_values.append(value)
            data[key] = new_values
        if all_resolved:
            return data


SSP_PREFIX = "https://admin-shell.io/aas/API/3/0/"

_available_suites = _extend({
    # APIs
    "Asset Administration Shell API": [
        "GetAssetAdministrationShell",
        "PutAssetAdministrationShell",
        "GetAllSubmodelReferences",
        "PostSubmodelReference",
        "DeleteSubmodelReference",
        "GetAssetInformation",
        "PutAssetInformation",
        "GetThumbnail",
        "PutThumbnail",
        "DeleteThumbnail"
    ],
    "Submodel API": [
        "GetSubmodel",
        "GetAllSubmodelElements",
        "GetSubmodelElementByPath",
        "GetFileByPath",
        "PutFileByPath",
        "DeleteFileByPath",
        "PutSubmodel",
        "PatchSubmodel",
        "PostSubmodelElement",
        "PostSubmodelElementByPath",
        "PutSubmodelElementByPath",
        "PatchSubmodelElementByPath",
        "GetSubmodelElementValueByPath",
        "DeleteSubmodelElementByPath",
        "InvokeOperationSync",
        "InvokeOperationAsync",
        "GetOperationAsyncStatus",
        "GetOperationAsyncResult",
    ],
    "Serialization API": [
        "GenerateSerializationByIds",
    ],
    "AASX File Server API": [
        "GetAllAASXPackageIds",
        "GetAASXByPackageId",
        "PostAASXPackage",
        "PutAASXByPackageId",
        "DeleteAASXByPackageId",
    ],
    "Asset Administration Shell Registry API": [
        "GetAllAssetAdministrationShellDescriptors",
        "GetAssetAdministrationShellDescriptorById",
        "PostAssetAdministrationShellDescriptor",
        "PutAssetAdministrationShellDescriptorById",
        "DeleteAssetAdministrationShellDescriptorById",
    ],
    "Submodel Registry API": [
        "GetAllSubmodelDescriptors",
        "GetSubmodelDescriptorById",
        "PostSubmodelDescriptor",
        "PutSubmodelDescriptorById",
        "DeleteSubmodelDescriptorById",
    ],
    "Asset Administration Shell Repository API": [
        "GetAllAssetAdministrationShells",
        "GetAllAssetAdministrationShells-Reference",
        "GetAssetAdministrationShellById",
        "GetAllAssetAdministrationShellsByAssetId",
        "GetAllAssetAdministrationShellsByIdShort",
        "PostAssetAdministrationShell",
        "PutAssetAdministrationShellById",
        "DeleteAssetAdministrationShellById",
        "GetAssetAdministrationShellById-Reference_AasRepository",
    ],
    "Submodel Repository API": [
        "GetAllSubmodelDescriptors",
        "GetSubmodelDescriptorById",
        "PostSubmodelDescriptor",
        "PutSubmodelDescriptorById",
        "DeleteSubmodelDescriptorById",
    ],
    "Concept Description Repository API": [
        "GetAllConceptDescriptions",
        "GetConceptDescriptionById",
        "GetAllConceptDescriptionsByIdShort",
        "GetAllConceptDescriptionsByIsCaseOf",
        "GetAllConceptDescriptionsByDataSpecificationReference",
        "PostConceptDescription",
        "PutConceptDescriptionById",
        "DeleteConceptDescriptionById",
    ],
    "Asset Administration Shell Basic Discovery API": [
        "GetAllAssetAdministrationShellIdsByAssetLink",
        "GetAllAssetLinksById",
        "PostAllAssetLinksById",
        "DeleteAllAssetLinksById",
    ],
    "Description API": [
        "GetSelfDescription",
    ],
    # Service Specs
    "Asset Administration Shell Service Specification": [
        "Asset Administration Shell API",
        "Submodel API",  # TODO: via super path
        "Serialization API",
        "Description API",
    ],
    "Submodel Service Specification": [
        "Submodel API",
        "Serialization API",
        "Description API",
    ],
    "AASX File Server Service Specification": [
        "AASX File Server API",
        "Description API",
    ],
    "Asset Administration Shell Registry Service Specification": [
        "Asset Administration Shell Registry API",
        "Submodel Registry API",  # TODO: via super path
        "Description API",
    ],
    "Submodel Registry Service Specification": [
        "Submodel Registry API",
        "Description API",
    ],
    "Discovery Service Specification": [
        "Asset Administration Shell Basic Discovery API",
        "Description API",
    ],
    "Asset Administration Shell Repository Service Specification": [
        "Asset Administration Shell API",  # TODO: via super path
        "Submodel API",  # TODO: via super path
        "Asset Administration Shell Repository API",
        "Submodel Repository API",  # TODO: via super path
        "Serialization API",
        "Description API",
    ],
    "Submodel Repository Service Specification": [
        "Submodel API",  # TODO: via super path
        "Submodel Repository API",  # TODO: via super path
        "Serialization API",
        "Description API",
    ],
    "ConceptDescription Repository Service Specification": [
        "Serialization API",
        "Description API",
        "Concept Description Repository API",
    ],
    # Service Spec Profiles
    f"{SSP_PREFIX}AssetAdministrationShellServiceSpecification/SSP-001": [
        "Asset Administration Shell Service Specification"
    ],
    f"{SSP_PREFIX}AssetAdministrationShellServiceSpecification/SSP-002": [
        "GetAssetAdministrationShell",
        "GetAllSubmodelReferences",
        "GetAssetInformation",
        "GetThumbnail",
        "GetSubmodel",  # TODO: via super path
        "GetAllSubmodelElements",  # TODO: via super path
        "GetSubmodelElementByPath",  # TODO: via super path
        "GetFileByPath",  # TODO: via super path
    ],
    f"{SSP_PREFIX}SubmodelServiceSpecification/SSP-001": [
        "Submodel Service Specification",
    ],
    f"{SSP_PREFIX}SubmodelServiceSpecification/SSP-002": [
        "GetSubmodel",
        "GetAllSubmodelElements",
        "GetSubmodelElementByPath",
        "GetFileByPath",
        "GenerateSerializationByIds",
        "GetDescription",
    ],
    f"{SSP_PREFIX}SubmodelServiceSpecification/SSP-003": [
        "GetSubmodel",
        "InvokeOperationSync",
        "GetDescription",
    ],
    f"{SSP_PREFIX}AasxFileServerServiceSpecification/SSP-001": [
        "AASX File Server Service Specification"
    ],
    f"{SSP_PREFIX}AssetAdministrationShellRegistryServiceSpecification/SSP-001": [
        "Asset Administration Shell Registry Service Specification",
    ],
    f"{SSP_PREFIX}AssetAdministrationShellRegistryServiceSpecification/SSP-002": [
        "GetAllAssetAdministrationShellDescriptors",
        "GetAssetAdministrationShellDescriptorById",
        "GetAllSubmodelDescriptors",  # TODO: via super path
        "GetSubmodelDescriptorById",  # TODO: via super path
    ],
    f"{SSP_PREFIX}SubmodelRegistryServiceSpecification/SSP-001": [
        "Submodel Registry Service Specification",
    ],
    f"{SSP_PREFIX}SubmodelRegistryServiceSpecification/SSP-002": [
        "GetAllSubmodelDescriptors",
        "GetSubmodelDescriptorById",
        "GetDescription",
    ],
    f"{SSP_PREFIX}DiscoveryServiceSpecification/SSP-001": [
        "Discovery Service Specification",
    ],
    f"{SSP_PREFIX}AssetAdministrationShellRepositoryServiceSpecification/SSP-001": [
        "Asset Administration Shell Repository Service Specification",
    ],
    f"{SSP_PREFIX}AssetAdministrationShellRepositoryServiceSpecification/SSP-002": [
        # AAS Repository API:
        "GetAllAssetAdministrationShells",  # includes ...ByAssetId and ...ByIdShort
        "GetAllAssetAdministrationShells-Reference",
        "GetAssetAdministrationShellById",
        "GetAssetAdministrationShellById-Reference_AasRepository",
        # AAS API by superpath:
        "GetAllSubmodelReferences_AasRepository",
        "GetAssetInformation_AasRepository",
        "GetThumbnail_AasRepository",
        # Submodel Repository API by superpath:
        "GetSubmodelById_AasRepository",
        "GetSubmodelById-Metadata_AasRepository",
        "GetSubmodelById-ValueOnly_AasRepository",
        "GetSubmodelById-Reference_AasRepository",
        "GetSubmodelById-Path_AasRepository",
        # Submodel API by superpath:
        "GetAllSubmodelElements_AasRepository",
        "GetAllSubmodelElements-Metadata_AasRepository",
        "GetAllSubmodelElements-ValueOnly_AasRepository",
        "GetAllSubmodelElements-Reference_AasRepository",
        "GetAllSubmodelElements-Path_AasRepository",
        "GetSubmodelElementByPath_AasRepository",
        "GetSubmodelElementByPath-Metadata_AasRepository",
        "GetSubmodelElementByPath-ValueOnly_AasRepository",
        "GetSubmodelElementByPath-Reference_AasRepository",
        "GetSubmodelElementByPath-Path_AasRepository",
        "GetFileByPath_AasRepository",
        # Serialization API
        "GenerateSerializationByIds",
        # Description API
        "GetDescription",
    ],
    f"{SSP_PREFIX}SubmodelRepositoryServiceSpecification/SSP-001": [
        "Submodel Repository Service Specification",
    ],
    f"{SSP_PREFIX}SubmodelRepositoryServiceSpecification/SSP-002": [
        "GetAllSubmodels",
        "GetSubmodelById",
        "GetAllSubmodelsBySemanticId",
        "GetAllSubmodelsByIdShort",
        "GetSubmodel",
        "GetAllSubmodelElements",
        "GetSubmodelElementByPath",
        "GetFileByPath",
        "GenerateSerializationByIds",
        "GetDescription"
    ],
    f"{SSP_PREFIX}SubmodelRepositoryServiceSpecification/SSP-003": [
        "SubmodelRepositoryServiceSpecification/SSP-001"  # TODO: Constraint AASa-003
    ],
    f"{SSP_PREFIX}SubmodelRepositoryServiceSpecification/SSP-004": [
        "SubmodelRepositoryServiceSpecification/SSP-002"  # TODO: Constraint AASa-004
    ],
    f"{SSP_PREFIX}ConceptDescriptionRepositoryServiceSpecification/SSP-001": [
        "Concept Description Repository Service Specification"
    ]
})


@dataclass
class ExecConf:
    dry: bool = False
    verify: bool = True


def _check_server(server: str, exec_conf: ExecConf) -> AasTestResult:
    result = AasTestResult(f'Trying to reach {server}')
    if exec_conf.dry:
        result.append(AasTestResult("Skipped due to dry run", '', Level.WARNING))
        return result

    try:
        requests.get(server, verify=exec_conf.verify)
        result.append(AasTestResult('OK', '', Level.INFO))
    except requests.exceptions.RequestException as e:
        result.append(AasTestResult('Failed to reach: {}'.format(e), '', Level.ERROR))
    return result


class AasSpec:

    def __init__(self, open_api: OpenApi) -> None:
        self.open_api = open_api


def _find_specs() -> Dict[str, AasSpec]:
    result = {}
    script_dir = os.path.dirname(os.path.realpath(__file__))
    data_dir = os.path.join(script_dir, 'data', 'api')
    for i in os.listdir(data_dir):
        path = os.path.join(data_dir, i)
        if not i.endswith('.yml'):
            continue
        with open(path, 'rb') as f:
            spec = load(f, Loader=Loader)
        open_api = OpenApi.from_dict(spec)
        result[i[:-4]] = AasSpec(open_api)
    return result


_specs = _find_specs()

_DEFAULT_VERSION = '3.0'


def _get_spec(version: str) -> AasSpec:
    try:
        return _specs[version]
    except KeyError:
        raise AasTestToolsException(
            f"Unknown version {version}, must be one of {supported_versions()}")


def _shorten(content: bytes, max_len: int = 300) -> str:
    try:
        content = content.decode()
    except UnicodeDecodeError:
        return "<binary-data>"
    if len(content) > max_len:
        return content[:max_len] + "..."
    return content


def _make_invoke_result(request: Request) -> AasTestResult:
    return AasTestResult(f"Invoke: {request.operation.method.upper()} {request.make_path()}")


class ApiTestSuiteException(Exception):
    pass


class ApiTestSuite:

    def __init__(self, server: str, operation: Operation, conf: ExecConf, sample_cache: SampleCache, open_api: OpenApi, suite: str):
        self.server = server
        self.operation = operation
        self.conf = conf
        self.sample_cache = sample_cache
        self.open_api = open_api
        self.suite = suite
        self.valid_values: Dict[str, List[any]] = {}

    def setup(self, result: AasTestResult):
        pass

    def execute_syntactic_test(self, request: Request, result: AasTestResult) -> requests.models.Response:
        result_request = _make_invoke_result(request)
        response = request.execute(self.server)
        if response.status_code >= 500:
            result.append(AasTestResult(f"Server crashed with code {response.status_code}: {_shorten(response.content)}", level=Level.CRITICAL))
        elif response.status_code >= 400:
            result_request.append(AasTestResult(f"Ok ({response.status_code}): {_shorten(response.content)}"))
        else:
            result_request.append(AasTestResult(f"Got status code {response.status_code}, but expected 4xx: {_shorten(response.content)}", level=Level.ERROR))
        result.append(result_request)
        return response

    def execute_semantic_test(self, request: Request, result: AasTestResult) -> requests.models.Response:
        result_request = _make_invoke_result(request)
        response = request.execute(self.server)
        if response.status_code >= 500:
            result.append(AasTestResult(f"Server crashed with code {response.status_code}: {_shorten(response.content)}", level=Level.CRITICAL))
        elif response.status_code >= 400:
            result_request.append(AasTestResult(f"Got status code {response.status_code}, but expected 2xx: {_shorten(response.content)}", level=Level.ERROR))
        else:
            result_request.append(AasTestResult(f"Ok ({response.status_code}): {_shorten(response.content)}"))
        result.append(result_request)
        return response

    def execute(self, result_positive: AasTestResult, result_negative: AasTestResult):
        graph = generate_all(self.operation, self.sample_cache, self.valid_values)
        for i in graph.generate_paths():
            request: Request = graph.execute(i.path)
            if i.is_valid:
                self.execute_semantic_test(request, result_positive)
            else:
                self.execute_syntactic_test(request, result_negative)

    def teardown(self):
        pass


class GetAllAasTestSuite(ApiTestSuite):
    def setup(self, result: AasTestResult) -> Dict[str, List[any]]:
        request = generate_one_valid(self.open_api.operations["GetAllAssetAdministrationShells"], self.sample_cache, {'limit': 1})
        result.append(_make_invoke_result(request))
        response = request.execute(self.server)
        if response.status_code != 200:
            raise ApiTestSuiteException(f"Cannot look up idShort, got status {response.status_code}")
        data = response.json()
        self.valid_values = {
            'limit': [1],
            'cursor': [_lookup(data, ['paging_metadata', 'cursor'])],
            'idShort': [_lookup(data, ['result', 0, 'idShort'])],
        }


class GetAasById(ApiTestSuite):
    def setup(self, result: AasTestResult) -> Dict[str, List[any]]:
        request = generate_one_valid(self.open_api.operations["GetAllAssetAdministrationShells"], self.sample_cache, {'limit': 1})
        result.append(_make_invoke_result(request))
        response = request.execute(self.server)
        if response.status_code != 200:
            raise ApiTestSuiteException(f"Cannot look up aasIdentifier, got status {response.status_code}")
        data = response.json()
        valid_id = _lookup(data, ['result', 0, 'id'])
        self.valid_values = {
            'aasIdentifier': [b64urlsafe(valid_id)]
        }


class AasBySuperpathSuite(ApiTestSuite):
    def setup(self, result: AasTestResult) -> Dict[str, List[any]]:
        request = generate_one_valid(self.open_api.operations["GetAllAssetAdministrationShells"], self.sample_cache, {'limit': 1})
        result.append(_make_invoke_result(request))
        response = request.execute(self.server)
        if response.status_code != 200:
            raise ApiTestSuiteException(f"Cannot look up aasIdentifier, got status {response.status_code}")
        data = response.json()
        valid_id = _lookup(data, ['result', 0, 'id'])
        self.valid_values = {
            'aasIdentifier': [b64urlsafe(valid_id)]
        }


class SubmodelBySuperpathSuite(ApiTestSuite):
    def setup(self, result: AasTestResult) -> Dict[str, List[any]]:
        request = generate_one_valid(self.open_api.operations["GetAllAssetAdministrationShells"], self.sample_cache, {'limit': 1})
        result.append(_make_invoke_result(request))
        response = request.execute(self.server)
        if response.status_code != 200:
            raise ApiTestSuiteException(f"Cannot look up submodelIdentifier, got status {response.status_code}")
        data = response.json()
        valid_id = _lookup(data, ['result', 0, 'id'])
        valid_submodel_id = _lookup(data, ['result', 0, 'submodels', 0, 'keys', 0, 'value'])
        self.valid_values = {
            'aasIdentifier': [b64urlsafe(valid_id)],
            'submodelIdentifier': [b64urlsafe(valid_submodel_id)],
        }


def _collect_submodel_elements(data: list, paths: Dict[str, List[str]], path_prefix: str):
    for i in data:
        id_short = path_prefix + _lookup(i, ['idShort'])
        model_type = _lookup(i, ['modelType'])
        try:
            paths[model_type].append(id_short)
        except KeyError:
            paths[model_type] = [id_short]
        if model_type == 'SubmodelElementCollection':
            value = _lookup(i, ['value'])
            _collect_submodel_elements(value, paths, id_short + ".")


class SubmodelElementBySuperpathSuite(ApiTestSuite):
    ALL_TYPES = [
        'SubmodelElementCollection',
        'SubmodelElementList',
        'Entity',
        'BasicEventElement',
        'Capability',
        'Operation',
        'Property',
        'MultiLanguageProperty',
        'Range',
        'ReferenceElement',
        'RelationshipElement',
        'AnnotatedRelationshipElement',
        'Blob',
        'File',
    ]

    def setup(self, result: AasTestResult) -> Dict[str, List[any]]:
        request = generate_one_valid(self.open_api.operations["GetAllAssetAdministrationShells"], self.sample_cache, {'limit': 1})
        result.append(_make_invoke_result(request))
        response = request.execute(self.server)
        if response.status_code != 200:
            raise ApiTestSuiteException(f"Cannot look up submodelIdentifier, got status {response.status_code}")
        data = response.json()
        valid_id = _lookup(data, ['result', 0, 'id'])
        valid_submodel_id = _lookup(data, ['result', 0, 'submodels', 0, 'keys', 0, 'value'])
        overwrites = {
            'aasIdentifier': [b64urlsafe(valid_id)],
            'submodelIdentifier': [b64urlsafe(valid_submodel_id)],
        }
        request = generate_one_valid(self.open_api.operations["GetAllSubmodelElements_AasRepository"], self.sample_cache, overwrites)
        result.append(_make_invoke_result(request))
        response = request.execute(self.server)
        if response.status_code != 200:
            raise ApiTestSuiteException(f"Cannot look up idShortPath, got status {response.status_code}")
        data = response.json()
        elements = _lookup(data, ['result'])
        self.paths = {}
        _collect_submodel_elements(elements, self.paths, '')
        overwrites['idShortPath'] = [i[0] for i in self.paths.values()]
        self.valid_values = overwrites

    def execute(self, result_positive: AasTestResult, result_negative: AasTestResult):
        graph = generate_all(self.operation, self.sample_cache, self.valid_values)
        for i in graph.generate_paths():
            request: Request = graph.execute(i.path)
            if i.is_valid:
                pass  # skip, we do semantic testing manually
            else:
                self.execute_syntactic_test(request, result_negative)

        for model_type in self.ALL_TYPES:
            result_type = AasTestResult(f"Checking {model_type}")
            try:
                id_short_path = self.paths[model_type][0]
            except KeyError:
                result_type.append(AasTestResult("No such element present", level=Level.WARNING))
                id_short_path = None
            if id_short_path:
                valid_values = self.valid_values.copy()
                valid_values['idShortPath'] = [id_short_path]
                graph = generate_all(self.operation, self.sample_cache, valid_values)
                for i in graph.generate_paths():
                    request: Request = graph.execute(i.path)
                    if i.is_valid:
                        has_extend = 'extend' in request.query_parameters
                        has_level = 'level' in request.query_parameters
                        if (not has_extend and not has_level) or \
                                model_type in ['SubmodelElementCollection', 'SubmodelElementList', 'Entity'] or \
                                model_type in ['Blob'] and not has_level:
                            self.execute_semantic_test(request, result_type)
                        else:
                            self.execute_syntactic_test(request, result_type)
            result_positive.append(result_type)


class GetFileByPathSuperpathSuite(ApiTestSuite):
    def setup(self, result: AasTestResult) -> Dict[str, List[any]]:
        request = generate_one_valid(self.open_api.operations["GetAllAssetAdministrationShells"], self.sample_cache, {'limit': 1})
        result.append(_make_invoke_result(request))
        response = request.execute(self.server)
        if response.status_code != 200:
            raise ApiTestSuiteException(f"Cannot look up submodelIdentifier, got status {response.status_code}")
        data = response.json()
        valid_id = _lookup(data, ['result', 0, 'id'])
        valid_submodel_id = _lookup(data, ['result', 0, 'submodels', 0, 'keys', 0, 'value'])
        overwrites = {
            'aasIdentifier': [b64urlsafe(valid_id)],
            'submodelIdentifier': [b64urlsafe(valid_submodel_id)],
        }
        request = generate_one_valid(self.open_api.operations["GetAllSubmodelElements_AasRepository"], self.sample_cache, overwrites)
        result.append(_make_invoke_result(request))
        response = request.execute(self.server)
        if response.status_code != 200:
            raise ApiTestSuiteException(f"Cannot look up idShortPath, got status {response.status_code}")
        data = response.json()
        paths = {}
        _collect_submodel_elements(_lookup(data, ['result']), paths, '')
        try:
            overwrites['idShortPath'] = [paths['File']]
        except KeyError:
            raise ApiTestSuiteException("No submodel element of type 'File' found, skipping test.")
        self.valid_values = overwrites


class GenerateSerializationSuite(ApiTestSuite):
    def setup(self, result: AasTestResult) -> Dict[str, List[any]]:
        request = generate_one_valid(self.open_api.operations["GetAllAssetAdministrationShells"], self.sample_cache, {'limit': 1})
        result.append(_make_invoke_result(request))
        response = request.execute(self.server)
        if response.status_code != 200:
            raise ApiTestSuiteException(f"Cannot look up submodelIdentifier, got status {response.status_code}")
        data = response.json()
        valid_id = _lookup(data, ['result', 0, 'id'])
        valid_submodel_id = _lookup(data, ['result', 0, 'submodels', 0, 'keys', 0, 'value'])
        self.valid_values = {
            'aasIds': [[b64urlsafe(valid_id)]],
            'submodelIds': [[b64urlsafe(valid_submodel_id)]],
        }


class GetDescriptionTestSuite(ApiTestSuite):
    def execute_semantic_test(self, request: Request, result: AasTestResult):
        response = super().execute_semantic_test(request, result)
        data = response.json()
        profiles = data["Profiles"]
        if self.suite not in profiles:
            result.append(AasTestResult(f"Suite {self.suite} not part of profiles", level=Level.ERROR))


_test_suites = {
    'GetAllAssetAdministrationShells': GetAllAasTestSuite,
    'GetAllAssetAdministrationShells-Reference': GetAllAasTestSuite,

    'GetAssetAdministrationShellById': GetAasById,
    'GetAssetAdministrationShellById-Reference_AasRepository': GetAasById,

    "GetAllSubmodelReferences_AasRepository": AasBySuperpathSuite,
    "GetAssetInformation_AasRepository": AasBySuperpathSuite,
    "GetThumbnail_AasRepository": AasBySuperpathSuite,
    "GetAllSubmodels_AasRepository": AasBySuperpathSuite,
    "GetAllSubmodels_AasRepository Metadata": AasBySuperpathSuite,
    "GetAllSubmodels_AasRepository-ValueOnly": AasBySuperpathSuite,
    "GetAllSubmodels_AasRepository-Reference": AasBySuperpathSuite,
    "GetAllSubmodels_AasRepository-Path": AasBySuperpathSuite,

    "GetSubmodelById_AasRepository": SubmodelBySuperpathSuite,
    "GetSubmodelById-Metadata_AasRepository": SubmodelBySuperpathSuite,
    "GetSubmodelById-ValueOnly_AasRepository": SubmodelBySuperpathSuite,
    "GetSubmodelById-Reference_AasRepository": SubmodelBySuperpathSuite,
    "GetSubmodelById-Path_AasRepository": SubmodelBySuperpathSuite,
    "GetAllSubmodelElements_AasRepository": SubmodelBySuperpathSuite,
    "GetAllSubmodelElements-Metadata_AasRepository": SubmodelBySuperpathSuite,
    "GetAllSubmodelElements-ValueOnly_AasRepository": SubmodelBySuperpathSuite,
    "GetAllSubmodelElements-Reference_AasRepository": SubmodelBySuperpathSuite,
    "GetAllSubmodelElements-Path_AasRepository": SubmodelBySuperpathSuite,

    "GetSubmodelElementByPath_AasRepository": SubmodelElementBySuperpathSuite,
    "GetSubmodelElementByPath-Metadata_AasRepository": SubmodelElementBySuperpathSuite,
    "GetSubmodelElementByPath-ValueOnly_AasRepository": SubmodelElementBySuperpathSuite,
    "GetSubmodelElementByPath-Reference_AasRepository": SubmodelElementBySuperpathSuite,
    "GetSubmodelElementByPath-Path_AasRepository": SubmodelElementBySuperpathSuite,

    "GetFileByPath_AasRepository": GetFileByPathSuperpathSuite,

    "GenerateSerializationByIds": GenerateSerializationSuite,

    "GetDescription": GetDescriptionTestSuite,
}


def execute_tests(server: str, suite: str, version: str = _DEFAULT_VERSION, conf: ExecConf = ExecConf()) -> AasTestResult:
    spec = _get_spec(version)
    try:
        operation_ids = _available_suites[suite]
    except KeyError:
        all_suites = "\n".join(sorted(_available_suites.keys()))
        raise AasTestToolsException(f"Unknown suite {suite}, must be one of:\n{all_suites}")

    # Sanity check, should never fail
    for i in operation_ids:
        if i not in spec.open_api.operations:
            raise AasTestToolsException(f"Unknown operation {i}")

    sample_cache = SampleCache()
    result_root = AasTestResult(f"Checking compliance to {suite}")

    # Initial connection check
    r = _check_server(server, conf)
    result_root.append(r)
    if not result_root.ok():
        return result_root

    # Check individual operations
    mat = ConfusionMatrix()
    for operation in spec.open_api.operations.values():
        if operation.operation_id not in operation_ids:
            continue
        result_op = AasTestResult(f"Checking {operation.path} ({operation.operation_id})")
        if conf.dry:
            result_root.append(result_op)
            continue

        ctr = _test_suites[operation.operation_id]
        test_suite: ApiTestSuite = ctr(server, operation, conf, sample_cache, spec.open_api, suite)

        result_before_suite = AasTestResult("Setup")
        try:
            test_suite.setup(result_before_suite)
            result_before_suite.append(AasTestResult(f"Valid values: {test_suite.valid_values}"))
        except ApiTestSuiteException as e:
            result_before_suite.append(AasTestResult(f"Failed: {e}", level=Level.ERROR))
        result_op.append(result_before_suite)

        if result_op.ok():
            result_negative = AasTestResult("Syntactic tests")
            result_positive = AasTestResult("Semantic tests")
            test_suite.execute(result_positive, result_negative)
            result_op.append(result_negative)
            result_op.append(result_positive)
            for i in result_positive.sub_results:
                mat.add(True, i.ok())
            for i in result_negative.sub_results:
                mat.add(False, not i.ok())
        result_root.append(result_op)
    result_summary = AasTestResult("Summary")
    result_summary.append(AasTestResult(f"Syntactic tests passed: {mat.invalid_rejected} / {mat.invalid_accepted + mat.invalid_rejected}"))
    result_summary.append(AasTestResult(f"Semantic tests passed: {mat.valid_accepted} / {mat.valid_accepted + mat.valid_rejected}"))
    result_root.append(result_summary)
    return result_root


def supported_versions() -> Dict[str, List[str]]:
    return {ver: _available_suites.keys() for ver, spec in _specs.items()}


def latest_version():
    return _DEFAULT_VERSION
