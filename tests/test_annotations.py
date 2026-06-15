import pytest

from app.services import annotations


@pytest.mark.asyncio
async def test_create_and_list_scoped_by_entity(session, user):
    a = await annotations.create_annotation(
        session, entity_type="regression", entity_id=42, text="flaky on CI only", author_id=user.id
    )
    assert a.id is not None
    assert a.author_id == user.id

    # second entity gets its own thread
    await annotations.create_annotation(
        session, entity_type="case", entity_id=42, text="different entity", author_id=user.id
    )

    got = await annotations.list_annotations(session, "regression", 42)
    assert len(got) == 1
    assert got[0].text == "flaky on CI only"


@pytest.mark.asyncio
async def test_annotate_over_rest(session, client, auth_headers, user):
    r = await client.post(
        "/api/v1/annotations",
        headers=auth_headers,
        json={"entity_type": "build", "entity_id": 7, "text": "investigating"},
    )
    assert r.status_code == 201
    assert r.json()["author_id"] == user.id

    r = await client.get(
        "/api/v1/annotations", headers=auth_headers, params={"entity_type": "build", "entity_id": 7}
    )
    assert r.status_code == 200
    assert [a["text"] for a in r.json()] == ["investigating"]
