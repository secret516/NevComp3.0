def swap_nibble(val):
    return ((val >> 4) | (val << 4)) & 0xFF

def ror(val, r):
    return ((val >> r) | (val << (8 - r))) & 0xFF

flag = b"NevComp3.0{shuffl1ng_n1bbl3s_4nd_r0ll1ng_b1ts_l1k3_4_pr0f3ss10n4l_ch3f}"
key = b"4_l1ttl3_b1t_0f_x0r_4nd_4_wh0l3_l0t_0f_sh1ft1ng"

ct = []
for i in range(len(flag)):
    val = flag[i] ^ key[i % len(key)]
    val = (val + i) & 0xFF
    val = swap_nibble(val)
    val = ror(val, 5)
    
    ct.append(hex(val))

print(f"unsigned char ct[{len(flag)}] = {{" + ", ".join(ct) + "};")