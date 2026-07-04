<p align="center">
  <img src="images/primevideo_logo.jpg" width="400" alt="Prime Video Logo">
</p>

# Prime Video Cookie Checker

**Checks Amazon Prime Video cookies for validity.**

*<b>Education purpose only.</b>*

---

## What's New

> **Latest update** brings full proxy support with automatic validation, a native file picker UI, a `failed_cookies/` retry system, and more reliable Prime Video account data extraction.

<details open>
<summary><b>Proxy Support & Improvements - Latest</b></summary>

### New Features
- **Proxy support** - HTTP, HTTPS, SOCKS4, and SOCKS5 proxies now fully supported
- **Automatic proxy validation** - dead proxies are filtered out before checking begins
- **Native file picker** - Tkinter dialog to browse and select your proxy list
- **failed_cookies folder** - cookies that fail due to network errors are saved for later retry
- **Prime membership detection** - distinguishes Prime members from Free accounts
- **Console title bar live progress** - real-time status during proxy validation and cookie checking

### Improvements
- `validate_proxy` - uses `except Exception` to catch socket-level errors
- `load_and_validate_proxies` - shows progress and terminal title while validating
- Return values now distinguish `"expired"` vs `"network_error"`
- Exponential backoff retry - `time.sleep(RETRY_DELAY * (attempt + 1))`
- Summary includes Network failed count with retry tip
 </details>

---

## Features

- Multi-threading
- JSON + Netscape cookie support
- Prime / Free Account detection
- Extracts customerID, country, and profile name
- Optional proxy support (HTTP / HTTPS / SOCKS4 / SOCKS5)
- Automatic proxy validation before use
- **failed_cookies/** - saves network-failed cookies for retry
- Duplicate cookie detection
- No rate limiting
- Super fast

---

## Installation

```cmd
  git clone https://github.com/rxvxrsx/PrimeVideo-Cookie-Checker.git
  cd PrimeVideo-Cookie-Checker
  pip install -r requirements.txt
```

| Dependency | Version |
|-----------|---------|
| colorama  | 0.4.6   |
| requests  | 2.34.2  |

---

## Usage

1. Run [cookie_converter.py](cookie_converter.py) to convert Netscape cookies to JSON format.
2. Edit the number of threads in [main.py](main.py) (line 50: `num_threads = 5`).
3. Run [main.py](main.py).

**Make sure you have a good internet connection.**

| Network Speed | Recommended threads |
|---------------|---------------------|
| < 5 Mbps      | 1-3                 |
| 5-20 Mbps     | 3-5                 |
| 20-100 Mbps   | 5-10                |
| > 100 Mbps    | 10-20               |

---

## Proxy Support

### Proxy File Format

Your proxy file should be a plain `.txt` with one proxy per line:

```
# host:port
1.2.3.4:8080

# host:port:user:pass
1.2.3.4:8080:myuser:mypass

# user:pass@host:port
myuser:mypass@1.2.3.4:8080
```

Lines starting with `#` are ignored.

---

## Output Structure

```
PrimeVideo-Cookie-Checker/
├── main.py
├── cookie_converter.py
├── json_cookies/          ← input: JSON cookie files
├── working_cookies/       ← output: working cookies
│   └── [XX] - [customerID] - [profile] - Prime Member.txt
└── failed_cookies/        ← output: network-failed cookies (retry later)
```

### Cookie JSON Format

```json
[
    {
        "domain": ".primevideo.com",
        "flag": "TRUE",
        "path": "/",
        "secure": true,
        "expiration": "1810933581",
        "name": "at-main-av",
        "value": "Atza|..."
    }
]
```

---

## Credits

Adapted from [Netflix-cookie-checker](https://github.com/matheeshapathirana/Netflix-cookie-checker) by matheeshapathirana.

---

## License

GNU General Public License v3.0
