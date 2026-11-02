import pytest

from app.engine.merchant import extract_merchant


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Spec table
        ("UPI/DR/402918374651/SWIGGY/YESB/swiggy@ybl/Payment", "Swiggy"),
        ("UPI-ZOMATO LTD-zomato@hdfcbank-HDFC0000001-4029...", "Zomato"),
        ("POS 4591XXXXXXXX1234 AMAZON PAY IN", "Amazon"),
        ("NEFT-HDFCN52026110112-ACME TECH PVT LTD-SALARY", "Acme Tech (Salary)"),
        ("ACH D- BAJAJ FINANCE LTD-P400XXXX", "Bajaj Finance"),
        # More real-world shapes
        ("UPI/DR/402918370101/RAMESH KUMAR/SBIN/rameshk@oksbi/Rent for Aug", "Ramesh Kumar"),
        (
            "UPI-RAJU STORES-q12345678@ybl-YESB0YBLUPI-412345678901-PAYMENT FROM PHONE",
            "Raju Stores",
        ),
        ("UPI/DR/402918370707/SWIGGY INSTAMART/YESB/instamart@ybl/Payment", "Swiggy Instamart"),
        ("NETFLIX.COM SI 4591XXXXXXXX1234", "Netflix"),
        ("UPI/DR/402918370808/UBER INDIA/YESB/uber@axisbank/Trip", "Uber"),
        ("NEFT-UNIV00012345-STATE UNIVERSITY-STIPEND OCT", "State University (Stipend)"),
        ("UPI/DR/1234567890/9876543210@ybl/YESB/Payment", "9876543210"),
        # A person paying through a Jio VPA must not become "Jio"
        ("UPI/DR/402918379999/MEERA NAIR/JIOP/meera@jio/Dinner", "Meera Nair"),
        ("", ""),
    ],
)
def test_extract_merchant(raw: str, expected: str) -> None:
    assert extract_merchant(raw) == expected


def test_vpa_fallback_when_no_payee_segment() -> None:
    assert extract_merchant("UPI/DR/402918374651/swiggy@ybl") == "Swiggy"
