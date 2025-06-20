import sys, pathlib, math
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from backend.bdr_extractor import extract_bdr


def test_extract_bdr_sample():
    text = (
        "Vessel Name: MATSON ANCHORAGE\n"
        "Barge: CENTERLINE LOGISTICS CORP. / SHAUNA KAY\n"
        "Flag: U.S.\n"
        "Port: TACOMA, WA\n"
        "Date: 2025-06-18\n\n"
        "Product Description | Weight (MT) | Gross Bbls | Net Bbls | API @ 60F | Density @ 15C | Visc CST @ 50C | Temp °C | Flash °C | Pour °C | Sulfur % Wt\n"
        "IFO 380 | 903.81 | 5888.17 | 5781.07 | 12.1 | 984.5 | 250 cSt @ 50C | 45 | 82 | -9 | 1.37\n\n"
        "Product | Marpol | Supplier | Ship | Barge\n"
        "IFO 380 | 1120971 | 1120973 | 1120972 | 1120974\n"
    )
    result = extract_bdr(text)
    assert result["vessel_name"] == "MATSON ANCHORAGE"
    assert result["delivery_port"] == "TACOMA, WA"
    assert len(result["products"]) == 1
    prod = result["products"][0]
    assert math.isclose(prod["flash_point_f"], 179.6, abs_tol=0.1)


def test_extract_bdr_variant_headers():
    text = (
        "Vessel Name: TEST SHIP\n"
        "Barge Name: TEST BARGE\n"
        "Flag: US\n"
        "Port Delivery Location: MOBILE\n"
        "Date: 2025-07-01\n\n"
        "Fuel Grade | Metric Tons | Gross Barrels | Net Barrels | API | Density | Viscosity | Temp F | Flash F | Pour F | Sulphur % (M/M)\n"
        "MGO | 100 | 630 | 620 | 45 | 820 | 10 cSt @ 40C | 100 | 150 | 30 | 0.10\n\n"
        "Product | Marpol Sample | Supplier | Ship Sample | Barge\n"
        "MGO | A1 | B2 | C3 | D4\n"
    )
    result = extract_bdr(text)
    prod = result["products"][0]
    assert prod["product_description"] == "MGO"
    assert prod["weight_mt"] == 100


