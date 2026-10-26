FROM ubuntu:24.04

RUN apt-get update && \
    apt-get install -y socat python3 python3-pip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN pip3 install pycryptodome --break-system-packages

RUN useradd -U -m -s /bin/bash ctf

COPY chall.py /home/ctf/chall.py

WORKDIR /home/ctf

RUN chown -R root:ctf /home/ctf && \
    chmod -R 550 /home/ctf

EXPOSE 1111

CMD ["socat", "-T60", "TCP-LISTEN:1111,reuseaddr,fork", "EXEC:python3 /home/ctf/chall.py,stderr"]