from flask import Flask,session, render_template, request
import os
import logging
from flask_socketio import SocketIO, emit, join_room, leave_room
import random


# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
socketio = SocketIO(app)


# Load the model
logger.info("Model loaded successfully")


@app.route("/")
def index():
    user_id = session.get("user_id")
    if not user_id:
        session["user_id"] = random.randint(1,100000)
    logger.info("Rendering index page")
    return render_template("home.html")

@socketio.on("connect")
def handle_connect():
    user_sid = session.get("user_id")
    join_room(user_sid)
    print("Client connected started", user_sid)


@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected")
    user_sid = session.get("user_id")
    leave_room(user_sid)
    print(f"Client with SID {user_sid} disconnected")

@socketio.on("process_frame")
def process_frame(data):
    user_sid = session.get("user_id")
    emit("frame_processed", user_sid, room=user_sid) # Emit to the specific client


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    socketio.run(app, host="0.0.0.0", port=8000, log_output=True,debug=True)