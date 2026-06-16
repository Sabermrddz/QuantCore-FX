# Excel Import Guide — APEX Layer 1

## **Quick Start**

1. **Ask AI for data** (use the prompt in [EXCEL_IMPORT_PROMPT.md](EXCEL_IMPORT_PROMPT.md))
2. **Download the Excel file**
3. Open APEX Layer 1 app → **Monthly Entry tab**
4. Click **"📊 Import Excel"** button
5. Select your file → Click **"Save & Calculate Scores"**

---

## **Supported File Formats**

### **Format 1: Multi-Sheet Excel** (Recommended)
**File:** `monthly_data.xlsx`

**Sheet 1: CPI**
```
Currency | Target % | Actual CPI %
---------|----------|-------------
USD      | 2.0      | 3.2
EUR      | 2.0      | 2.8
GBP      | 2.0      | 3.1
JPY      | 2.0      | 1.9
AUD      | 2.5      | 3.5
CAD      | 2.0      | 2.3
CHF      | 1.5      | 1.2
NZD      | 2.0      | 3.8
```

**Sheet 2: PMI**
```
Currency | Composite PMI
---------|---------------
USD      | 52.3
EUR      | 48.7
GBP      | 51.2
JPY      | 49.5
AUD      | 50.1
CAD      | 51.8
CHF      | 49.2
NZD      | 52.5
```

---

### **Format 2: Single-Sheet Excel**
**File:** `monthly_data.xlsx`

```
Currency | Target_CPI | Actual_CPI | Composite_PMI
---------|------------|------------|---------------
USD      | 2.0        | 3.2        | 52.3
EUR      | 2.0        | 2.8        | 48.7
GBP      | 2.0        | 3.1        | 51.2
JPY      | 2.0        | 1.9        | 49.5
AUD      | 2.5        | 3.5        | 50.1
CAD      | 2.0        | 2.3        | 51.8
CHF      | 1.5        | 1.2        | 49.2
NZD      | 2.0        | 3.8        | 52.5
```

---

### **Format 3: CSV File**
**File:** `monthly_data.csv`

```csv
Currency,Target_CPI,Actual_CPI,Composite_PMI
USD,2.0,3.2,52.3
EUR,2.0,2.8,48.7
GBP,2.0,3.1,51.2
JPY,2.0,1.9,49.5
AUD,2.5,3.5,50.1
CAD,2.0,2.3,51.8
CHF,1.5,1.2,49.2
NZD,2.0,3.8,52.5
```

---

## **Data Requirements**

### **All 8 Currencies Required (in any order):**
- USD, EUR, GBP, JPY, AUD, CAD, CHF, NZD

### **Value Ranges:**
- **CPI Actual:** Any realistic percentage (e.g., 1.0 - 5.0%)
- **PMI:** 0-100 scale (50 = neutral, >50 = expanding, <50 = contracting)
- **Use decimal format:** `3.45`, not `3.45%`

### **Important:**
- No merge cells or complex formatting
- Column headers needed (any name with "CPI", "PMI", "Currency" is recognized)
- Empty cells or 0 values = not imported

---

## **Generate Template Files**

Run this command to create example files:

```bash
python create_excel_template.py
```

This creates:
- `example_monthly_data.xlsx` (multi-sheet)
- `example_monthly_data_single_sheet.xlsx` (single sheet)
- `example_monthly_data.csv` (CSV format)

---

## **AI Prompt for Data Generation**

See [EXCEL_IMPORT_PROMPT.md](EXCEL_IMPORT_PROMPT.md) for ready-to-use prompt templates.

### **Quick Prompt:**
```
Generate realistic monthly economic data for the 8 major currencies 
for June 2026 in Excel format:

CPI: Actual inflation rates (YoY %)
PMI: Composite PMI readings (0-100 scale, 50=neutral)

Currencies: USD, EUR, GBP, JPY, AUD, CAD, CHF, NZD

Provide in two sheets:
- Sheet 1: CPI (Currency, Target %, Actual CPI %)
- Sheet 2: PMI (Currency, Composite PMI)
```

---

## **Troubleshooting**

| Problem | Solution |
|---------|----------|
| "Import Error: Sheet not found" | Use correct sheet names: "CPI" and "PMI" |
| "No data imported" | Check column names contain "Currency", "CPI", "PMI" |
| "0 values not imported" | Use non-zero values; 0 = skip |
| "File locked" | Close Excel before importing |
| "Column mismatch" | Ensure 8 currencies (USD, EUR, GBP, JPY, AUD, CAD, CHF, NZD) |

---

## **Workflow Example**

1. **Ask AI:**
   ```
   Create an Excel file with CPI and PMI data for the 8 major 
   currencies for June 2026. Make it realistic based on current 
   economic trends.
   ```

2. **Download** the Excel file from AI

3. **Open APEX Layer 1** → Monthly Entry tab

4. **Click Import Excel** → Select the file

5. **Data auto-fills** the entry form

6. **Click Save & Calculate Scores** → Done!

7. **Check Dashboard** tab for the generated signal

---

## **Notes**

- App auto-detects file format (Excel or CSV)
- If Excel has both formats, app tries multi-sheet first
- PMI default is 50 (neutral); enter actual PMI, not delta
- CPI target values are auto-looked up from config
- You can edit values after import before saving

