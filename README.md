
<p align="center">
  <img src="images/primevideo_logo.jpg" width="400" alt="Prime Video Logo">
</p>

# Prime Video Cookie Checker

**ตรวจสอบความถูกต้องของคุกกี้ Amazon Prime Video แบบอัตโนมัติ**

*<b>เพื่อการศึกษาเท่านั้น (Education purpose only).</b>*

---

## 🆕 What's New

> **อัปเดตล่าสุด** — รองรับ Proxy เต็มรูปแบบ, ระบบเซฟคุกกี้ที่ network error (`failed_cookies/`), และดึงข้อมูลบัญชี Prime Video ได้แม่นยำขึ้น

<details open>
<summary><b>🔥 Latest Features</b></summary>

### ✨ New Features
- **Proxy support** — HTTP, HTTPS, SOCKS4, SOCKS5 พร้อม auto-validate
- **Native file picker** — เลือกไฟล์ proxy ผ่าน Tkinter dialog
- **failed_cookies folder** 🆕 — คุกกี้ที่ network error จะถูกเซฟไว้ retry ทีหลัง ไม่หาย
- **Prime membership detection** — แยกสมาชิก Prime / Free Account
- **Console title bar live progress** — แสดงสถานะ real-time ขณะ validate proxy และตรวจสอบคุกกี้

### 🔧 Improvements (อ้างอิงจาก Netflix-Cookie-Checker)
- `validate_proxy` — ใช้ `except Exception` ครอบคลุม socket-level errors
- `load_and_validate_proxies` — แสดง progress และ terminal title ระหว่าง validate
- Return value แยกเหตุผล `"expired"` / `"network_error"` ชัดเจน
- Exponential backoff retry — `time.sleep(RETRY_DELAY * (attempt + 1))`
- Summary แสดง Network failed พร้อม 💡 Tip ให้ retry
 </details>

---

## Features

- ✅ Multi-threading — ตรวจสอบพร้อมกันหลายคุกกี้
- ✅ JSON + Netscape cookie support
- ✅ ตรวจจับสมาชิก Prime / Free Account
- ✅ ดึงข้อมูล customerID, ประเทศ, ชื่อโปรไฟล์
- ✅ Optional proxy (HTTP / HTTPS / SOCKS4 / SOCKS5)
- ✅ Auto proxy validation ก่อนใช้งาน
- ✅ **failed_cookies/** — เซฟคุกกี้ที่ network error ไว้ retry ได้
- ✅ ตรวจจับคุกกี้ซ้ำ (duplicate detection)
- ✅ Super fast — ไม่มี rate limiting

---

## Installation

```cmd
  git clone https://github.com/YOUR_USER/PrimeVideo-Cookie-Checker.git
  cd PrimeVideo-Cookie-Checker
  pip install -r requirements.txt
```

**Requirements:** `colorama==0.4.6`, `requests==2.34.2`

---

## Usage

1. รัน `cookie_converter.py` เพื่อแปลง Netscape cookies → JSON format  
   (เลือก folder ที่มีไฟล์คุกกี้ผ่าน Tkinter dialog)
2. แก้ไขจำนวน threads ใน `main.py` (line 50: `num_threads = 5`)
3. รัน `main.py`

**ต้องการอินเทอร์เน็ตที่เสถียร**

| Network Speed | Recommended threads |
|---------------|---------------------|
| < 5 Mbps      | 1-3                 |
| 5-20 Mbps     | 3-5                 |
| 20-100 Mbps   | 5-10                |
| > 100 Mbps    | 10-20               |

---

## Proxy Support

### Proxy File Format

ไฟล์ `.txt` หนึ่ง proxy ต่อบรรทัด รองรับทุกรูปแบบ:

```
# host:port
1.2.3.4:8080

# host:port:user:pass
1.2.3.4:8080:myuser:mypass

# user:pass@host:port
myuser:mypass@1.2.3.4:8080
```

บรรทัดที่ขึ้นต้นด้วย `#` จะถูกข้าม

---

## Output Structure

```
PrimeVideo-Cookie-Checker/
├── main.py
├── cookie_converter.py
├── json_cookies/          ← input: ไฟล์ JSON คุกกี้
├── working_cookies/       ← output: คุกกี้ที่ใช้งานได้
│   └── [XX] - [customerID] - [profile] - Prime Member.txt
└── failed_cookies/        ← output: คุกกี้ที่ network error (เอาไป retry ได้)
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

ดัดแปลงมาจาก [Netflix-cookie-checker](https://github.com/matheeshapathirana/Netflix-cookie-checker) โดย matheeshapathirana

---

## License

GNU General Public License v3.0
