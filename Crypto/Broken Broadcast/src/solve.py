from pwn import *
from Crypto.Util.number import long_to_bytes
from sympy.ntheory.modular import crt
import gmpy2

e = 11
n_list = []
ct_list = []

for i in range(e):
    p = remote("127.0.0.1", 1111)
    
    p.recvuntil(b'n = ')
    n = int(p.recvline().strip())
    
    p.recvuntil(b'ct = ')
    ct = int(p.recvline().strip())
    
    n_list.append(n)
    ct_list.append(ct)

    p.close()

m_cubed = crt(n_list, ct_list)[0]
m = gmpy2.iroot(m_cubed, e)[0]

print(f"Flag: {long_to_bytes(m).decode()}")