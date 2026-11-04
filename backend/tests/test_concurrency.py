"""Run against the PostgreSQL CI service: SQLite does not support SELECT FOR UPDATE."""

import os
from concurrent.futures import ThreadPoolExecutor

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="PostgreSQL required for real row locks"
)


def test_concurrent_prepare_and_submit_are_idempotent(client, headers, demo_jobs):
    job = next(job for job in demo_jobs if job["match"]["eligible"])

    def prepare():
        return client.post("/api/v1/applications", headers=headers, json={"job_id": job["id"]})

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: prepare(), range(2)))
    assert all(response.status_code == 201 for response in responses)
    app_ids = {response.json()["id"] for response in responses}
    assert len(app_ids) == 1
    app_id = app_ids.pop()
    assert client.post(f"/api/v1/applications/{app_id}/approve", headers=headers).status_code == 200
    assert client.post("/api/v1/automation/start", headers=headers).status_code == 200

    def submit():
        return client.post(f"/api/v1/applications/{app_id}/submit", headers=headers)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: submit(), range(2)))
    assert all(response.status_code == 200 for response in responses), [
        response.text for response in responses
    ]
    assert all(response.json()["attempts"] == 1 for response in responses)
    assert len({response.json()["result_reference"] for response in responses}) == 1


def test_concurrent_distinct_submissions_share_daily_quota(client, headers, demo_jobs):
    context = client.get("/api/v1/context", headers=headers).json()
    context.pop("version")
    context["rules"]["max_daily"] = 1
    client.put("/api/v1/context", headers=headers, json=context)
    ids = []
    for job in [job for job in demo_jobs if job["match"]["eligible"]][:2]:
        application = client.post("/api/v1/applications", headers=headers, json={"job_id": job["id"]}).json()
        ids.append(application["id"])
        assert (
            client.post(f"/api/v1/applications/{application['id']}/approve", headers=headers).status_code
            == 200
        )
    assert len(ids) == 2
    client.post("/api/v1/automation/start", headers=headers)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda app_id: client.post(f"/api/v1/applications/{app_id}/submit", headers=headers), ids
            )
        )
    assert sorted(response.status_code for response in responses) == [200, 409], [r.text for r in responses]
    assert (
        "diario" in next(response for response in responses if response.status_code == 409).json()["detail"]
    )
