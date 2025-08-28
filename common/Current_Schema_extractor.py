import mysql.connector
import json

# Step 1: Connect to your MySQL database
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="admin",
    database="tcg",
    port=3306
)
cursor = conn.cursor(dictionary=True)

# Step 2: Query all tables and columns
cursor.execute("""
SELECT 
    TABLE_NAME, 
    COLUMN_NAME, 
    COLUMN_TYPE, 
    IS_NULLABLE, 
    COLUMN_KEY, 
    COLUMN_DEFAULT, 
    EXTRA 
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_SCHEMA = %s
ORDER BY TABLE_NAME, ORDINAL_POSITION;
""", ("tcg",))

rows = cursor.fetchall()

# Step 3: Convert to nested JSON format
schema_json = {}
for row in rows:
    table = row["TABLE_NAME"]
    if table not in schema_json:
        schema_json[table] = []
    schema_json[table].append({
        "column_name": row["COLUMN_NAME"],
        "column_type": row["COLUMN_TYPE"],
        "nullable": row["IS_NULLABLE"],
        "key": row["COLUMN_KEY"],
        "default": row["COLUMN_DEFAULT"],
        "extra": row["EXTRA"]
    })

# Step 4: Print or save JSON
print(json.dumps(schema_json, indent=2))

# Optional: Save to file
with open("tcg.json", "w") as f:
    json.dump(schema_json, f, indent=2)

# Clean up
cursor.close()
conn.close()
