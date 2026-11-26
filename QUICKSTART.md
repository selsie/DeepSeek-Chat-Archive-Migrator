# Quick Start Guide

Follow these three steps to convert your DeepSeek export, host your attachments, and import your chats into Google Gemini.

## Prerequisites
* **Python 3.9+** installed (uses standard library modules only — no `pip install` required).
* Your unzipped **DeepSeek export folder** containing `chat_sessions/` and any exported asset folders.
* A **web host / static server** (e.g., InfinityFree, GitHub Pages, S3, or any FTP-accessible webspace) to host your images and attachments.

---

## Step 1: Configure Your Hosting URL
1. Place `build_gemini_import.py` (and `export_individual_chats.py` if needed) in the root directory of your unzipped DeepSeek export:
   ```text
   deepseek-export/
   ├── chat_sessions/
   ├── <exported_asset_folders>/
   ├── build_gemini_import.py
   └── export_individual_chats.py
   ```
2. Open `build_gemini_import.py` and set `BASE_URL` to the public URL where your assets will live:
   ```python
   BASE_URL = "[https://your-domain.example.com/ds_archive](https://your-domain.example.com/ds_archive)"
   ```
3. *(Optional)* Edit `ANCHOR_USER_PROMPT` and `ANCHOR_ASSISTANT_REPLY` at the top of `build_gemini_import.py` to customize the persona, tone, or form of address carried over into Gemini.

---

## Step 2: Run the Migration Builder
Run `build_gemini_import.py` (double-click the file on Windows or run `python build_gemini_import.py` in your terminal).

The script will generate:
* `htdocs_upload/` — A ready-to-upload folder containing your cleanly renamed images (`DeepSeek_<Chat_Title>_001.png`) and randomized `403 Forbidden` `index.html` files in every directory to block directory browsing.
* `import_all_chats.zip` — Contains `conversations.json` with all chats, rewritten image links, and persona handover anchors.
* `test_web_chat.zip` — A single-chat archive containing at least one image link so you can verify your setup before importing everything.

---

## Step 3: Upload Assets & Import into Gemini
1. **Upload the assets:** Connect to your web server via an FTP client (such as FileZilla) and upload the contents of `htdocs_upload/` to the directory matching your `BASE_URL`. *(Tip: Use FTP rather than browser-based file managers to avoid timeouts on large folders.)*
2. **Verify with a single test chat:** Open Gemini, go to **Settings → Import chats**, and upload `test_web_chat.zip`. Open the imported chat and confirm that the image link loads properly in your browser.
3. **Import the full archive:** Once verified, upload `import_all_chats.zip`.
   > **Note:** Gemini enforces a daily limit on the number of separate import actions. Batching all sessions into `import_all_chats.zip` counts as a single import.
