"""
Slim Flask entry point. DO NOT MOVE - if this ever gets deployed to Render,
its Start Command will point at this exact path (same convention as
ai-consulting-lab/app.py).
"""
from flask import Flask, jsonify

import config
from routes.ingestion import ingestion_bp

app = Flask(__name__)
app.register_blueprint(ingestion_bp)


@app.route("/")
def health_check():
    return jsonify({"status": "ok", "service": "claims-triage-agent"})


if __name__ == "__main__":
    app.run(port=config.PORT, debug=True)
