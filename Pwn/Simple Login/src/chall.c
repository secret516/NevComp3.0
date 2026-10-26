#include <stdio.h>
#include <stdlib.h>
#include <string.h>

char *gets(char *s);

static char welcome_name[32];

int main() {
    setvbuf(stdin,  NULL, _IONBF, 0);
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);

    char username[32];
    char password[64];

    puts("Username: ");
    fgets(username, sizeof(username), stdin);
    username[strcspn(username, "\n")] = 0;

    strncpy(welcome_name, username, sizeof(welcome_name) - 1);
    welcome_name[sizeof(welcome_name) - 1] = 0;

    puts("Password: ");
    gets(password);

    printf("Welcome %s", welcome_name);

    __asm__ __volatile__(
        "jmp end_gadget\n"
        "pop %rdi\n"
        "ret\n"
        "end_gadget:\n"
    );

    return 0;
}

// gcc -fno-stack-protector -no-pie -o chall chall.c