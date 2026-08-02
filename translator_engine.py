import os, json, cv2, numpy as np, zipfile, fitz
from PIL import Image, ImageDraw, ImageFont

def convert_to_images(input_path, output_folder="temp_pages"):
    os.makedirs(output_folder, exist_ok=True)
    ext = os.path.splitext(input_path)[1].lower()
    if ext == ".pdf":
        doc = fitz.open(input_path)
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            img.save(f"{output_folder}/{i+1:04d}.png")
        doc.close()
    elif ext == ".zip":
        with zipfile.ZipFile(input_path, 'r') as z:
            images = sorted([f for f in z.namelist() if f.lower().endswith(('.png','.jpg','.jpeg','.bmp'))])
            for idx, name in enumerate(images):
                z.extract(name, "temp_extracted")
                Image.open(os.path.join("temp_extracted", name)).convert("RGB").save(f"{output_folder}/{idx+1:04d}.png")
    elif ext in (".jpg",".jpeg",".png"):
        Image.open(input_path).convert("RGB").save(f"{output_folder}/0001.png")
    return sorted(os.listdir(output_folder))

def detect_bubbles(image_path):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    bubbles = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = cv2.contourArea(cnt)
        if 1000 < area < 800000 and 0.2 < w/h < 5:
            x1, y1 = max(0, x-5), max(0, y-5)
            x2, y2 = min(img.shape[1], x+w+5), min(img.shape[0], y+h+5)
            bubbles.append({'bbox': (x1,y1,x2,y2), 'contour': cnt})
    return bubbles

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
        bubbles = detect_bubbles(page_path)
        bubble_data = []

        img = cv2.imread(page_path)
        for idx, b in enumerate(bubbles):
            bbox = b['bbox']
            contour = b['contour']
            bid = f"{page_file.replace('.png','')}_{idx+1}"

            orig_text = "[Text Detected]"  # Placeholder for native mobile OCR
            bubble_info = {
                'id': bid, 'bbox': bbox, 'contour_points': contour.tolist(),
                'original_text': orig_text, 'colour': (0,0,0)
            }
            bubble_data.append(bubble_info)

            txt_lines.append(f"{bid}=Dilouges={orig_text}")
            txt_lines.append("Font=default")
            txt_lines.append("Colour=(0,0,0)")

            # Inpaint / Clean text box area
            x1, y1, x2, y2 = bbox
            cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), -1)

        full_map[page_file] = bubble_data
        clean_path = os.path.join(clean_pages, page_file)
        cv2.imwrite(clean_path, img)

    json_path = os.path.join(output_dir, "translation_map.json")
    txt_path = os.path.join(output_dir, "translate_me.txt")
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(full_map, f, indent=2)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(txt_lines))

    return txt_path