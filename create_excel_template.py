"""
APEX Layer 1 — Example Excel Template Generator

Run this script to create example Excel files with the correct format.

Usage:
    python create_excel_template.py

This will generate:
    - example_monthly_data.xlsx (multi-sheet format)
    - example_monthly_data_single_sheet.xlsx (single sheet format)
"""

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
import config
from datetime import datetime

def create_multi_sheet_template():
    """Create Excel with separate CPI and PMI sheets."""
    
    # CPI Data
    cpi_data = {
        'Currency': config.CURRENCIES,
        'Target %': [config.CB_TARGETS[c] for c in config.CURRENCIES],
        'Actual CPI %': [3.2, 2.8, 3.1, 1.9, 3.5, 2.3, 1.2, 3.8]  # Example values
    }
    
    # PMI Data
    pmi_data = {
        'Currency': config.CURRENCIES,
        'Composite PMI': [52.3, 48.7, 51.2, 49.5, 50.1, 51.8, 49.2, 52.5]  # Example values
    }
    
    # Create Excel file
    with pd.ExcelWriter('example_monthly_data.xlsx', engine='openpyxl') as writer:
        pd.DataFrame(cpi_data).to_excel(writer, sheet_name='CPI', index=False)
        pd.DataFrame(pmi_data).to_excel(writer, sheet_name='PMI', index=False)
    
    print("✓ Created: example_monthly_data.xlsx")
    print("  - Sheet 1: CPI data")
    print("  - Sheet 2: PMI data")

def create_single_sheet_template():
    """Create Excel with all data in one sheet."""
    
    data = {
        'Currency': config.CURRENCIES,
        'Target_CPI': [config.CB_TARGETS[c] for c in config.CURRENCIES],
        'Actual_CPI': [3.2, 2.8, 3.1, 1.9, 3.5, 2.3, 1.2, 3.8],
        'Composite_PMI': [52.3, 48.7, 51.2, 49.5, 50.1, 51.8, 49.2, 52.5]
    }
    
    df = pd.DataFrame(data)
    df.to_excel('example_monthly_data_single_sheet.xlsx', index=False)
    
    print("✓ Created: example_monthly_data_single_sheet.xlsx")
    print("  - All data in one sheet")

def create_csv_template():
    """Create CSV example."""
    
    data = {
        'Currency': config.CURRENCIES,
        'Target_CPI': [config.CB_TARGETS[c] for c in config.CURRENCIES],
        'Actual_CPI': [3.2, 2.8, 3.1, 1.9, 3.5, 2.3, 1.2, 3.8],
        'Composite_PMI': [52.3, 48.7, 51.2, 49.5, 50.1, 51.8, 49.2, 52.5]
    }
    
    df = pd.DataFrame(data)
    df.to_csv('example_monthly_data.csv', index=False)
    
    print("✓ Created: example_monthly_data.csv")

if __name__ == "__main__":
    print(f"APEX Layer 1 - Template Generator")
    print(f"Month: {datetime.now().strftime('%Y-%m')}\n")
    
    try:
        create_multi_sheet_template()
        create_single_sheet_template()
        create_csv_template()
        
        print("\n" + "="*60)
        print("Templates created successfully!")
        print("="*60)
        print("\nUsage:")
        print("1. Open any template file")
        print("2. Replace example values with real economic data")
        print("3. In APEX app: Monthly Entry tab → Import Excel")
        print("4. Select your file and click Open")
        print("5. Click 'Save & Calculate Scores'")
        
    except Exception as e:
        print(f"\n✗ Error creating templates: {e}")
        print("\nMake sure you have openpyxl and pandas installed:")
        print("  pip install openpyxl pandas")
