from pathlib import Path
from urllib.request import urlretrieve
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
URL = "https://archive.ics.uci.edu/static/public/601/ai4i+2020+predictive+maintenance+dataset.zip"
if __name__ == "__main__":
    raw = ROOT / "data/raw"
    raw.mkdir(parents=True, exist_ok=True)
    archive = raw / "ai4i.zip"
    urlretrieve(URL, archive)
    with ZipFile(archive) as package:
        package.extractall(raw)
    print(f"Downloaded official UCI dataset to {raw / 'ai4i2020.csv'}")
