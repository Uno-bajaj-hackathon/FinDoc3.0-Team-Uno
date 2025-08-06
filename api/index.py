from fastapi import FastAPI
from mangum import Mangum  # ASGI adapter for AWS Lambda/Vercel

import sys
sys.path.append("..")  # So you can import app.main

from app.main import app

handler = Mangum(app)