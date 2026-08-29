"""
Standalone segmentation spike (Milestone 1 from PRD.md).

Not wired into the API yet. Run this directly against a folder of test
photos to check subject cutout quality before building anything else.

Usage:
    python segmentation_spike.py input.jpg output.png
"""
import sys
from pathlib import Path

from PIL import Image
from rembg import remove


def segment_subject(input_path: str, output_path: str) -> None:
    input_image = Image.open(input_path)
    output_image = remove(input_image)
    output_image.save(output_path)
    print(f"Saved cutout to {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python segmentation_spike.py <input_path> <output_path>")
        sys.exit(1)

    in_path, out_path = sys.argv[1], sys.argv[2]
    if not Path(in_path).exists():
        print(f"Input file not found: {in_path}")
        sys.exit(1)

    segment_subject(in_path, out_path)
