"""gRPC integration tests — mock servicer offline; live server test skipped."""
from __future__ import annotations

import grpc
import pytest

pytest.importorskip("apex.api.apex_pb2")
pytest.importorskip("apex.api.apex_pb2_grpc")

from apex.api import apex_pb2, apex_pb2_grpc  # noqa: E402


class _FakeRpcContext:
    def set_code(self, *_args, **_kwargs) -> None:
        return None

    def set_details(self, *_args, **_kwargs) -> None:
        return None


class _MockSearchServicer(apex_pb2_grpc.SearchServiceServicer):
    def Search(self, request, context):
        chunk = apex_pb2.Chunk(
            id="mock-chunk-1",
            modality=apex_pb2.MODALITY_TEXT,
            content="Chief Justice John Marshall delivered the opinion.",
            context_summary="Marbury excerpt",
            provenance=apex_pb2.Provenance(
                source_uri="sample_marbury_excerpt.txt",
                modality=apex_pb2.MODALITY_TEXT,
                page=1,
            ),
        )
        yield apex_pb2.RetrievedChunk(chunk=chunk, score=0.92, fusion_rank=1)


def test_grpc_search_mock_server_response():
    """Unit test: mock SearchService servicer streams one RetrievedChunk."""
    servicer = _MockSearchServicer()
    request = apex_pb2.SearchRequest(query="Who delivered the opinion in Marbury?", top_k=3)
    results = list(servicer.Search(request, _FakeRpcContext()))
    assert len(results) == 1
    assert "Marshall" in results[0].chunk.content
    assert results[0].score == pytest.approx(0.92)
    assert results[0].chunk.provenance.source_uri == "sample_marbury_excerpt.txt"


@pytest.mark.grpc_integration
@pytest.mark.skip(reason="needs live gRPC server")
def test_grpc_search_live_server():
    """Integration test: requires `make api-grpc` on GRPC_PORT (default 50051)."""
    from apex.settings import get_settings

    settings = get_settings()
    channel = grpc.insecure_channel(f"localhost:{settings.grpc_port}")
    stub = apex_pb2_grpc.SearchServiceStub(channel)
    stream = stub.Search(apex_pb2.SearchRequest(query="Brown v. Board", top_k=5))
    results = list(stream)
    assert len(results) >= 1
