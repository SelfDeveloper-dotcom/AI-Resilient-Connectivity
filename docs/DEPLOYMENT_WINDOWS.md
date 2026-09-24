# Windows Deployment

## Install

1. Install Python 3.11 (64-bit), Git and VS Code.
2. Open the repository folder in VS Code.
3. Run:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

## Operational commands

```powershell
python pipeline.py sandbox-demo
python pipeline.py all
python pipeline.py train
python pipeline.py predict
python pipeline.py policy
python pipeline.py serve
```

## Continuous Collector

For continuous local-folder monitoring:

```powershell
python collector.py --config config/collector_config.json --watch --interval 60
```
