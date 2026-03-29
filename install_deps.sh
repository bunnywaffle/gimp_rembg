#!/usr/bin/env python3
"""Worker script for GIMP RemBG plugin - runs rembg in a subprocess."""
import sys
import os

def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <input> <output> <model>", file=sys.stderr)
        sys.exit(1)

    input_path, output_path, model_name = sys.argv[1], sys.argv[2], sys.argv[3]

    if not os.path.exists(input_path):
        print(f"Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    try:
        from rembg import remove
        from PIL import Image
    except ImportError as e:
        print(f"Import error: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        img = Image.open(input_path)
        result = remove(img, alpha_matting=False,
                       alpha_matting_foreground_threshold=240,
                       alpha_matting_background_threshold=10,
                       alpha_matting_erode_size=10,
                       only_mask=False,
                       post_process_mask=False)
        result.save(output_path)
    except Exception as e:
        print(f"rembg error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
