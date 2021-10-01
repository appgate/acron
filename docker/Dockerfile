FROM python:3.9-buster
ARG POETRY_VERSION
ENV POETRY_VERSION=${POETRY_VERSION:-1.0.3} \
    POETRY_NO_INTERACTION=1

RUN mkdir /build
COPY pyproject.toml /build
COPY tests/ /build/tests
COPY acron/ /build/acron

WORKDIR /build

RUN pip3 install poetry
RUN poetry install

ENTRYPOINT ["poetry"]
