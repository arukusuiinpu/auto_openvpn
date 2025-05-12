#!/usr/bin/env python
import os
import time
import sys
import argparse
import requests
from bs4 import BeautifulSoup
import datetime
import subprocess
import socket
import pycountry

# Constants
CONFIG_ROOT = os.path.join(os.path.expanduser("~"), "OpenVPN", "config")
OPENVPN_EXE = r"C:\Program Files\OpenVPN\bin\openvpn.exe"
DEFAULT_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/115.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9',
    'Referer': 'https://google.com/',
}


def is_connected(host="8.8.8.8", port=53, timeout=3):
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error:
        return False


IP_SERVICES = [
    "https://ident.me", # minimal
    "https://api.ipify.org",  # IPv4 & IPv6
    "https://api4.ipify.org",  # force IPv4 :contentReference[oaicite:1]{index=1}
    "https://ifconfig.me/ip"  # popular
]


def get_public_ip():
    for url in IP_SERVICES:
        try:
            ip = requests.get(url, timeout=2, proxies={"http": None, "https": None}).text.strip()
            if ip:
                return ip
        except requests.RequestException:
            continue
    return None


WAITING_FOR_INTERNET_MODE = False
NATIVE_IP = get_public_ip()


def country_to_alpha2(name: str) -> str | None:
    """
    Convert a country name to its ISO 3166-1 alpha-2 code (e.g., 'de', 'us').
    Returns None if not found.
    """
    try:
        country = pycountry.countries.lookup(name)
        return country.alpha_2.lower()
    except LookupError:
        return None


def list_servers(args):
    """Fetch the VPN list page, filter out Russian Federation, sort by ping ascending, and print each .ovpn URL."""

    global WAITING_FOR_INTERNET_MODE
    global NATIVE_IP

    os.system(f"title NOT WORKING")

    url = args.url or "https://ipspeed.info/freevpn_openvpn.php?language=en"

    if not is_connected():
        if args.silent: print(
            "It appears either the site was terminated or you have troubles with a steady internet connection... Waiting for a fix...")
        WAITING_FOR_INTERNET_MODE = True

    n = 0
    while WAITING_FOR_INTERNET_MODE or n == 0:
        os.system(f"title NO INTERNET CONNECTION")

        n += 1
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
            resp.raise_for_status()

            WAITING_FOR_INTERNET_MODE = False
            break
        except:
            "It appears either the site was terminated or you have troubles with a steady internet connection... Waiting for a fix..."

        time.sleep(1)

    if NATIVE_IP:
        if args.silent: print(f"Baseline public IP: {NATIVE_IP}")
        os.system(f"title VPN IS DISABLED: {NATIVE_IP}")

    allowed_countries_list = [str(i).lower() for i in args.countries.split(",") if "!" not in str(i)]
    disallowed_countries_list = [str(i).lower().replace("!","") for i in args.countries.split(",") if "!" in str(i)]

    soup = BeautifulSoup(resp.text, "html.parser")
    entries = []

    # Each server entry is in a div with margin style
    for entry in soup.find_all("div", style=lambda s: s):
        # Extract country
        country_divs = entry.find_all("div", class_="list")
        if len(country_divs) < 4:
            continue
        country = country_divs[0].get_text(strip=True)
        # Skip Russian Federation

        filt = True
        if "*" not in allowed_countries_list:
            if len(allowed_countries_list) != 0:
                filt = filt and country_to_alpha2(country) in allowed_countries_list
            if len(disallowed_countries_list) != 0:
                filt = filt and country_to_alpha2(country) not in disallowed_countries_list

        if not filt:
            continue

        # Extract ping (in ms) from the 4th .list div
        ping_text = country_divs[3].get_text(strip=True)
        try:
            ping = int(ping_text.split()[0])
        except (ValueError, IndexError):
            # Skip if ping can't be parsed
            continue

        # Extract all .ovpn links
        links_div = country_divs[1]
        for a in links_div.find_all("a", href=True):
            href = a['href']
            full_url = href if href.startswith("http") else f"https://ipspeed.info{href}"
            entries.append((country, ping, full_url))

    # Sort entries by ping
    entries.sort(key=lambda x: x[1])

    if not args.silent:
        # Print sorted URLs
        for country, ping, url in entries:
            if args.showping:
                print(f"{ping} ms - {url} ({country})")
            else:
                print(url)


