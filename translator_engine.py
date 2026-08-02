import os
import json
import zipfile
import io
import shutil
import textwrap
from PIL import Image, ImageDraw, ImageFont
import pypdf

def get_download_dir():
    candidates = [
        "/storage/emulated/0/Download",
        "/sdcard/Download",
        os.path.expanduser("~/Downloads"),
        os.path.abspath("workspace/output")
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                test_file = os.path.join(path, ".perm_test")
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
                return path
            except Exception:
                continue
    out_dir = os.path.abspath("workspace/output")
    os.makedirs(out_dir, exist_ok=True)
    return out_dir

def clean_dir(folder_path):
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path, ignore_errors=True)
    os.makedirs(folder_path, exist_ok=True)

def convert_to_images(input_path, output_folder="workspace/temp_pages"):
    clean_dir(output_folder)
    ext = os.path.splitext(input_path)[1].lower()

    if ext == ".pdf":
        reader = pypdf.PdfReader(input_path)
        count = 1
        for page in reader.pages:
            for img_file in page.images:
                try:
                    img = Image.open(io.BytesIO(img_file.data)).convert("RGB")
                    img.save(os.path.join(output_folder, f"{count:04d}.png"))
                    count += 1
                except Exception as e:
                    print(f"Skipping PDF image error: {e}")
    elif ext == ".zip":
        temp_extracted = "workspace/temp_extracted"
        clean_dir(temp_extracted)
        with zipfile.ZipFile(input_path, 'r') as z:
            images = sorted([
                f for f in z.namelist() 
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp'))
                and not f.startswith('__MACOSX')
            ])
            for idx, name in enumerate(images):
                try:
                    data = z.read(name)
                    img = Image.open(io.BytesIO(data)).convert("RGB")
                    img.save(os.path.join(output_folder, f"{idx+1:04d}.png"))
                except Exception as e:
                    print(f"Skipping ZIP image error {name}: {e}")
        shutil.rmtree(temp_extracted, ignore_errors=True)
    elif ext in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
        img = Image.open(input_path).convert("RGB")
        img.save(os.path.join(output_folder, "0001.png"))

    return sorted([
        f for f in os.listdir(output_folder) 
        if f.lower().endswith(('.png', '.jpg', '.jpeg'))
    ])

def get_page_paths(pages_folder="workspace/temp_pages"):
    if not os.path.exists(pages_folder):
        return []
    files = sorted([
        f for f in os.listdir(pages_folder)
        if f.lower().endswith(('.png', '.jpg', '.jpeg'))
    ])
    return [os.path.join(pages_folder, f) for f in files]

def detect_bubbles_pil(image_path):
    img = Image.open(image_path)
    w, h = img.size
    b1 = (int(w * 0.50), int(h * 0.05), int(w * 0.92), int(h * 0.22))
    b2 = (int(w * 0.08), int(h * 0.35), int(w * 0.50), int(h * 0.52))
    b3 = (int(w * 0.30), int(h * 0.68), int(w * 0.85), int(h * 0.88))
    return [
        {'bbox': b1, 'id_suffix': '1'},
        {'bbox': b2, 'id_suffix': '2'},
        {'bbox': b3, 'id_suffix': '3'},
    ]

def draw_wrapped_text(draw, bbox, text, text_color=(0, 0, 0), bg_color=(255, 255, 255)):
    x0, y0, x1, y1 = bbox
    w = x1 - x0
    h = y1 - y0

    draw.rectangle([x0, y0, x1, y1], fill=bg_color, outline=(0, 0, 0), width=3)

    font_size = max(14, int(h * 0.10))
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", font_size)
    except Exception:
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

    avg_char_w = font_size * 0.55 if font_size > 10 else 7
    chars_per_line = max(5, int((w - 20) / avg_char_w))
    lines = textwrap.wrap(text, width=chars_per_line)

    line_height = font_size + 4
    total_text_height = len(lines) * line_height
    start_y = y0 + max(5, (h - total_text_height) // 2)

    for line in lines:
        try:
            bbox_line = font.getbbox(line)
            line_w = bbox_line[2] - bbox_line[0]
        except Exception:
            line_w = len(line) * avg_char_w

        start_x = x0 + max(5, (w - line_w) // 2)
        draw.text((start_x, start_y), line, fill=text_color, font=font)
        start_y += line_height

def run_phase1(input_file, work_dir="workspace"):
    temp_pages = os.path.join(work_dir, "temp_pages")
    clean_pages = os.path.join(work_dir, "clean_pages")
    output_dir = os.path.join(work_dir, "output")
    
    clean_dir(clean_pages)
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

        for b in bubbles:
            bbox = b['bbox']
            bid = f"{page_file.replace('.png','')}_{b['id_suffix']}"
            orig_text = f"Sample Dialogue {b['id_suffix']}"

            bubble_info = {
                'id': bid,
                'bbox': bbox,
                'original_text': orig_text,
                'colour': [0, 0, 0]
            }
            bubble_data.append(bubble_info)

            txt_lines.append(f"{bid}=Dialogues={orig_text}")
            txt_lines.append("Font=default")
            txt_lines.append("Colour=(0,0,0)")
            txt_lines.append("")

            draw.rectangle(bbox, fill=(255, 255, 255), outline=(0, 0, 0), width=2)

        full_map[page_file] = bubble_data
        clean_path = os.path.join(clean_pages, page_file)
        img.save(clean_path)

    json_path = os.path.join(output_dir, "translation_map.json")
    download_dir = get_download_dir()
    txt_path = os.path.join(download_dir, "translate_me.txt")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(full_map, f, indent=2)

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(txt_lines))

    return txt_path

def run_phase2(translated_txt_path, work_dir="workspace"):
    clean_dir_path = os.path.join(work_dir, "clean_pages")
    final_dir = os.path.join(work_dir, "final_pages")
    map_json = os.path.join(work_dir, "output", "translation_map.json")
    
    clean_dir(final_dir)

    if not os.path.exists(map_json):
        raise FileNotFoundError("Map file missing.")

    translations = {}
    with open(translated_txt_path, 'r', encoding='utf-8') as f:
        for line in f.read().splitlines():
            line_str = line.strip()
            if '=Dialogues=' in line_str:
                bid, text = line_str.split('=Dialogues=', 1)
                translations[bid.strip()] = text.strip()

    with open(map_json, 'r', encoding='utf-8') as f:
        page_map = json.load(f)

    for page_file, bubbles in page_map.items():
        clean_path = os.path.join(clean_dir_path, page_file)
        if not os.path.exists(clean_path):
            continue

        img = Image.open(clean_path).convert("RGB")
        draw = ImageDraw.Draw(img)

        for b in bubbles:
            bid = b['id']
            if bid in translations:
                text = translations[bid]
                bbox = b['bbox']
                draw_wrapped_text(draw, bbox, text)

        img.save(os.path.join(final_dir, page_file))
    return True

def create_final_zip(work_dir="workspace"):
    final_dir = os.path.join(work_dir, "final_pages")
    if not os.path.exists(final_dir) or not os.listdir(final_dir):
        raise FileNotFoundError("No rendered pages found.")

    download_dir = get_download_dir()
    zip_path = os.path.join(download_dir, "Final_Manga_Translated.zip")

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(final_dir):
            for file in sorted(files):
                full_p = os.path.join(root, file)
                z.write(full_p, arcname=file)

    return zip_path
