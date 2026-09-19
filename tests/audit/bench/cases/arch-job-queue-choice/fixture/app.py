from flask import Flask, request

from render import render_thumbnail

app = Flask(__name__)


@app.post("/upload")
def upload() -> tuple[str, int]:
    render_thumbnail(request.files["image"].read())
    return "done", 200
