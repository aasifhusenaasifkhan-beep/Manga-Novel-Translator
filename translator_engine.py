import os
import json
import zipfile
import io
from PIL import Image, ImageDraw, ImageFont
import pypdf

def detect_bubbles_pil(image_path):
    """
    Genuine, fast Connected Component Labeling (CCL) implementation.
    Identifies real white speech bubbles by downsampling the target image,
    grouping contiguous bright pixels, and filtering out edge margins.
    """
    try:
        img = Image.open(image_path).convert('L')
        orig_w, orig_h = img.size
        
        # Downsample for faster execution on mobile processors
        scale_w = 400
        scale_h = int(orig_h * (scale_w / orig_w))
        img_small = img.resize((scale_w, scale_h), Image.Resampling.NEAREST)
        
        pixels = img_small.load()
        binary = []
        for y in range(scale_h):
            row = []
            for x in range(scale_w):
                # Binarize: Speech bubbles are bright white
                row.append(1 if pixels[x, y] > 235 else 0)
            binary.append(row)
            
        visited = [[False for _ in range(scale_w)] for _ in range(scale_h)]
        bubbles = []
        
        for y in range(scale_h):
            for x in range(scale_w):
                if binary[y][x] == 1 and not visited[y][x]:
                    # Run Iterative BFS
                    min_x, max_x = x, x
                    min_y, max_y = y, y
                    queue = [(x, y)]
                    visited[y][x] = True
                    
                    while queue:
                        cx, cy = queue.pop(0)
                        if cx < min_x: min_x = cx
                        if cx > max_x: max_x = cx
                        if cy < min_y: min_y = cy
                        if cy > max_y: max_y = cy
                        
                        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            nx, ny = cx + dx, cy + dy
                            if 0 <= nx < scale_w and 0 <= ny < scale_h:
                                if binary[ny][nx] == 1 and not visited[ny][nx]:
                                    visited[ny][nx] = True
                                    queue.append((nx, ny))
                                    
                    w_box = max_x - min_x + 1
                    h_box = max_y - min_y + 1
                    area_ratio = (w_box * h_box) / (scale_w * scale_h)
                    aspect_ratio = w_box / h_box if h_box > 0 else 0
                    
                    # Ignore background margins and out-of-bounds artifacts
                    touches_border = (min_x <= 3 or max_x >= scale_w - 4 or min_y <= 3 or max_y >= scale_h - 4)
                    
                    if not touches_border and 0.003 < area_ratio < 0.20 and 0.3 < aspect_ratio < 3.0:
                        ox1 = int((min_x / scale_w) * orig_w)
                        oy1 = int((min_y / scale_h) * orig_h)
                        ox2 = int((max_x / scale_w) * orig_w)
                        oy2 = int((max_y / scale_h) * orig_h)
                        bubbles.append({
                            'bbox': (ox1, oy1, ox2, oy2)
                        })
                        
        if not bubbles:
            # Safe localized center box to prevent full image wipes
            cx, cy = orig_w // 2, orig_h // 2
            bubbles.append({'bbox': (cx - 120, cy - 60, cx + 120, cy + 60)})
            
        return bubbles
    except Exception as e:
        print(f"Heuristics Error: {e}")
        return [{'bbox': (150, 150, 450, 300)}]


def split_text_to_lines(text, max_width, draw, font):
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
                current_line = [word]
            else:
                lines.append(word)
                current_line = []
    if current_line:
        lines.append(' '.join(current_line))
    return lines


