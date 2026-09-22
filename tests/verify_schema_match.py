import sys
import re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from extensions import db
import models

app = create_app('development')
with app.app_context():
    model_tables = set()
    for mapper in db.Model.registry.mappers:
        model_tables.add(mapper.class_.__tablename__)

print("Total SQLAlchemy Model Tables:", len(model_tables))
for t in sorted(model_tables):
    print("  -", t)

with open("migrations/versions/0001_baseline_all_tables.py", "r", encoding="utf-8") as f:
    migration_content = f.read()

migration_tables = set(re.findall(r"op\.create_table\(\s*'([^']+)'", migration_content))
print("\nTotal Baseline Migration Tables:", len(migration_tables))
for t in sorted(migration_tables):
    print("  -", t)

missing_in_migration = model_tables - migration_tables
missing_in_models = migration_tables - model_tables

print("\n--- AUDIT RESULT ---")
if not missing_in_migration and not missing_in_models:
    print(f"SUCCESS: 100% MATCH! All {len(model_tables)} models map directly to migration tables.")
else:
    print("ERROR: Mismatch detected!")
    if missing_in_migration:
        print("In models but missing in migration:", missing_in_migration)
    if missing_in_models:
        print("In migration but missing in models:", missing_in_models)
    sys.exit(1)
