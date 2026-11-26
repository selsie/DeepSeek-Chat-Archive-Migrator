"""
DeepSeek-to-Gemini Chat Archive Migrator (build_gemini_import.py)
https://github.com/selsie/DeepSeek-Chat-Archive-Migrator
=================================================================
Converts exported DeepSeek chat sessions (`chat_sessions/*.json`) into a
ChatGPT-compatible `conversations.json` archive ready for import into Google Gemini.

What this script does:
1. Reconstructs chronological message threads from DeepSeek's `parent_id` tree.
2. Renames and organizes all exported images/attachments into clean folders
   (`htdocs_upload/`) ready for FTP/static web hosting, and rewrites file links
   inside the chat messages to point to your `BASE_URL`.
3. Generates randomized `403 Forbidden` `index.html` files in every asset folder
   to prevent public directory browsing.
4. Optionally appends a customizable User/Assistant handover prompt at the end of
   each chat so Gemini retains your established persona and conversational style.

Outputs created in the script directory:
- `htdocs_upload/`      -> Upload this folder's contents to your web host.
- `import_all_chats.zip` -> Full archive to import into Google Gemini.
- `test_web_chat.zip`    -> Single-chat sample with an attachment to test first.

Usage:
1. Place this script in the root folder of your unzipped DeepSeek export
   (next to `chat_sessions/`).
2. Set `BASE_URL` in the CONFIGURATION section below to your hosting URL.
3. Run the script (`python build_gemini_import.py` or double-click on Windows).
"""

import json
import random
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

# ==============================================================================
# CONFIGURATION
# ==============================================================================
# Replace with the public URL where you will upload the contents of htdocs_upload/
BASE_URL = "https://example.com/ds_archive"

BASE_DIR = Path(__file__).parent
SESSIONS_DIR = BASE_DIR / "chat_sessions"
UPLOAD_ROOT_DIR = BASE_DIR / "htdocs_upload"
CHAT_PREFIX = "DeepSeek - "

# ------------------------------------------------------------------------------
# OPTIONAL: Persona & Style Continuity Anchor
# Uncomment and customize the two constants below if you want a handover message
# pair appended to the end of each imported chat so Gemini keeps your tone/style.
# ------------------------------------------------------------------------------
ANCHOR_USER_PROMPT = ""
ANCHOR_ASSISTANT_REPLY = ""

# ANCHOR_USER_PROMPT = (
#     "[Archive Handover & Style Anchor]\n"
#     "Analyze the imported conversation history above. For all upcoming responses in this chat, "
#     "seamlessly adopt the established persona, technical depth, formatting style, and dry humor "
#     "present in the previous assistant messages rather than reverting to generic boilerplate."
# )
#
# ANCHOR_ASSISTANT_REPLY = (
#     "Understood. I have reviewed the conversation history and will continue seamlessly "
#     "with the established tone, depth, and style. What would you like to work on next?"
# )

HEADLINES_403 = [
    "🧙‍♂️ 403 Forbidden: You shall not pass!",
    "🛑 403: Nothing to see here. Move along, citizen.",
    "👋 403 Forbidden: This is not the directory you are looking for.",
    "🔌 403: Access denied.",
    "🧭 403 Forbidden: Look, I'm a web server, not a tour guide.",
    "👀 403 Forbidden: Nosey, aren't we?",
    "🚧 403: Keep out. Yes, that means you.",
    "🌱 403 Forbidden: Stop poking around the directories.",
    "🤖 403: You don't have the clearance for this.",
    "🕷️ 403 Forbidden: Curiosity killed the crawler.",
    "🔒 403: Nothing to see here.",
    "↩️ 403: Wrong turn.",
    "📦 403: Private stash."
]

SUBLINES_403 = [
    "Nice try, Gandalf isn't letting you in either.",
    "Move along, citizen.",
    "This is not the directory you are looking for.",
    "Have you tried turning your permissions off and on again?",
    "Look, I'm a web server, not a tour guide.",
    "Nosey, aren't we?",
    "Yes, that means you.",
    "Go outside and touch some grass.",
    "Neither do the bots.",
    "Curiosity killed the crawler.",
    "Wrong turn. Nothing indexed here.",
    "Private stash – directory listing is disabled."
]