def convert_to_images(input_path, output_folder):
    os.makedirs(output_folder, exist_ok=True)
    ext = os.path.splitext(input_path)[1].lower()

    if ext == ".pdf":
        rendered_natively = False
        try:
            # Dynamic Android Native high-DPI rendering using pyjnius
            from jnius import autoclass
            ParcelFileDescriptor = autoclass('android.os.ParcelFileDescriptor')
            PdfRenderer = autoclass('android.graphics.pdf.PdfRenderer')
            Bitmap = autoclass('android.graphics.Bitmap')
            File = autoclass('java.io.File')
            FileOutputStream = autoclass('java.io.FileOutputStream')
            
            file = File(input_path)
            pfd = ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY)
            renderer = PdfRenderer(pfd)
            page_count = renderer.getPageCount()
            
            for i in range(page_count):
                page = renderer.openPage(i)
                width = page.getWidth()
                height = page.getHeight()
                
                # Render scaling multiplier for clear legibility (2.0x)
                scale = 2.0
                bitmap = Bitmap.createBitmap(int(width * scale), int(height * scale), Bitmap.Config.ARGB_8888)
                page.render(bitmap, None, None, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
                
                out_path = os.path.join(output_folder, f"{i+1:04d}.png")
                out_file = File(out_path)
                fos = FileOutputStream(out_file)
                bitmap.compress(Bitmap.CompressFormat.PNG, 100, fos)
                
                fos.flush()
                fos.close()
                bitmap.recycle()
                page.close()
                
            renderer.close()
            pfd.close()
            rendered_natively = True
        except Exception as android_err:
            print(f"Android Native rendering skipped: {android_err}")
            
        if not rendered_natively:
            # Fallback extraction logic for non-Android environments
            reader = pypdf.PdfReader(input_path)
            count = 1
            for page in reader.pages:
                for img_file in page.images:
                    img = Image.open(io.BytesIO(img_file.data)).convert("RGB")
                    img.save(os.path.join(output_folder, f"{count:04d}.png"))
                    count += 1
                    
    elif ext == ".zip":
        temp_extract = os.path.join(os.path.dirname(output_folder), "temp_extracted")
        os.makedirs(temp_extract, exist_ok=True)
        with zipfile.ZipFile(input_path, 'r') as z:
            images = sorted([f for f in z.namelist() if f.lower().endswith(('.png','.jpg','.jpeg','.bmp'))])
            for idx, name in enumerate(images):
                z.extract(name, temp_extract)
                p_out = os.path.join(output_folder, f"{idx+1:04d}.png")
                Image.open(os.path.join(temp_extract, name)).convert("RGB").save(p_out)
                
    elif ext in (".jpg", ".jpeg", ".png"):
        Image.open(input_path).convert("RGB").save(os.path.join(output_folder, "0001.png"))

    return sorted(os.listdir(output_folder))


def get_page_paths(pages_folder):
    if not os.path.exists(pages_folder):
        return []
    files = sorted([
        f for f in os.listdir(pages_folder)
        if f.lower().endswith(('.png', '.jpg', '.jpeg'))
    ])
    return [os.path.join(pages_folder, f) for f in files]


def run_phase1(input_file, work_dir):
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
        img = Image.open(page_path).convert("RGB")
        bubbles = detect_bubbles_pil(page_path)
        
        bubble_data = []
        draw = ImageDraw.Draw(img)

        for idx, b in enumerate(bubbles):
            bbox = b['bbox']
            bid = f"{page_file.replace('.png','')}_{idx+1}"

            orig_text = "[Enter Translation]"
            bubble_data.append({'id': bid, 'bbox': bbox, 'original_text': orig_text})

            # Resolved Spelling Typo 'Dialogue='
            txt_lines.append(f"{bid}=Dialogue={orig_text}")
            txt_lines.append(f"{bid}_Colour=0,0,0")

            # Solid cleaning fill
            draw.rectangle(bbox, fill=(255, 255, 255))

        full_map[page_file] = bubble_data
        img.save(os.path.join(clean_pages, page_file))

    json_path = os.path.join(output_dir, "translation_map.json")
    txt_path = os.path.join(work_dir, "translate_me.txt")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(full_map, f, indent=2)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(txt_lines))

    return txt_path


