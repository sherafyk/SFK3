# AGENTS.md

## Bunker Delivery Receipt (BDR) Extraction Agent

### Overview

This model extracts standardized, structured data from Bunker Delivery Receipts (BDRs), which can vary significantly in format, layout, and header naming. The agent must **robustly parse all required information**, regardless of terminology or column order, and output a consistent JSON schema.

This guide details the expected extraction logic, required fields, header mappings, normalization requirements (e.g., temperature conversions), and sample outputs for downstream processing.

---

## Core Extraction Goals

* **Extract and normalize essential BDR information**, even if header names and table layouts vary.
* **Convert all temperatures to Fahrenheit.**
* **Output data in a clean, standardized JSON structure.**
* **Identify and table all fuel sample seal numbers by product and sample type.**

---

## 1. **Standardized Output Fields**

| Field Name               | Header Variations (Examples)                    | Notes             |
| ------------------------ | ----------------------------------------------- | ----------------- |
| vessel\_name             | Vessel Name, Bunkers Delivered to (Vessel Name) | String            |
| barge\_name              | Barge Name, Delivery Company, Barge             | String            |
| vessel\_flag             | Flag, Vessel Flag                               | String            |
| port\_delivery\_location | Delivery Location, Port, Terminal Location      | String            |
| date                     | Date, Date of Commencement of Delivery          | Date (YYYY-MM-DD) |

### Per-Product Information

| Field                    | Header Variations                     | Notes                             |
| ------------------------ | ------------------------------------- | --------------------------------- |
| product\_name            | Product Description, Fuel Grade       | String                            |
| weight\_mt               | Weight (MT), Metric Tons              | Number (MT)                       |
| gross\_barrels           | Gross Bbls, Gross Barrels             | Number                            |
| net\_barrels             | Net Bbls, Net Barrels                 | Number                            |
| api\_gravity             | Gravity API, API @ 60F, API @ 15C     | Number                            |
| density\_kgm3            | Density, Density @ 15C, Density @ 60F | Number (kg/m³)                    |
| viscosity                | Visc CST @ 50C, Visc cSt @ 40C/50C    | Object: value, unit, measured\_at |
| delivery\_temperature\_f | Temp °C, Temp °F, Temp @ Delivery     | Number (always output in °F)      |
| flash\_point\_f          | Flash °C, Flash °F                    | Number (always output in °F)      |
| pour\_point\_f           | Pour °C, Pour °F                      | Number (always output in °F)      |
| sulfur\_content\_percent | Sulfur % Wt, Sulphur % (M/M)          | Number (%)                        |

### Fuel Sample Seal Numbers Table

| Field        | Header Variations                      | Notes         |
| ------------ | -------------------------------------- | ------------- |
| product      | Product                                | String        |
| sample\_type | Marpol, Vessel Sample, Supplier, Barge | String        |
| seal\_number | Sample #, Marpol #, Seal Number        | String/Number |

---

## 2. **Field Normalization and Conversions**

* **Temperature:**

  * If °C, convert to °F using: `°F = (°C × 9/5) + 32`.
  * Always output temperature fields (delivery, pour, flash point) in °F.

* **Density:**

  * Output in kg/m³ if possible; if other units found, indicate original unit in a note.

* **Sample Seal Numbers:**

  * List every product/sample\_type/seal\_number combination as a row in a table.

---

## 3. **Expected JSON Output Schema**

```json
{
  "vessel_name": "",
  "barge_name": "",
  "vessel_flag": "",
  "port_delivery_location": "",
  "date": "",
  "products": [
    {
      "product_name": "",
      "weight_mt": null,
      "gross_barrels": null,
      "net_barrels": null,
      "api_gravity": null,
      "density_kgm3": null,
      "viscosity": {
        "value": null,
        "unit": "",
        "measured_at": ""
      },
      "delivery_temperature_f": null,
      "flash_point_f": null,
      "pour_point_f": null,
      "sulfur_content_percent": null
    }
  ],
  "sample_seal_numbers": [
    {
      "product": "",
      "sample_type": "",
      "seal_number": ""
    }
  ]
}
```

* Set missing values to `null`.
* Always include all above fields for each product, even if some are missing.

---

## 4. **Agent Extraction Workflow**

1. **Parse document layout** (table or freeform).
2. **Identify key fields** by searching for **header synonyms** (see table above).
3. **Extract values** for each field, handling multiple products per BDR.
4. **Normalize values** (convert temperatures, standardize units).
5. **Extract sample seal numbers:**

   * For each product, parse all available sample seal types (e.g., Marpol, Vessel, Supplier, Barge) and associated numbers.
6. **Return JSON output** per the above schema.

---

## 5. **Sample Output (Populated)**

```json
{
  "vessel_name": "MATSON ANCHORAGE",
  "barge_name": "CENTERLINE LOGISTICS CORP. / SHAUNA KAY",
  "vessel_flag": "U.S.",
  "port_delivery_location": "TACOMA, WA",
  "date": "2025-06-18",
  "products": [
    {
      "product_name": "IFO 380",
      "weight_mt": 903.81,
      "gross_barrels": 5888.17,
      "net_barrels": 5781.07,
      "api_gravity": 12.1,
      "density_kgm3": 984.5,
      "viscosity": {
        "value": 250.00,
        "unit": "cSt",
        "measured_at": "50°C"
      },
      "delivery_temperature_f": 113.3,
      "flash_point_f": 179.6,
      "pour_point_f": 15.8,
      "sulfur_content_percent": 1.37
    }
  ],
  "sample_seal_numbers": [
    {"product": "IFO 380", "sample_type": "Marpol", "seal_number": "1120971"},
    {"product": "IFO 380", "sample_type": "Supplier", "seal_number": "1120973"},
    {"product": "IFO 380", "sample_type": "Ship", "seal_number": "1120972"},
    {"product": "IFO 380", "sample_type": "Barge", "seal_number": "1120974"}
  ]
}
```

---

## 6. **Implementation Notes**

* Support **multi-page** or **multi-product** BDRs.
* Extraction should be **header-agnostic**: search for synonyms, not exact header matches.
* Handle **unit conversions** and note ambiguous cases for manual QA if needed.
* Extraction logic should be implemented as a reusable function/class for easy integration.

---

## 7. **Prompt Template for LLM or OCR Extraction**

```
Extract the following standardized fields from this Bunker Delivery Receipt (BDR), regardless of exact header wording or layout. If a value is missing, return null.

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
```
