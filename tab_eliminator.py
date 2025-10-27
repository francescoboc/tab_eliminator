import os, sys, argparse, pdf2image, img2pdf
from utils import *

# parser degli argomenti
parser = argparse.ArgumentParser(description="Rimuove le TAB da un PDF di spartito di basso")
parser.add_argument("input_pdf", help="Percorso al PDF da elaborare")
parser.add_argument("--margin", type=int, default=20, help="Margine del rettangolo di mascheramento (default 20 px)")
parser.add_argument("--perc", type=float, default=0.7, help="Percentuale di lunghezza minima delle linee (default 0.7)")
parser.add_argument("--width", type=int, default=4, help="Spessore massimo delle linee (default 4 px)")
parser.add_argument("--blur_width", type=int, default=30, help="Larghezza del gaussian blur per chiudere i gap dei numeri sulle TAB (default 30 px)")
parser.add_argument("--gap", type=float, default=1.8, help="Parametro per decidere come raggruppare le linee (default 1.8)")
parser.add_argument("--raster", action="store_true", help="Se presente, forza l'output raster anche per un PDF vettoriale")
parser.add_argument("--crop", action="store_true", help="Se presente, taglia via le TAB invece di coprirle (solo per output raster)")
parser.add_argument("--bgr", type=int, nargs="+", default=(255, 255, 255), help="Colore in formato BGR dei rettangoli di riempimento (default 255 255 255)")

args = parser.parse_args()

INPUT_PDF = args.input_pdf
MARGIN_MASK = args.margin
LINE_LENGTH_PERC = args.perc
LINE_WIDTH_PX = args.width
BLUR_WIDTH = args.blur_width
MAX_GAP_FACTOR = args.gap
FORCE_RASTER = args.raster
CROP_TABS = args.crop

if len(args.bgr) != 3 or np.any(np.array(args.bgr)<0) or np.any(np.array(args.bgr)>255): 
    raise Exception("I parametri dell'opzione --bgr devono essere tre numeri interi tra 0 e 255")

# colore dei rettangoli
RECT_COLOR_BGR = (tuple(args.bgr))
RECT_COLOR_RGB = (RECT_COLOR_BGR[2]/255, RECT_COLOR_BGR[1]/255, RECT_COLOR_BGR[0]/255)

print(f"Margine della maschera impostato a {MARGIN_MASK} px\n")

# file e cartelle
TMP_INPUT_DIR = "tmp_input_img"
TMP_OUTPUT_DIR = "tmp_output_img"
OUTPUT_PDF = INPUT_PDF.replace(".pdf","") + " noTAB.pdf"

# crea cartelle
os.makedirs(TMP_INPUT_DIR, exist_ok=True)
os.makedirs(TMP_OUTPUT_DIR, exist_ok=True)

# controlla se il PDF di input è vettoriale
IS_VECTOR = is_pdf_vector(INPUT_PDF)

if CROP_TABS and IS_VECTOR and not FORCE_RASTER:
    raise Exception("L'opzione --crop è utilizzabile solo in modalità raster")

# converti PDF in immagini o estrai immagini se il PDF è già raster
if IS_VECTOR:
    print("Conversione pagine da PDF vettoriale")
    pages = pdf2image.convert_from_path(INPUT_PDF, dpi=300)
else:
    print("Estrazione pagine da PDF raster")
    pdf = fitz.open(INPUT_PDF)
    pages = [page.get_pixmap() for page in pdf]

# salva pagine singole in cartella temporanea
for i, page in enumerate(pages):
    img_path = os.path.join(TMP_INPUT_DIR, f"pag_{i:03d}.png")
    page.save(img_path, "PNG")
print(f"Salvate {len(pages)} pagine\n")

# elabora pagine
output_images_for_pdf = []
tab_groups_per_page = []
img_heights = []

for filename in sorted(os.listdir(TMP_INPUT_DIR)):
    print(f"Analizzo {filename}...")
    path = os.path.join(TMP_INPUT_DIR, filename)
    img = cv2.imread(path)

    # estrai altezza della pagina in pixel
    img_heights.append(img.shape[0])  

    # estrai posizioni delle linee rilevate
    line_positions = extract_lines(img, LINE_LENGTH_PERC, LINE_WIDTH_PX, BLUR_WIDTH)

    # raggruppa le linee in grouppi (pentagrammi e TABs)
    groups = group_lines(line_positions, MAX_GAP_FACTOR)

    # estrai i gruppi di 4 linee (TABs)
    tab_groups = [group for group in groups if len(group)==4]

    # appendi i gruppi a lista
    tab_groups_per_page.append(tab_groups)
    
    if not tab_groups: print(f"Warning: Nessuna TAB trovata in {filename}")

    # se l'output è raster, croppiamo o cancelliamo le TABs
    if not IS_VECTOR or FORCE_RASTER:
        if CROP_TABS:
            img = crop_tabs_pdf(tab_groups, img, MARGIN_MASK, RECT_COLOR_BGR)
        else:
            erase_tabs_pdf(tab_groups, img, MARGIN_MASK, RECT_COLOR_BGR)

        # salva immagine modificata
        out_path = os.path.join(TMP_OUTPUT_DIR, filename)
        cv2.imwrite(out_path, img)
        output_images_for_pdf.append(out_path)

# se raster, ricomponi PDF come immagini
if not IS_VECTOR or FORCE_RASTER:
    with open(OUTPUT_PDF, "wb") as f: f.write(img2pdf.convert(output_images_for_pdf))
    print(f"\nSalvato PDF raster: \n{OUTPUT_PDF}")
# se vettoriale, sovraimponi rettangoli vettoriali sul file originale
else:
    stack_tabs_rects_pdf(INPUT_PDF, OUTPUT_PDF, tab_groups_per_page, img_heights, MARGIN_MASK, RECT_COLOR_RGB)
    print(f"\nSalvato PDF vettoriale: \n{OUTPUT_PDF}")

# rimuovi file temporanei
for filename in os.listdir(TMP_INPUT_DIR): 
    os.remove(os.path.join(TMP_INPUT_DIR, filename))

for filename in os.listdir(TMP_OUTPUT_DIR): 
    os.remove(os.path.join(TMP_OUTPUT_DIR, filename))
