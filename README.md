# Password Manager
A command‑line password manager with Caesar cipher encryption and MySQL storage.

## Requirements
- [Python 3.8+](https://www.python.org/downloads/)
- [MySQL 8.0+](https://dev.mysql.com/downloads/installer/)

## Quick Start
1. Double‑click `setup.bat`.
   - It will ask for your MySQL username and password.
   - It creates a virtual environment, installs dependencies, and sets up the database.
2. Double‑click `run.bat` to launch the app.
   - On first launch, create a vault with a master password.

## Features
- Add, edit, delete, and view passwords
- Search by service or username
- Favourites
- Password generator with strength score
- CSV export/import
- Undo last action
- Pagination for large vaults
- PIN‑protected viewing

## Files
- `setup.bat` – one‑time setup
- `run.bat` – launch the app
- `config.json` – created by setup.bat

## License
GPL-3.0 license
