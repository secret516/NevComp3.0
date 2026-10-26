def rol(val, r_bits, max_bits=8):
    return ((val << (r_bits % max_bits)) & (2**max_bits - 1)) | \
           ((val & (2**max_bits - 1)) >> (max_bits - (r_bits % max_bits)))

flag = b"NevComp3.0{tr4c3_m3_1f_y0u_c4n_w1th_gdb_ptr4c3}"

prng = 0x1337BEEF
cipher = []

for char in flag:
    prng = (prng * 0x5bd1e995 + 0x273cb) & 0xffffffff
    
    key1 = (prng >> 16) & 0xFF
    key2 = (prng >> 8) & 0xFF
    
    enc = char ^ key1
    enc = (enc + key2) & 0xFF
    enc = rol(enc, 3, 8)
    
    cipher.append(enc)

print("unsigned char cipher[] = {" + ", ".join(hex(x) for x in cipher) + "};")