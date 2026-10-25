from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, Response
from flask_login import login_required, current_user
import json
import csv
import io
from app.extensions import db
from app.models.auction import AuctionRoom, AuctionPlayer
from app.models.team import Team, TeamSquad
from app.models.player import Player, format_inr
from app.models.bid import Bid
from app.services.auction_service import (
    create_auction_room,
    get_available_teams_for_room,
    start_auction_service,
    pause_auction_service,
    resume_auction_service,
    get_auction_results_summary,
    load_franchise_data
)

auction_bp = Blueprint("auction", __name__)

@auction_bp.route("/")
def index():
    active_rooms_count = AuctionRoom.query.filter_by(status="active").count()
    total_players_count = Player.query.count()
    franchises = load_franchise_data()
    return render_template(
        "index.html",
        active_rooms_count=active_rooms_count,
        total_players_count=total_players_count,
        franchises=franchises
    )


@auction_bp.route("/dashboard")
@login_required
def dashboard():
    # User's hosted auctions
    hosted_auctions = AuctionRoom.query.filter_by(host_id=current_user.id).order_by(AuctionRoom.created_at.desc()).all()
    # User's teams in auctions
    my_teams = Team.query.filter_by(owner_id=current_user.id).order_by(Team.created_at.desc()).all()
    franchises = load_franchise_data()
    
    return render_template(
        "dashboard.html",
        user=current_user,
        hosted_auctions=hosted_auctions,
        my_teams=my_teams,
        franchises=franchises
    )


@auction_bp.route("/create-auction", methods=["GET", "POST"])
@login_required
def create_auction():
    if request.method == "POST":
        room_name = request.form.get("room_name", "").strip()
        auction_type = request.form.get("auction_type", "mega")
        budget_cr = request.form.get("starting_budget", "120")
        max_teams = int(request.form.get("max_teams", 10))
        timer_duration = int(request.form.get("timer_duration", 30))
        max_overseas = int(request.form.get("max_overseas", 8))
        min_squad = int(request.form.get("min_squad_size", 18))
        max_squad = int(request.form.get("max_squad_size", 25))

        if not room_name:
            flash("Please specify an auction room name.", "danger")
            return render_template("create_auction.html")

        try:
            budget_amount = int(float(budget_cr) * 10000000)
        except Exception:
            budget_amount = 1200000000

        custom_rules = {
            "min_squad_size": min_squad,
            "max_squad_size": max_squad,
            "max_overseas": max_overseas,
            "timer_duration": timer_duration,
            "timer_extend_seconds": 15
        }

        room = create_auction_room(
            user_id=current_user.id,
            room_name=room_name,
            auction_type=auction_type,
            starting_budget=budget_amount,
            max_teams=max_teams,
            custom_rules=custom_rules
        )

        flash(f"Auction '{room.room_name}' created successfully with code {room.room_code}!", "success")
        return redirect(url_for("auction.lobby", auction_id=room.id))

    return render_template("create_auction.html")


@auction_bp.route("/join-auction", methods=["GET", "POST"])
@login_required
def join_auction():
    if request.method == "POST":
        room_code = request.form.get("room_code", "").strip().upper()
        room = AuctionRoom.query.filter_by(room_code=room_code).first()
        if not room:
            flash(f"No auction room found with code '{room_code}'. Please check and try again.", "danger")
            return render_template("join_auction.html")
        
        return redirect(url_for("auction.lobby", auction_id=room.id))

    code_param = request.args.get("code", "")
    return render_template("join_auction.html", code_param=code_param)


@auction_bp.route("/lobby/<int:auction_id>")
@login_required
def lobby(auction_id):
    room = AuctionRoom.query.get_or_404(auction_id)
    if room.status == "active":
        return redirect(url_for("auction.live_auction", auction_id=room.id))
    elif room.status == "completed":
        return redirect(url_for("auction.results", auction_id=room.id))

    user_team = Team.query.filter_by(auction_id=room.id, owner_id=current_user.id).first()
    available_franchises = get_available_teams_for_room(room.id)

    return render_template(
        "lobby.html",
        room=room,
        user_team=user_team,
        available_franchises=available_franchises,
        is_host=(room.host_id == current_user.id)
    )


