"""Run a real local Ollama visual extraction against one worksheet image."""
from __future__ import annotations
import argparse
import json
from config import get_settings
from services.ollama_service import VisionServiceError, extract_worksheet

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract visible worksheet facts with local Ollama.")
    parser.add_argument("image", help="Path to a .jpg, .jpeg, .png, or .webp worksheet")
    args = parser.parse_args()
    try:
        print(json.dumps(extract_worksheet(args.image).model_dump(by_alias=True), indent=2, ensure_ascii=False))
    except VisionServiceError as error:
        print(f"Vision/OCR error [{type(error).__name__}]: {error}")
        if get_settings().debug and error.metadata:
            print(f"Debug generation metadata: {error.metadata}")
        if get_settings().debug and error.raw_response:
            print(f"Debug model response: {error.raw_response!r}")
        raise SystemExit(1)
