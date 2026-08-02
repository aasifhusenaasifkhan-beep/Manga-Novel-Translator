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
    elif ext == ".zip":
        with zipfile.ZipFile(input_path, 'r') as z:
            images = sorted([f for f in z.namelist() if f.lower().endswith(('.png','.jpg','.jpeg','.bmp'))])
            for idx, name in enumerate(images):
                z.extract(name, "workspace/temp_extracted")
                Image.open(os.path.join("workspace/temp_extracted", name)).convert("RGB").save(f"{output_folder}/{idx+1:04d}.png")
    elif ext in (".jpg",".jpeg",".png"):
        Image.open(input_path).convert("RGB").save(f"{output_folder}/0001.png")

    return sorted(os.listdir(output_folder))

def detect_bubbles_pil(image_path):
    img = Image.open(image_path).convert('RGB')
    w, h = img.size
    margin = 20
    return [{'bbox': (margin, margin, w - margin, h - margin), 'contour': [[margin, margin], [w-margin, margin], [w-margin, h-margin], [margin, h-margin]]}]

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

        for idx, b in enumerate(bubbles):
            bbox = b['bbox']
            bid = f"{page_file.replace('.png','')}_{idx+1}"

            orig_text = "[Dialogue Text Here]"
            bubble_info = {'id': bid, 'bbox': bbox, 'original_text': orig_text, 'colour': (0,0,0)}
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
    with open(translated_txt_path, 'r', encoding='utf-8') as f:
        for line in f.read().splitlines():
            if '=' in line and 'Dilouges=' in line:
                bid, text = line.split('=Dilouges=', 1)
                translations[bid] = text

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
                draw.text((rx + 10, ry + 10), text, fill=(0,0,0))

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
