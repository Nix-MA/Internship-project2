import sys
import logging
logging.basicConfig(level=logging.ERROR)
sys.path.append('src')
from utils.exporters import generate_pdf_report

out = generate_pdf_report({"summary": {}})
if out is None:
    print("FAILED")
else:
    print("SUCCESS")
