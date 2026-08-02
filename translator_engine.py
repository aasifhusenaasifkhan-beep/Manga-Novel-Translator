import os, json, zipfile, io
from PIL import Image, ImageDraw, ImageFont
import pypdf

def convert_to_images(input_path, output_folder="temp_pages"):
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
                z.extract(name, "temp_extracted")
                Image.open(os.path.join("temp_extracted", name)).convert("RGB").save(f"{output_folder}/{idx+1:04d}.png")
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
            contour = b['contour']
            bid = f"{page_file.replace('.png','')}_{idx+1}"

            orig_text = "[Dialogue Text Here]"
            bubble_info = {
                'id': bid, 'bbox': bbox, 'contour_points': contour,
                'original_text': orig_text, 'colour': (0,0,0)
            }
            bubble_data.append(bubble_info)

            txt_lines.append(f"{bid}=Dilouges={orig_text}")
            txt_lines.append("Font=default")
            txt_lines.append("Colour=(0,0,0)")

            draw.rectangle(bbox, fill=(255, 255, 255))

        full_map[page_file] = bubble_data
        clean_path = os.path.join(clean_pages, page_file)
        img.save(clean_path)

    json_path = os.path.join(output_dir, "translation_map.json")
    txt_path = os.path.join(output_dir, "translate_me.txt")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(full_map, f, indent=2)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(txt_lines))

    return txt_path
