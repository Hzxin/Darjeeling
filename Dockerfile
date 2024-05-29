FROM ubuntu:18.04
MAINTAINER Ridwan Shariffdeen <rshariffdeen@gmail.com>
RUN apt-get update && apt-get install -y apt-transport-https ca-certificates software-properties-common

RUN DEBIAN_FRONTEND=noninteractive apt-get -y install \
    software-properties-common \
    && apt-get update

# Install libraries pyenv will need for Python 3.9.
RUN DEBIAN_FRONTEND=noninteractive apt-get -y install \
    python3 python3-pip \
    git nano \
    libssl-dev libffi-dev libncurses-dev \
    libbz2-dev liblzma-dev \
    libreadline-dev libsqlite3-dev \
    ca-certificates curl \
    make build-essential autoconf libtool

RUN DEBIAN_FRONTEND=noninteractive apt-get -y install \
    libssl-dev zlib1g-dev wget llvm libncurses5-dev xz-utils tk-dev


WORKDIR /opt
RUN git clone https://github.com/pyenv/pyenv.git /opt/pyenv
ENV PYENV_ROOT=/opt/pyenv
RUN git clone https://github.com/pyenv/pyenv-virtualenv.git "$PYENV_ROOT/plugins/pyenv-virtualenv"
ENV PATH="$PYENV_ROOT/shims:$PYENV_ROOT/bin:$PATH"
RUN pyenv install 3.9.14 && pyenv global 3.9.14 && python3 --version
RUN python3 -m pip install pip setuptools
RUN python3 -m pip install pipenv

RUN git clone https://github.com/hzxin/Darjeeling.git /opt/darjeeling
WORKDIR /opt/darjeeling
RUN git submodule update --init --recursive
RUN env PIPENV_VENV_IN_PROJECT=1 python3 -m pipenv install --deploy
ENV PATH="/opt/darjeeling/.venv/bin:$PATH"


# install dependencies
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      docker.io \
      gcc \
      gcovr \
      libc6-dev \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ENV LC_ALL C.UTF-8
ENV LANG C.UTF-8

# create darjeeling user
RUN apt-get update \
 && apt-get install --no-install-recommends -y sudo patch cmake make libtool \
 && useradd -ms /bin/bash darjeeling \
 && echo "Defaults secure_path=\"$PATH\"" >> /etc/sudoers \
 && echo 'darjeeling ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers \
 && adduser darjeeling sudo \
 && apt-get clean \
 && mkdir -p /home/darjeeling \
 && sudo chown -R darjeeling /home/darjeeling \
 && sudo chown -R darjeeling /usr/local/bin \
 && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
USER darjeeling
