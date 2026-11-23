import argparse
import json
from dataclasses import dataclass
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from geopandas import GeoDataFrame
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .places import filter_places, find_places_nearby, load_places


class FilterArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    category: Optional[str] = Field(
        default=None, min_length=1, description="Category, such as Restaurant. Omit for all categories."
    )
    locality: Optional[str] = Field(
        default=None, min_length=1, description="Locality, such as Al Satwa. Omit for all localities."
    )

    @field_validator("category", "locality")
    @classmethod
    def normalize_all(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value.casefold() == "all":
            return None
        return value


class NearbyArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    category: str = Field(min_length=1, description="Dataset category, such as Restaurant.")
    landmark_name: str = Field(min_length=1, description="Exact name of the reference place.")
    radius_m: float = Field(gt=0, allow_inf_nan=False, description="Distance in meters.")


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "filter_places",
            "description": "List Dubai places with optional category and locality filters. Use empty arguments for all places.",
            "parameters": FilterArguments.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_places_nearby",
            "description": "Find places in a category within a stated distance of a named point.",
            "parameters": NearbyArguments.model_json_schema(),
        },
    },
]

SYSTEM_PROMPT = (
    "You select GIS functions for a fixed Dubai points-of-interest sample. "
    "The dataset stores categories in singular form, for example Restaurant, "
    "and locality labels such as Al Satwa. A named point in the sample is "
    "Financial Center Metro Bus Stop Seaside. "
    "Use the exact dataset labels and convert requested distances to meters. "
    "For 'show all POIs', call filter_places with empty arguments. "
    "Omit category or locality filters the question does not specify. "
    "Dubai is the whole sample, so a citywide request uses no locality filter. "
    "Call one function only when the question supplies all of its required details. "
    "For unsupported requests or missing details, return no tool call. "
    "The backend calculates and reports all results."
)

GREETINGS = {
    "hi", "hello", "hey", "hi there", "hello there", "hey there",
    "good morning", "good afternoon", "good evening",
}


@dataclass
class ChatResult:
    answer: str
    features: Optional[GeoDataFrame] = None
    tool_name: Optional[str] = None
    arguments: Optional[dict] = None
    is_greeting: bool = False


def request_tool_call(model: str, question: str) -> list[dict]:
    """Send a question and the available functions to the local Ollama API."""
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        "tools": TOOLS,
        "options": {"temperature": 0},
    }
    request = Request(
        "http://127.0.0.1:11434/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            message = json.load(response)["message"]
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama returned HTTP {error.code}: {detail}") from error
    except (URLError, TimeoutError) as error:
        raise RuntimeError(f"Could not connect to local Ollama: {error}") from error

    return message.get("tool_calls") or []


def answer_question(places: GeoDataFrame, question: str, model: str) -> ChatResult:
    greeting = " ".join(question.casefold().split()).rstrip("!?.").strip()
    if greeting in GREETINGS:
        return ChatResult(
            'Hi! Ask me about places in the Dubai sample. Try "Show restaurants in Al Satwa."',
            is_greeting=True,
        )

    calls = request_tool_call(model, question)
    if not calls:
        return ChatResult(
            "Ask for a category in a Dubai locality, or give me a category, "
            "a named place, and a distance in meters."
        )
    if len(calls) != 1:
        return ChatResult("Please ask one map question at a time.")

    try:
        function = calls[0]["function"]
        name = function["name"]
        if name == "filter_places":
            args = FilterArguments.model_validate(function["arguments"])
            matches = filter_places(places, args.category, args.locality)
            category = f" in the {args.category} category" if args.category else ""
            locality = f" in {args.locality}" if args.locality else ""
            answer = f"Found {len(matches):,} places{category}{locality} in the Dubai sample."
        elif name == "find_places_nearby":
            args = NearbyArguments.model_validate(function["arguments"])
            matches = find_places_nearby(
                places, args.category, args.landmark_name, args.radius_m
            )
            answer = (
                f"Found {len(matches):,} places in the {args.category} category "
                f"within {args.radius_m:g} m of {args.landmark_name} in the Dubai sample."
            )
        else:
            return ChatResult("That operation is unavailable in this demo.")
    except (KeyError, TypeError, ValidationError):
        return ChatResult("Please restate the question with the category and location details.")
    except ValueError as error:
        return ChatResult(str(error))

    return ChatResult(answer, matches, name, args.model_dump(exclude_none=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask Ollama a question about Dubai places.")
    parser.add_argument("question", help="Map question in quotes")
    parser.add_argument("--model", required=True, help="Name of your installed Ollama model")
    args = parser.parse_args()

    places = load_places()
    try:
        result = answer_question(places, args.question, args.model)
    except RuntimeError as error:
        parser.exit(1, f"{error}\n")

    if result.tool_name:
        print(f"Tool: {result.tool_name}")
        print(f"Arguments: {json.dumps(result.arguments)}")
    print(result.answer)


if __name__ == "__main__":
    main()
