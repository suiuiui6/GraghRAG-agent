FROM graphrag-linux-mvp-numpy:20261028 AS python
FROM rust@sha256:a86cada82e36ebd7a9bffed7548792c55a952fdb20718eea9278a936bcb76e62
COPY --from=python /usr/local/ /opt/python/
ENV PYTHONHOME=/opt/python LD_LIBRARY_PATH=/opt/python/lib
USER 1000:1000
ENTRYPOINT ["/opt/python/bin/python3.12"]
