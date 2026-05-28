"""Extract the blue icon from the Repak logo PNG and trace it to a smooth SVG."""

from PIL import Image, ImageFilter
import numpy as np
import vtracer
import tempfile
import os
import re

# Load and isolate blue pixels
img = Image.open(r"D:\Downloads\repak_logo.png").convert("RGBA")
arr = np.array(img)
r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]

# Blue mask — the icon part only
blue_mask = (b > 150) & (r < 100) & (a > 128)

# Crop to blue region with padding
coords = np.argwhere(blue_mask)
ymin, xmin = coords.min(axis=0)
ymax, xmax = coords.max(axis=0)
pad = 4
ymin = max(0, ymin - pad)
xmin = max(0, xmin - pad)
ymax = min(arr.shape[0] - 1, ymax + pad)
xmax = min(arr.shape[1] - 1, xmax + pad)

cropped_mask = blue_mask[ymin : ymax + 1, xmin : xmax + 1]
h, w = cropped_mask.shape
print(f"Cropped blue icon: {w}x{h}")

# Create grayscale mask image and upscale with LANCZOS for smooth edges
scale = 10
sw, sh = w * scale, h * scale

mask_img = Image.fromarray((cropped_mask * 255).astype(np.uint8), "L")
mask_smooth = mask_img.resize((sw, sh), Image.LANCZOS)

# Apply slight gaussian blur then re-threshold for extra smoothness
mask_smooth = mask_smooth.filter(ImageFilter.GaussianBlur(radius=1.5))
mask_arr = np.array(mask_smooth)
mask_binary = (mask_arr > 128).astype(np.uint8) * 255

# Build black-on-white RGBA image for vtracer
out_arr = np.full((sh, sw, 4), 255, dtype=np.uint8)
black = mask_binary > 128
out_arr[black, 0] = 0
out_arr[black, 1] = 0
out_arr[black, 2] = 0

rgba_img = Image.fromarray(out_arr, "RGBA")

# Save temp PNG for vtracer
tmp = tempfile.mktemp(suffix=".png")
rgba_img.save(tmp)

# Trace with high quality spline settings
tmp_svg = tempfile.mktemp(suffix=".svg")
vtracer.convert_image_to_svg_py(
    image_path=tmp,
    out_path=tmp_svg,
    colormode="color",
    mode="spline",
    filter_speckle=4,
    color_precision=8,
    corner_threshold=60,
    length_threshold=4.0,
    splice_threshold=45,
    max_iterations=10,
    path_precision=2,
)

with open(tmp_svg, "r") as f:
    svg_str = f.read()

os.unlink(tmp)
os.unlink(tmp_svg)

print(f"Raw SVG length: {len(svg_str)}")

# Extract paths with their fills
all_paths = re.findall(r'd="([^"]+)"', svg_str)
all_fills = re.findall(r'fill="([^"]+)"', svg_str)

print(f"All paths found: {len(all_paths)}")
for i, (p, f) in enumerate(zip(all_paths, all_fills)):
    print(f"  Path {i}: fill={f}, d_length={len(p)}")

# Path 0 is the white background rectangle — skip it.
# Remaining paths: 2 black outer rings + 2 white inner holes.
# Combine all with evenodd fill-rule so inner paths punch holes.
icon_paths = all_paths[1:]  # skip the background rect

print(f"Icon paths (excluding bg): {len(icon_paths)}")

if not icon_paths:
    print("ERROR: No icon paths found!")
    exit(1)

combined = " ".join(icon_paths)

# Build clean SVG with oklch fill
svg = (
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {sw} {sh}"'
    f' fill="oklch(0.4515 0.0902 230.26)">\n'
    f'  <path d="{combined}" fill-rule="evenodd"/>\n'
    f"</svg>\n"
)

out_path = r"C:\Users\collert\WebstormProjects\AI-calling-assistant\dashboard\public\repak_icon.svg"
with open(out_path, "w") as f:
    f.write(svg)

print(f"SVG written to {out_path}")
print(f"SVG size: {len(svg)} bytes")
