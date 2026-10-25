import pytest
from app import create_app
from app.extensions import db
from app.models.player import Player
from app.services.player_service import search_players, get_player_by_id, seed_or_sync_players

@pytest.fixture
def player_ctx():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        # Seed players if testing DB empty
        if Player.query.count() < 300:
            seed_or_sync_players(force=True)
        yield app
        db.session.remove()
        db.drop_all()

def test_total_player_count_is_300(player_ctx):
    assert Player.query.count() == 300

def test_role_distribution(player_ctx):
    batsmen = Player.query.filter_by(role="Batsman").count()
    wicketkeepers = Player.query.filter_by(role="Wicketkeeper").count()
    allrounders = Player.query.filter_by(role="All-rounder").count()
    bowlers = Player.query.filter_by(role="Bowler").count()

    assert batsmen == 85
    assert wicketkeepers == 40
    assert allrounders == 85
    assert bowlers == 90
    assert (batsmen + wicketkeepers + allrounders + bowlers) == 300

def test_breakout_stars_included(player_ctx):
    # Verify key 2026 stars are present
    vaibhav = Player.query.filter_by(name="Vaibhav Suryavanshi").first()
    assert vaibhav is not None
    assert vaibhav.role == "Batsman"
    assert vaibhav.is_uncapped is True

    digvesh = Player.query.filter_by(name="Digvesh Rathi").first()
    assert digvesh is not None
    assert digvesh.role == "Bowler"
    assert digvesh.is_uncapped is True

    mayank = Player.query.filter_by(name="Mayank Yadav").first()
    assert mayank is not None
    assert mayank.rating >= 90

    andre = Player.query.filter_by(name="C Andre Siddarth").first()
    assert andre is not None

def test_retired_players_excluded(player_ctx):
    # Retired players should not be in the active 300 pool
    assert Player.query.filter_by(name="Dinesh Karthik").first() is None
    assert Player.query.filter_by(name="Wriddhiman Saha").first() is None
    assert Player.query.filter_by(name="Shikhar Dhawan").first() is None

def test_search_and_pagination(player_ctx):
    # Search by name
    res = search_players(query="Kohli", page=1, per_page=10)
    assert len(res["players"]) >= 1
    assert res["players"][0]["name"] == "Virat Kohli"

    # Filter by role
    res_bowlers = search_players(role="Bowler", page=1, per_page=20)
    assert res_bowlers["total"] == 90
    assert len(res_bowlers["players"]) == 20
    assert all(p["role"] == "Bowler" for p in res_bowlers["players"])

    # Filter by overseas
    res_overseas = search_players(is_overseas=True, page=1, per_page=10)
    assert all(p["is_overseas"] is True for p in res_overseas["players"])

def test_player_api_endpoints(player_ctx):
    with player_ctx.test_client() as client:
        # API list
        res = client.get("/api/players?per_page=10")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["total"] == 300
        assert len(data["players"]) == 10

        # API single player
        res_p = client.get("/api/players/1")
        assert res_p.status_code == 200
        p_data = res_p.get_json()
        assert p_data["success"] is True
        assert p_data["player"]["name"] == "Virat Kohli"
