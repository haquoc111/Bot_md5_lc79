"""
server.py – File server giữ cho Render instance sống
Render free tier sẽ sleep nếu không có HTTP traffic.
File này tạo một web server nhỏ cùng lúc với bot.
"""
import os
import threading
from flask import Flask, jsonify
from bot import main as run_bot

app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "bot":    "SXD Prediction Bot",
        "ping":   "pong"
    })

@app.route("/health")
def health():
    return jsonify({"status": "healthy"}), 200

def start_bot():
    run_bot()

if __name__ == "__main__":
    # Chạy bot trong thread riêng
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()

    # Chạy Flask web server (Render cần HTTP port)
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
