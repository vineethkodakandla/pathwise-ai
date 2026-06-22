FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    mininet \
    openvswitch-switch \
    openvswitch-testcontroller \
    python3 \
    python3-pip \
    iproute2 \
    iputils-ping \
    net-tools \
    iperf3 \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install mininet

COPY topologies/ /topologies/
COPY scripts/ /scripts/

CMD ["service", "openvswitch-switch", "start"]
