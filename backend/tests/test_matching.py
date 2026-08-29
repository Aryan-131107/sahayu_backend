"""
tests/test_matching.py — Explainable Rule-Based Matching Engine Verification
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_matching_recommendations_endpoint():
    """Verify explainable matching endpoint returns expected structure and valid scores."""
    resp = client.get(
        "/api/matching/recommendations?service_id=1&latitude=23.1815&longitude=79.9864&top_n=5"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "recommendations" in data
    recs = data["recommendations"]
    assert len(recs) > 0

    for rec in recs:
        # Check required fields
        assert "worker_id" in rec
        assert "name" in rec
        assert "matching_score" in rec
        assert "recommendation_score" in rec
        assert "score_breakdown" in rec
        assert "reasons" in rec
        assert isinstance(rec["reasons"], list)
        assert len(rec["reasons"]) > 0

        # Verify score normalization (0 to 100)
        assert 0.0 <= rec["matching_score"] <= 100.0
        assert 0.0 <= rec["recommendation_score"] <= 1.0

        # Verify sub-scores
        sb = rec["score_breakdown"]
        assert 0.0 <= sb["skill_score"] <= 100.0
        assert 0.0 <= sb["availability_score"] <= 100.0
        assert 0.0 <= sb["experience_score"] <= 100.0
        assert 0.0 <= sb["rating_score"] <= 100.0
        assert 0.0 <= sb["distance_score"] <= 100.0
        assert 0.0 <= sb["price_score"] <= 100.0

        # Verify exact weighted formula calculation:
        # 0.35*skill + 0.20*avail + 0.15*exp + 0.15*rating + 0.10*dist + 0.05*price
        expected_score = round(
            (sb["skill_score"] * 0.35)
            + (sb["availability_score"] * 0.20)
            + (sb["experience_score"] * 0.15)
            + (sb["rating_score"] * 0.15)
            + (sb["distance_score"] * 0.10)
            + (sb["price_score"] * 0.05),
            2
        )
        assert abs(rec["matching_score"] - expected_score) <= 0.05, (
            f"Calculated score {rec['matching_score']} differs from expected formula {expected_score}"
        )


def test_matching_recommendations_sorted_descending():
    """Verify recommendations are ranked in strictly descending order of matching score."""
    resp = client.get(
        "/api/matching/recommendations?service_id=1&latitude=23.1815&longitude=79.9864&top_n=10"
    )
    assert resp.status_code == 200
    recs = resp.json()["recommendations"]
    if len(recs) > 1:
        scores = [r["matching_score"] for r in recs]
        assert scores == sorted(scores, reverse=True), "Recommendations must be sorted by score descending"


def test_legacy_workers_recommend_endpoint_compatibility():
    """Verify /workers/recommend backwards compatibility."""
    resp = client.get(
        "/workers/recommend?service_id=1&latitude=23.1815&longitude=79.9864&top_n=5"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "recommendations" in data
    assert len(data["recommendations"]) > 0
    rec = data["recommendations"][0]
    assert "relevant_skill" in rec
    assert rec["relevant_skill"] == "Electrician"
