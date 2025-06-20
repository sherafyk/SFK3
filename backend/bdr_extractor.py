import re
from typing import Any, Dict, List

# Prompt used when sending BDR images to the LLM.  It mirrors the template
# defined in AGENTS.md and instructs the model to return key fields in a
# structured format.
BDR_PROMPT = """Extract the following standardized fields from this Bunker Delivery Receipt (BDR), regardless of exact header wording or layout. If a value is missing, return null.

Return your answer in the specified JSON format.

Required fields:
- Vessel Name
- Barge Name
- Vessel Flag
- Port Delivery Location
- Date

For each product delivered:
- Product Name
- Weight (metric tons)
- Gross Barrels
- Net Barrels
- API Gravity
- Density (kg/m³ or specify original units)
- Viscosity (value, unit, temperature measured at)
- Delivery Temperature (convert to °F if needed)
- Flash Point (convert to °F if needed)
- Pour Point (convert to °F if needed)
- Sulfur Content (% by weight or m/m)

List all fuel sample seal numbers in a table with: Product, Sample Type (e.g., Marpol, Supplier, Barge), and Seal Number.

Convert all temperatures to °F. Split any combined cells into multiple entries. Omit unstructured or irrelevant data.
"""


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
    def _split(line: str):
        d = "|" if "|" in line else None
        if d:
            return [p.strip() for p in line.strip("|").split("|")], d
        return re.split(r"\s{2,}", line.strip()), d

    lines = [ln.strip() for ln in text.splitlines()]
    start = None
    header_parts: List[str] = []
    delim = None
    col_map: Dict[str, int] = {}
    header_map: Dict[str, str] = {}

    for i, line in enumerate(lines):
        if not line:
            continue
        parts, d = _split(line)
        tmp_map: Dict[str, int] = {}
        tmp_header: Dict[str, str] = {}
        for canon, syns in _PRODUCT_HEADER_MAP.items():
            for syn in syns:
                idx = _match_header_index(parts, syn)
                if idx is not None:
                    tmp_map[canon] = idx
                    tmp_header[canon] = parts[idx].lower()
                    break
        if "product_name" in tmp_map and len(tmp_map) >= 3:
            start = i
            header_parts = parts
            delim = d
            col_map = tmp_map
            header_map = tmp_header
            break

    if start is None:
        return []

    products = []
    for j in range(start + 1, len(lines)):
        row = lines[j]
        if not row:
            break
        parts, _ = _split(row)
        if len(parts) < len(col_map):
            continue
        prod = {key: parts[idx] if idx < len(parts) else "" for key, idx in col_map.items()}
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
    SAMPLE_HEADERS = ["marpol", "sample", "supplier", "ship", "vessel", "barge"]

    def _split(line: str):
        d = "|" if "|" in line else None
        if d:
            return [p.strip() for p in line.strip("|").split("|")], d
        return re.split(r"\s{2,}", line.strip()), d

    lines = [ln.strip() for ln in text.splitlines()]
    start = None
    headers: List[str] = []
    delim = None
    for i, line in enumerate(lines):
        if not line:
            continue
        if not re.search(r"product", line, re.IGNORECASE):
            continue
        parts, d = _split(line)
        if any(re.search(h, line, re.IGNORECASE) for h in SAMPLE_HEADERS):
            start = i
            headers = [p.lower() for p in parts]
            delim = d
            break
    if start is None:
        return []

    sample_types = [h for h in headers[1:] if h]
    results = []
    for j in range(start + 1, len(lines)):
        row = lines[j]
        if not row:
            break
        parts, _ = _split(row)
        if not parts:
            continue
        product = parts[0]
        for idx, stype in enumerate(sample_types, start=1):
            if idx < len(parts):
                seal = parts[idx].strip()
                if seal:
                    results.append({
                        "product": product,
                        "sample_type": stype.title(),
                        "seal_number": seal,
                    })
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


def merge_bdr_json(existing: Dict[str, Any] | None, new: Dict[str, Any]) -> Dict[str, Any]:
    """Merge ``new`` BDR data into ``existing`` without overwriting values.

    Fields already populated in ``existing`` are preserved.  Lists are extended
    with any new items not already present.  ``existing`` may be ``None`` or an
    invalid structure, in which case ``new`` is returned.
    """

    if not isinstance(existing, dict):
        existing = {}

    for key, val in new.items():
        if isinstance(val, dict):
            existing[key] = merge_bdr_json(existing.get(key), val)
        elif isinstance(val, list):
            cur = existing.get(key)
            if not isinstance(cur, list):
                existing[key] = val
            else:
                for item in val:
                    if item not in cur:
                        cur.append(item)
        else:
            if key not in existing or existing[key] in (None, "", []):
                existing[key] = val
    return existing

