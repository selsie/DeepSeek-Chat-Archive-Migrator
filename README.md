# DeepSeek-Chat-Archive-Migrator
DeepSeek Chat Archive Migrator (with Image Hosting &amp; Persona Continuity)

A lightweight, zero-dependency Python toolkit to migrate exported **DeepSeek** chat histories (`chat_sessions/*.json`) into **Google Gemini** (via the ChatGPT-compatible `conversations.json` import format) or organize them as clean, human-readable individual JSON files.

## Why this exists
When exporting data from DeepSeek, chats are stored as cryptic UUID-named JSON files with local relative paths to uploaded images/attachments. Standard importers either drop local attachments or lose the conversational tone/persona when continuing a chat in another LLM.

This toolkit solves four problems in one go:
1. **Tree-accurate message reconstruction:** Traverses DeepSeek's `parent_id` message graph in exact chronological order.
2. **Self-hosted attachment mapping:** Renames and organizes all exported images/files into clean folders, rewrites links inside the chat messages to point to your own web host (e.g., InfinityFree, GitHub Pages, S3, or any static host), and generates randomized `403 Forbidden` `index.html` files to prevent directory indexing.
3. **Persona & style continuity anchor:** Appends a customizable User/Assistant handover pair at the end of each imported chat so the target LLM immediately picks up the established tone, form of address, and style without manual re-prompting.
4. **Individual readable exports:** Includes a second script to split/rename the raw UUID files into clean titles (`DeepSeek_<Chat_Title>.json`) with updated URLs for local archiving or RAG/knowledge-base workflows.

---

## Folder Structure

Place both scripts in the root directory of your unzipped DeepSeek export:

```text
deepseek-export/
├── chat_sessions/               # Original exported UUID .json files from DeepSeek
├── <exported_asset_folders>/    # Original image/file folders referenced by export_path
├── build_gemini_import.py       # Script 1: Builds Gemini import ZIP + upload folder
└── export_individual_chats.py   # Script 2: Exports clean, individual named JSON files