def generate_random_index_html() -> str:
    """Generates a standalone 403 HTML page with a randomized headline/subline combo."""
    h1_text = random.choice(HEADLINES_403)
    p_text = random.choice(SUBLINES_403)
    while p_text.lower() in h1_text.lower():
        p_text = random.choice(SUBLINES_403)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="robots" content="noindex, nofollow">
  <title>403 Forbidden</title>
  <style>
    body {{ font-family: system-ui, sans-serif; background: #f4f1ea; color: #1a1a1a; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
    .box {{ background: #fff; border: 2px solid #1a1a1a; padding: 2rem 3rem; text-align: center; max-width: 520px; }}
    h1 {{ margin-top: 0; font-size: 1.4rem; }}
    p {{ margin-bottom: 0; color: #444; }}
  </style>
</head>
<body>
  <div class="box">
    <h1>{h1_text}</h1>
    <p>{p_text}</p>
  </div>
</body>
</html>"""


def sanitize_name(name: str) -> str:
    """Sanitizes chat titles for URL- and FTP-safe directory/file names."""
    cleaned = re.sub(r'[\\/*?:"<>|]', "_", name).strip()
    return re.sub(r'\s+', "_", cleaned)[:65].strip("_")


def to_timestamp(val):
    if not val:
        return datetime.now().timestamp()
    if isinstance(val, (int, float)):
        return val / 1000.0 if val > 1e11 else float(val)
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return datetime.now().timestamp()
    return datetime.now().timestamp()


def get_ordered_messages(msg_list: list) -> list:
    """Traverses the parent_id message tree to restore chronological order."""
    by_id = {m["id"]: m for m in msg_list if isinstance(m, dict) and "id" in m}
    children_map = {mid: [] for mid in by_id}
    roots = []

    for mid, m in by_id.items():
        pid = m.get("parent_id")
        if pid in by_id:
            children_map[pid].append(mid)
        else:
            roots.append(mid)

    roots.sort()
    for cid_list in children_map.values():
        cid_list.sort()

    ordered = []
    visited = set()

    def dfs(node_id):
        if node_id in visited:
            return
        visited.add(node_id)
        ordered.append(by_id[node_id])
        for child_id in children_map[node_id]:
            dfs(child_id)

    for r in roots:
        dfs(r)
    return ordered


def convert_session(raw: dict, fallback_id: str) -> tuple[dict, str, list[tuple[Path, str]]]:
    chat_id = str(raw.get("id") or fallback_id)
    raw_title = (raw.get("title") or "Imported Chat").strip()

    gemini_title = raw_title if raw_title.startswith(CHAT_PREFIX) else f"{CHAT_PREFIX}{raw_title}"
    clean_base = raw_title[len(CHAT_PREFIX):] if raw_title.startswith(CHAT_PREFIX) else raw_title
    folder_chat_name = sanitize_name(clean_base) or f"Chat_{chat_id[:8]}"

    inserted_at = to_timestamp(raw.get("inserted_at"))
    updated_at = to_timestamp(raw.get("updated_at") or inserted_at)

    msg_list_sorted = get_ordered_messages(raw.get("messages") or [])

    root_id = f"root-{chat_id}"
    mapping = {
        root_id: {
            "id": root_id,
            "message": None,
            "parent": None,
            "children": []
        }
    }

    raw_by_id = {m["id"]: m for m in msg_list_sorted}
    valid_nodes = {}
    session_assets = []
    file_counter = 1

    for m in msg_list_sorted:
        role = (m.get("role") or "user").lower()
        if role not in ("user", "assistant", "system"):
            role = "assistant" if "bot" in role or "model" in role else "user"

        text_parts = []
        attachment_urls = []
        has_image = False

        if isinstance(m.get("fragments"), list):
            for frag in m["fragments"]:
                if not isinstance(frag, dict):
                    if isinstance(frag, str) and frag.strip():
                        text_parts.append(frag.strip())
                    continue

                ftype = (frag.get("type") or "").upper()

                if ftype == "FILE" and isinstance(frag.get("files"), list):
                    for fobj in frag["files"]:
                        if not isinstance(fobj, dict):
                            continue
                        rel_path = fobj.get("export_path")
                        orig_name = fobj.get("file_name") or "file.png"
                        ext = Path(orig_name).suffix.lower() or ".png"

                        if rel_path:
                            local_file = BASE_DIR / Path(rel_path)
                            if local_file.exists():
                                new_file_name = f"DeepSeek_{folder_chat_name}_{file_counter:03d}{ext}"
                                file_counter += 1
                                session_assets.append((local_file, new_file_name))

                                url_folder = quote(folder_chat_name)
                                url_file = quote(new_file_name)
                                full_url = f"{BASE_URL}/{url_folder}/{url_file}"
                                attachment_urls.append(full_url)

                                if fobj.get("is_image"):
                                    has_image = True
                            else:
                                attachment_urls.append(f"[Attachment (missing in export): {orig_name}]")
                else:
                    content = frag.get("content") or ""
                    if content:
                        if ftype == "THINK":
                            text_parts.append(f"<thought>\n{content}\n</thought>")
                        else:
                            text_parts.append(str(content))
        elif m.get("content"):
            text_parts.append(str(m["content"]))

        body_text = "\n\n".join(text_parts).strip()

        if attachment_urls:
            urls_block = "\n".join(attachment_urls)
            if body_text:
                prefix_icon = "🖼️ " if has_image else "📎 "
                final_text = f"{prefix_icon}{body_text}\n\n{urls_block}"
            else:
                prefix_icon = "🖼️\n" if has_image else "📎\n"
                final_text = f"{prefix_icon}{urls_block}"
        else:
            final_text = body_text

        if final_text:
            valid_nodes[m["id"]] = (f"msg-{chat_id}-{m['id']}", m, role, final_text)

    def resolve_valid_parent(raw_parent_id):
        visited = set()
        curr = raw_parent_id
        while curr is not None and curr not in visited:
            visited.add(curr)
            if curr in valid_nodes:
                return valid_nodes[curr][0]
            parent_obj = raw_by_id.get(curr)
            curr = parent_obj.get("parent_id") if parent_obj else None
        return root_id

    last_node_id = root_id
    last_msg_time = updated_at

    for raw_id, (node_id, m, role, text) in valid_nodes.items():
        parent_node_id = resolve_valid_parent(m.get("parent_id"))
        msg_time = to_timestamp(m.get("inserted_at") or inserted_at)

        mapping[node_id] = {
            "id": node_id,
            "parent": parent_node_id,
            "children": [],
            "message": {
                "id": node_id,
                "author": {"role": role, "name": None, "metadata": {}},
                "create_time": msg_time,
                "update_time": msg_time,
                "content": {
                    "content_type": "text",
                    "parts": [text]
                },
                "status": "finished_successfully",
                "end_turn": True,
                "weight": 1.0,
                "metadata": {},
                "recipient": "all"
            }
        }
        last_node_id = node_id
        last_msg_time = max(last_msg_time, msg_time)

    # Resolve active leaf node
    if len(mapping) > 1:
        curr_msg_id = raw.get("current_message_id")
        active_leaf = (
            resolve_valid_parent(curr_msg_id)
            if curr_msg_id not in valid_nodes
            else valid_nodes[curr_msg_id][0]
        )
        if active_leaf == root_id:
            active_leaf = last_node_id

        # Append optional User/Assistant handover anchor if configured
        if ANCHOR_USER_PROMPT.strip() and ANCHOR_ASSISTANT_REPLY.strip():
            anchor_user_id = f"anchor-user-{chat_id}"
            anchor_asst_id = f"anchor-asst-{chat_id}"

            mapping[anchor_user_id] = {
                "id": anchor_user_id,
                "parent": active_leaf,
                "children": [],
                "message": {
                    "id": anchor_user_id,
                    "author": {"role": "user", "name": None, "metadata": {}},
                    "create_time": last_msg_time + 1,
                    "update_time": last_msg_time + 1,
                    "content": {
                        "content_type": "text",
                        "parts": [ANCHOR_USER_PROMPT]
                    },
                    "status": "finished_successfully",
                    "end_turn": True,
                    "weight": 1.0,
                    "metadata": {},
                    "recipient": "all"
                }
            }

            mapping[anchor_asst_id] = {
                "id": anchor_asst_id,
                "parent": anchor_user_id,
                "children": [],
                "message": {
                    "id": anchor_asst_id,
                    "author": {"role": "assistant", "name": None, "metadata": {}},
                    "create_time": last_msg_time + 2,
                    "update_time": last_msg_time + 2,
                    "content": {
                        "content_type": "text",
                        "parts": [ANCHOR_ASSISTANT_REPLY]
                    },
                    "status": "finished_successfully",
                    "end_turn": True,
                    "weight": 1.0,
                    "metadata": {},
                    "recipient": "all"
                }
            }
            final_current_node = anchor_asst_id
        else:
            final_current_node = active_leaf
    else:
        final_current_node = root_id

    for node_id, node in mapping.items():
        pid = node["parent"]
        if pid and pid in mapping and node_id != root_id:
            mapping[pid]["children"].append(node_id)

    conv_obj = {
        "id": chat_id,
        "conversation_id": chat_id,
        "title": gemini_title,
        "create_time": inserted_at,
        "update_time": updated_at,
        "mapping": mapping,
        "current_node": final_current_node,
        "moderation_results": [],
        "plugin_ids": None,
        "gizmo_id": None,
        "is_archived": False
    }
    return conv_obj, folder_chat_name, session_assets


def write_zip(convs: list, zip_path: Path):
    json_bytes = json.dumps(convs, ensure_ascii=False, indent=2).encode("utf-8")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("conversations.json", json_bytes)
    print(f"Created: {zip_path.name} ({len(convs)} chat(s))")


def main():
    files = sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_size)
    if not files:
        print("No JSON files found in 'chat_sessions/'.")
        return

    if UPLOAD_ROOT_DIR.exists():
        shutil.rmtree(UPLOAD_ROOT_DIR)
    UPLOAD_ROOT_DIR.mkdir(exist_ok=True)

    (UPLOAD_ROOT_DIR / "index.html").write_text(generate_random_index_html(), encoding="utf-8")

    converted_all = []
    test_image_conv = None
    copied_files = 0
    used_folders = set()

    for jf in files:
        raw_data = json.loads(jf.read_text(encoding="utf-8"))
        conv, folder_name, assets = convert_session(raw_data, jf.stem)

        unique_folder = folder_name
        if unique_folder in used_folders:
            unique_folder = f"{folder_name}_{conv['id'][:6]}"
            old_enc = quote(folder_name)
            new_enc = quote(unique_folder)
            for node in conv["mapping"].values():
                msg = node.get("message")
                if msg:
                    msg["content"]["parts"] = [
                        p.replace(f"/{old_enc}/", f"/{new_enc}/")
                         .replace(f"DeepSeek_{folder_name}_", f"DeepSeek_{unique_folder}_")
                        for p in msg["content"]["parts"]
                    ]
        used_folders.add(unique_folder)

        anchor_active = bool(ANCHOR_USER_PROMPT.strip() and ANCHOR_ASSISTANT_REPLY.strip())
        min_nodes = 3 if anchor_active else 1
        if len(conv["mapping"]) > min_nodes:
            converted_all.append(conv)
            if assets and test_image_conv is None:
                test_image_conv = conv

        if assets:
            target_dir = UPLOAD_ROOT_DIR / unique_folder
            target_dir.mkdir(exist_ok=True)
            (target_dir / "index.html").write_text(generate_random_index_html(), encoding="utf-8")

            for src, new_name in assets:
                final_name = new_name.replace(f"DeepSeek_{folder_name}_", f"DeepSeek_{unique_folder}_")
                shutil.copy2(src, target_dir / final_name)
                copied_files += 1

    if test_image_conv:
        write_zip([test_image_conv], BASE_DIR / "test_web_chat.zip")

    write_zip(converted_all, BASE_DIR / "import_all_chats.zip")
    print(f"Done! {copied_files} asset(s) + randomized 403 index.html files ready in '{UPLOAD_ROOT_DIR.name}/'.")


if __name__ == "__main__":
    main()
    input("\nAll done! Press Enter to exit...")
