"""Create the demo invoice: a fictional invoice that looks scanned.

The page is an image only (no text layer), so ATLAS must read it with OCR,
which is what demo scenario 3 shows. The invoice matches the demo contract
(service_agreement.pdf, Agreement No. HDS-2026-014): same parties, the Monthly
Fee and rates of Article 3.1, payment within 30 days (Article 3.3).

Usage, from the backend folder:
    python -m scripts.make_demo_invoice

The PDF is written to demo_documents/ at the root of the repository, then read
back with Tesseract to check that the key values are recognised.
"""

import random
from pathlib import Path

import pytesseract
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUTPUT = Path(__file__).resolve().parents[2] / "demo_documents" / "invoice_HDS-INV-2026-0042.pdf"

DPI = 200
WIDTH, HEIGHT = 1654, 2339  # A4 at 200 dpi
MARGIN = 130
SEED = 42  # fixed, so the grain of the "scan" is the same at every run

# The values that demo scenario 3 extracts, checked again after OCR.
EXPECTED_AFTER_OCR = ["HDS-INV-2026-0042", "1 April 2026", "1 May 2026", "15,950.00"]

# (description, quantity, unit price, amount)
LINES = [
    ("Monthly Fee - April 2026 (in advance)", "1", "12,500.00", "12,500.00"),
    ("Additional user licences - March 2026", "15", "40.00", "600.00"),
    ("Extra consulting work - March 2026 (days)", "3", "950.00", "2,850.00"),
]


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Pillow's built-in font, so the script works on any machine."""
    return ImageFont.load_default(size=size)


def draw_invoice() -> Image.Image:
    """Draw the invoice on a clean white page."""
    page = Image.new("L", (WIDTH, HEIGHT), 255)
    draw = ImageDraw.Draw(page)
    x, right = MARGIN, WIDTH - MARGIN
    y = MARGIN

    draw.text((x, y), "Helix Data Services Ltd.", font=font(52), fill=20)
    draw.text((right, y + 6), "INVOICE", font=font(64), fill=20, anchor="ra")
    y += 80
    for line in [
        "14 Harbour Street, Bristol BS1 4QA, United Kingdom",
        "Company No. 09876543 - accounts@helixdata.example",
    ]:
        draw.text((x, y), line, font=font(30), fill=60)
        y += 42

    y += 50
    details = [
        ("Invoice No.", "HDS-INV-2026-0042"),
        ("Invoice date", "1 April 2026"),
        ("Due date", "1 May 2026"),
        ("Agreement No.", "HDS-2026-014"),
    ]
    for label, value in details:
        draw.text((x, y), f"{label}:", font=font(34), fill=40)
        draw.text((x + 330, y), value, font=font(34), fill=20)
        y += 52

    y += 40
    draw.text((x, y), "Bill to:", font=font(34), fill=40)
    y += 52
    for line in [
        "Orion Freight Co. - Accounts Payable",
        "220 Lakeview Avenue, Chicago, IL 60601, United States",
    ]:
        draw.text((x, y), line, font=font(32), fill=20)
        y += 46

    # Table of services.
    y += 60
    columns = [x, x + 780, x + 900, right]  # description, quantity, unit price, amount
    draw.line((x, y, right, y), fill=80, width=3)
    y += 18
    headers = ["Description", "Qty", "Unit price", "Amount (USD)"]
    draw.text((columns[0], y), headers[0], font=font(30), fill=40)
    draw.text((columns[1], y), headers[1], font=font(30), fill=40)
    draw.text((columns[2], y), headers[2], font=font(30), fill=40)
    draw.text((columns[3], y), headers[3], font=font(30), fill=40, anchor="ra")
    y += 52
    draw.line((x, y, right, y), fill=80, width=2)
    y += 24
    for description, quantity, unit_price, amount in LINES:
        draw.text((columns[0], y), description, font=font(30), fill=20)
        draw.text((columns[1], y), quantity, font=font(30), fill=20)
        draw.text((columns[2], y), unit_price, font=font(30), fill=20)
        draw.text((columns[3], y), amount, font=font(30), fill=20, anchor="ra")
        y += 56
    draw.line((x, y, right, y), fill=80, width=2)

    y += 34
    totals = [
        ("Subtotal", "USD 15,950.00"),
        ("Tax (0%)", "USD 0.00"),
        ("Total due", "USD 15,950.00"),
    ]
    for label, value in totals:
        size = 38 if label == "Total due" else 32
        draw.text((columns[1] - 300, y), label, font=font(size), fill=20)
        draw.text((right, y), value, font=font(size), fill=20, anchor="ra")
        y += 56

    y += 70
    for line in [
        "Payment terms: within 30 days of the invoice date, by bank transfer, in US dollars.",
        "Tax: services supplied outside the scope of UK VAT.",
        "Late payment: interest of 1.5% per month on overdue amounts (Article 3.4).",
        "Please quote the invoice number HDS-INV-2026-0042 with your payment.",
    ]:
        draw.text((x, y), line, font=font(28), fill=50)
        y += 44

    note = "Fictional document created for demonstration purposes only."
    draw.text((WIDTH // 2, HEIGHT - MARGIN), note, font=font(26), fill=90, anchor="ms")
    return page


def scan(page: Image.Image) -> Image.Image:
    """Make the clean page look scanned: grey paper, slight tilt, blur and noise."""
    tilted = page.rotate(0.6, resample=Image.Resampling.BICUBIC, fillcolor=255)
    blurred = tilted.filter(ImageFilter.GaussianBlur(radius=0.7))
    # Paper is never pure white: darken a little, then add grain.
    paper = blurred.point(lambda value: int(value * 0.93))
    # Grain from a fixed seed: running the script again gives the same image.
    noise = random.Random(SEED).randbytes(WIDTH * HEIGHT)
    grain = Image.frombytes("L", (WIDTH, HEIGHT), noise)
    return Image.blend(paper, grain, 0.06)


def main() -> None:
    image = scan(draw_invoice())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    # An image-only PDF: no text layer, exactly like a scanner produces.
    image.save(OUTPUT, "PDF", resolution=DPI)
    print(f"Created {OUTPUT}")

    text = pytesseract.image_to_string(image, lang="eng")
    missing = [value for value in EXPECTED_AFTER_OCR if value not in text]
    if missing:
        raise SystemExit(f"OCR check failed, not recognised: {missing}\n\n{text}")
    print(f"OCR check passed: {', '.join(EXPECTED_AFTER_OCR)}")


if __name__ == "__main__":
    main()