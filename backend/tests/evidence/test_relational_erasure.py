import pytest

from app.evidence.relational import _public_record, _purge_prior_record_versions


class RecordingConnection:
    def __init__(self):
        self.calls=[]

    async def execute(self, query, params):
        self.calls.append((" ".join(query.split()),params))


@pytest.mark.asyncio
async def test_erasure_purges_restricted_input_and_superseded_record_versions():
    connection=RecordingConnection()
    records={
        "record-erased":{"record_version":2,"_purge_prior_versions":True},
        "record-unchanged":{"record_version":4},
    }

    await _purge_prior_record_versions(connection,"project-1",records)

    assert connection.calls==[
        ("DELETE FROM restricted_record_inputs WHERE project_id=%s AND record_id=%s",
         ("project-1","record-erased")),
        ("DELETE FROM record_spans WHERE project_id=%s AND record_id=%s AND record_version<>%s",
         ("project-1","record-erased",2)),
        ("DELETE FROM record_versions WHERE project_id=%s AND record_id=%s AND version<>%s",
         ("project-1","record-erased",2)),
    ]


def test_erasure_purge_marker_is_not_persisted_in_record_payload():
    assert _public_record({
        "record_id":"record-1",
        "record_version":2,
        "title":"[deleted user] approved the rollout",
        "_purge_prior_versions":True,
    })=={
        "record_id":"record-1",
        "record_version":2,
        "title":"[deleted user] approved the rollout",
    }
