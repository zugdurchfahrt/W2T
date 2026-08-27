# w2t (WhatsApp to Telegram chat migration tool)

Utility migrates your exported WhatsApp chats (including all media files) directly into Telegram using the official MTProto API.

Unlike bots or message forwarders, this tool utilizes Telegram's native `InitHistoryImportRequest` API. This ensures that your chat history is imported with the **original timestamps**, making it appear as a natural Telegram chat history.

## Features
- Supports both **Private Chat** and **Group Chat** imports.
- Validates that the export file type matches your selected import mode before uploading.
- Preserves original message timestamps and chronology.
- Uploads and links all media files — images, videos, audio, documents (PDF, Word, Excel, PowerPoint, etc.).
- Shows file sizes during upload for progress visibility.
- Requires explicit user confirmation before starting the import to double-check the destination folder and prevent accidental uploads.
- Automatically migrates Telegram Basic Groups to Supergroups when needed.
- Gracefully handles connection errors, Anti-Flood restrictions, and network interruptions during media upload.
- Properly closes the Telegram session on exit.

## Requirements
- Python 3.8+
- [Telethon](https://github.com/LonamiWebs/Telethon) (installed automatically via `requirements.txt`)

## Download (No Python Required)
You don't need to install Python or use the command line to use this tool!

1. Go to the [Releases](https://github.com/zugdurchfahrt/w2t/releases) page.
2. Download **`w2t.exe`** from the **Assets** section of the latest release.
3. Double-click the file to run it.

> **Note on Windows SmartScreen:** Because this open-source tool does not have a paid digital signature certificate, Windows Defender SmartScreen might show a blue warning saying "Windows protected your PC" on the first run. This is a standard warning for indie applications. Click **More info** -> **Run anyway**.

## Setup (For Developers)
1. Clone this repository:
   ```bash
   git clone https://github.com/your-username/w2t.git
   cd w2t
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Obtain your Telegram **API ID** and **API Hash** from [my.telegram.org](https://my.telegram.org/auth).

## Usage
1. Export your WhatsApp chat (with media, no size limits) to a `.zip` file on your phone and transfer it to your computer.
2. Unzip the archive into a folder.
3. **If importing into a group**: create a fresh Telegram group and **add all members before importing**. Telegram restricts visibility of imported messages to participants who were present at the time of import.
4. Run the executable (`w2t.exe`) or the Python script:
   ```bash
   python main.py
   ```
   *(Advanced: You can also pass arguments via CLI: `python main.py --api-id YOUR_API_ID --api-hash YOUR_API_HASH --export-dir /path`)*
5. Follow the interactive prompts:
   - **Step 1**: Select import type (Private Chat or Group Chat).
   - Enter the path to the unzipped WhatsApp export directory.
   - **Step 2**: Select the target Telegram dialog from the full list of your chats.
   - Confirm the import when prompted.
6. Wait for the upload to complete.

## How It Works
1. The script reads the WhatsApp `.txt` export file and sends the first 2000 characters to Telegram's `CheckHistoryImportRequest` to determine whether it is a private or group chat.
2. It validates that the detected chat type matches your selection. If there is a mismatch, the script stops with a clear error message.
3. After you select the target dialog and confirm, the script uploads the text file, then uploads each media file referenced in the chat log.
4. Finally, it calls `StartHistoryImportRequest` to finalize the import on Telegram's side.

## Notes on Privacy
When importing into a group, Telegram hides imported messages from participants who were added **after** the import started. Make sure all participants are in the group before you run the script.

## Troubleshooting
| Problem | Solution |
|---|---|
| `ConnectionError` on startup | You may be in a region with restricted Telegram access. Turn on a VPN. |
| `IncompleteReadError (0 bytes read)` | Your session was revoked or Telegram's Anti-Flood triggered. Change your VPN server and wait before retrying. |
| `IMPORT_PEER_TYPE_INVALID` | Chat type mismatch. Make sure you select the correct import type (Private vs. Group). |
| Media files not found | Ensure the media files are in the same folder as the `.txt` file and their names match exactly. |
| Console appears frozen when entering password | This is expected. When Telegram prompts for your 2FA password, the console deliberately hides your input (no characters are displayed while you type). Just type your password and press Enter — it is being recorded. |
