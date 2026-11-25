"""Writes data/demo_batch_c/: a rehearsal batch for the live demo ("ingest a small batch
of documents you have not seen"). Plain PDFs and an HTML page with NO sidecar metadata,
the way an examiner's files would arrive. Synthetic documents written by the group.

    python scripts/make_demo_batch.py

The PDFs are written by hand (no PDF library needed): one page, Helvetica, a document
info dictionary with dates but no Title, so the ingestion Job has to derive doc_version
from the PDF date and the title from the first line.
"""

from __future__ import annotations

import shutil
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "demo_batch_c"


def pdf(path: Path, lines: list[str], date: str) -> None:
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    stream = "BT /F1 11 Tf 14 TL 56 780 Td " + " ".join(f"({esc(ln)}) '" for ln in lines) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        f"<< /Producer (RAHBAR demo batch) /CreationDate (D:{date}) /ModDate (D:{date}) >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info 6 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode()
    path.write_bytes(out)


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    pdf(OUT / "c01-convocation-notice.pdf", [
        "Convocation Notice 2026",
        "",
        "1. The annual convocation for the class of 2026 is held on Saturday 12 December 2026",
        "in the main auditorium. Graduates report at 9:00 for gowns and seating.",
        "2. Each graduate may bring two guests. Guest passes are collected from the Student",
        "Affairs office with the graduate's ID card until 5 December 2026.",
        "3. A graduate with outstanding dues, including library fines, is not allowed to",
        "receive the degree at the ceremony; the degree is posted after the dues are cleared.",
    ], "20261110093000+05'00'")
    pdf(OUT / "c02-laptop-loan-scheme.pdf", [
        "Laptop Loan Scheme",
        "",
        "1. Students on need-based financial aid may borrow a laptop for one semester.",
        "Applications are made through the Financial Aid office in the first two weeks.",
        "2. A borrowed laptop is returned in working condition within three days after the",
        "last final examination. A late return is charged 200 rupees per day.",
        "3. Loss or damage is charged at the repair cost or the replacement price.",
    ], "20261118140000+05'00'")
    (OUT / "c03-cafeteria-timings.html").write_text(
        "<html><head><title>Cafeteria Timings</title></head><body><h1>Cafeteria Timings</h1>"
        "<p>The main cafeteria is open from 8:00 to 18:00 on working days and from 9:00 to "
        "14:00 on Saturdays. During the examination weeks it stays open until 20:00.</p>"
        "<p>Students may not take crockery out of the cafeteria. Food is not allowed in the "
        "library or the computing labs.</p></body></html>", encoding="utf-8")
    print(f"wrote {len(list(OUT.iterdir()))} files to {OUT}")


if __name__ == "__main__":
    main()