def run_phase2(translated_txt_path, work_dir):
    clean_dir = os.path.join(work_dir, "clean_pages")
    final_dir = os.path.join(work_dir, "final_pages")
    map_json = os.path.join(work_dir, "output", "translation_map.json")
    os.makedirs(final_dir, exist_ok=True)

    if not os.path.exists(map_json):
        raise FileNotFoundError("JSON Map configuration missing.")

    translations = {}
    colors = {}
    
    # Safe parsing parameters
    with open(translated_txt_path, 'r', encoding='utf-8') as f:
        for line in f.read().splitlines():
            if '=' in line:
                parts = line.split('=', 1)
                key, val = parts[0], parts[1]
                if 'Dialogue=' in line:
                    bid, text = line.split('=Dialogue=', 1)
                    translations[bid] = text
                elif key.endswith('_Colour'):
                    bid = key.replace('_Colour', '')
                    try:
                        r, g, b = map(int, val.split(','))
                        colors[bid] = (r, g, b)
                    except ValueError:
                        colors[bid] = (0, 0, 0)

    with open(map_json, 'r', encoding='utf-8') as f:
        page_map = json.load(f)

    font = ImageFont.load_default()

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
                x1, y1, x2, y2 = b['bbox']
                color = colors.get(bid, (0, 0, 0))
                
                lines = split_text_to_lines(text, (x2 - x1), draw, font)
                y_offset = y1 + 10
                for line in lines:
                    draw.text((x1 + 10, y_offset), line, fill=color, font=font)
                    y_offset += 25

        img.save(os.path.join(final_dir, page_file))
    return True


def run_manual_compile(work_dir, config):
    pages_dir = os.path.join(work_dir, "manual_pages")
    final_dir = os.path.join(work_dir, "final_manual_pages")
    os.makedirs(final_dir, exist_ok=True)

    annotations = config.get('manual_annotations', {})
    font_path = config.get('font_path', "")
    font_size = config.get('font_size', 24)

    if font_path and os.path.exists(font_path):
        try:
            font = ImageFont.truetype(font_path, font_size)
        except Exception:
            font = ImageFont.load_default()
    else:
        font = ImageFont.load_default()

    for page_name, items in annotations.items():
        src_page = os.path.join(pages_dir, page_name)
        if not os.path.exists(src_page):
            continue

        img = Image.open(src_page).convert("RGB")
        draw = ImageDraw.Draw(img)
        w, h = img.size

        for item in items:
            norm_x, norm_y = item['pos']
            text = item.get('text', '')
            box_w = item.get('box_w', 180)
            color_str = item.get('color', '0,0,0')

            try:
                color = tuple(map(int, color_str.split(',')))
            except ValueError:
                color = (0, 0, 0)

            px = int(norm_x * w)
            py = int(norm_y * h)

            lines = split_text_to_lines(text, box_w, draw, font)
            test_bbox = draw.textbbox((0, 0), "Wg", font=font)
            line_height = (test_bbox[3] - test_bbox[1]) + 4
            box_h = (len(lines) * line_height) + 20

            bx1 = max(0, px - 10)
            by1 = max(0, py - 10)
            bx2 = min(w, px + box_w + 10)
            by2 = min(h, py + box_h)

            draw.rectangle([bx1, by1, bx2, by2], fill=(255, 255, 255), outline=(0, 0, 0), width=2)

            curr_y = by1 + 10
            for line in lines:
                draw.text((bx1 + 10, curr_y), line, fill=color, font=font)
                curr_y += line_height

        img.save(os.path.join(final_dir, page_name))

    zip_path = os.path.join(work_dir, "Manual_Manga_Export.zip")
    with zipfile.ZipFile(zip_path, 'w') as z:
        for f in os.listdir(final_dir):
            if f.lower().endswith(('.png', '.jpg', '.jpeg')):
                z.write(os.path.join(final_dir, f), f)

    return zip_path


def create_final_zip(work_dir):
    final_dir = os.path.join(work_dir, "final_pages")
    zip_path = os.path.join(work_dir, "Final_Manga_Translated.zip")

    with zipfile.ZipFile(zip_path, 'w') as z:
        for root, _, files in os.walk(final_dir):
            for file in files:
                z.write(os.path.join(root, file), file)

    return zip_path
