"""
Rebuilds the two small PDFs the end-to-end tests upload (KV-32).

    pip install reportlab
    python make_fixtures.py

The PDFs are committed, so you only need this if you want to change them.
  - tide-pools.pdf  has a text layer, so it uploads and can be searched.
  - blank-scan.pdf  draws a shape and no text, like a scanned page, so the
    backend refuses it with "No text could be found in this PDF".
"""

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent

TIDE_POOLS = [
    "Tide pools of the Pacific coast",
    "",
    "A tide pool is a shallow basin of seawater left among the rocks when the",
    "ocean pulls back at low tide. Sea stars, anemones and hermit crabs live",
    "there, and each one has to survive hours of sun, wind and changing salt.",
    "Barnacles seal their shells shut to keep from drying out, while anemones",
    "tuck in their tentacles and wait for the water to return.",
    "",
    "Visitors should step on bare rock, never on living creatures, and put",
    "every animal back exactly where it was found.",
]


def make_tide_pools() -> None:
    pdf = canvas.Canvas(str(HERE / "tide-pools.pdf"), pagesize=letter)
    pdf.setTitle("Tide pools of the Pacific coast")
    y = 740
    for line in TIDE_POOLS:
        pdf.setFont("Helvetica-Bold" if y == 740 else "Helvetica", 14 if y == 740 else 11)
        pdf.drawString(72, y, line)
        y -= 18
    pdf.save()


def make_blank_scan() -> None:
    pdf = canvas.Canvas(str(HERE / "blank-scan.pdf"), pagesize=letter)
    pdf.setTitle("Scanned page")
    pdf.rect(72, 400, 300, 200, fill=1)  # a shape, but no text anywhere
    pdf.save()


if __name__ == "__main__":
    make_tide_pools()
    make_blank_scan()
    print("Wrote tide-pools.pdf and blank-scan.pdf")
