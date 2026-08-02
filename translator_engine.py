import os, json, zipfile, io
from PIL import Image, ImageDraw, ImageFont
import pypdf

def convert_to_images(input_path, output_folder="workspace/temp_pages"):
    os.makedirs(output_folder, exist_ok=True)
    ext = os.path.splitext(input_path)[1].lower()

    if ext == ".pdf":
        reader = pypdf.PdfReader(input_path)
        count = 1
        for page in reader.pages:
            for img_file in page.images:
                img = Image.open(io.BytesIO(img_file.data)).convert("RGB")
                img.save(f"{output_folder}/{count:04d}.png")
                count += 1
        if count == 1:
            # FIX: this only pulls embedded raster images out of the PDF —
            # it does NOT render PDF pages that are pure text/vector content.
            # Previously that case silently produced zero pages with no
            # explanation ("Koi pages nahi mile" was the only symptom).
            raise ValueError(
                "Is PDF mein koi embedded image nahi mili (ye text/vector PDF ho sakta hai). "
                "Ye tool sirf un PDFs se pages nikal sakta hai jinke pages scanned/raster images ke roop mein embedded hain."
            )
    elif ext == ".zip":
        # FIX: extraction folder was hardcoded to "workspace/temp_extracted"
        # regardless of what output_folder the caller passed in. It only
        # ever worked by coincidence because every call site used the
        # default "workspace/..." paths. Now it's derived from output_folder.
        extract_dir = os.path.join(os.path.dirname(output_folder.rstrip('/')) or ".", "temp_extracted")
        with zipfile.ZipFile(input_path, 'r') as z:
            images = sorted([f for f in z.namelist() if f.lower().endswith(('.png','.jpg','.jpeg','.bmp'))])
            for idx, name in enumerate(images):
                z.extract(name, extract_dir)
                Image.open(os.path.join(extract_dir, name)).convert("RGB").save(f"{output_folder}/{idx+1:04d}.png")
    elif ext in (".jpg",".jpeg",".png"):
        Image.open(input_path).convert("RGB").save(f"{output_folder}/0001.png")

    return sorted(os.listdir(output_folder))


def get_page_paths(pages_folder="workspace/temp_pages"):
    """Return sorted full file paths of converted page images (used by Manual Mode gallery)."""
    if not os.path.exists(pages_folder):
        return []
    files = sorted([
        f for f in os.listdir(pages_folder)
        if f.lower().endswith(('.png', '.jpg', '.jpeg'))
    ])
    return [os.path.join(pages_folder, f) for f in files]

def detect_bubbles_pil(image_path, min_area_ratio=0.003, max_area_ratio=0.35, analysis_width=300):
    """
    FIX: the old version returned ONE fake 'bubble' = the entire page minus a
    20px margin. run_phase1() then whited-out that bbox, which meant every
    page's artwork was being erased completely, not just the speech bubbles.

    This version does a real (if simple) flood-fill over bright/white regions
    to find bubble-shaped blobs, using only Pillow (no extra Android build
    dependencies like OpenCV/scipy):
      1. Downscale to `analysis_width` for speed.
      2. Threshold near-white pixels (typical bubble fill colour).
      3. Flood-fill connected white regions (iterative, no recursion limit issues).
      4. Keep only blobs whose size is "bubble-sized" — big enough to matter,
         but not so big it's just the page background (which would recreate
         the old bug). Anything outside that range is ignored, not force-fit.
      5. Scale bounding boxes back up to the original image size.

    Returns [] if nothing bubble-like is found — in that case run_phase1()
    now leaves the page untouched instead of guessing.

    NOTE: this is a lightweight heuristic, not real ML-based bubble
    detection — irregular bubble shapes, coloured bubbles, or bubbles
    touching the page edge can still be missed or merged. Good enough to
    stop destroying pages; not a substitute for a trained detector.
    """
    img = Image.open(image_path).convert('RGB')
    w, h = img.size
    gray = img.convert('L')

    scale = min(1.0, analysis_width / w) if w > 0 else 1.0
    if scale < 1.0:
        small = gray.resize((max(1, int(w * scale)), max(1, int(h * scale))))
    else:
        small = gray
        scale = 1.0
    sw, sh = small.size
    pixels = small.load()

    threshold = 235  # near-white
    total_area = sw * sh
    min_area = max(20, int(total_area * min_area_ratio))
    max_area = int(total_area * max_area_ratio)

    visited = [[False] * sw for _ in range(sh)]
    bubbles = []

    for y in range(sh):
        for x in range(sw):
            if visited[y][x]:
                continue
            if pixels[x, y] < threshold:
                visited[y][x] = True
                continue

            # Iterative flood fill (stack-based — avoids recursion depth issues)
            stack = [(x, y)]
            visited[y][x] = True
            min_x = max_x = x
            min_y = max_y = y
            area = 0
            while stack:
                cx, cy = stack.pop()
                area += 1
                min_x, max_x = min(min_x, cx), max(max_x, cx)
                min_y, max_y = min(min_y, cy), max(max_y, cy)
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < sw and 0 <= ny < sh and not visited[ny][nx] and pixels[nx, ny] >= threshold:
                        visited[ny][nx] = True
                        stack.append((nx, ny))

            if min_area <= area <= max_area:
                bw, bh = max_x - min_x, max_y - min_y
                if bw > 0 and bh > 0:
                    ox1, oy1 = int(min_x / scale), int(min_y / scale)
                    ox2, oy2 = int(max_x / scale), int(max_y / scale)
                    bubbles.append({'bbox': (ox1, oy1, ox2, oy2)})

    return bubbles  # may be empty — caller must handle that, not fabricate one

