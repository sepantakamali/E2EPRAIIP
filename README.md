## Operate the API

### Local
```bash
pip install -e ".[dev]"
python -m textclf.cli --save --tag demo
uvicorn textclf.api:app --reload

![CI](https://github.com/sepantakamali/textclf/actions/workflows/ci.yml/badge.svg)
![Docker](https://github.com/sepantakamali/textclf/actions/workflows/docker.yml/badge.svg)