import jwt, time
token = jwt.encode(
    {"username": "Luna Rubinance", "role": "admin", "iat": int(time.time())},
    "trustno1", algorithm="HS256"
)
print(token)
