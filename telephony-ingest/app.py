import logging

from flask import Flask

from routes import bp

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
app.register_blueprint(bp)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5010, debug=True)
