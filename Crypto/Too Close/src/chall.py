from Crypto.Util.number import getPrime, isPrime, bytes_to_long

flag = b"NevComp3.0{REDACTED}"

e = 65537

p = getPrime(1024)

q = p + 2
while not isPrime(q):
    q += 2

n = p * q
ct = pow(bytes_to_long(flag), e, n)

print(f"n = {n}")
print(f"e = {e}")
print(f"ct = {ct}")