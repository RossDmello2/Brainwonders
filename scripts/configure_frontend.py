"""Set the reviewed production API origin in public config and CSP."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).parents[1]
parser=argparse.ArgumentParser()
parser.add_argument("api_origin",help="Exact deployed HTTPS API origin, without a path")
args=parser.parse_args()
parsed=urlsplit(args.api_origin)
if parsed.scheme!="https" or not parsed.netloc or parsed.path not in ("", "/") or parsed.query or parsed.fragment or parsed.username:
    parser.error("api_origin must be one exact HTTPS origin")
origin=f"https://{parsed.netloc}"
(ROOT/"frontend/config.json").write_text(json.dumps({"api_base":origin},indent=2)+"\n",encoding="utf-8",newline="\n")
headers=(ROOT/"frontend/_headers").read_text("utf-8")
headers=headers.replace("http://127.0.0.1:8000",origin)
(ROOT/"frontend/_headers").write_text(headers,encoding="utf-8",newline="\n")
print(f"Configured frontend for {origin}")