def run_phase1(input_file, work_dir="workspace"):
    temp_pages = os.path.join(work_dir, "temp_pages")
    clean_pages = os.path.join(work_dir, "clean_pages")
    output_dir = os.path.join(work_dir, "output")
    os.makedirs(clean_pages, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    pages = convert_to_images(input_file, temp_pages)
    full_map = {}
    txt_lines = []

    for page_file in pages:
        page_path = os.path.join(temp_pages, page_file)
        bubbles = detect_bubbles_pil(page_path)
        bubble_data = []

        img = Image.open(page_path).convert("RGB")
        draw = ImageDraw.Draw(img)

        # FIX: previously `bubbles` always had exactly one entry (the whole
        # page). Now it can legitimately be empty if no bubble-shaped region
        # was found — in that case we save the page as-is (untouched art)
        # instead of forcing a fake bubble onto it.
        for idx, b in enumerate(bubbles):
            bbox = b['bbox']
            bid = f"{page_file.replace('.png','')}_{idx+1}"

            orig_text = "[Dialogue Text Here]"
            bubble_info = {'id': bid, 'bbox': bbox, 'original_text': orig_text, 'colour': (0, 0, 0)}
            bubble_data.append(bubble_info)

            txt_lines.append(f"{bid}=Dilouges={orig_text}")
            txt_lines.append("Font=default")
            txt_lines.append("Colour=(0,0,0)")

            draw.rectangle(bbox, fill=(255, 255, 255))

        full_map[page_file] = bubble_data
        clean_path = os.path.join(clean_pages, page_file)
        img.save(clean_path)

    json_path = os.path.join(output_dir, "translation_map.json")
    txt_path = "/sdcard/Download/translate_me.txt" if os.path.exists("/sdcard/Download") else os.path.join(output_dir, "translate_me.txt")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(full_map, f, indent=2)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(txt_lines))

    return txt_path

def run_phase2(translated_txt_path, work_dir="workspace"):
    clean_dir = os.path.join(work_dir, "clean_pages")
    final_dir = os.path.join(work_dir, "final_pages")
    map_json = os.path.join(work_dir, "output", "translation_map.json")
    os.makedirs(final_dir, exist_ok=True)

    if not os.path.exists(map_json):
        return "JSON Map Missing"

    translations = {}
    # FIX: previously only the "=Dilouges=" typo'd delimiter was accepted.
    # If anyone (or a future version) writes the correctly-spelled
    # "=Dialogues=" in the translated file, every line used to be silently
    # skipped — no error, no bubbles updated. Both are accepted now.
    with open(translated_txt_path, 'r', encoding='utf-8') as f:
        for line in f.read().splitlines():
            for delim in ('=Dilouges=', '=Dialogues='):
                if delim in line:
                    bid, text = line.split(delim, 1)
                    translations[bid] = text
                    break

    with open(map_json, 'r', encoding='utf-8') as f:
        page_map = json.load(f)

    for page_file, bubbles in page_map.items():
        clean_path = os.path.join(clean_dir, page_file)
        if not os.path.exists(clean_path):
            continue

        img = Image.open(clean_path).convert("RGB")
        draw = ImageDraw.Draw(img)

        for b in bubbles:
            bid = b['id']
            if bid in translations:
                text = translations[bid]
                rx, ry, rw, rh = b['bbox']
                # FIX: this used to hardcode fill=(0,0,0) even though a
                # 'colour' was stored per-bubble in the JSON map — that
                # field was written but never actually applied.
                fill_colour = tuple(b.get('colour', (0, 0, 0)))
                draw.text((rx + 10, ry + 10), text, fill=fill_colour)

        img.save(os.path.join(final_dir, page_file))
    return True

def create_final_zip(work_dir="workspace"):
    final_dir = os.path.join(work_dir, "final_pages")
    export_dir = "/sdcard/Download" if os.path.exists("/sdcard/Download") else "output"
    zip_path = os.path.join(export_dir, "Final_Manga_Translated.zip")

    with zipfile.ZipFile(zip_path, 'w') as z:
        for root, _, files in os.walk(final_dir):
            for file in files:
                z.write(os.path.join(root, file), file)

    return zip_path
