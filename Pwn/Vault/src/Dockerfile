FROM ubuntu:25.04

RUN apt-get update && \
    apt-get install -y socat openssl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN useradd -U -m -s /bin/bash ctf

COPY chall /home/ctf/chall

WORKDIR /home/ctf

RUN random=$(openssl rand -hex 32) && echo "NevComp3.0{0gw_&_0rw_sh3llc0d3_e3sy_r1ght?_099f82d7d4}" > /home/ctf/flag-${random}.txt

RUN chown -R root:ctf /home/ctf && \
    chmod -R 550 /home/ctf

EXPOSE 1338

CMD ["socat", "-T60", "TCP-LISTEN:1338,reuseaddr,fork", "EXEC:/home/ctf/chall,stderr"]  