# Chat with Maps

Explore Dubai points of interest through natural-language questions and an interactive map. Chat with Maps uses a local Ollama model to select geographic search functions, then computes results from a bundled GeoJSON dataset using GeoPandas and PyProj.

## Features

- Filter places by category, locality, or both.
- Find places within a distance of a named landmark, with distances in meters.
- View matching points, result tables, and a search-radius overlay.
- Keep up to 20 conversations in browser local storage.
- Run a plain HTML/CSS/JavaScript client and FastAPI API from one server, with no Node.js or frontend build step.

Model inference runs locally. The map requires internet access for MapLibre assets from unpkg and the OpenFreeMap basemap.

## Quick start

### 1. Prerequisites

- Python with `pip` and `venv`. The current pinned dependencies have been exercised locally with Python 3.9.11; newer Python versions have not been verified for this project.
- Git to clone the repository.
- [Ollama](https://ollama.com/download) installed and running locally, with enough memory and disk space for your chosen model.
- A modern browser with WebGL support and internet access for the map.

### 2. Clone the project

```sh
git clone https://github.com/khaled-ibrahim-11/chat-with-maps.git
cd chat-with-maps
```

### 3. Install Python dependencies

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r server/requirements.txt
```

**macOS / Linux**

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r server/requirements.txt
```

The commands below use the virtual environment's Python directly, so activation is optional.

### 4. Prepare Ollama

Start the Ollama application, or run `ollama serve` in a separate terminal if it is not already running. Then download the default model:

```sh
ollama pull llama3.1:8b
ollama list
```

The backend expects Ollama at `http://127.0.0.1:11434`. Keep Ollama running while using chat.

### 5. Start the application

Run from the repository root.

**Windows (PowerShell)**

```powershell
.\.venv\Scripts\python.exe -m server
```

**macOS / Linux**

```sh
.venv/bin/python -m server
```

Open **http://127.0.0.1:8000**. Stop the server with `Ctrl+C`.

The bundled `data/dubai-pois.geojson` is loaded automatically. No API key, database, `.env` file, or separate frontend server is required.

## Example questions

- "Show restaurants in Al Satwa."
- "Show all places in Al Satwa."
- "Show restaurants within 500 meters of Financial Center Metro Bus Stop Seaside."
- "Show all POIs."

Each request is independent: saved conversation history is displayed in the browser but is not sent as context to the model. Include the category, location, and distance needed for each question. Search matches dataset labels exactly and is case-sensitive; the model is prompted to select those labels.

## Configuration

With your virtual environment activated, or using its Python executable as above:

```sh
python -m server --model llama3.1:8b --port 8000
```

| Setting | Default | How to change it |
| --- | --- | --- |
| Model | `llama3.1:8b` | `--model`; pull the model in Ollama first and use a model supporting tool calls |
| Application port | `8000` | `--port` |
| Bind address | `127.0.0.1` | Defined in `server/app.py` |
| Ollama endpoint | `http://127.0.0.1:11434/api/chat` | Defined in `server/chat.py` |
| Dataset | `data/dubai-pois.geojson` | `DATA_PATH` in `server/config.py` |

Paths are resolved relative to the project. Environment variables are not currently used for configuration. The Ollama request timeout is 120 seconds; the browser timeout is 150 seconds.

## Dataset

The bundled sample contains **9,465 point features** in WGS 84 (`EPSG:4326`). It is a fixed sample, not a live directory or a complete inventory of Dubai.

To replace it, provide a GeoJSON FeatureCollection at the configured path with nonempty Point geometries, a valid coordinate reference system, and these properties:

| Property | Purpose | Example |
| --- | --- | --- |
| `POI_Name_English` | Display name and exact landmark lookup | `Financial Center Metro Bus Stop Seaside` |
| `Category` | Category filter | `Restaurant` |
| `Locality` | Neighborhood filter | `Al Satwa` |

For WGS 84 GeoJSON, coordinates are `[longitude, latitude]`. Landmark names used for radius searches must identify exactly one feature. Distances use WGS 84 geodesic calculations, not walking or driving routes. Nearby results include a `distance_m` property.

Loading selects these three properties and geometry; other source properties are not returned by the API. If you change the dataset, update the sample-specific prompt in `server/chat.py` and suggestions in `client/index.html`. Restart the server after dataset changes.

Dataset provenance and redistribution terms are not documented in this repository.

## Architecture and project structure

```text
Browser -> FastAPI -> Ollama (select a tool and its arguments)
                  -> GeoPandas / PyProj (execute the search)
Browser <- answer + GeoJSON results + optional search area
```

The model selects from two validated tools, `filter_places` and `find_places_nearby`. The backend computes the matches and response text.

```text
client/
  index.html           Page structure and suggested questions
  css/styles.css       Layout and styling
  js/app.js            Chat, browser history, and MapLibre rendering
server/
  __init__.py          Python package
  __main__.py          python -m server entry point
  app.py               FastAPI routes, static files, and search overlays
  config.py            Project and dataset paths
  chat.py              Ollama requests and validated tool selection
  places.py            Dataset loading, filters, and distance calculations
  requirements.txt     Pinned direct Python dependencies
data/
  dubai-pois.geojson    Bundled Dubai sample
```

## API

With the server running, interactive documentation is available at `/docs`, alternative documentation at `/redoc`, and the OpenAPI schema at `/openapi.json`.

### `POST /api/chat`

Request body:

```json
{
  "question": "Show restaurants in Al Satwa."
}
```

`question` must contain 1–500 characters after surrounding whitespace is stripped.

**PowerShell**

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/chat -Method Post -ContentType 'application/json' -Body '{"question":"Show restaurants in Al Satwa."}'
```

**macOS / Linux**

```sh
curl http://127.0.0.1:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"Show restaurants in Al Satwa."}'
```

Response fields:

| Field | Meaning |
| --- | --- |
| `answer` | Backend-generated result summary or guidance |
| `features` | GeoJSON FeatureCollection of matching points; may be empty |
| `search_area` | GeoJSON FeatureCollection containing a radius polygon and landmark point for nearby searches; otherwise `null` |
| `is_greeting` | Whether the request was handled as a greeting without calling Ollama |

Invalid request bodies return HTTP `422`. Ollama connection failures, timeouts, and HTTP errors handled by the backend return HTTP `502`. Unsupported questions or ambiguous landmarks can return HTTP `200` with guidance in `answer` and no matches.

The server also serves the application at `/` and client assets at `/static/`.

## Development and verification

Use the virtual environment's Python executable, or activate it before running these commands:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```sh
# macOS / Linux
source .venv/bin/activate
```

If PowerShell blocks activation, continue using `.\.venv\Scripts\python.exe` directly.

```sh
# Check backend imports and command-line options
python -m server --help

# Load the dataset and run geographic queries without Ollama
python -m server.places

# Run a full natural-language query through Ollama
python -m server.chat "Show restaurants in Al Satwa." --model llama3.1:8b
```

For a basic API smoke check without model inference, send `{"question":"hello"}` to `/api/chat`. To check the full workflow, run an example search in the browser and verify the table, map markers, and radius overlay for a nearby query.

Restart the server after Python changes; refresh the browser after client changes. There is currently no automated test suite or CI workflow. Direct dependencies are pinned, but transitive dependencies are not locked.

When contributing, keep changes focused, describe how to reproduce the issue or feature, and include the verification you performed. Changes to tool arguments should update their Pydantic schemas, tool definitions, and relevant documentation together.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| `Dataset not found` | Ensure `data/dubai-pois.geojson` exists, or update `DATA_PATH`. |
| Missing field or geometry errors | Check the required properties, Point geometries, and CRS described above. |
| `Could not connect to local Ollama` / HTTP `502` | Start Ollama and confirm it is listening on port `11434`. |
| Model not found | Run `ollama pull llama3.1:8b`, or pull the model supplied with `--model`. |
| Search times out | Confirm the model runs locally; initial loading may take time. A smaller tool-capable model can reduce resource needs, but results may differ. |
| No matches or clarification response | Use exact dataset labels and supply the required details. Landmark names must be unique. |
| Map fails but chat works | Check internet access, WebGL support, and access to `unpkg.com` and `tiles.openfreemap.org`. |
| Chat fails after opening the HTML file directly | Open `http://127.0.0.1:8000` through the running server. |
| Port already in use | Start with `--port 8001` and open the matching address. |
| Python dependencies fail to install | Use an isolated environment and check compatibility with the pinned versions in `server/requirements.txt`. |

## Scope and privacy

This is a local development demo. It has no authentication, rate limiting, or production deployment configuration. Questions are sent to the local Ollama endpoint. Conversation messages and returned results are stored in the browser's local storage; clear site data to remove them. Map assets and basemap requests contact external services.

Supported searches cover category/locality filtering and straight-line proximity to a dataset landmark. Routing, live business information, and multi-turn reasoning are not implemented.

## License

No project license has been specified yet. Dependency licenses and dataset usage rights are separate from the application code.
