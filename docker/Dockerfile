FROM python:3.12-slim

RUN mkdir /build
COPY pyproject.toml /build
COPY src/ /build/src

WORKDIR /build

RUN pip install uv
RUN uv install

ENTRYPOINT ["bash"]
