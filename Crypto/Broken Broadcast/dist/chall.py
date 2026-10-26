import time
from Crypto.Util.number import getPrime, bytes_to_long

FLAG = b"NevComp3.0{REDACTED}"

def generate():
    e = 11
    p = getPrime(512)
    q = getPrime(512)
    n = p * q
    return n, e

def main():
    time.sleep(0.3) 
    
    n, e = generate()
    m = bytes_to_long(FLAG)
    ct = pow(m, e, n)
    
    print(f"n = {n}")
    print(f"e = {e}")
    print(f"ct = {ct}")

if __name__ == "__main__":
    main()