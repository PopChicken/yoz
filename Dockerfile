FROM python:3.10.4-bullseye
COPY . /yoz/
WORKDIR /yoz
RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple some-package
FROM python:3.10.4-alpine3.14
COPY --from=0 /usr/local/lib/python3.10/site-packages/ \
    /usr/local/lib/python3.10/site-packages/
COPY . /yoz/
WORKDIR /yoz
RUN rm requirements.txt
CMD ["python", "run.py"]