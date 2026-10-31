FROM graphrag-numeric-build-candidate:20261029 AS installed
USER 0:0
COPY app /app
RUN /opt/python/bin/python3.12 /app/native/vector_numeric/build.py install 20d2166cd218fdd0dff2914939c07e400fa38231f06139b91689ee45279418d0
RUN chmod 0444 /app/native/vector_numeric/Cargo.toml /app/native/vector_numeric/Cargo.lock /app/native/vector_numeric/rust-toolchain.toml /app/native/vector_numeric/src/main.rs /app/vector_numeric.py && chmod 0555 /app /app/native /app/native/vector_numeric /app/native/vector_numeric/src /app/native/vector_numeric/bin
FROM graphrag-linux-mvp-numpy:20261028 AS good
COPY --from=installed /app /app
USER 65534:65534
FROM good AS noexec
USER 0:0
RUN chmod 0444 /app/native/vector_numeric/bin/x86_64-unknown-linux-gnu/vector-numeric-bridge
USER 65534:65534
FROM good AS missing
USER 0:0
RUN rm /app/native/vector_numeric/bin/x86_64-unknown-linux-gnu/vector-numeric-bridge
USER 65534:65534
