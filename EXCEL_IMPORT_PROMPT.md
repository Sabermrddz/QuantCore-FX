# APEX Layer 1 — Excel Data Import Prompt

Use this prompt template to ask AI (ChatGPT, Claude, etc.) to generate monthly economic data in the required Excel format.

---

## **Example Prompt for AI:**

```
I need you to create an Excel file with monthly economic data for the 8 major currencies.

The file should have two sheets:

**Sheet 1: CPI**
- Column A: Currency (USD, EUR, GBP, JPY, AUD, CAD, CHF, NZD)
- Column B: Target % (2.0, 2.0, 2.0, 2.0, 2.5, 2.0, 1.5, 2.0)
- Column C: Actual CPI % (provide realistic values for June 2026)

**Sheet 2: PMI**
- Column A: Currency (USD, EUR, GBP, JPY, AUD, CAD, CHF, NZD)
- Column B: Composite PMI (provide realistic values between 40-60, where 50=neutral)

Format:
- Use decimal values (e.g., 3.45, not "3.45%")
- Include header row
- One row per currency
- No merge cells or formulas

Provide realistic economic data for June 2026 based on:
- Recent inflation trends
- Manufacturing activity
- Monetary policy directions

Please generate this as a downloadable Excel file or CSV format.
```

---

## **Required Data Format:**

### **CPI Sheet:**
| Currency | Target % | Actual CPI % |
|----------|----------|-------------|
| USD      | 2.0      | 3.2         |
| EUR      | 2.0      | 2.8         |
| GBP      | 2.0      | 3.1         |
| JPY      | 2.0      | 1.9         |
| AUD      | 2.5      | 3.5         |
| CAD      | 2.0      | 2.3         |
| CHF      | 1.5      | 1.2         |
| NZD      | 2.0      | 3.8         |

### **PMI Sheet:**
| Currency | Composite PMI |
|----------|---------------|
| USD      | 52.3          |
| EUR      | 48.7          |
| GBP      | 51.2          |
| JPY      | 49.5          |
| AUD      | 50.1          |
| CAD      | 51.8          |
| CHF      | 49.2          |
| NZD      | 52.5          |

---

## **How to Use:**

1. Copy the prompt above and send to ChatGPT/Claude
2. Ask for Excel file download
3. Save the Excel file
4. In APEX Layer 1 app → Monthly Entry tab → Click "Import Excel"
5. Select your Excel file
6. Data auto-fills the entry form
7. Click "Save & Calculate Scores"

---

## **Example AI Responses to Accept:**

- **ChatGPT**: Says "I can't create actual files, but here's the data:" → Copy to Excel manually
- **Claude**: May provide CSV format → Import that
- **Perplexity/Other**: Often provides downloadable formats directly

---

## **Alternative: Generate Test Data**

Ask AI:
```
Create realistic monthly CPI and PMI data for the 8 major currencies (USD, EUR, GBP, JPY, AUD, CAD, CHF, NZD) 
for June 2026 in this format:

Currency,Target_CPI,Actual_CPI,Composite_PMI
...

Make it realistic based on economic forecasts and recent trends.
```

Then paste the CSV into your Excel file.
