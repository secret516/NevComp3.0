#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ptrace.h>
#include <unistd.h>

unsigned char cipher[] = {0x81, 0xba, 0x52, 0xf8, 0x53, 0x90, 0x76, 0x2d, 0x78, 0x53, 0xd3, 0xb6, 0x19, 0xbd, 0x7c, 0xf4, 0xf, 0xda, 0x22, 0xd, 0x91, 0x51, 0x9b, 0x6d, 0x2b, 0xd4, 0x63, 0xe6, 0xab, 0xac, 0x10, 0xd9, 0xc7, 0xd0, 0x26, 0x7b, 0x84, 0x86, 0x40, 0x21, 0xd, 0x7f, 0x68, 0xa7, 0xa4, 0x20, 0x18};
unsigned int len = 47;

void __attribute__((constructor)) anti_debug() {
    if (ptrace(PTRACE_TRACEME, 0, 1, 0) < 0) {
        puts("Debugger Detected!");
        exit(1);
    }
}

int main() {
    char input[100];
    printf("Enter the flag: ");
    if (scanf("%99s", input) != 1) {
        return 1;
    }

    unsigned char expected[100] = {0};
    int i = 0;
    unsigned int prng = 0x1337BEEF;
    int state = 13;
    unsigned char key1, key2, tmp;

    while (state != 99) {
        switch(state) {
            case 13:
                if (i < len) {
                    state = 42;
                } else {
                    state = 99;
                }
                break;
            case 42:
                prng = (prng * 0x5bd1e995 + 0x273cb) & 0xffffffff;
                key1 = (prng >> 16) & 0xFF;
                key2 = (prng >> 8) & 0xFF;
                state = 7;
                break;
            case 7:
                tmp = cipher[i];
                
                tmp = (tmp >> 3) | (tmp << 5); 
                tmp = (tmp - key2) & 0xFF;
                expected[i] = tmp ^ key1;
                
                state = 88;
                break;
            case 88:
                i++;
                for (volatile int j = 0; j < 5000; j++); 
                state = 13;
                break;
            default:
                state = 99;
                break;
        }
    }
    
    if (strncmp(input, (char *)expected, len) == 0) {
        puts("Correct!");
    } else {
        puts("Wrong flag!");
    }

    return 0;
}

// gcc chall.c -o chall -s -O2