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
    assert result["barge_name"] == "CENTERLINE LOGISTICS CORP. / SHAUNA KAY"
    assert result["vessel_flag"] == "U.S."
    assert result["port_delivery_location"] == "TACOMA, WA"
    assert result["date"] == "2025-06-18"
    assert len(result["products"]) == 1
    prod = result["products"][0]
    assert math.isclose(prod["delivery_temperature_f"], 113.0, abs_tol=0.1)
    assert math.isclose(prod["flash_point_f"], 179.6, abs_tol=0.1)
    assert math.isclose(prod["pour_point_f"], 15.8, abs_tol=0.1)
    seals = {(d["product"], d["sample_type"], d["seal_number"]) for d in result["sample_seal_numbers"]}
    assert ("IFO 380", "Marpol", "1120971") in seals
    assert ("IFO 380", "Barge", "1120974") in seals
