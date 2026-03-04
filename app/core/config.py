import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

SECRET_KEY = "c0ec674dad70354bebfe417c3b944d1c8790bc0ac67d4af76b61586fd074116314d899b08b082e7ca8b7e597e86b6e41a6641157c30bea5b2e073c0dcb8eadde"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60