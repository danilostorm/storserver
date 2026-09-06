import os
from pathlib import Path

TEST_DB = Path('/tmp/storserver-test.db')
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    'JWT_SECRET': 'test-secret-that-is-long-enough-for-tests',
    'ADMIN_EMAIL': 'admin@example.com',
    'ADMIN_PASSWORD': 'integration-test-password',
    'DATABASE_URL': f'sqlite+pysqlite:///{TEST_DB}',
    'AGENT_SHARED_TOKEN': 'test-agent-token',
    'AGENT_URL': 'http://agent.test:9000',
    'NODE_NAME': 'test-node',
    'NODE_REGION': 'test-region',
})

import pytest
from fastapi.testclient import TestClient

import app.main as main


@pytest.fixture(scope='module')
def client():
    with TestClient(main.app) as test_client:
        yield test_client


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post('/api/auth/login', data={
        'username': 'admin@example.com',
        'password': 'integration-test-password',
    })
    assert response.status_code == 200
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


def test_health_and_login(client: TestClient):
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'

    headers = auth_headers(client)
    me = client.get('/api/me', headers=headers)
    assert me.status_code == 200
    assert me.json()['role'] == 'admin'


def test_node_status_polling(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def fake_agent_request(node, method, path, json=None):
        assert method == 'GET'
        assert path == '/v1/node'
        return {
            'status': 'ok',
            'hostname': 'node-host',
            'docker_version': '28.0.0',
            'containers': 4,
            'containers_running': 3,
            'cpus': 8,
            'memory_bytes': 16 * 1024**3,
        }

    monkeypatch.setattr(main, 'agent_request', fake_agent_request)
    response = client.get('/api/nodes/status', headers=auth_headers(client))
    assert response.status_code == 200
    status = response.json()[0]
    assert status['online'] is True
    assert status['hostname'] == 'node-host'
    assert status['containers_running'] == 3


def test_server_lifecycle_logs_and_delete(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    calls = []

    async def fake_agent_request(node, method, path, json=None):
        calls.append((method, path))
        if method == 'POST' and path == '/v1/servers':
            return {
                'container_id': 'abc123',
                'status': 'running',
                'public_host': '203.0.113.10',
                'public_port': 27015,
            }
        if method == 'GET' and path.startswith('/v1/servers/') and '/logs?' in path:
            return {'logs': 'server booted\nready'}
        if method == 'DELETE' and path.startswith('/v1/servers/'):
            return {'status': 'deleted'}
        if method == 'POST' and path.endswith('/stop'):
            return {'status': 'stopped'}
        if method == 'POST' and path.endswith('/start'):
            return {'status': 'running'}
        if method == 'POST' and path.endswith('/restart'):
            return {'status': 'running'}
        raise AssertionError(f'unexpected agent call: {method} {path}')

    monkeypatch.setattr(main, 'agent_request', fake_agent_request)
    headers = auth_headers(client)
    node_id = client.get('/api/nodes', headers=headers).json()[0]['id']

    created = client.post('/api/servers', headers=headers, json={
        'name': 'Integration CS',
        'game_key': 'cs16',
        'node_id': node_id,
        'cpu_limit': 2,
        'memory_mb': 1024,
    })
    assert created.status_code == 201
    server = created.json()
    assert server['status'] == 'running'
    server_id = server['id']

    stopped = client.post(f'/api/servers/{server_id}/stop', headers=headers)
    assert stopped.status_code == 200
    assert stopped.json()['status'] == 'stopped'

    log_response = client.get(f'/api/servers/{server_id}/logs?tail=50', headers=headers)
    assert log_response.status_code == 200
    assert 'server booted' in log_response.json()['logs']

    deleted = client.delete(f'/api/servers/{server_id}', headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()['status'] == 'deleted'

    inventory = client.get('/api/servers', headers=headers)
    assert inventory.status_code == 200
    assert all(item['id'] != server_id for item in inventory.json())
    assert ('DELETE', f'/v1/servers/{server_id}') in calls
