from fastapi.testclient import TestClient
from api.main import app
from db import db
from story.checkpoints import compare_worlds


def test_comparison_does_not_restore_or_cross_session_boundaries():
    user = db.create_user('comparison-fixture')
    story = db.create_session(user.id, 'Synthetic branch')
    db.update_session(story.id, world_state={'place': 'forest', 'note': None}, current_step=1)
    saved = db.create_snapshot(story.id, title='Before the bridge')
    db.update_session(story.id, world_state={'place': 'bridge'}, current_step=2)
    other = db.create_session(user.id, 'Other branch')
    before = db.get_session(story.id).world_state
    with TestClient(app) as client:
        response = client.get(f'/api/session/{story.id}/compare/{saved.id}')
        assert response.status_code == 200
        report = response.json()
        assert report['current_step'] == 2 and report['saved_step'] == 1
        assert report['changed_field_count'] == 2
        assert client.get(f'/api/session/{other.id}/compare/{saved.id}').status_code == 404
    assert db.get_session(story.id).world_state == before
    assert db.get_snapshot_details(saved.id).world_state == saved.world_state


def test_comparison_bounds_previews_and_distinguishes_missing_from_null():
    report = compare_worlds({'story': 'a' * 1000}, {'story': 'old', 'note': None})
    rows = {row['field']: row for row in report['fields']}
    assert rows['story']['current_truncated'] and len(rows['story']['current']) == 600
    assert not rows['note']['current_present'] and rows['note']['saved_present']