@auction_bp.route("/auction/<int:auction_id>")
@login_required
def live_auction(auction_id):
    room = AuctionRoom.query.get_or_404(auction_id)
    if room.status == "lobby":
        return redirect(url_for("auction.lobby", auction_id=room.id))
    elif room.status == "completed":
        return redirect(url_for("auction.results", auction_id=room.id))

    user_team = Team.query.filter_by(auction_id=room.id, owner_id=current_user.id).first()
    
    return render_template(
        "live_auction.html",
        room=room,
        user_team=user_team,
        is_host=(room.host_id == current_user.id)
    )


@auction_bp.route("/auction/<int:auction_id>/host")
@login_required
def host_dashboard(auction_id):
    room = AuctionRoom.query.get_or_404(auction_id)
    if room.host_id != current_user.id:
        flash("Access denied. Only the auction host can access this panel.", "danger")
        return redirect(url_for("auction.live_auction", auction_id=room.id))

    teams = Team.query.filter_by(auction_id=room.id).all()
    recent_bids = Bid.query.filter_by(auction_id=room.id).order_by(Bid.id.desc()).limit(20).all()
    queue = AuctionPlayer.query.filter_by(auction_id=room.id).order_by(AuctionPlayer.order_index).all()

    return render_template(
        "host_dashboard.html",
        room=room,
        teams=teams,
        recent_bids=recent_bids,
        queue=queue
    )


@auction_bp.route("/auction/<int:auction_id>/results")
@login_required
def results(auction_id):
    room = AuctionRoom.query.get_or_404(auction_id)
    summary = get_auction_results_summary(auction_id)
    user_team = Team.query.filter_by(auction_id=room.id, owner_id=current_user.id).first()

    return render_template(
        "results.html",
        room=room,
        summary=summary,
        user_team=user_team
    )


@auction_bp.route("/history")
@login_required
def history():
    # User's hosted or participated auctions
    user_team_auction_ids = [t.auction_id for t in current_user.teams]
    auctions = AuctionRoom.query.filter(
        (AuctionRoom.host_id == current_user.id) | (AuctionRoom.id.in_(user_team_auction_ids))
    ).order_by(AuctionRoom.created_at.desc()).all()

    return render_template("history.html", auctions=auctions)


# Export Endpoints
@auction_bp.route("/auction/<int:auction_id>/export/json")
@login_required
def export_json(auction_id):
    summary = get_auction_results_summary(auction_id)
    if not summary:
        return jsonify({"error": "Auction not found"}), 404
    
    response = Response(
        json.dumps(summary, indent=2),
        mimetype="application/json",
        headers={"Content-disposition": f"attachment; filename=auction_{summary['room_code']}_results.json"}
    )
    return response


@auction_bp.route("/auction/<int:auction_id>/export/csv")
@login_required
def export_csv(auction_id):
    room = AuctionRoom.query.get_or_404(auction_id)
    squad_entries = TeamSquad.query.filter_by(auction_id=auction_id).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Auction Code", "Team Name", "Team Code", "Player Name", "Role", "Country", "Overseas", "Purchase Price (INR)", "Purchase Price Formatted"])

    for entry in squad_entries:
        writer.writerow([
            room.room_code,
            entry.team.team_name if entry.team else "N/A",
            entry.team.team_code if entry.team else "N/A",
            entry.player.name if entry.player else "N/A",
            entry.player.role if entry.player else "N/A",
            entry.player.country if entry.player else "N/A",
            "Yes" if (entry.player and entry.player.is_overseas) else "No",
            entry.purchase_price,
            format_inr(entry.purchase_price)
        ])

    response = Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename=auction_{room.room_code}_squads.csv"}
    )
    return response