def list_countries(args):
    """List available countries and associated .ovpn config URLs."""
    url = args.url or "https://ipspeed.info/freevpn_openvpn.php?language=en"
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        sys.exit(f"Error fetching server list: {e}")

    soup = BeautifulSoup(resp.text, "html.parser")
    divs = soup.find_all("div", style=lambda s: s)

    if not divs:
        sys.exit("No server entries found. The structure may have changed.")

    for entry in divs:
        country_div = entry.find_all("div", class_="list")
        if len(country_div) >= 2:
            country = country_div[0].text.strip()
            link = country_div[1].find("a", href=True)
            if link and link['href'].lower().endswith(".ovpn"):
                href = link['href']
                full_url = href if href.startswith("http") else f"https://ipspeed.info{href}"
                print(f"{country}: {full_url}")


def download_config(args):
    """Download a single .ovpn file into its own folder."""
    url = args.url
    basename = os.path.splitext(os.path.basename(url))[0]
    cfgdir = os.path.join(CONFIG_ROOT, basename)
    os.makedirs(cfgdir, exist_ok=True)

    outpath = os.path.join(cfgdir, f"{basename}.ovpn")
    try:
        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
        r.raise_for_status()
    except requests.RequestException as e:
        sys.exit(f"Error downloading {url}: {e}")

    with open(outpath, "wb") as f:
        f.write(r.content)
    print(f"Downloaded: {outpath}")


def run_vpn(args):
    """Launch OpenVPN against the given basename."""
    basename = args.basename
    cfgpath = os.path.join(CONFIG_ROOT, basename, f"{basename}.ovpn")
    if not os.path.isfile(cfgpath):
        sys.exit(f"Config not found: {cfgpath}")
    try:
        subprocess.Popen([
            OPENVPN_EXE,
            "--config", cfgpath
        ], shell=False)
        print(f"Launched OpenVPN for: {basename}")
    except Exception as e:
        sys.exit(f"Error launching OpenVPN: {e}")


def kill_vpn():
    """Kill all running openvpn.exe processes (brute force)."""
    os.system('taskkill /f /im openvpn.exe >nul 2>&1')


def normalize_log_content(log_content):
    """Normalize spaces in log content."""
    return log_content.replace('\x00', '')


