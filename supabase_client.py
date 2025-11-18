from dotenv import load_dotenv

load_dotenv()

import os
url=os.getenv("SUPABASE_PROJECT_URL")
key=os.getenv("SB_API_KEY")

from supabase import create_client
supabase=create_client(url,key)







