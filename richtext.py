import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
import urllib.request
import urllib.error
import json
import re
import os
import mimetypes
import uuid

BOT_TOKEN = "****"
CHANNEL = "@****"

MEDIA_FILES = {}

# Global direction state
IS_RTL = False

def new_media_id():
    return "media_" + uuid.uuid4().hex[:10]

def detect_media_type(path):
    mime, _ = mimetypes.guess_type(path)
    if not mime:
        return "document"
    if mime.startswith("image/"):
        return "photo"
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("audio/"):
        return "audio"
    return "document"

def add_media_file(path, caption="", forced_type=None):
    media_type = forced_type or detect_media_type(path)
    media_id = new_media_id()
    MEDIA_FILES[media_id] = {
        "id": media_id,
        "type": media_type,
        "path": path,
        "caption": caption
    }
    return media_id

def get_media_reference(media_id):
    item = MEDIA_FILES.get(media_id)
    if not item:
        return None
    media_type = item["type"]
    if media_type == "photo":
        return f"tg://photo?id={media_id}"
    if media_type == "video":
        return f"tg://video?id={media_id}"
    if media_type == "audio":
        return f"tg://audio?id={media_id}"
    return f"tg://document?id={media_id}"


# DIALOG BOX
# -------------------
def multi_input_dialog(title, fields):
    result = [None]

    def on_ok():
        values = []
        for entry in entries:
            values.append(entry.get().strip())
        result[0] = values
        dialog.destroy()

    def on_cancel():
        dialog.destroy()

    dialog = tk.Toplevel(window)
    dialog.title(title)
    dialog.transient(window)
    dialog.grab_set()
    dialog.resizable(False, False)

    frame = tk.Frame(dialog, padx=12, pady=10)
    frame.pack(fill="both", expand=True)

    entries = []
    for i, (label, default) in enumerate(fields):
        tk.Label(frame, text=label, anchor="w").grid(row=i, column=0, sticky="w", pady=3)
        e = tk.Entry(frame, width=42)
        e.insert(0, default or "")
        e.grid(row=i, column=1, sticky="ew", pady=3, padx=(8, 0))
        entries.append(e)

    btn_frame = tk.Frame(frame)
    btn_frame.grid(row=len(fields), column=0, columnspan=2, pady=(12, 0))
    tk.Button(btn_frame, text="OK", width=10, command=on_ok).pack(side="left", padx=4)
    tk.Button(btn_frame, text="Cancel", width=10, command=on_cancel).pack(side="left", padx=4)

    if entries:
        entries[0].focus_set()

    dialog.wait_window()
    return result[0]

# TELEGRAM MULTIPART HELPERS
# ---------------------------
def build_multipart(fields, files):
    boundary = "----TelegramRichPublisherBoundary" + uuid.uuid4().hex
    body = bytearray()
    for name, value in fields.items():
        part = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n'
            f"\r\n"
            f"{value}\r\n"
        )
        body.extend(part.encode("utf-8"))
    for field_name, file_info in files.items():
        filename, content, content_type = file_info
        part = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; '
            f'name="{field_name}"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n"
            f"\r\n"
        )
        body.extend(part.encode("utf-8"))
        body.extend(content)
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    content_type = f"multipart/form-data; boundary={boundary}"
    return bytes(body), content_type

# TELEGRAM PUBLISH
# -----------------
def publish():
    markdown = editor.get("1.0", tk.END).strip()
    if not markdown:
        messagebox.showwarning("Empty post", "Please enter some Markdown.")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendRichMessage"
    rich_media = []
    upload_files = {}
    for media_id, item in list(MEDIA_FILES.items()):
        if media_id not in markdown:
            continue
        path = item["path"]
        if not os.path.isfile(path):
            messagebox.showerror("Missing file", f"The following file no longer exists:\n\n{path}")
            return
        try:
            with open(path, "rb") as f:
                content = f.read()
        except Exception as e:
            messagebox.showerror("File error", f"Could not read:\n\n{path}\n\n{e}")
            return
        filename = os.path.basename(path)
        mime_type, _ = mimetypes.guess_type(path)
        if not mime_type:
            mime_type = "application/octet-stream"
        rich_media.append({
            "id": media_id,
            "media": {
                "type": item["type"],
                "media": f"attach://{media_id}"
            }
        })
        upload_files[media_id] = (filename, content, mime_type)

    # Add is_rtl when the editor is in RTL mode
    rich_message = {"markdown": markdown}
    if IS_RTL:
        rich_message["is_rtl"] = True

    if rich_media:
        rich_message["media"] = rich_media
    data = {
        "chat_id": CHANNEL,
        "rich_message": rich_message
    }
    try:
        if not upload_files:
            request = urllib.request.Request(
                url,
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
        else:
            fields = {
                "chat_id": CHANNEL,
                "rich_message": json.dumps(rich_message, ensure_ascii=False)
            }
            body, content_type = build_multipart(fields, upload_files)
            request = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": content_type},
                method="POST"
            )
        with urllib.request.urlopen(request) as response:
            result = json.loads(response.read().decode("utf-8"))
        if result.get("ok"):
            status.config(text="✓ Published successfully", fg="green")
        else:
            status.config(
                text="Telegram error: " + result.get("description", "Unknown error"),
                fg="red"
            )
    except urllib.error.HTTPError as e:
        try:
            error_body = e.read().decode("utf-8")
        except Exception:
            error_body = str(e)
        status.config(text="Telegram HTTP error", fg="red")
        messagebox.showerror("Telegram error", error_body)
    except Exception as e:
        status.config(text="Error: " + str(e), fg="red")

# EDITOR HELPERS
# ---------------
def get_selection():
    try:
        start = editor.index("sel.first")
        end = editor.index("sel.last")
        text = editor.get(start, end)
        return start, end, text
    except tk.TclError:
        return None, None, ""

def replace_selection(before, after=""):
    start, end, text = get_selection()
    if text:
        editor.delete(start, end)
        editor.insert(start, before + text + after)
        editor.tag_remove("sel", "1.0", tk.END)
        editor.mark_set("insert", f"{start}+{len(before) + len(text) + len(after)}c")
    else:
        cursor = editor.index("insert")
        editor.insert(cursor, before + after)
        editor.mark_set("insert", f"{cursor}+{len(before)}c")
    update_preview()
    editor.focus_set()

