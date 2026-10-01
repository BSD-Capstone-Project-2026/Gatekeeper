import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from utils.log_integrity import verify_log_chain

with create_app().app_context():
    result = verify_log_chain()
    print(f"Chain valid ({result['checked']} logs checked)" if result["valid"]
          else f"Chain broken at access log id {result['broken_at']}")
    sys.exit(0 if result["valid"] else 1)
