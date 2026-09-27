# export_data.py
import sqlite3
import pandas as pd
import os

# Database path
db_path = 'instance/secure_access.db'

# Check if DB exists
if not os.path.exists(db_path):
    print(f"❌ Database not found at: {db_path}")
    exit()

# Connect to database
conn = sqlite3.connect(db_path)

# Tables to export
tables = ['users', 'doors', 'access_logs', 'zones', 'audit_logs']

# Output file
output_file = 'database_export.xlsx'

try:
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        for table in tables:
            try:
                df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
                
                if df.empty:
                    print(f"⚠️ Table '{table}' is empty.")
                
                df.to_excel(writer, sheet_name=table, index=False)
                print(f"✅ Exported table: {table}")
            
            except Exception as e:
                print(f"❌ Failed to export table '{table}': {e}")

    print(f"\n🎉 Export completed: {output_file}")

except Exception as e:
    print(f"❌ Failed to create Excel file: {e}")

finally:
    conn.close()