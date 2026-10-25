/**
 * Socket.IO Connection Manager for IPL Auction Simulator
 */

class AuctionSocket {
  constructor() {
    this.socket = null;
    this.roomId = null;
    this.handlers = {};
  }

  connect(roomId, username = "Participant") {
    this.roomId = roomId;

    if (typeof io === "undefined") {
      console.error("Socket.io library not loaded!");
      return;
    }

    // Connect to same host
    this.socket = io({
      transports: ["websocket", "polling"],
      reconnection: true,
      reconnectionAttempts: 15,
      reconnectionDelay: 1000
    });

    this.socket.on("connect", () => {
      console.log("Connected to auction socket server with id:", this.socket.id);
      this.joinRoom(this.roomId, username);
    });

    this.socket.on("disconnect", (reason) => {
      console.warn("Socket disconnected:", reason);
      if (typeof showToast === "function") {
        showToast("Connection to auction server interrupted. Reconnecting...", "warning");
      }
    });

    this.socket.on("reconnect", () => {
      console.log("Socket reconnected!");
      if (typeof showToast === "function") {
        showToast("Reconnected to live auction!", "success");
      }
      this.joinRoom(this.roomId, username);
      this.socket.emit("request_auction_state", { room_id: this.roomId });
    });

    this.socket.on("error_message", (data) => {
      console.error("Socket error received:", data);
      if (typeof showToast === "function") {
        showToast(data.message || "An error occurred", "danger");
      }
    });
  }

  joinRoom(roomId, username) {
    if (!this.socket) return;
    this.socket.emit("join_room", { room_id: roomId, username: username });
  }

  leaveRoom() {
    if (!this.socket || !this.roomId) return;
    this.socket.emit("leave_room", { room_id: this.roomId });
  }

  on(event, callback) {
    if (!this.socket) {
      console.warn("Socket not initialized yet. Registering deferred handler for:", event);
      return;
    }
    this.socket.on(event, callback);
  }

  emit(event, data) {
    if (!this.socket) {
      console.error("Cannot emit event, socket not initialized:", event);
      return;
    }
    this.socket.emit(event, data);
  }
}

window.auctionSocket = new AuctionSocket();