def insert_text(text):
    cursor = editor.index("insert")
    editor.insert(cursor, text)
    editor.mark_set("insert", f"{cursor}+{len(text)}c")
    update_preview()
    editor.focus_set()

# RTL / LTR SUPPORT
# ------------------
def apply_direction_tags():
    """Force the direction tag on the entire content of editor and preview.
    Must be called after any text change so every line starts with the tag
    (Tk uses the first character of a line to decide justification)."""
    justify = "right" if IS_RTL else "left"

    # Editor
    editor.tag_configure("direction", justify=justify)
    editor.tag_remove("direction", "1.0", "end")
    editor.tag_add("direction", "1.0", "end")

    # Preview
    preview.tag_configure("direction", justify=justify)
    preview.tag_remove("direction", "1.0", "end")
    preview.tag_add("direction", "1.0", "end")

def set_direction(rtl: bool):
    """Apply RTL or LTR to both editor and preview."""
    global IS_RTL
    IS_RTL = rtl

    # Try the internal bdir option when the Tcl/Tk build supports it
    bdir = "rtl" if rtl else "ltr"
    for widget in (editor, preview):
        try:
            widget.tk.call(widget._w, "configure", "-bdir", bdir)
        except tk.TclError:
            pass

    apply_direction_tags()

    # Update button text
    rtl_btn.config(text="LTR ←" if rtl else "RTL →")

    update_preview()

def toggle_direction():
    set_direction(not IS_RTL)

