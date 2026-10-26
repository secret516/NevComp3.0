#include <stdio.h>
#include <string.h>

unsigned char swap_nibble(unsigned char val) {
    return (val >> 4) | (val << 4);
}

unsigned char ror(unsigned char val, int r) {
    return (unsigned char)((val >> r) | (val << (8 - r)));
}

void check(const char *input) {
    unsigned char ct[71] = {0x3d, 0x9d, 0xe, 0xba, 0x8f, 0xf, 0x11, 0x83, 0xbc, 0xad, 0x2a, 0x9, 0xa1, 0x29, 0x7, 0x24, 0x12, 0x9, 0x17, 0xa5, 0xbf, 0x8a, 0xb5, 0x2a, 0x37, 0x26, 0x2f, 0x1b, 0xc5, 0xba, 0xbd, 0x2d, 0xa9, 0xb1, 0x33, 0x2b, 0x40, 0x3e, 0xab, 0x9d, 0xaf, 0x3e, 0xc0, 0x95, 0x37, 0x2f, 0x9c, 0x1a, 0x32, 0x48, 0x50, 0xb9, 0xaf, 0xa8, 0xbb, 0x53, 0x1e, 0x9d, 0xa0, 0xb3, 0x9e, 0xc9, 0xb7, 0xc5, 0x4e, 0x37, 0x3f, 0xcf, 0xd0, 0xa3, 0x34};
    
    unsigned char secret[] = "4_l1ttl3_b1t_0f_x0r_4nd_4_wh0l3_l0t_0f_sh1ft1ng";

    if (strlen(input) != sizeof(ct)) {
        puts("Invalid Length");
        return;
    }

    for (int i = 0; i < sizeof(ct); i++) {
        unsigned char result = input[i] ^ secret[i % (sizeof(secret) - 1)];
        result = (result + i) & 0xFF;
        result = swap_nibble(result);
        result = ror(result, 5);
        
        if (result != ct[i]) {
            puts("I think you missed a column, try again");
            return;
        }
    }
    puts("You Win! That's the correct flag.");
}

int main(void) {
    char input[256];
    printf("Enter the flag: \n");
    if (scanf("%255s", input) != 1) {
        return 1;
    }
    check(input);
    return 0;
}

// gcc chall.c -o chall -s