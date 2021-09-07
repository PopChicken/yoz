FROM python:3.10.0rc1-buster
COPY . /yoz/
COPY dep/websockets /yoz/dep/
WORKDIR /yoz
RUN pip install -r requirements.txt \
    && cd dep/websockets \
    && python setup.py install
FROM python:3.10.0rc1-alpine3.14
COPY --from=0 /usr/local/lib/python3.10/site-packages/ \
    /usr/local/lib/python3.10/site-packages/
COPY . /yoz/
WORKDIR /yoz
RUN rm -rf dep \
    && rm requirements.txt
CMD ["python", "run.py"]