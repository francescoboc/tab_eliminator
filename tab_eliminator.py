import os, cv2, img2pdf, argparse
from pdf2image import convert_from_path

# parser degli argomenti
parser = argparse.ArgumentParser(description="Rimuove le TAB da un PDF di spartito di basso")
parser.add_argument("input_pdf", help="Percorso al PDF da elaborare")
parser.add_argument("--margin", type=int, default=20, help="Margine del rettangolo di mascheramento (default 20 px)")
parser.add_argument("--crop", action="store_true", help="Se presente, taglia le TAB invece di coprirle")

args = parser.parse_args()

INPUT_PDF = args.input_pdf
MARGIN_MASK = args.margin
CROP_TABS = args.crop

# parametri di rilevamento linee
MIN_GROUP_SPACING = 20
MAX_GROUP_SPACING = 40
PEAK_PROMINENCE = 0.05
LINE_LENGTH_PERC = 0.7
LINE_WIDTH_PX = 4

# print(f"PDF da elaborare: {INPUT_PDF}")
print(f"Margine della maschera impostato a {MARGIN_MASK} px\n")

# file e cartelle
TMP_INPUT_DIR = "tmp_input_img"
TMP_OUTPUT_DIR = "tmp_output_img"
OUTPUT_PDF = INPUT_PDF.replace(".pdf","") + " noTAB.pdf"

# crea cartelle
os.makedirs(TMP_INPUT_DIR, exist_ok=True)
os.makedirs(TMP_OUTPUT_DIR, exist_ok=True)

# converti pdf in immagini
print(f"Converto {INPUT_PDF} in immagini...")
pages = convert_from_path(INPUT_PDF, dpi=300)
for i, page in enumerate(pages):
    img_path = os.path.join(TMP_INPUT_DIR, f"pag_{i:03d}.png")
    page.save(img_path, "PNG")
print(f"Estratte {len(pages)} pagine\n")

# elabora pagine
output_images_for_pdf = []

for filename in sorted(os.listdir(TMP_INPUT_DIR)):
    path = os.path.join(TMP_INPUT_DIR, filename)
    print(f"Analizzo {filename}...")

    # converti in grayscale e binario
    img = cv2.imread(path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    
    # estrai solo linee orizzontali lunghe
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (int(img.shape[1]*LINE_LENGTH_PERC), 1))
    horizontal_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    
    # trova contorni
    contours, _ = cv2.findContours(horizontal_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    filtered_y = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        # cerca solo linee sottili e abbastanza lunghe
        if h <= LINE_WIDTH_PX and w >= img.shape[1]*LINE_LENGTH_PERC:
            # salva centro verticale della linea
            filtered_y.append(y + h//2)
    
    filtered_y = sorted(filtered_y)
    
    # raggruppa linee in gruppi di 4 per identificare le tablature
    tab_groups = []
    current_group = [filtered_y[0]]
    for i in range(1, len(filtered_y)):
        gap = filtered_y[i] - filtered_y[i - 1]
        if MIN_GROUP_SPACING <= gap <= MAX_GROUP_SPACING:
            current_group.append(filtered_y[i])
        else:
            if len(current_group) == 4:
                tab_groups.append(current_group)
            current_group = [filtered_y[i]]
    if len(current_group) == 4:
        tab_groups.append(current_group)

    if not tab_groups:
        print("Nessun gruppo da 4 linee (TAB) trovato, prova a cambiare i parametri di rilevamento")
    else:

    # maschera le tablature
        if not CROP_TABS:
            for g in tab_groups:
                # print(f"Gruppo TAB trovato alle y={g}")
                y_top = max(0, g[0] - MARGIN_MASK)
                y_bottom = min(img.shape[0], g[-1] + MARGIN_MASK)
                cv2.rectangle(img, (0, y_top), (img.shape[1], y_bottom), (255, 255, 255), -1)

    # rimuove le tablature "tirando su" il contenuto sottostante
        else:
            import numpy as np
            height, width = img.shape[:2]
        
            # calcola intervalli da mantenere (non TAB)
            keep_intervals = []
            last_y = 0
            for g in tab_groups:
                y_top = max(0, g[0] - MARGIN_MASK)
                y_bottom = min(height, g[-1] + MARGIN_MASK)
                if y_top > last_y:
                    keep_intervals.append((last_y, y_top))
                last_y = y_bottom
            if last_y < height:
                keep_intervals.append((last_y, height))
        
            # nuova altezza
            new_height = sum([b - t for t, b in keep_intervals])
            new_img = np.zeros((new_height, width, 3), dtype=img.dtype)
        
            # copia porzioni non TAB
            current_y = 0
            for t, b in keep_intervals:
                h = b - t
                new_img[current_y:current_y+h, :, :] = img[t:b, :, :]
                current_y += h
        
            # aggiorna immagine da salvare
            img = new_img

    # salva immagine modificata
    out_path = os.path.join(TMP_OUTPUT_DIR, filename)
    cv2.imwrite(out_path, img)
    output_images_for_pdf.append(out_path)

# ricomponi pdf
with open(OUTPUT_PDF, "wb") as f:
    f.write(img2pdf.convert(output_images_for_pdf))

print(f"\nSalvato {OUTPUT_PDF}")

# rimuovi file temporanei
for filename in os.listdir(TMP_INPUT_DIR): 
    os.remove(os.path.join(TMP_INPUT_DIR, filename))

for filename in os.listdir(TMP_OUTPUT_DIR): 
    os.remove(os.path.join(TMP_OUTPUT_DIR, filename))
