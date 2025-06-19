import re
from typing import Any, Dict, List


def _find_value(text: str, patterns: List[str]) -> str:
    """Return the value after the first matching pattern."""
    for pattern in patterns:
        regex = rf"{pattern}\s*[:\-]?\s*(.+)"
        m = re.search(regex, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def _to_float(value: str) -> float | None:
    if not value:
        return None
    value = value.replace(",", "").strip()
    try:
        return float(value)
    except ValueError:
        return None


def _temp_to_f(value: str, header: str = "") -> float | None:
    if not value:
        return None
    value = value.strip()
    m = re.match(r"(-?\d+(?:\.\d+)?)\s*°?\s*([CF])?", value, re.IGNORECASE)
    if m:
        num = float(m.group(1))
        unit = m.group(2)
    else:
        num = _to_float(value)
        unit = None
    if unit:
        if unit.upper() == "C":
            num = num * 9 / 5 + 32
    else:
        if "c" in header.lower():
            num = num * 9 / 5 + 32
    return num


def _parse_viscosity(value: str) -> Dict[str, Any]:
    if not value:
        return {"value": None, "unit": "", "measured_at": ""}
    m = re.match(r"(-?\d+(?:\.\d+)?)\s*([a-zA-Z]+)?\s*@?\s*(\d+\s*°?[CF])?", value)
    if not m:
        return {"value": _to_float(value), "unit": "", "measured_at": ""}
    val = _to_float(m.group(1))
    unit = m.group(2) or ""
    measured_at = m.group(3) or ""
    return {"value": val, "unit": unit, "measured_at": measured_at}


_FIELD_PATTERNS = {
    "vessel_name": [r"vessel name", r"bunkers delivered to \(vessel name\)"],
    "barge_name": [r"barge name", r"delivery company", r"barge"],
    "vessel_flag": [r"vessel flag", r"flag"],
    "port_delivery_location": [r"delivery location", r"port", r"terminal location"],
    "date": [r"date", r"date of commencement of delivery"],
}

_PRODUCT_HEADER_MAP = {
    "product_name": ["product description", "fuel grade", "product"],
    "weight_mt": ["weight (mt)", "metric tons"],
    "gross_barrels": ["gross bbls", "gross barrels"],
    "net_barrels": ["net bbls", "net barrels"],
    "api_gravity": ["gravity api", "api @ 60f", "api @ 15c", "api"],
    "density_kgm3": ["density", "density @ 15c", "density @ 60f"],
    "viscosity": ["visc", "viscosity", "visc cst @ 40c", "visc cst @ 50c"],
    "delivery_temperature": ["temp °c", "temp °f", "temp @ delivery", "temp"],
    "flash_point": ["flash °c", "flash °f", "flash point"],
    "pour_point": ["pour °c", "pour °f", "pour point"],
    "sulfur_content_percent": ["sulfur % wt", "sulphur % (m/m)", "sulfur"],
}


def _match_header_index(headers: List[str], target: str) -> int | None:
    for i, h in enumerate(headers):
        if re.search(target, h, re.IGNORECASE):
            return i
    return None


def _parse_products(text: str) -> List[Dict[str, Any]]:
    lines = [ln.strip() for ln in text.splitlines()]
    start = None
    for i, line in enumerate(lines):
        if re.search(r"product", line, re.IGNORECASE) and re.search(r"weight", line, re.IGNORECASE):
            start = i
            break
    if start is None:
        return []
    header_line = lines[start]
    delim = "|" if "|" in header_line else None
    if delim:
        header_parts = [p.strip().lower() for p in header_line.strip("|").split("|")]
    else:
        header_parts = re.split(r"\s{2,}", header_line.lower())
    # Map columns
    col_map = {}
    header_map = {}
    for canon, syns in _PRODUCT_HEADER_MAP.items():
        for syn in syns:
            idx = _match_header_index(header_parts, syn)
            if idx is not None:
                col_map[canon] = idx
                header_map[canon] = header_parts[idx]
                break
    products = []
    for j in range(start + 1, len(lines)):
        row = lines[j]
        if not row:
            break
        if delim:
            parts = [p.strip() for p in row.strip("|").split("|")]
        else:
            parts = re.split(r"\s{2,}", row)
        if len(parts) < len(col_map):
            continue
        prod = {}
        for key, idx in col_map.items():
            prod[key] = parts[idx] if idx < len(parts) else ""
    products.append(prod)
    result = []
    for p in products:
        result.append(
            {
                "product_name": p.get("product_name", ""),
                "weight_mt": _to_float(p.get("weight_mt")),
                "gross_barrels": _to_float(p.get("gross_barrels")),
                "net_barrels": _to_float(p.get("net_barrels")),
                "api_gravity": _to_float(p.get("api_gravity")),
                "density_kgm3": _to_float(p.get("density_kgm3")),
                "viscosity": _parse_viscosity(p.get("viscosity", "")),
                "delivery_temperature_f": _temp_to_f(p.get("delivery_temperature", ""), header_map.get("delivery_temperature", "")),
                "flash_point_f": _temp_to_f(p.get("flash_point", ""), header_map.get("flash_point", "")),
                "pour_point_f": _temp_to_f(p.get("pour_point", ""), header_map.get("pour_point", "")),
                "sulfur_content_percent": _to_float(p.get("sulfur_content_percent")),
            }
        )
    return result


def _parse_seal_numbers(text: str) -> List[Dict[str, str]]:
    lines = [ln.strip() for ln in text.splitlines()]
    start = None
    for i, line in enumerate(lines):
        if re.search(r"product", line, re.IGNORECASE) and re.search(r"marpol", line, re.IGNORECASE):
            start = i
            break
    if start is None:
        return []
    header_line = lines[start]
    delim = "|" if "|" in header_line else None
    if delim:
        headers = [h.strip().lower() for h in header_line.strip("|").split("|")]
    else:
        headers = re.split(r"\s{2,}", header_line.lower())
    sample_types = [h for h in headers[1:] if h]
    results = []
    for j in range(start + 1, len(lines)):
        row = lines[j]
        if not row:
            break
        if delim:
            parts = [p.strip() for p in row.strip("|").split("|")]
        else:
            parts = re.split(r"\s{2,}", row)
        if not parts:
            continue
        product = parts[0]
        for idx, stype in enumerate(sample_types, start=1):
            if idx < len(parts):
                seal = parts[idx]
                if seal:
                    results.append({"product": product, "sample_type": stype.title(), "seal_number": seal})
    return results


def extract_bdr(text: str) -> Dict[str, Any]:
    """Extract structured BDR data from raw text."""
    result = {
        "vessel_name": _find_value(text, _FIELD_PATTERNS["vessel_name"]),
        "barge_name": _find_value(text, _FIELD_PATTERNS["barge_name"]),
        "vessel_flag": _find_value(text, _FIELD_PATTERNS["vessel_flag"]),
        "port_delivery_location": _find_value(text, _FIELD_PATTERNS["port_delivery_location"]),
        "date": _find_value(text, _FIELD_PATTERNS["date"]),
        "products": _parse_products(text),
        "sample_seal_numbers": _parse_seal_numbers(text),
    }
    return result

