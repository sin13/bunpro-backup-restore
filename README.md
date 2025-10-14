# Bunpro Backup/Restore

A lightweight Python tool to **backup** and **restore** your Bunpro grammar deck progress.

This script logs into [bunpro.jp](https://bunpro.jp), extracts deck and SRS information, saves it as JSON, and can later restore it through Bunpro’s API — useful for migrations or account resets.

---

## Features
- Login automation using your Bunpro credentials (adapted from [bunpro-llm](https://github.com/enjuichang/bunpro-llm). Since that project’s grammar-fetching functionality is currently deprecated, this client includes a custom implementation for those parts.)
- Backup deck SRS data to a local JSON file 
- Restore saved progress through Bunpro’s frontend API 
- Simple, dependency-light, and easy to extend

---

## Installation
1. Clone the repository:
```sh
git clone https://github.com/sin13/bunpro-backup-restore.git
cd bunpro-backup-restore
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```



## Usage
Create a .env file:
```env
BUNPRO_EMAIL=your@email.com
BUNPRO_PASSWORD=your_password
```

Run the script:
```bash
python runner.py --help
```


## Disclaimer

This tool uses Bunpro’s frontend endpoints for personal backup/restore purposes.
Use responsibly and at your own risk — it’s not affiliated with Bunpro.
