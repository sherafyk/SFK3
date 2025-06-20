import re
import json
from typing import Any, Dict, List, Optional

# Prompt used when sending BDR images to the LLM.  The model should return two
# markdown tables that can later be converted to JSON.
BDR_PROMPT = (
    "Please analyze the attached image and extract the transaction data as two "
    "separate tables, in markdown format:\n"
    "- The first table should show general information found at the top header "
    "table of the document.\n"
    "- The second table should show product specifications found just below the "
    "top header table of the document.\n\n"
    "The first table should use these columns (with these exact headers):\n"
    "| Vessel Name | IMO Number | Flag Country | Delivery Port |\n"
    "| ----------- | ---------- | ------------ | ------------- |\n\n"
    "The second table should use these columns (with these exact headers):\n"
    "| Product Description | Weight (MT) | Gross Barrels | Net Barrels | API | "
    "Density | Visc cSt (°C) | Flash (°C) | Sulfur % |\n"
    "| ------------------- | ----------- | ------------- | ----------- | --- | "
    "------- | ------------- | ---------- | -------- |"
)


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Return the first JSON object found in ``text`` or ``None``.

    The LLM may include explanations or wrap the object in a fenced code block.
    This helper searches for a JSON snippet that can be decoded.
    """

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        snippet = fence.group(1)
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            pass

    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        snippet = brace.group(0)
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            pass

    return None


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
    "imo_number": [r"imo number"],
    "flag_country": [r"flag", r"flag country"],
    "delivery_port": [r"delivery port", r"delivery location", r"port"],
}

_PRODUCT_HEADER_MAP = {
    "product_description": ["product description", "fuel grade", "product"],
    "weight_mt": ["weight (mt)", "metric tons"],
    "gross_barrels": ["gross bbls", "gross barrels"],
    "net_barrels": ["net bbls", "net barrels"],
    "api": ["api", "gravity api", "api @ 60f", "api @ 15c"],
    "density": ["density", "density @ 15c", "density @ 60f"],
    "viscosity": ["visc", "viscosity", "visc cst", "visc cst @ 40c", "visc cst @ 50c"],
    "flash_point": ["flash", "flash °c", "flash °f", "flash point"],
    "sulfur_percent": ["sulfur %", "sulphur %", "sulfur % wt", "sulphur % (m/m)"]
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
        if "product_description" in tmp_map and len(tmp_map) >= 3:
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
                "product_description": p.get("product_description", ""),
                "weight_mt": _to_float(p.get("weight_mt")),
                "gross_barrels": _to_float(p.get("gross_barrels")),
                "net_barrels": _to_float(p.get("net_barrels")),
                "api": _to_float(p.get("api")),
                "density": _to_float(p.get("density")),
                "viscosity": _parse_viscosity(p.get("viscosity", "")),
                "flash_point_f": _temp_to_f(p.get("flash_point", ""), header_map.get("flash_point", "")),
                "sulfur_percent": _to_float(p.get("sulfur_percent")),
            }
        )
    return result



def extract_bdr(text: str) -> Dict[str, Any]:
    """Extract structured BDR data from raw text or JSON output."""

    json_obj = _extract_json(text)
    if isinstance(json_obj, dict):
        return json_obj

    result = {
        "vessel_name": _find_value(text, _FIELD_PATTERNS["vessel_name"]),
        "imo_number": _find_value(text, _FIELD_PATTERNS["imo_number"]),
        "flag_country": _find_value(text, _FIELD_PATTERNS["flag_country"]),
        "delivery_port": _find_value(text, _FIELD_PATTERNS["delivery_port"]),
        "products": _parse_products(text),
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


# Prompt for converting the BDR markdown tables to JSON.  The schema mirrors the
# fields described in ``AGENTS.md``.  Any missing values should be set to null.
BDR_JSON_PROMPT = """
Convert the two markdown tables below into the following JSON structure. Use
null when a value is missing.

```json
{
  "vessel_name": "",
  "imo_number": "",
  "flag_country": "",
  "delivery_port": "",
  "products": [
    {
      "product_description": "",
      "weight_mt": null,
      "gross_barrels": null,
      "net_barrels": null,
      "api": null,
      "density": null,
      "viscosity": {"value": null, "unit": "", "measured_at": ""},
      "flash_point_f": null,
      "sulfur_percent": null
    }
  ]
}
```

Convert any temperatures from Celsius to Fahrenheit. Output only valid JSON.
"""


def call_openai_bdr_json(tables: str, model: str | None = None) -> str:
    """Use OpenAI to convert BDR tables to standardized JSON."""
    from .utils import MODEL, openai

    if model is None:
        model = MODEL

    message = tables + "\n\n" + BDR_JSON_PROMPT
    params = {
        "model": model,
        "messages": [{"role": "user", "content": message}],
        "response_format": {"type": "json_object"},
    }
    if model not in {"o3", "o3-mini", "o4-mini"}:
        params["temperature"] = 0.25

    try:
        response = openai.chat.completions.create(**params)
    except openai.BadRequestError as e:
        if (
            getattr(e, "body", None)
            and e.body.get("error", {}).get("code") == "unsupported_value"
            and e.body.get("error", {}).get("param") == "temperature"
        ):
            params.pop("temperature", None)
            response = openai.chat.completions.create(**params)
        else:
            raise
    return response.choices[0].message.content