def contains_persian_or_arabic(text: str) -> bool:
    """Simple detection of Persian / Arabic characters."""
    return bool(re.search(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]', text))

def auto_detect_direction(event=None):
    """Optional: automatically switch to RTL when Persian text is typed."""
    content = editor.get("1.0", "end")
    if contains_persian_or_arabic(content):
        if not IS_RTL:
            set_direction(True)
    else:
        if IS_RTL:
            set_direction(False)

# FORMATTING
# -----------
def heading(level):
    start, end, text = get_selection()
    prefix = "#" * level + " "
    if text:
        lines = text.splitlines()
        formatted = "\n".join(
            prefix + line if line.strip() else line for line in lines
        )
        editor.delete(start, end)
        editor.insert(start, formatted)
    else:
        insert_text(prefix)
        return
    update_preview()
    editor.focus_set()

def bold():
    replace_selection("**", "**")

def italic():
    replace_selection("*", "*")

def underline():
    replace_selection("<u>", "</u>")

def strike():
    replace_selection("~~", "~~")

def highlight():
    replace_selection("==", "==")

def spoiler():
    replace_selection("||", "||")

def code():
    replace_selection("`", "`")

def code_block():
    start, end, text = get_selection()
    if text:
        editor.delete(start, end)
        editor.insert(start, "```\n" + text + "\n```\n")
    else:
        insert_text("```\n\n```\n")
        editor.mark_set("insert", "insert-4c")
    update_preview()
    editor.focus_set()

def superscript():
    replace_selection("<sup>", "</sup>")

def subscript():
    replace_selection("<sub>", "</sub>")

def insert_footer():
    start, end, text = get_selection()
    content = text.strip() if text else "Your footer text here"
    footer = f"<footer>{content}</footer>\n\n"
    if text:
        editor.delete(start, end)
        editor.insert(start, footer)
    else:
        insert_text(footer)
    update_preview()
    editor.focus_set()

def insert_blockquote():
    start, end, text = get_selection()
    content = text.strip() if text else "Quote text here"
    values = multi_input_dialog("Blockquote", [
        ("Quote text:", content),
        ("Author / credit (optional):", "")
    ])
    if not values:
        return
    content, author = values
    if not content:
        return
    if author:
        block = f"<blockquote>{content}<cite>{author}</cite></blockquote>\n\n"
    else:
        block = f"<blockquote>{content}</blockquote>\n\n"
    if text:
        editor.delete(start, end)
        editor.insert(start, block)
    else:
        insert_text(block)
    update_preview()
    editor.focus_set()

def insert_expandable_blockquote():
    start, end, text = get_selection()
    content = text.strip() if text else "Expandable quote text here"
    values = multi_input_dialog("Expandable Blockquote", [
        ("Quote text:", content),
        ("Author / credit (optional):", "")
    ])
    if not values:
        return
    content, author = values
    if not content:
        return
    if author:
        block = f"<blockquote expandable>{content}<cite>{author}</cite></blockquote>\n\n"
    else:
        block = f"<blockquote expandable>{content}</blockquote>\n\n"
    if text:
        editor.delete(start, end)
        editor.insert(start, block)
    else:
        insert_text(block)
    update_preview()
    editor.focus_set()

def insert_pullquote():
    start, end, text = get_selection()
    content = text.strip() if text else "Pull quote text here"
    values = multi_input_dialog("Pull Quote", [
        ("Quote text:", content),
        ("Author / credit (optional):", "")
    ])
    if not values:
        return
    content, author = values
    if not content:
        return
    if author:
        block = f"<aside>{content}<cite>{author}</cite></aside>\n\n"
    else:
        block = f"<aside>{content}</aside>\n\n"
    if text:
        editor.delete(start, end)
        editor.insert(start, block)
    else:
        insert_text(block)
    update_preview()
    editor.focus_set()

def bullet_list():
    start, end, text = get_selection()
    if text:
        formatted = "\n".join(
            "- " + line if line.strip() else line for line in text.splitlines()
        )
        editor.delete(start, end)
        editor.insert(start, formatted)
    else:
        insert_text("- ")
    update_preview()

def numbered_list():
    start, end, text = get_selection()
    if text:
        lines = text.splitlines()
        formatted = "\n".join(
            f"{i}. {line}" if line.strip() else line
            for i, line in enumerate(lines, 1)
        )
        editor.delete(start, end)
        editor.insert(start, formatted)
    else:
        insert_text("1. ")
    update_preview()

def task_list():
    start, end, text = get_selection()
    if text:
        formatted = "\n".join(
            "- [ ] " + line if line.strip() else line for line in text.splitlines()
        )
        editor.delete(start, end)
        editor.insert(start, formatted)
    else:
        insert_text("- [ ] ")
    update_preview()

def insert_link():
    start, end, text = get_selection()
    values = multi_input_dialog("Insert Link", [
        ("URL:", ""),
        ("Link text (leave empty to use selection):", text or "")
    ])
    if not values:
        return
    url, label = values
    if not url:
        return
    if not label:
        label = url
    link = f"[{label}]({url})"
    if text:
        editor.delete(start, end)
        editor.insert(start, link)
    else:
        insert_text(link)
    update_preview()
    editor.focus_set()

def insert_math_inline():
    replace_selection("$", "$")

def insert_math_block():
    start, end, text = get_selection()
    if text:
        editor.delete(start, end)
        editor.insert(start, "$$\n" + text + "\n$$\n")
    else:
        insert_text("$$\n\n$$\n")
        editor.mark_set("insert", "insert-4c")
    update_preview()
    editor.focus_set()

def insert_empty_line():
    insert_text("</br><br> </br><br>")

# NAVIGATE
# --------
def insert_anchor():
    values = multi_input_dialog("Insert Anchor", [
        ("Anchor name (e.g. chapter-1):", "")
    ])
    if not values or not values[0]:
        return
    name = values[0]
    insert_text(f'<a name="{name}"></a>\n')

def insert_link_to_anchor():
    start, end, text = get_selection()
    values = multi_input_dialog("Link to Anchor", [
        ("Target anchor name (leave empty for top of message):", ""),
        ("Visible link text:", text or "Go to section")
    ])
    if not values:
        return
    name, label = values
    if not label:
        return
    href = f"#{name}" if name else "#"
    link = f'<a href="{href}">{label}</a>'
    if text:
        editor.delete(start, end)
        editor.insert(start, link)
    else:
        insert_text(link)
    update_preview()
    editor.focus_set()

def insert_link_to_top():
    start, end, text = get_selection()
    values = multi_input_dialog("Link to Top of Message", [
        ("Visible link text:", text or "Back to top")
    ])
    if not values or not values[0]:
        return
    label = values[0]
    link = f'<a href="#">{label}</a>'
    if text:
        editor.delete(start, end)
        editor.insert(start, link)
    else:
        insert_text(link)
    update_preview()
    editor.focus_set()

def insert_reference():
    start, end, text = get_selection()
    values = multi_input_dialog("Create Footnote / Reference Definition", [
        ("Reference ID (e.g. note-1):", ""),
        ("Full text that will appear in the footnote:", text or "")
    ])
    if not values or not values[0]:
        return
    name, content = values
    if not content:
        content = "Footnote content"
    ref = f'<tg-reference name="{name}">{content}</tg-reference>\n'
    if text:
        editor.delete(start, end)
        editor.insert(start, ref)
    else:
        insert_text(ref)
    update_preview()
    editor.focus_set()

def insert_reference_link():
    start, end, text = get_selection()
    values = multi_input_dialog("Create Link to a Footnote", [
        ("Reference ID to link to (e.g. note-1):", ""),
        ("Visible text of the link (e.g. [1] or *):", text or "[1]")
    ])
    if not values or not values[0]:
        return
    name, label = values
    link = f'<a href="#{name}">{label}</a>'
    if text:
        editor.delete(start, end)
        editor.insert(start, link)
    else:
        insert_text(link)
    update_preview()
    editor.focus_set()

# INSERT helpers
# --------------
def insert_email():
    start, end, text = get_selection()
    values = multi_input_dialog("Email Link", [
        ("Email address:", ""),
        ("Visible text (optional):", text or "")
    ])
    if not values or not values[0]:
        return
    email, label = values
    if not label:
        label = email
    link = f'<a href="mailto:{email}">{label}</a>'
    if text:
        editor.delete(start, end)
        editor.insert(start, link)
    else:
        insert_text(link)
    update_preview()
    editor.focus_set()

def insert_phone():
    start, end, text = get_selection()
    values = multi_input_dialog("Phone Link", [
        ("Phone number (e.g. +123456789):", ""),
        ("Visible text (optional):", text or "")
    ])
    if not values or not values[0]:
        return
    phone, label = values
    if not label:
        label = phone
    link = f'<a href="tel:{phone}">{label}</a>'
    if text:
        editor.delete(start, end)
        editor.insert(start, link)
    else:
        insert_text(link)
    update_preview()
    editor.focus_set()

def insert_user_mention():
    start, end, text = get_selection()
    values = multi_input_dialog("User Mention", [
        ("User ID (numeric):", ""),
        ("Visible text (optional):", text or "")
    ])
    if not values or not values[0]:
        return
    user_id, label = values
    if not label:
        label = f"User {user_id}"
    link = f'<a href="tg://user?id={user_id}">{label}</a>'
    if text:
        editor.delete(start, end)
        editor.insert(start, link)
    else:
        insert_text(link)
    update_preview()
    editor.focus_set()

def insert_map():
    values = multi_input_dialog("Insert Map", [
        ("Latitude (e.g. 41.9):", ""),
        ("Longitude (e.g. 12.5):", ""),
        ("Zoom (0-24, optional):", "14")
    ])
    if not values or not values[0] or not values[1]:
        return
    lat, long, zoom = values
    zoom_attr = f' zoom="{zoom}"' if zoom else ""
    insert_text(f'<tg-map lat="{lat}" long="{long}"{zoom_attr}/>\n\n')

def insert_datetime():
    start, end, text = get_selection()
    values = multi_input_dialog("Date / Time", [
        ("Unix timestamp (e.g. 1647531900):", ""),
        ("Format (e.g. wDT):", "wDT"),
        ("Visible text (optional):", text or "date/time")
    ])
    if not values or not values[0]:
        return
    unix, fmt, label = values
    if not fmt:
        fmt = "wDT"
    if not label:
        label = "date/time"
    tag = f'<tg-time unix="{unix}" format="{fmt}">{label}</tg-time>'
    if text:
        editor.delete(start, end)
        editor.insert(start, tag)
    else:
        insert_text(tag)
    update_preview()
    editor.focus_set()

def insert_table():
    table = (
        "| Column 1 | Column 2 | Column 3 |\n"
        "|:---|:---|:---|\n"
        "| Value 1 | Value 2 | Value 3 |\n"
        "| Value 4 | Value 5 | Value 6 |\n\n"
    )
    insert_text(table)

def insert_details():
    values = multi_input_dialog("Details / Collapsible", [
        ("Summary title:", "Technical details")
    ])
    if not values:
        return
    summary = values[0] or "Details"
    details = (
        f"<details>\n"
        f"<summary>{summary}</summary>\n\n"
        f"Your content here.\n\n"
        f"</details>\n\n"
    )
    insert_text(details)

def insert_separator():
    insert_text("\n---\n\n")

def insert_button_row():
    values = multi_input_dialog("Button Row (Bot API 10.3)", [
        ("Button text:", ""),
        ("Type (url / callback_data / web_app / copy_text / disabled):", "url"),
        ("Style (primary / success / danger / link) optional:", ""),
        ("URL or data (depending on type):", ""),
        ("Row align (left / center / right) optional:", "center")
    ])
    if not values or not values[0]:
        return

    text, btn_type, style, data, align = values
    btn_type = btn_type.strip().lower().replace(" ", "_").replace("-", "_")

    type_map = {
        "url": "url",
        "callback": "callback_data",
        "callback_data": "callback_data",
        "callbackdata": "callback_data",
        "web_app": "web_app",
        "webapp": "web_app",
        "web": "web_app",
        "copy": "copy_text",
        "copy_text": "copy_text",
        "copytext": "copy_text",
        "disabled": "disabled",
        "disable": "disabled",
    }
    btn_type = type_map.get(btn_type, btn_type)

    style_attr = f' style="{style}"' if style else ""
    align_attr = f' align="{align}"' if align else ""

    if btn_type == "url":
        if not data:
            messagebox.showwarning("Missing", "URL is required for type=url")
            return
        btn = f'<tg-button type="url"{style_attr} url="{data}">{text}</tg-button>'
    elif btn_type == "callback_data":
        if not data:
            messagebox.showwarning("Missing", "Callback data is required")
            return
        btn = f'<tg-button type="callback_data"{style_attr} data="{data}">{text}</tg-button>'
    elif btn_type == "web_app":
        if not data:
            messagebox.showwarning("Missing", "Web App URL is required")
            return
        btn = f'<tg-button type="web_app"{style_attr} url="{data}">{text}</tg-button>'
    elif btn_type == "copy_text":
        if not data:
            messagebox.showwarning("Missing", "Text to copy is required")
            return
        btn = f'<tg-button type="copy_text"{style_attr} text="{data}">{text}</tg-button>'
    elif btn_type == "disabled":
        btn = f'<tg-button type="disabled"{style_attr}>{text}</tg-button>'
    else:
        messagebox.showwarning(
            "Unsupported button type",
            f"You entered: '{values[1]}'\n\n"
            "Supported types:\n"
            "• url\n"
            "• callback_data (or callback)\n"
            "• web_app (or webapp / web)\n"
            "• copy_text (or copy)\n"
            "• disabled (or disable)"
        )
        return

    row = f"<tg-button-row{align_attr}>\n  {btn}\n</tg-button-row>\n\n"
    insert_text(row)

# MEDIA INSERT
# -------------
def insert_image():
    paths = filedialog.askopenfilenames(
        title="Select image",
        filetypes=[
            ("Images", "*.jpg *.jpeg *.png *.gif *.webp"),
            ("All files", "*.*")
        ]
    )
    if not paths:
        return
    for path in paths:
        caption = simpledialog.askstring(
            "Image Caption",
            f"Caption for:\n{os.path.basename(path)}\n\nLeave empty for no caption:"
        )
        media_id = add_media_file(path, caption or "", "photo")
        reference = get_media_reference(media_id)
        if caption:
            markdown = f'![]({reference} "{caption}")\n\n'
        else:
            markdown = f"![]({reference})\n\n"
        insert_text(markdown)

def insert_slideshow():
    paths = filedialog.askopenfilenames(
        title="Select images for slideshow",
        filetypes=[
            ("Images", "*.jpg *.jpeg *.png *.gif *.webp"),
            ("All files", "*.*")
        ]
    )
    if not paths:
        return
    if len(paths) < 2:
        messagebox.showwarning("Slideshow", "Please select at least 2 images.")
        return
    if len(paths) > 50:
        messagebox.showwarning(
            "Slideshow",
            "Telegram supports up to 50 media attachments in a Rich Message."
        )
        paths = paths[:50]

    caption = simpledialog.askstring(
        "Slideshow Caption",
        "Enter caption for the whole slideshow (optional):\n\n"
        "This will be placed inside <figcaption>…</figcaption>"
    )

    lines = ["<tg-slideshow>", ""]
    for path in paths:
        media_id = add_media_file(path, "", "photo")
        reference = get_media_reference(media_id)
        lines.append(f"![]({reference})")
    if caption:
        lines.append(f"<figcaption>{caption}</figcaption>")
    lines.extend(["", "</tg-slideshow>", "", ""])
    insert_text("\n".join(lines))

def insert_collage():
    paths = filedialog.askopenfilenames(
        title="Select images for collage",
        filetypes=[
            ("Images", "*.jpg *.jpeg *.png *.gif *.webp"),
            ("All files", "*.*")
        ]
    )
    if not paths:
        return
    if len(paths) < 2:
        messagebox.showwarning("Collage", "Please select at least 2 images.")
        return
    if len(paths) > 50:
        paths = paths[:50]

    caption = simpledialog.askstring(
        "Collage Caption",
        "Enter caption for the whole collage (optional):\n\n"
        "This will be placed inside <figcaption>…</figcaption>"
    )

    lines = ["<tg-collage>", ""]
    for path in paths:
        media_id = add_media_file(path, "", "photo")
        reference = get_media_reference(media_id)
        lines.append(f"![]({reference})")
    if caption:
        lines.append(f"<figcaption>{caption}</figcaption>")
    lines.extend(["", "</tg-collage>", "", ""])
    insert_text("\n".join(lines))

def insert_file():
    path = filedialog.askopenfilename(title="Select file")
    if not path:
        return
    caption = simpledialog.askstring(
        "File Caption",
        f"Caption for:\n{os.path.basename(path)}\n\nLeave empty to use the filename:"
    )
    if not caption:
        caption = os.path.basename(path)
    media_id = add_media_file(path, caption, "document")
    reference = get_media_reference(media_id)
    markdown = f'![]({reference} "{caption}")\n\n'
    insert_text(markdown)

# PREVIEW
# --------
details_counter = 0
details_states = {}

def insert_preview_text(text, tag="normal"):
    preview.insert(tk.END, text, tag)

def normalize_html_breaks(text):
    text = text.replace("</br><br> </br><br>", "\n")
    text = re.sub(r"</?br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text

def render_inline(text):
    text = normalize_html_breaks(text)

    pattern = re.compile(
        r"("
        r"<a\s+name=\"[^\"]*\"\s*>\s*</a>"
        r"|<a\s+href=\"[^\"]*\"[^>]*>.*?</a>"
        r"|<tg-time\s+[^>]*>.*?</tg-time>"
        r"|<tg-reference\s+name=\"[^\"]*\">.*?</tg-reference>"
        r"|<footer>.*?</footer>"
        r"|<blockquote(?:\s+expandable)?[^>]*>.*?</blockquote>"
        r"|<aside>.*?</aside>"
        r"|<tg-map\s+[^/]*/>"
        r"|<tg-button-row[^>]*>.*?</tg-button-row>"
        r"|<tg-button[^>]*>.*?</tg-button>"
        r"|<u>.*?</u>"
        r"|<sup>.*?</sup>"
        r"|<sub>.*?</sub>"
        r"|<mark>.*?</mark>"
        r"|<tg-spoiler>.*?</tg-spoiler>"
        r"|\*\*.*?\*\*"
        r"|__.*?__"
        r"|~~.*?~~"
        r"|==.*?=="
        r"|\|\|.*?\|\|"
        r"|`[^`]*`"
        r"|\*[^*]+\*"
        r"|_[^_]+_"
        r"|\[[^\]]+\]\([^)]+\)"
        r"|<br\s*/?>"
        r"|</br>"
        r")",
        re.IGNORECASE | re.DOTALL
    )

    position = 0
    for match in pattern.finditer(text):
        if match.start() > position:
            insert_preview_text(text[position:match.start()], "normal")
        token = match.group()
        lower = token.lower()

        if lower.startswith('<a name='):
            m = re.search(r'name="([^"]*)"', token, re.IGNORECASE)
            name = m.group(1) if m else "?"
            insert_preview_text(f"⚓[{name}]", "link")
        elif lower.startswith('<a href='):
            m = re.search(r'>([^<]+)</a>', token, re.IGNORECASE)
            label = m.group(1) if m else "link"
            insert_preview_text(label, "link")
        elif lower.startswith('<tg-time'):
            m = re.search(r'>([^<]+)</tg-time>', token, re.IGNORECASE)
            label = m.group(1) if m else "[date/time]"
            insert_preview_text(label, "link")
        elif lower.startswith('<tg-reference'):
            m = re.search(r'>([^<]+)</tg-reference>', token, re.IGNORECASE)
            label = m.group(1) if m else "[ref]"
            insert_preview_text(f"[{label}]", "quote")
        elif lower.startswith('<footer>'):
            insert_preview_text(token[8:-9], "quote")
        elif lower.startswith('<blockquote'):
            clean = re.sub(r'<[^>]+>', '', token)
            insert_preview_text("│ " + clean.strip(), "quote")
        elif lower.startswith('<aside>'):
            clean = re.sub(r'<[^>]+>', '', token)
            insert_preview_text("❝ " + clean.strip() + " ❞", "quote")
        elif lower.startswith('<tg-map'):
            insert_preview_text("[ MAP ]", "media_box")
        elif lower.startswith('<tg-button-row') or lower.startswith('<tg-button'):
            insert_preview_text("[ BUTTON ]", "media_box")
        elif lower.startswith('<u>'):
            insert_preview_text(token[3:-4], "underline")
        elif lower.startswith('<sup>'):
            insert_preview_text(token[5:-6], "sup")
        elif lower.startswith('<sub>'):
            insert_preview_text(token[5:-6], "sub")
        elif lower.startswith('<mark>'):
            insert_preview_text(token[6:-7], "highlight")
        elif lower.startswith('<tg-spoiler>'):
            insert_preview_text("████ " + token[12:-13] + " ████", "spoiler")
        elif token.startswith("**") or token.startswith("__"):
            insert_preview_text(token[2:-2], "bold")
        elif token.startswith("~~"):
            insert_preview_text(token[2:-2], "strike")
        elif token.startswith("=="):
            insert_preview_text(token[2:-2], "highlight")
        elif token.startswith("||"):
            insert_preview_text("████ " + token[2:-2] + " ████", "spoiler")
        elif token.startswith("`"):
            insert_preview_text(token[1:-1], "code")
        elif token.startswith("*") or token.startswith("_"):
            insert_preview_text(token[1:-1], "italic")
        elif token.startswith("["):
            m = re.match(r"\[([^\]]+)\]\(([^)]+)\)", token)
            if m:
                insert_preview_text(m.group(1), "link")
            else:
                insert_preview_text(token, "normal")
        elif lower.startswith("<br") or lower == "</br>":
            preview.insert(tk.END, "\n", "normal")
        else:
            insert_preview_text(token, "normal")

        position = match.end()

    if position < len(text):
        insert_preview_text(text[position:], "normal")

def render_media_preview(line, media_type=None, media_id=None):
    match = re.match(r"!\[(.*?)\]\((.*?)\)", line.strip())
    caption = ""
    if match:
        caption = match.group(1)
        target = match.group(2)
        title_match = re.search(r'\s+"(.*?)"$', target)
        if title_match:
            caption = title_match.group(1)
    if media_type == "photo":
        icon = "[ IMAGE ]"
    elif media_type == "video":
        icon = "[ VIDEO ]"
    elif media_type == "audio":
        icon = "[ AUDIO ]"
    else:
        icon = "[ FILE ]"
    preview.insert(tk.END, "\n")
    preview.insert(tk.END, "┌────────────────────────────────────┐\n", "media_box")
    preview.insert(tk.END, f"│ {icon:<34} │\n", "media_box")
    if media_id and media_id in MEDIA_FILES:
        filename = os.path.basename(MEDIA_FILES[media_id]["path"])
        preview.insert(tk.END, f"│ {filename[:32]:<32} │\n", "media_box")
    if caption:
        preview.insert(tk.END, f"│ {caption[:32]:<32} │\n", "media_caption")
    preview.insert(tk.END, "└────────────────────────────────────┘\n", "media_box")
    preview.insert(tk.END, "\n")

def render_table(lines, start):
    rows = []
    i = start
    while i < len(lines):
        line = lines[i].strip()
        if not line.startswith("|"):
            break
        if re.match(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?$", line):
            i += 1
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        rows.append(cells)
        i += 1
    if not rows:
        return start
    columns = max(len(row) for row in rows)
    for row in rows:
        while len(row) < columns:
            row.append("")
    widths = []
    for col in range(columns):
        width = max(len(row[col]) for row in rows)
        widths.append(min(max(width, 8), 30))
    preview.insert(tk.END, "┌" + "┬".join("─" * (w + 2) for w in widths) + "┐\n", "table")
    for row_index, row in enumerate(rows):
        preview.insert(tk.END, "│", "table")
        for col, cell in enumerate(row):
            cell = cell[:widths[col]]
            preview.insert(tk.END, " " + cell.ljust(widths[col]) + " │", "table")
        preview.insert(tk.END, "\n")
        if row_index == 0 and len(rows) > 1:
            preview.insert(tk.END, "├" + "┼".join("─" * (w + 2) for w in widths) + "┤\n", "table")
    preview.insert(tk.END, "└" + "┴".join("─" * (w + 2) for w in widths) + "┘\n", "table")
    return i

def toggle_details(tag_name):
    current = details_states.get(tag_name, False)
    new_state = not current
    details_states[tag_name] = new_state
    preview.tag_configure(tag_name, elide=not new_state)

def render_details(lines, start):
    global details_counter
    details_counter += 1
    tag_name = f"details_body_{details_counter}"
    summary = "Details"
    summary_index = start + 1
    if summary_index < len(lines):
        match = re.match(r"<summary>(.*?)</summary>", lines[summary_index].strip(), re.IGNORECASE)
        if match:
            summary = match.group(1)
    end = start + 1
    while end < len(lines):
        if lines[end].strip().lower() == "</details>":
            break
        end += 1
    header_tag = f"details_header_{details_counter}"
    preview.insert(tk.END, "▼ ", header_tag)
    render_inline(summary)
    preview.insert(tk.END, "\n", header_tag)
    preview.tag_configure(
        header_tag,
        font=("Segoe UI", 12, "bold"),
        background="#eeeeee",
        spacing1=6,
        spacing3=6
    )
    preview.tag_bind(header_tag, "<Button-1>", lambda event, tag=tag_name: toggle_details(tag))
    preview.tag_bind(header_tag, "<Enter>", lambda event: preview.config(cursor="hand2"))
    preview.tag_bind(header_tag, "<Leave>", lambda event: preview.config(cursor=""))
    body_start_index = preview.index(tk.END)
    body_lines = lines[summary_index + 1:end]
    if body_lines:
        render_preview_lines(body_lines)
    body_end_index = preview.index(tk.END)
    preview.tag_add(tag_name, body_start_index, body_end_index)
    preview.tag_configure(tag_name, background="#f7f7f7", lmargin1=18, lmargin2=18, elide=False)
    details_states[tag_name] = True
    preview.insert(tk.END, "\n")
    return end + 1

def render_media_group(lines, start, closing_tag, title):
    i = start + 1
    preview.insert(tk.END, f"\n{title}\n", "media_group")
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.lower() == closing_tag:
            preview.insert(tk.END, "\n")
            return i + 1
        if stripped.startswith("!["):
            match = re.search(r"tg://(?:photo|video|audio|document)\?id=([A-Za-z0-9_-]+)", stripped)
            if match:
                media_id = match.group(1)
                item = MEDIA_FILES.get(media_id)
                media_type = item["type"] if item else "photo"
                render_media_preview(stripped, media_type, media_id)
        i += 1
    return i

def render_preview_lines(lines):
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = normalize_html_breaks(line).strip()

        if not stripped:
            preview.insert(tk.END, "\n", "normal")
            i += 1
            continue

        if stripped.lower().startswith("<details"):
            i = render_details(lines, i)
            continue
        if stripped.lower() == "<tg-slideshow>":
            i = render_media_group(lines, i, "</tg-slideshow>", "SLIDESHOW")
            continue
        if stripped.lower() == "<tg-collage>":
            i = render_media_group(lines, i, "</tg-collage>", "COLLAGE")
            continue

        if stripped.startswith("!["):
            media_match = re.search(
                r"tg://(photo|video|audio|document)\?id=([A-Za-z0-9_-]+)", stripped
            )
            if media_match:
                media_type = media_match.group(1)
                media_id = media_match.group(2)
                render_media_preview(stripped, media_type, media_id)
                i += 1
                continue
            if re.search(r"!\[[^\]]*\]\(https?://", stripped, re.IGNORECASE):
                render_media_preview(stripped, "photo")
                i += 1
                continue

        heading_match = re.match(r"^(#{1,6})\s+(.*)", line)
        if heading_match:
            level = len(heading_match.group(1))
            tag = f"h{min(level, 6)}"
            content = heading_match.group(2)
            preview.insert(tk.END, "", tag)
            start_idx = preview.index(tk.END)
            render_inline(content)
            end_idx = preview.index(tk.END)
            preview.tag_add(tag, start_idx, end_idx)
            preview.insert(tk.END, "\n")
            i += 1
            continue

        if line.startswith(">"):
            quote_text = line[1:].lstrip()
            preview.insert(tk.END, "│ ", "quote")
            render_inline(quote_text)
            preview.insert(tk.END, "\n")
            i += 1
            continue

        if re.match(r"^[-*+]\s+\[[ xX]\]\s+", line):
            match = re.match(r"^[-*+]\s+\[([ xX])\]\s+(.*)", line)
            checked = match.group(1).lower() == "x"
            mark = "☑ " if checked else "☐ "
            preview.insert(tk.END, mark, "normal")
            render_inline(match.group(2))
            preview.insert(tk.END, "\n")
            i += 1
            continue

        if re.match(r"^[-*+]\s+", line):
            match = re.match(r"^[-*+]\s+(.*)", line)
            preview.insert(tk.END, "• ", "normal")
            render_inline(match.group(1))
            preview.insert(tk.END, "\n")
            i += 1
            continue

        if re.match(r"^\d+\.\s+", line):
            match = re.match(r"^(\d+)\.\s+(.*)", line)
            preview.insert(tk.END, match.group(1) + ". ", "normal")
            render_inline(match.group(2))
            preview.insert(tk.END, "\n")
            i += 1
            continue

        if (
            stripped.startswith("|")
            and i + 1 < len(lines)
            and re.match(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?$", lines[i + 1].strip())
        ):
            i = render_table(lines, i)
            continue

        if re.match(r"^\s*---+\s*$", stripped):
            preview.insert(tk.END, "────────────────────────────────\n", "separator")
            i += 1
            continue

        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            preview.insert(tk.END, f"[code block{(' – ' + lang) if lang else ''}]\n", "code")
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                preview.insert(tk.END, lines[i] + "\n", "code")
                i += 1
            if i < len(lines):
                i += 1
            continue

        render_inline(line)
        preview.insert(tk.END, "\n")
        i += 1

def render_preview(markdown):
    global details_counter
    details_counter = 0
    details_states.clear()
    normalized = normalize_html_breaks(markdown)
    lines = normalized.splitlines()
    render_preview_lines(lines)

def update_preview():
    markdown = editor.get("1.0", tk.END).strip()
    preview.config(state="normal")
    preview.delete("1.0", tk.END)
    if markdown:
        render_preview(markdown)
    # Always re-apply direction after rendering
    apply_direction_tags()
    preview.config(state="disabled")

def on_key_release(event=None):
    """Update live preview and keep direction tag alive on every keystroke."""
    update_preview()
    apply_direction_tags()

# TEST / CLEAR
# -------------
def test_all_syntax():
    test_text = (
        "# Telegram Rich Markdown Test\n\n"
        "## Headings\n\n"
        "### Heading 3\n\n"
        "#### Heading 4\n\n"
        "##### Heading 5\n\n"
        "###### Heading 6\n\n"
        "Normal paragraph with **bold**, *italic*, __bold__, ~~strike~~, "
        "==highlight==, ||spoiler||, `inline code`, <u>underline</u>, "
        "<sup>superscript</sup> and <sub>subscript</sub>.\n\n"
        "[Telegram](https://telegram.org)\n\n"
        "> This is a quotation with **bold** and *italic* text.\n\n"
        "- First bullet\n"
        "- Second bullet\n"
        "- Third bullet\n\n"
        "1. First item\n"
        "2. Second item\n"
        "3. Third item\n\n"
        "- [ ] Task one\n"
        "- [x] Task two (done)\n\n"
        "| Feature | Status | Value |\n"
        "|:---|:---:|---:|\n"
        "| Rich Markdown | **OK** | 100% |\n"
        "| Tables | ==OK== | Supported |\n\n"
        "---\n\n"
        "<details>\n"
        "<summary>Technical details with **bold text**</summary>\n\n"
        "### Inside Details\n\n"
        "This content is actually **inside the expandable block**.\n\n"
        "- Nested list\n"
        "- Another item\n"
        "- `Code`\n\n"
        "> Nested quotation.\n\n"
        "</details>\n\n"
        "```python\n"
        "print(\"Hello from a code block\")\n"
        "```\n\n"
        "External media example:\n\n"
        "![](https://telegram.org/example/photo.jpg \"Example image caption\")\n"
    )
    editor.delete("1.0", tk.END)
    editor.insert("1.0", test_text)
    update_preview()

def clear_editor():
    editor.delete("1.0", tk.END)
    MEDIA_FILES.clear()
    update_preview()
    status.config(text="")

# GUI
# -----
window = tk.Tk()
window.title("Telegram Rich Markdown Publisher by Moradi IT (git.amoradi.ir)")
window.geometry("1100x680")
window.minsize(900, 600)

toolbar = tk.Frame(window, relief="groove", borderwidth=1)
toolbar.pack(fill="x", padx=10, pady=(6, 4))

def create_menu_button(parent, text, items):
    mb = tk.Menubutton(
        parent,
        text=text + " ▼",
        font=("Segoe UI", 8, "bold"),
        relief="raised",
        padx=5,
        pady=2
    )
    menu = tk.Menu(mb, tearoff=0, font=("Segoe UI", 9))
    for label, command in items:
        menu.add_command(label=label, command=command)
    mb.config(menu=menu)
    mb.pack(side="left", padx=1, pady=1)
    return mb

# Headings
create_menu_button(toolbar, "Headings", [
    ("Heading 1", lambda: heading(1)),
    ("Heading 2", lambda: heading(2)),
    ("Heading 3", lambda: heading(3)),
    ("Heading 4", lambda: heading(4)),
    ("Heading 5", lambda: heading(5)),
    ("Heading 6", lambda: heading(6)),
])

# Formatting
create_menu_button(toolbar, "Formatting", [
    ("Bold", bold),
    ("Italic", italic),
    ("Underline", underline),
    ("Strikethrough", strike),
    ("Highlight / Marked", highlight),
    ("Spoiler", spoiler),
    ("Superscript", superscript),
    ("Subscript", subscript),
    ("Footer", insert_footer),
    ("Blockquote (+ author)", insert_blockquote),
    ("Expandable Blockquote", insert_expandable_blockquote),
    ("Pull Quote", insert_pullquote),
])

# Lists
create_menu_button(toolbar, "Lists", [
    ("Bullet list", bullet_list),
    ("Numbered list", numbered_list),
    ("Task list", task_list),
])

# Code
create_menu_button(toolbar, "Code", [
    ("Inline code", code),
    ("Code block", code_block),
])

# Navigate
create_menu_button(toolbar, "Navigate", [
    ("Insert Anchor (name=…)", insert_anchor),
    ("Link to Anchor", insert_link_to_anchor),
    ("Link to Top of Message", insert_link_to_top),
    ("Create Footnote / Reference Definition", insert_reference),
    ("Create Link to a Footnote", insert_reference_link),
])

# Insert
create_menu_button(toolbar, "Insert", [
    ("Link", insert_link),
    ("Email link", insert_email),
    ("Phone link", insert_phone),
    ("User mention (by ID)", insert_user_mention),
    ("Date / Time", insert_datetime),
    ("Map", insert_map),
    ("Table", insert_table),
    ("Details / Collapsible", insert_details),
    ("Separator (---)", insert_separator),
    ("Math (inline $...$)", insert_math_inline),
    ("Math (block $$...$$)", insert_math_block),
    ("Button Row (Bot API 10.3)", insert_button_row),
])

# Media
create_menu_button(toolbar, "Media", [
    ("Image", insert_image),
    ("Slideshow", insert_slideshow),
    ("Collage", insert_collage),
    ("File / Document", insert_file),
])

# Empty line
tk.Button(
    toolbar,
    text="Empty Line",
    command=insert_empty_line,
    font=("Segoe UI", 8, "bold"),
    relief="raised",
    padx=5,
    pady=2
).pack(side="left", padx=1, pady=1)

# RTL / LTR Toggle button
rtl_btn = tk.Button(
    toolbar,
    text="RTL →",
    command=toggle_direction,
    font=("Segoe UI", 8, "bold"),
    relief="raised",
    padx=5,
    pady=2,
    bg="#e3f2fd"
)
rtl_btn.pack(side="left", padx=4, pady=1)

# Test Syntax
tk.Button(
    toolbar,
    text="Test Syntax",
    command=test_all_syntax,
    font=("Segoe UI", 8, "bold"),
    relief="raised",
    padx=5,
    pady=2
).pack(side="left", padx=1, pady=1)

# MAIN AREA
# ----------
main = tk.Frame(window)
main.pack(fill="both", expand=True, padx=6, pady=4)

# EDITOR
left = tk.Frame(main)
left.pack(side="left", fill="both", expand=True, padx=(0, 4))
tk.Label(left, text="Markdown", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 2))

# Font for Persian
editor_font = ("Tahoma", 12)

editor = tk.Text(
    left,
    wrap="word",
    font=editor_font,
    padx=6,
    pady=6,
    undo=True
)
editor.pack(fill="both", expand=True)

# PREVIEW
right = tk.Frame(main)
right.pack(side="right", fill="both", expand=True, padx=(4, 0))
tk.Label(right, text="Preview", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 2))

preview = tk.Text(
    right,
    wrap="word",
    font=("Tahoma", 12),
    padx=8,
    pady=8,
    bg="#ffffff",
    relief="solid",
    borderwidth=1
)
preview.pack(fill="both", expand=True)

# PREVIEW STYLES
preview.tag_configure("h1", font=("Tahoma", 20, "bold"), spacing3=8)
preview.tag_configure("h2", font=("Tahoma", 17, "bold"), spacing3=6)
preview.tag_configure("h3", font=("Tahoma", 15, "bold"), spacing3=5)
preview.tag_configure("h4", font=("Tahoma", 13, "bold"))
preview.tag_configure("h5", font=("Tahoma", 12, "bold"))
preview.tag_configure("h6", font=("Tahoma", 11, "bold"))
preview.tag_configure("normal", font=("Tahoma", 12))
preview.tag_configure("bold", font=("Tahoma", 12, "bold"))
preview.tag_configure("italic", font=("Tahoma", 12, "italic"))
preview.tag_configure("underline", underline=True)
preview.tag_configure("strike", overstrike=True)
preview.tag_configure("highlight", background="#fff176")
preview.tag_configure("spoiler", foreground="#ffffff", background="#555555")
preview.tag_configure("code", font=("Consolas", 10), background="#eeeeee")
preview.tag_configure("quote", foreground="#555555", lmargin1=12, lmargin2=12)
preview.tag_configure("table", font=("Consolas", 9))
preview.tag_configure("link", foreground="#1565c0", underline=True)
preview.tag_configure("sup", font=("Tahoma", 8), offset=4)
preview.tag_configure("sub", font=("Tahoma", 8), offset=-2)
preview.tag_configure("separator", foreground="#888888")
preview.tag_configure("media_box", font=("Consolas", 9, "bold"), background="#eeeeee")
preview.tag_configure("media_caption", font=("Tahoma", 9, "italic"), foreground="#555555")
preview.tag_configure("media_group", font=("Tahoma", 11, "bold"))
preview.config(state="disabled")

# BOTTOM
#--------
bottom = tk.Frame(window)
bottom.pack(fill="x", padx=6, pady=(0, 4))
tk.Button(
    bottom,
    text="Publish to Telegram",
    command=publish,
    font=("Segoe UI", 8, "bold"),
    padx=6,
    pady=2
).pack(side="left", padx=(0, 4))
tk.Button(
    bottom,
    text="Clear",
    command=clear_editor,
    font=("Segoe UI", 8),
    padx=6,
    pady=2
).pack(side="left")
status = tk.Label(bottom, text="", font=("Segoe UI", 8))
status.pack(side="right")

editor.bind("<KeyRelease>", on_key_release)

# Initialise direction tags
apply_direction_tags()
update_preview()
window.mainloop()