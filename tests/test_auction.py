import pytest
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.auction import AuctionRoom
from app.models.team import Team
from app.services.auction_service import (
    create_auction_room,
    select_franchise,
    start_auction_service,
    pause_auction_service,
    resume_auction_service
)

@pytest.fixture
def app_ctx():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        # Create users
        host = User(username="auction_host", email="host@ipl.com")
        host.set_password("hostpass123")
        user2 = User(username="player_two", email="p2@ipl.com")
        user2.set_password("userpass123")
        db.session.add_all([host, user2])
        db.session.commit()
        yield app, host, user2
        db.session.remove()
        db.drop_all()

def test_create_auction_room(app_ctx):
    app, host, user2 = app_ctx
    room = create_auction_room(
        user_id=host.id,
        room_name="Grand Auction 2026",
        auction_type="mega",
        starting_budget=1200000000,
        max_teams=10
    )
    assert room.id is not None
    assert len(room.room_code) == 6
    assert room.host_id == host.id
    assert room.status == "lobby"
    assert room.starting_budget == 1200000000

def test_select_franchise(app_ctx):
    app, host, user2 = app_ctx
    room = create_auction_room(user_id=host.id, room_name="Test Room")
    
    # Host claims CSK
    ok, team_csk = select_franchise(room.id, host.id, "CSK")
    assert ok is True
    assert team_csk.team_code == "CSK"
    assert team_csk.remaining_budget == 1200000000

    # User 2 tries to claim CSK (should fail: duplicate team claim)
    ok_dup, msg = select_franchise(room.id, user2.id, "CSK")
    assert ok_dup is False
    assert "already claimed" in msg

    # User 2 claims MI (should succeed)
    ok_mi, team_mi = select_franchise(room.id, user2.id, "MI")
    assert ok_mi is True
    assert team_mi.team_code == "MI"

def test_start_and_pause_auction(app_ctx):
    app, host, user2 = app_ctx
    room = create_auction_room(user_id=host.id, room_name="Auction Start Test")
    select_franchise(room.id, host.id, "RCB")

    # Start auction
    ok, started_room = start_auction_service(room.id, host.id)
    assert ok is True
    assert started_room.status == "active"
    assert started_room.current_player_id is not None
    assert started_room.bid_deadline is not None

    # Pause auction
    ok_pause, paused_room = pause_auction_service(room.id, host.id)
    assert ok_pause is True
    assert paused_room.status == "paused"

    # Resume auction
    ok_resume, resumed_room = resume_auction_service(room.id, host.id)
    assert ok_resume is True
    assert resumed_room.status == "active"
