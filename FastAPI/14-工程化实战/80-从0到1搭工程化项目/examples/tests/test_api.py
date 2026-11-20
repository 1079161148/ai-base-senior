"""接口测试：契约层验 201/404/409/422/401。"""

BASE = "/api/v1/notes"


def test_healthz(client) -> None:
    assert client.get("/healthz").json()["status"] == "ok"


def test_create_with_location(client, auth) -> None:
    response = client.post(BASE, json={"title": "买牛奶"}, headers=auth)

    assert response.status_code == 201
    assert response.headers["location"] == f"{BASE}/{response.json()['id']}"


def test_duplicate_title_conflict(client, auth) -> None:
    client.post(BASE, json={"title": "同一个"}, headers=auth)
    response = client.post(BASE, json={"title": "同一个"}, headers=auth)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "duplicate_title"


def test_pagination_envelope(client, auth) -> None:
    for index in range(3):
        client.post(BASE, json={"title": f"t{index}"}, headers=auth)

    body = client.get(BASE, params={"size": 2}).json()

    assert (body["total"], body["pages"], len(body["items"])) == (3, 2, 2)


def test_pinned_filter(client, auth) -> None:
    client.post(BASE, json={"title": "a"}, headers=auth)
    client.post(BASE, json={"title": "b"}, headers=auth)
    client.post(f"{BASE}/2/pin", headers=auth)

    items = client.get(BASE, params={"pinned": True}).json()["items"]

    assert [item["id"] for item in items] == [2]


def test_not_found_contract(client) -> None:
    response = client.get(f"{BASE}/999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_422_contract(client, auth) -> None:
    response = client.post(BASE, json={"title": ""}, headers=auth)

    assert response.status_code == 422
    assert response.json()["error"]["details"]["fields"][0]["loc"] == "body.title"


def test_writes_need_token(client) -> None:
    assert client.post(BASE, json={"title": "x"}).status_code == 401
    assert client.patch(f"{BASE}/1", json={"body": "x"}).status_code == 401
    assert client.delete(f"{BASE}/1").status_code == 401


def test_delete_then_gone(client, auth) -> None:
    client.post(BASE, json={"title": "x"}, headers=auth)

    assert client.delete(f"{BASE}/1", headers=auth).status_code == 204
    assert client.get(f"{BASE}/1").status_code == 404


def test_observability_headers(client) -> None:
    response = client.get(BASE, headers={"X-Request-ID": "trace-80"})

    assert response.headers["x-request-id"] == "trace-80"
    assert "x-elapsed-ms" in response.headers