#! /usr/bin/env python3

from aas_test_engines import api
import os
import shutil
import subprocess
import atexit
import requests
import time
from dataclasses import dataclass

HOST = 'http://localhost:5001'
script_dir = os.path.dirname(os.path.realpath(__file__))

test_data_dir = os.path.join(script_dir, '..', '..', 'bin', 'check_servers', 'test_data')
runner_temp = os.environ.get('RUNNER_TEMP', None)
if runner_temp:
    # In Github actions, only certain directories can be mounted
    runner_temp = os.path.join(runner_temp, 'test_data')
    print(f"Copy '{test_data_dir}' to '{runner_temp}'")
    shutil.copytree(test_data_dir, runner_temp)
    test_data_dir = runner_temp
print(f"test_data_dir={test_data_dir}")


def wait_for_server(url: str, max_tries=10):
    for _ in range(max_tries):
        try:
            requests.get(url, verify=False)
            print(f"Server is up at {url}")
            return
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(1)
    print(f"Cannot reach server at {url}")


def start_server(test_data_dir: str) -> str:
    container_id = subprocess.check_output([
        'docker', 'run',
        '--publish', '5001:5001',
        '--detach',
        # TODO
        #        '--mount', f'type=bind,src={test_data_dir},target=/AasxServerBlazor/aasxs',
        'docker.io/adminshellio/aasx-server-blazor-for-demo:main',
    ])
    return container_id.decode().strip()


def stop_server(container_id: str):
    print(f"Stopping {container_id}")
    subprocess.check_output([
        'docker', 'kill', container_id
    ])


def show_server_logs(container_id: str):
    subprocess.check_call([
        'docker', 'logs', container_id
    ])


container_id = start_server(test_data_dir)
atexit.register(lambda: stop_server(container_id))
wait_for_server(HOST)
show_server_logs(container_id)


@dataclass
class Params:
    url: str
    suite: str


params = [
    Params('/api/v3.0', "https://admin-shell.io/aas/API/3/0/AssetAdministrationShellRepositoryServiceSpecification/SSP-002"),
    Params('/api/v3.0', "https://admin-shell.io/aas/API/3/0/SubmodelRepositoryServiceSpecification/SSP-002"),
    # Params('/api/v3.0', "https://admin-shell.io/aas/API/3/0/AssetAdministrationShellServiceSpecification/SSP-002"),
    # Params('/api/v3.0', "https://admin-shell.io/aas/API/3/0/SubmodelServiceSpecification/SSP-002"),
]

for param in params:
    print("-"*10)
    print(f"Checking {param.suite}")
    conf = api.ExecConf(
        server=f"{HOST}{param.url}"
    )
    result, mat = api.execute_tests(conf, param.suite)
    mat.print()
    # TODO
    # assert result.ok()
    assert mat.valid_rejected == 3  # Constraint violations in ExampleMotor.aasx
    assert mat.invalid_accepted == 0
