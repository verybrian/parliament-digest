import io
import logging
import requests
from pdf2image import convert_from_bytes
import pytesseract

log = logging.getLogger(__name__)

SKIP_PAGES = 2
MAX_CONTENT_PAGES = 8
TAIL_PAGES = 4
TESSERACT_CONFIG = "--psm 1 -l eng"
RASTERIZE_DPI = 300
DOWNLOAD_TIMEOUT = 60

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/pdf,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://parliament.go.ke/",
}


def download_pdf(url: str) -> bytes:
    log.info("Downloading: %s", url)
    resp = requests.get(url, headers=HEADERS, timeout=DOWNLOAD_TIMEOUT, verify=False)
    resp.raise_for_status()
    size_kb = len(resp.content) / 1024
    if size_kb < 10:
        raise ValueError(f"Downloaded file is only {size_kb:.1f} KB.")
    log.info("Downloaded %.1f KB", size_kb)
    return resp.content


def ocr_page(image, page_num: int) -> str:
    log.info("OCR page %d...", page_num)
    text = pytesseract.image_to_string(image, config=TESSERACT_CONFIG).strip()
    return f"[Page {page_num}]\n{text}" if text else ""


def ocr_pdf(pdf_bytes: bytes, skip: int = SKIP_PAGES, max_pages: int = MAX_CONTENT_PAGES) -> dict:
    log.info("Rasterizing PDF at %d DPI...", RASTERIZE_DPI)
    images = convert_from_bytes(pdf_bytes, dpi=RASTERIZE_DPI)
    total_pages = len(images)
    log.info("PDF has %d page(s)", total_pages)

    content_images = images[skip: skip + max_pages]
    if not content_images:
        raise ValueError(f"PDF only has {total_pages} page(s); nothing left after skipping {skip}.")

    pages_text = []
    for i, img in enumerate(content_images, start=skip + 1):
        ocrd = ocr_page(img, i)
        if ocrd:
            pages_text.append(ocrd)
        else:
            log.warning("Page %d returned empty OCR output — may be blank or unreadable", i)

    if not pages_text:
        raise ValueError("OCR returned no text. The PDF may be too low quality or Tesseract is not installed.")

    # Scan the last pages for endorser/date and skip any that were already OCR'd in the content window to avoid duplicate submission.
    content_window_indices = set(range(skip, skip + max_pages))
    tail_start = max(skip + max_pages, total_pages - TAIL_PAGES)
    tail_indices = [i for i in range(tail_start, total_pages) if i not in content_window_indices]

    tail_texts = []
    for i in tail_indices:
        ocrd = ocr_page(images[i], i + 1)
        if ocrd:
            tail_texts.append(ocrd)
        else:
            log.warning("Tail page %d returned empty OCR output — skipping", i + 1)

    if tail_texts:
        pages_text.append(f"[Tail pages — endorser/date]\n" + "\n\n".join(tail_texts))
        log.info("Tail scan: %d page(s) OCR'd outside content window", len(tail_indices))
    else:
        log.info("Tail pages either already in content window or returned no text")

    pages_read = len(content_images) + len(tail_indices)
    log.info("OCR complete: %d page(s) read, ~%d characters extracted", pages_read, sum(len(t) for t in pages_text))

    return {
        "text": "\n\n".join(pages_text),
        "page_count": total_pages,
        "pages_read": pages_read,
        "skipped": skip,
        "tail_text": "\n\n".join(tail_texts) if tail_texts else "",
    }


def extract(url: str) -> dict:
    pdf_bytes = download_pdf(url)
    result = ocr_pdf(pdf_bytes)
    result["url"] = url
    return result