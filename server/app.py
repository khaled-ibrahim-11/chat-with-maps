import argparse
import json
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from geopandas import GeoDataFrame
from pydantic import BaseModel, ConfigDict, Field

from .chat import answer_question
from .config import CLIENT_DIR, DATA_PATH
from .places import WGS84, find_landmark, load_places


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=500)


def search_area(places: GeoDataFrame, landmark_name: str, radius_m: float) -> dict:
    """Make a map overlay using the same center and distance as the search."""
    center = find_landmark(places, landmark_name)
    ring = []
    for bearing in range(0, -360, -5):
        longitude, latitude, _ = WGS84.fwd(center.x, center.y, bearing, radius_m)
        ring.append([longitude, latitude])
    ring.append(ring[0])

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [ring]},
                "properties": {"radius_m": radius_m},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [center.x, center.y]},
                "properties": {"name": landmark_name},
            },
        ],
    }


def create_app(data_path: Path = DATA_PATH, model: str = "llama3.1:8b") -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.places = load_places(data_path)
        yield

    app = FastAPI(title="Chat with Maps", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=CLIENT_DIR), name="client")

    @app.get("/", response_class=FileResponse, include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(CLIENT_DIR / "index.html", media_type="text/html")

    @app.post("/api/chat")
    def chat(message: ChatRequest, request: Request) -> dict:
        places = request.app.state.places
        try:
            result = answer_question(places, message.question, model)
        except RuntimeError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

        features = {"type": "FeatureCollection", "features": []}
        if result.features is not None:
            features = json.loads(result.features.to_crs(epsg=4326).to_json(drop_id=True))

        area = None
        if result.tool_name == "find_places_nearby" and result.arguments is not None:
            area = search_area(places, result.arguments["landmark_name"], result.arguments["radius_m"])

        return {
            "answer": result.answer,
            "features": features,
            "search_area": area,
            "is_greeting": result.is_greeting,
        }

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Chat with Maps demo.")
    parser.add_argument("--model", default="llama3.1:8b", help="Installed Ollama model")
    parser.add_argument("--port", type=int, default=8000, help="Local port for the web app")
    args = parser.parse_args()

    if not DATA_PATH.is_file():
        parser.error(f"Dataset not found: {DATA_PATH}. Place dubai-pois.geojson in the data folder.")

    uvicorn.run(create_app(model=args.model), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