# REST APIs
@auction_bp.route("/api/auctions", methods=["GET"])
def api_get_auctions():
    rooms = AuctionRoom.query.order_by(AuctionRoom.created_at.desc()).limit(20).all()
    return jsonify({"success": True, "auctions": [r.to_dict() for r in rooms]})


@auction_bp.route("/api/auctions/<int:auction_id>", methods=["GET"])
def api_get_auction(auction_id):
    room = db.session.get(AuctionRoom, auction_id)
    if not room:
        return jsonify({"success": False, "message": "Room not found"}), 404
    return jsonify({"success": True, "auction": room.to_dict(full=True)})


@auction_bp.route("/api/auctions", methods=["POST"])
@login_required
def api_create_auction():
    data = request.get_json() or {}
    room_name = data.get("room_name", "").strip()
    if not room_name:
        return jsonify({"success": False, "message": "Room name is required"}), 400

    room = create_auction_room(
        user_id=current_user.id,
        room_name=room_name,
        auction_type=data.get("auction_type", "mega"),
        starting_budget=data.get("starting_budget"),
        max_teams=data.get("max_teams", 10),
        custom_rules=data.get("custom_rules")
    )
    return jsonify({"success": True, "room": room.to_dict()}), 201


@auction_bp.route("/api/auctions/join", methods=["POST"])
@login_required
def api_join_auction():
    data = request.get_json() or {}
    room_code = data.get("room_code", "").strip().upper()
    room = AuctionRoom.query.filter_by(room_code=room_code).first()
    if not room:
        return jsonify({"success": False, "message": "Invalid room code"}), 404
    return jsonify({"success": True, "room_id": room.id, "room": room.to_dict()})


@auction_bp.route("/api/auctions/<int:auction_id>/start", methods=["POST"])
@login_required
def api_start_auction(auction_id):
    success, room_or_msg = start_auction_service(auction_id, current_user.id)
    if not success:
        return jsonify({"success": False, "message": room_or_msg}), 400
    return jsonify({"success": True, "auction": room_or_msg.to_dict()})


@auction_bp.route("/api/auctions/<int:auction_id>/pause", methods=["POST"])
@login_required
def api_pause_auction(auction_id):
    success, room_or_msg = pause_auction_service(auction_id, current_user.id)
    if not success:
        return jsonify({"success": False, "message": room_or_msg}), 400
    return jsonify({"success": True, "auction": room_or_msg.to_dict()})


@auction_bp.route("/api/auctions/<int:auction_id>/resume", methods=["POST"])
@login_required
def api_resume_auction(auction_id):
    success, room_or_msg = resume_auction_service(auction_id, current_user.id)
    if not success:
        return jsonify({"success": False, "message": room_or_msg}), 400
    return jsonify({"success": True, "auction": room_or_msg.to_dict()})


@auction_bp.route("/api/auctions/<int:auction_id>/current-player", methods=["GET"])
def api_current_player(auction_id):
    room = AuctionRoom.query.get(auction_id)
    if not room:
        return jsonify({"success": False, "message": "Room not found"}), 404
    return jsonify({
        "success": True,
        "current_player": room.current_player.to_dict() if room.current_player else None,
        "current_highest_bid": room.current_highest_bid,
        "current_highest_team": room.highest_bidding_team.to_dict() if room.highest_bidding_team else None
    })


@auction_bp.route("/api/auctions/<int:auction_id>/bids", methods=["GET"])
def api_auction_bids(auction_id):
    bids = Bid.query.filter_by(auction_id=auction_id).order_by(Bid.id.desc()).limit(50).all()
    return jsonify({"success": True, "bids": [b.to_dict() for b in bids]})


@auction_bp.route("/api/auctions/<int:auction_id>/results", methods=["GET"])
def api_auction_results(auction_id):
    summary = get_auction_results_summary(auction_id)
    if not summary:
        return jsonify({"success": False, "message": "Room not found"}), 404
    return jsonify({"success": True, "results": summary})
