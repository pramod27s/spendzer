"""Regenerate the synthetic PDF / XLSX statement fixtures (no real names, accounts or VPAs).

    uv run --with reportlab python tests/fixtures/make_pdf_fixtures.py

reportlab is only needed to *write* these files, so it is not a project dependency.
The November 2026 rows deliberately overlap across sources (same UPI references) so the
cross-source dedup tests have something to find.
"""

from pathlib import Path

import pikepdf
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.platypus.para import Paragraph  # noqa: F401  (keeps reportlab's font setup warm)

HERE = Path(__file__).parent
LOCKED_PASSWORD = "ASHA1234"


def table_pdf(path: Path, title: str, rows: list[list[str]]) -> None:
    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4), leftMargin=24, rightMargin=24)
    table = Table(rows, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    from reportlab.lib.styles import getSampleStyleSheet

    styles = getSampleStyleSheet()
    doc.build([Paragraph(title, styles["Title"]), Spacer(1, 12), table])


def _unicode_font() -> str:
    """A TrueType font with the ₹ glyph (Helvetica has none, so ₹ would extract as junk)."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    for candidate in (
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ):
        if Path(candidate).exists():
            pdfmetrics.registerFont(TTFont("StatementSans", candidate))
            return "StatementSans"
    raise SystemExit("Need a TrueType font with ₹ (Arial or DejaVu Sans) to write UPI fixtures")


def text_pdf(path: Path, lines: list[str]) -> None:
    font = _unicode_font()
    c = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for line in lines:
        c.setFont(font, 9)
        c.drawString(36, y, line)
        y -= 16
        if y < 40:
            c.showPage()
            y = 800
    c.save()


HDFC_ROWS = [
    [
        "Date",
        "Narration",
        "Chq./Ref.No.",
        "Value Dt",
        "Withdrawal Amt.",
        "Deposit Amt.",
        "Closing Balance",
    ],
    [
        "01/11/26",
        "NEFT-ACMEN52026110112-ACME TECH PVT LTD-SALARY",
        "ACMEN52026110112",
        "01/11/26",
        "",
        "30,000.00",
        "40,000.00",
    ],
    [
        "02/11/26",
        "UPI/DR/402918380001/SWIGGY/YESB/swiggy@ybl/Payment",
        "402918380001",
        "02/11/26",
        "450.00",
        "",
        "39,550.00",
    ],
    [
        "04/11/26",
        "UPI/DR/402918380002/RAMESH KUMAR/SBIN/rameshk@oksbi/Rent for Nov",
        "402918380002",
        "04/11/26",
        "9,000.00",
        "",
        "30,550.00",
    ],
    [
        "06/11/26",
        "UPI/DR/402918380003/BLINKIT/YESB/blinkit@ybl/Payment",
        "402918380003",
        "06/11/26",
        "640.00",
        "",
        "29,910.00",
    ],
    [
        "08/11/26",
        "UPI/CR/402918380004/KIRAN RAO/ICIC/kiranrao@okicici/Splitwise",
        "402918380004",
        "08/11/26",
        "",
        "500.00",
        "30,410.00",
    ],
    ["10/11/26", "POS 4591XXXXXXXX1234 AMAZON PAY IN", "", "10/11/26", "1,299.00", "", "29,111.00"],
]

ICICI_ROWS = [
    [
        "S No.",
        "Value Date",
        "Transaction Date",
        "Cheque Number",
        "Transaction Remarks",
        "Withdrawal Amount (INR)",
        "Deposit Amount (INR)",
        "Balance (INR)",
    ],
    [
        "1",
        "03/11/2026",
        "03/11/2026",
        "",
        "UPI/402918382001/Uber India/uber@axisbank",
        "230.00",
        "0.00",
        "14,770.00",
    ],
    [
        "2",
        "07/11/2026",
        "07/11/2026",
        "",
        "NEFT-FREELANCE CLIENT-INV 104",
        "0.00",
        "8,000.00",
        "22,770.00",
    ],
]

CARD_ROWS = [
    ["Date", "Transaction Description", "Amount (in Rs.)"],
    ["05/11/2026", "AMAZON PAY INDIA PVT LTD BANGALORE", "1,299.00"],
    ["09/11/2026", "NETFLIX.COM", "649.00"],
    ["15/11/2026", "PAYMENT RECEIVED - THANK YOU", "5,000.00 Cr"],
]

SBI_LINES = [
    "State Bank of India - Account Statement (anonymized test fixture)",
    "Txn Date Value Date Description Ref No./Cheque No. Debit Credit Balance",
    "Opening Balance 20,000.00",
    "03/11/2026 03/11/2026 UPI/DR/402918381111/ZEPTO/YESB/zepto@ybl 402918381111 350.00 19,650.00",
    "05/11/2026 05/11/2026 NEFT-SBIN0001234-STATE UNIVERSITY-STIPEND 12,000.00 31,650.00",
    "07/11/2026 07/11/2026 ATM WDL SBI ATM 2,000.00 29,650.00",
    "CASH WITHDRAWAL KORAMANGALA",
    "Closing Balance 29,650.00",
]

GPAY_LINES = [
    "Google Pay - Transaction statement (anonymized test fixture)",
    "02 Nov, 2026 Paid to Swiggy ₹450",
    "10:42 AM UPI Transaction ID: 402918380001",
    "Paid by Sample Bank 4321",
    "04 Nov, 2026 Paid to RAMESH KUMAR ₹9,000",
    "09:15 AM UPI Transaction ID: 402918380002",
    "08 Nov, 2026 Received from Kiran Rao ₹500",
    "06:01 PM UPI Transaction ID: 402918380004",
    "09 Nov, 2026 Paid to Chai Point ₹60",
    "08:30 AM UPI Transaction ID: 402918380009",
]

PHONEPE_LINES = [
    "PhonePe - Transaction Statement (anonymized test fixture)",
    "Nov 06, 2026 Paid to BLINKIT DEBIT ₹640",
    "07:12 pm Transaction ID T2611061912000001",
    "Nov 11, 2026 Received from Meera Nair CREDIT ₹1,200",
    "UTR No. 402918380011",
]


def main() -> None:
    table_pdf(
        HERE / "hdfc_statement.pdf",
        "HDFC BANK - Statement of account (anonymized test fixture)",
        HDFC_ROWS,
    )
    with pikepdf.open(HERE / "hdfc_statement.pdf") as pdf:
        pdf.save(
            HERE / "hdfc_statement_locked.pdf",
            encryption=pikepdf.Encryption(user=LOCKED_PASSWORD, owner="fixture-owner"),
        )
    table_pdf(
        HERE / "icici_statement.pdf",
        "ICICI Bank - Detailed Statement (anonymized test fixture)",
        ICICI_ROWS,
    )
    table_pdf(
        HERE / "hdfc_card.pdf",
        "HDFC Bank Credit Card Statement (anonymized test fixture)",
        CARD_ROWS,
    )
    text_pdf(HERE / "sbi_statement.pdf", SBI_LINES)
    text_pdf(HERE / "gpay_statement.pdf", GPAY_LINES)
    text_pdf(HERE / "phonepe_statement.pdf", PHONEPE_LINES)

    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(["Paytm UPI Statement (anonymized test fixture)"])
    ws.append([])
    ws.append(
        [
            "Date",
            "Time",
            "Transaction Details",
            "Other Transaction Details (UPI ID or A/c No)",
            "Your Account",
            "Amount",
            "UPI Ref No.",
            "Order ID",
            "Remarks",
            "Tags",
            "Comment",
        ]
    )
    ws.append(
        [
            "12/11/2026",
            "20:14",
            "Paid to Zomato Ltd",
            "zomato@paytm",
            "Sample Bank - 21",
            "-620.00",
            "402918380012",
            "",
            "",
            "#Food",
            "",
        ]
    )
    ws.append(
        [
            "13/11/2026",
            "11:02",
            "Received from Kiran Rao",
            "kiranrao@okicici",
            "Sample Bank - 21",
            "+250.00",
            "402918380013",
            "",
            "Movie split",
            "",
            "",
        ]
    )
    wb.save(HERE / "paytm_statement.xlsx")
    print("fixtures written to", HERE)


if __name__ == "__main__":
    main()
