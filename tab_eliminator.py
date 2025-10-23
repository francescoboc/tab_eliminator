import os, cv2, img2pdf, argparse
from pdf2image import convert_from_path

# parser degli argomenti
parser = argparse.ArgumentParser(description="Rimuove le TAB da un PDF di spartito di basso")
parser.add_argument("input_pdf", help="Percorso al PDF da elaborare")
parser.add_argument("--margin", type=int, default=20, help="MARGINE del rettangolo di mascheramento (default=20)")

args = parser.parse_args()

INPUT_PDF = args.input_pdf
MARGIN_MASK = args.margin

# parametri di rilevamento linee
PEAK_PROMINENCE = 0.05
MIN_GROUP_SPACING = 20
MAX_GROUP_SPACING = 40
LINE_LENGTH_PERC = 0.7
LINE_WIDTH_PX = 4

# print(f"PDF da elaborare: {INPUT_PDF}")
# print(f"MARGIN_MASK impostato a: {MARGIN_MASK}\n")

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
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)  # linee nere su bianco
    
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

    # maschera le tablature
    if not tab_groups:
        print("Nessun gruppo da 4 linee ravvicinate trovato (nessuna TAB rilevata)")
    else:
        for g in tab_groups:
            # print(f"Gruppo TAB trovato alle y={g}")
            y_top = max(0, g[0] - MARGIN_MASK)
            y_bottom = min(img.shape[0], g[-1] + MARGIN_MASK)
            cv2.rectangle(img, (0, y_top), (img.shape[1], y_bottom), (255, 255, 255), -1)

    # salva immagine modificata
    out_path = os.path.join(TMP_OUTPUT_DIR, filename)
    cv2.imwrite(out_path, img)
    output_images_for_pdf.append(out_path)

# ricomponi pdf
with open(OUTPUT_PDF, "wb") as f:
    f.write(img2pdf.convert(output_images_for_pdf))

print(f"\nSalvato PDF senza TAB: {OUTPUT_PDF}")

# rimuovi file temporanei
for filename in os.listdir(TMP_INPUT_DIR): 
    os.remove(os.path.join(TMP_INPUT_DIR, filename))

for filename in os.listdir(TMP_OUTPUT_DIR): 
    os.remove(os.path.join(TMP_OUTPUT_DIR, filename))
