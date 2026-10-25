import json
import os
from app.extensions import db
from app.models.player import Player

def seed_or_sync_players(force=False):
    """
    Seeds or synchronizes the database from data/players.json.
    If force=True, cleans and reloads the full 300-player roster with correct IDs 1..300.
    If force=False, seeds if empty or adds missing players up to the full 300 roster.
    """
    json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "players.json")
    if not os.path.exists(json_path):
        return 0

    with open(json_path, "r", encoding="utf-8") as f:
        players_data = json.load(f)

    existing_count = Player.query.count()

    if force:
        from app.models.bid import Bid, AuctionEvent
        from app.models.auction import AuctionPlayer, AuctionRoom
        from app.models.team import TeamSquad, Team

        # Clean test auction records that reference obsolete player IDs
        Bid.query.delete()
        AuctionEvent.query.delete()
        TeamSquad.query.delete()
        AuctionPlayer.query.delete()
        AuctionRoom.query.delete()
        Team.query.delete()
        Player.query.delete()
        db.session.commit()

        for item in players_data:
            p = Player(
                id=item.get("id"),
                name=item["name"],
                country=item.get("country", "India"),
                role=item.get("role", "Batsman"),
                batting_style=item.get("batting_style", "Right Handed"),
                bowling_style=item.get("bowling_style", "None"),
                base_price=item.get("base_price", 20000000),
                is_overseas=item.get("is_overseas", False),
                is_uncapped=item.get("is_uncapped", False),
                image_url=item.get("image_url", ""),
                rating=item.get("rating", 80)
            )
            db.session.add(p)
        db.session.commit()
        print(f"Force seeded all {len(players_data)} players into the database.")
        return len(players_data)

    if existing_count == 0:
        for item in players_data:
            p = Player(
                id=item.get("id"),
                name=item["name"],
                country=item.get("country", "India"),
                role=item.get("role", "Batsman"),
                batting_style=item.get("batting_style", "Right Handed"),
                bowling_style=item.get("bowling_style", "None"),
                base_price=item.get("base_price", 20000000),
                is_overseas=item.get("is_overseas", False),
                is_uncapped=item.get("is_uncapped", False),
                image_url=item.get("image_url", ""),
                rating=item.get("rating", 80)
            )
            db.session.add(p)
        db.session.commit()
        print(f"Seeded {len(players_data)} players into empty database.")
        return len(players_data)

    if existing_count < len(players_data):
        existing_ids = {p.id for p in Player.query.with_entities(Player.id).all()}
        added = 0
        for item in players_data:
            if item.get("id") not in existing_ids:
                p = Player(
                    id=item.get("id"),
                    name=item["name"],
                    country=item.get("country", "India"),
                    role=item.get("role", "Batsman"),
                    batting_style=item.get("batting_style", "Right Handed"),
                    bowling_style=item.get("bowling_style", "None"),
                    base_price=item.get("base_price", 20000000),
                    is_overseas=item.get("is_overseas", False),
                    is_uncapped=item.get("is_uncapped", False),
                    image_url=item.get("image_url", ""),
                    rating=item.get("rating", 80)
                )
                db.session.add(p)
                added += 1
        db.session.commit()
        print(f"Synchronized database with {added} new players (Total: {Player.query.count()}).")
        return Player.query.count()

    return existing_count


def seed_players_if_empty():
    """Backwards-compatible alias for seed_or_sync_players."""
    return seed_or_sync_players(force=False)


def search_players(query=None, role=None, country=None, is_overseas=None, is_uncapped=None, min_price=None, max_price=None, page=1, per_page=20):
    """Filters and searches players with pagination."""
    q = Player.query
    if query:
        q = q.filter(Player.name.ilike(f"%{query}%"))
    if role and role != "All":
        q = q.filter(Player.role == role)
    if country and country != "All":
        q = q.filter(Player.country == country)
    if is_overseas is not None:
        q = q.filter(Player.is_overseas == is_overseas)
    if is_uncapped is not None:
        q = q.filter(Player.is_uncapped == is_uncapped)
    if min_price is not None:
        q = q.filter(Player.base_price >= min_price)
    if max_price is not None:
        q = q.filter(Player.base_price <= max_price)

    # Order by rating descending, then base price descending
    q = q.order_by(Player.rating.desc(), Player.base_price.desc())
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)
    
    return {
        "players": [p.to_dict() for p in pagination.items],
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": page,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev
    }


def get_player_by_id(player_id):
    """Fetches a single player by ID."""
    return db.session.get(Player, player_id)
