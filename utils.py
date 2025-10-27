import cv2, fitz
import numpy as np

# estrai pagine direttamente da PDF raster
def extract_pages_from_raster_pdf(INPUT_PDF, DPI_RENDER=150):
    from PIL import Image
    import io

    pdf = fitz.open(INPUT_PDF)

    pages = []
    for i, page in enumerate(pdf):
        img_list = page.get_images(full=True)

        # se c'è esattamente 1 immagine nella pagina, estraila
        if len(img_list) == 1:
            xref = img_list[0][0]
            base_image = pdf.extract_image(xref)
            image_bytes = base_image["image"]
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # altrimenti, renderizza la pagina a DPI_RENDER
        else:
            zoom = DPI_RENDER / 72
            mat = fitz.Matrix(zoom, zoom)
            img = page.get_pixmap(matrix=mat)

        # appendi l'immagine alla lista di pagine da salvare
        pages.append(img)

    return pages

# controlla se il pdf è raster o vettoriale
def is_pdf_vector(pdf_path):
    pdf = fitz.open(pdf_path)
    for page in pdf:
        # se trovimo testo o disegni vettoriali, è vettoriale
        if page.get_text() or page.get_drawings():
            pdf.close()
            return True
    pdf.close()
    return False

# estrai linee orizzontali con opencv
def extract_lines(img, LINE_LENGTH_PERC, LINE_WIDTH_PX, BLUR_WIDTH):
    # converti in grayscale e binario
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    # pre-blur orizzontale per chiudere gap causati dai numeri
    kernel_blur = np.ones((1, BLUR_WIDTH), np.uint8)
    binary_blurred = cv2.dilate(binary, kernel_blur, iterations=1)

    # cv2.imwrite("debug_binary_blurred.png", binary_blurred)
        
    # estrai solo linee orizzontali lunghe almeno LINE_LENGTH_PERC della pagina
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (int(img.shape[1]*LINE_LENGTH_PERC), 1))

    horizontal_lines = cv2.morphologyEx(binary_blurred, cv2.MORPH_OPEN, kernel)

    # trova contorni
    contours, _ = cv2.findContours(horizontal_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # filtra solo linee con spessore <= LINE_WIDTH_PX
    filtered_y = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if h <= LINE_WIDTH_PX:
            # salva centro verticale della linea
            filtered_y.append(y + h//2)
    
    return sorted(filtered_y)

# raggruppa automaticamente le linee orizzontali in gruppi in base alla distanza verticale media tra linee vicine
def group_lines(line_positions, MAX_GAP_FACTOR):
    line_positions = np.array(line_positions)
    diffs = np.diff(line_positions)

    # stima della distanza media tra linee dello stesso gruppo
    median_gap = np.median(diffs)

    # identifica dove ci sono grossi salti tra le linee
    group_breaks = np.where(diffs > median_gap * MAX_GAP_FACTOR)[0]

    # salva le linee in lista di gruppi
    groups = []
    start = 0
    for b in group_breaks:
        groups.append(line_positions[start:b+1].tolist())
        start = b + 1
    groups.append(line_positions[start:].tolist())

    return groups

# nasconde le TABs coprendole con rettangoli vettoriali
def stack_tabs_rects_pdf(INPUT_PDF, OUTPUT_PDF, tab_groups_per_page, img_heights, MARGIN_MASK, RECT_COLOR_RGB):
    pdf = fitz.open(INPUT_PDF)
    
    for i, page in enumerate(pdf):
        page_height_pts = page.rect.height
        page_width_pts = page.rect.width
        img_h = img_heights[i]
        groups = tab_groups_per_page[i] if i < len(tab_groups_per_page) else []
        if not groups:
            continue
        
        for g in groups:
            y_top = max(0, g[0] - MARGIN_MASK)
            y_bottom = min(img_h, g[-1] + MARGIN_MASK)
            
            # converti pixel in punti PDF (origine in alto a sinistra)
            pdf_y_top = y_top / img_h * page_height_pts
            pdf_y_bottom = y_bottom / img_h * page_height_pts
            
            rect = fitz.Rect(0, pdf_y_top, page_width_pts, pdf_y_bottom)
            page.draw_rect(rect, fill=RECT_COLOR_RGB, color=None)
    
    pdf.save(OUTPUT_PDF)
    pdf.close()

# rimuove le TABs coprendole con dei rettangoli raster
def erase_tabs_pdf(tab_groups, img, MARGIN_MASK, RECT_COLOR_BGR):
    for g in tab_groups:
        y_top = max(0, g[0] - MARGIN_MASK)
        y_bottom = min(img.shape[0], g[-1] + MARGIN_MASK)
        cv2.rectangle(img, (0, y_top), (img.shape[1], y_bottom), RECT_COLOR_BGR, -1)

# rimuove le TABs "tirando su" il contenuto sottostante
def crop_tabs_pdf(tab_groups, img, MARGIN_MASK, RECT_COLOR_BGR):
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
    
        return new_img