def check_loop(args):
    """
    Poll the OpenVPN log until we either:
     - see "Initialization Sequence Completed" → success,
     - see "All connections have been connect-retry-max" → failure,
     - otherwise wait 2s and retry.
    On failure, append the URL to blacklist.txt.
    Returns True on success, False on failure.
    """
    home = os.path.expanduser("~")
    log_dir = os.path.join(home, "OpenVPN", "log")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"openvpn_{args.basename}.log")
    blacklist_path = os.path.join(home, "OpenVPN", "blacklist.txt")

    timer = 0
    if "d" in args.timestep:
        timestep = int(args.timestep.replace("d", "")) * 24 * 60 * 60
    elif "h" in args.timestep:
        timestep = int(args.timestep.replace("h", "")) * 60 * 60
    elif "m" in args.timestep:
        timestep = int(args.timestep.replace("m", "")) * 60
    else:
        timestep = int(args.timestep.replace("s", ""))

    if "d" in args.timeout:
        timeout = int(args.timeout.replace("d", "")) * 24 * 60 * 60
        timeout_message = f"{args.timeout.replace("d", "")} days"
    elif "h" in args.timeout:
        timeout = int(args.timeout.replace("h", "")) * 60 * 60
        timeout_message = f"{args.timeout.replace("h", "")} hours"
    elif "m" in args.timeout:
        timeout = int(args.timeout.replace("m", "")) * 60
        timeout_message = f"{args.timeout.replace("m", "")} minutes"
    else:
        timeout = int(args.timeout.replace("s", ""))
        timeout_message = f"{args.timeout.replace("s", "")} seconds"

    # ensure the log file exists
    if not os.path.exists(log_path):
        # touch an empty file
        open(log_path, "a").close()

    while True:
        os.system(f"title SETTING UP THE CONNECTION TO {args.basename}")
        # read entire log (ignore any decoding errors)
        with open(log_path, "r", errors="ignore") as log_file:
            log_content = log_file.read()
            log_content = normalize_log_content(log_content)

            # check for success
            if "Initialization Sequence Completed" in log_content:
                print(
                    f"VPN connection for {args.basename} established successfully for {timeout_message} (at {datetime.datetime.now().strftime("%H:%M:%S")}).")

                new_ip = get_public_ip()
                while not new_ip:
                    new_ip = get_public_ip()
                os.system(f"title VPN IS ENABLED: {new_ip}")

                while timer < timeout:
                    time.sleep(timestep)
                    timer += timestep

                    # if not is_connected():
                    #     print("The connection was terminated. Reinitializing...")
                    #     break
                    new_ip = get_public_ip()
                    if not (new_ip and new_ip != NATIVE_IP):
                        print("The connection was terminated. Reinitializing...")
                        os.system(f"title NOT WORKING")
                        break

                kill_vpn()

                # Set condition flag to false
                flag_path = os.path.join(os.environ.get("TEMP", "/tmp"), "vpn_condition.flag")
                with open(flag_path, "w") as f:
                    f.write("false")

                sys.exit(0)

            # check for known failure
            if "fatal error" in log_content or "process exiting" in log_content:
                print(f"VPN connection for {args.basename} failed. Trying next configuration...")
                os.system(f"title FAILED")
                # append to blacklist
                with open(blacklist_path, "a+") as bf:
                    bf.write(args.url + "\n")
                break

        time.sleep(1)


def main():
    p = argparse.ArgumentParser(prog="downloader.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("list", help="List all .ovpn URLs")
    sp.add_argument("--url", help="Page URL (default freevpn list)")
    sp.add_argument("--countries", help="Choose what countries to count (ex: US,jp,!RU (USA or Japan but definetely not Russia) or !ge (any except for Germany), * for any)", required=False, default="!RU")
    sp.add_argument("--showping", help="Show the ping of the servers", required=False, default=False)
    sp.add_argument("--silent", help="Print only the user interface prints", required=False, default=False)
    sp.set_defaults(func=list_servers)

    sp = sub.add_parser("countries", help="List countries and their .ovpn config URLs")
    sp.add_argument("--url", help="Page URL (default freevpn list)")
    sp.set_defaults(func=list_countries)

    sp = sub.add_parser("download", help="Download a single .ovpn file")
    sp.add_argument("url", help="Full URL of the .ovpn file")
    sp.set_defaults(func=download_config)

    sp = sub.add_parser("run", help="Run OpenVPN on a config")
    sp.add_argument("basename", help="Base name (no .ovpn) of the config")
    sp.set_defaults(func=run_vpn)

    sp = sub.add_parser("kill", help="Kill a running OpenVPN process")
    sp.set_defaults(func=kill_vpn)

    sp = sub.add_parser("check", help="Check a config")
    sp.add_argument("basename", help="Base name (no .ovpn) of the config")
    sp.add_argument("url", help="URL")
    sp.add_argument("--timeout", help="The timeout either in days (1d), hours (8h), minutes (15m) or seconds (30s)",
                    default="2h", required=False)
    sp.add_argument("--timestep", help="The timestep either in days (1d), hours (8h), minutes (15m) or seconds (30s)",
                    default="2s", required=False)
    sp.set_defaults(func=check_loop)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
