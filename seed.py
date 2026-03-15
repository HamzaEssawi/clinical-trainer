import json
from pathlib import Path
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

for case_file in Path("seed_cases").glob("*.json"):
    case = json.loads(case_file.read_text())
    supabase.table("cases").insert(case).execute()
    print(f"Seeded: {case['title']}")