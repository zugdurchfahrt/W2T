# w2t (WhatsApp to Telegram)

A Python CLI utility that seamlessly migrates your exported WhatsApp chats (including media) directly into Telegram using the official MTProto API.

Unlike bots or message forwarders, this tool utilizes Telegram's native InitHistoryImportRequest API. This ensures that your chat history is imported with the **original timestamps**, making it appear as a natural Telegram chat history.

## Features
- Preserves original message timestamps.
- Uploads and links all media files (images, videos, audio, documents).
- Automatically migrates Telegram Basic Groups to Supergroups to support history import.
- Handles interrupted connections automatically.

## Requirements
- Python 3.8+
- 	elethon

## Setup
1. Clone this repository:
   `ash
   git clone https://github.com/your-username/w2t.git
   cd w2t
   `
2. Install dependencies:
   `ash
   pip install -r requirements.txt
   `
3. Obtain your Telegram **API ID** and **API Hash** from [my.telegram.org](https://my.telegram.org/auth).

## Usage
1. Export your WhatsApp chat (without media size limits) to a .zip file on your phone and transfer it to your computer.
2. Unzip the archive into a folder.
3. If importing into a group, create a fresh Telegram group and **add all members before importing** (this is important for Telegram privacy rules so they can see the imported history).
4. Run the script:
   `ash
   python w2t.py --api-id YOUR_API_ID --api-hash YOUR_API_HASH --export-dir /path/to/unzipped_export
   `
5. The script will ask for your phone number and code to authenticate.
6. Select the target chat from your recent dialogs list.
7. Wait for the upload to complete!

## Notes on Privacy
When importing into a group, Telegram may hide imported messages from participants who were added *after* the import started. Make sure all participants are in the group before you start the script.
