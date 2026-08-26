import os
import re
import argparse
import asyncio
from telethon import TelegramClient, functions, types
from telethon.errors import RPCError

async def main():
    parser = argparse.ArgumentParser(description="Import WhatsApp chat to Telegram")
    parser.add_argument("--api-id", type=int, help="Telegram API ID")
    parser.add_argument("--api-hash", type=str, help="Telegram API Hash")
    parser.add_argument("--export-dir", type=str, help="Path to unzipped WhatsApp export directory")
    args = parser.parse_args()

    api_id = args.api_id or int(input("Enter Telegram API ID: "))
    api_hash = args.api_hash or input("Enter Telegram API Hash: ")

    print("\n--- STEP 1: IMPORT CONFIGURATION ---")
    print("Select the type of import you want to perform:")
    print("1. Private Chat (Import into a 1-on-1 Telegram dialog)")
    print("2. Group Chat (Import into a Telegram Group)")
    import_type = input("Enter 1 or 2: ").strip()

    export_dir = args.export_dir or input("\nEnter path to unzipped WhatsApp export directory: ")

    if not os.path.isdir(export_dir):
        print(f"Error: Directory '{export_dir}' not found.")
        return

    # Find the _chat.txt or equivalent text file
    txt_files = [f for f in os.listdir(export_dir) if f.endswith('.txt') and not f.startswith('_telegram_import_temp')]
    if not txt_files:
        print("Error: No .txt file found in the export directory.")
        return
    chat_file = os.path.join(export_dir, txt_files[0])
    print(f"Found chat file: {chat_file}")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    session_path = os.path.join(script_dir, 'whatsapp_import_session')
    client = TelegramClient(session_path, api_id, api_hash)
    try:
        await client.start()
    except asyncio.exceptions.IncompleteReadError:
        print("\n[!] ERROR: Telegram server closed the connection abruptly (0 bytes read).")
        print("[!] Your session was revoked or Telegram's Anti-Flood system blocked your IP.")
        print("[!] Please try changing your VPN server and wait some time before trying again.")
        return
    except ConnectionError:
        print("\n[!] Connection to Telegram failed.")
        print("[!] If you are in a region with restricted access to Telegram, the connection might be blocked by your ISP.")
        print("[!] Please turn on a VPN and try again.")
        return

    with open(chat_file, 'r', encoding='utf-8', errors='ignore') as f:
        original_content = f.read()
    
    head_str = original_content[:2000]
    try:
        check_res = await client(functions.messages.CheckHistoryImportRequest(import_head=head_str))
    except RPCError as e:
        print(f"CheckHistoryImport failed: {e}")
        return
    
    if import_type == '2':
        if not getattr(check_res, 'group', False):
            print("\n[!] ERROR: You selected Group Chat import, but the provided file is a Private Chat export.")
            print("[!] Telegram's API strictly forbids importing a Private Chat into a Group.")
            print("[!] Please restart the script and select '1. Private Chat', then select the respective user dialog.")
            return
    elif import_type == '1':
        if getattr(check_res, 'group', False):
            print("\n[!] ERROR: You selected Private Chat import, but the provided file is a Group Chat export.")
            print("[!] Telegram's API strictly forbids importing a Group Chat into a Private dialog.")
            print("[!] Please restart the script and select '2. Group Chat'.")
            return

    print("\n--- STEP 2: TARGET SELECTION ---")
    dialogs = await client.get_dialogs()
    
    active_dialogs = []
    for d in dialogs:
        if getattr(d.entity, 'deactivated', False) or getattr(d.entity, 'migrated_to', None) is not None:
            continue
        active_dialogs.append(d)

    print("\nRecent dialogs:")
    for i, dialog in enumerate(active_dialogs[:15]):
        print(f"{i}: {dialog.name} (ID: {dialog.id})")
    print("...")
    
    choice = input("\nSelect target dialog index (or type 'me' for Saved Messages): ")
    if choice.lower() == 'me':
        peer = await client.get_input_entity('me')
    else:
        try:
            choice_idx = int(choice)
            if choice_idx < len(active_dialogs):
                peer = active_dialogs[choice_idx].input_entity
            else:
                peer = await client.get_input_entity(int(choice))
        except (ValueError, IndexError):
            print("Invalid selection.")
            return

    print("\nChecking history import availability...")
    
    if isinstance(peer, types.InputPeerChat):
        print("Basic group detected. Migrating to supergroup to support history import...")
        try:
            updates = await client(functions.messages.MigrateChatRequest(chat_id=peer.chat_id))
            for chat in updates.chats:
                if getattr(chat, 'megagroup', False) or isinstance(chat, types.Channel):
                    peer = await client.get_input_entity(chat)
                    print(f"Successfully migrated! New Supergroup ID: {chat.id}")
                    break
        except RPCError as e:
            print(f"Failed to migrate group to supergroup: {e}")
            return

    try:
        check_peer = await client(functions.messages.CheckHistoryImportPeerRequest(peer=peer))
        print("\nPeer check result:", check_peer)
    except RPCError as e:
        print(f"\n[!] Target chat does not allow this type of import (or error occurred): {e}")
        print("[!] Note: You cannot import a Private Chat into a Telegram Group.")
        return

    media_pattern = re.compile(r'([A-Za-z0-9\-\_]+\.[a-zA-Z0-9]+)\s+\(file attached\)')
    media_files = list(set(media_pattern.findall(original_content)))
    print(f"\nFound {len(media_files)} attached media references in the log.")

    valid_media_files = [f for f in media_files if os.path.exists(os.path.join(export_dir, f))]
    print(f"Found {len(valid_media_files)} matching files in the directory.")

    print("\nUploading chat text file...")
    uploaded_txt = await client.upload_file(chat_file)

    print("Initializing history import...")
    try:
        init_req = await client(functions.messages.InitHistoryImportRequest(
            peer=peer,
            file=uploaded_txt,
            media_count=len(valid_media_files)
        ))
        import_id = init_req.id
        print(f"Import ID: {import_id}")
    except RPCError as e:
        print(f"Failed to initialize import: {e}")
        return

    for idx, filename in enumerate(valid_media_files):
        filepath = os.path.join(export_dir, filename)
        print(f"Uploading media {idx+1}/{len(valid_media_files)}: {filename}...")
        uploaded_media = await client.upload_file(filepath)
        
        # Determine mime type robustly
        import mimetypes
        mime_type, _ = mimetypes.guess_type(filename)
        if not mime_type:
            # Fallback for some common WhatsApp extensions if mimetypes fails
            ext = filename.split('.')[-1].lower()
            if ext == 'opus':
                mime_type = 'audio/ogg'
            elif ext == 'webp':
                mime_type = 'image/webp'
            else:
                mime_type = 'application/octet-stream'

        media_obj = types.InputMediaUploadedDocument(
            file=uploaded_media,
            mime_type=mime_type,
            attributes=[types.DocumentAttributeFilename(file_name=filename)]
        )
        
        try:
            await client(functions.messages.UploadImportedMediaRequest(
                peer=peer,
                import_id=import_id,
                file_name=filename,
                media=media_obj
            ))
        except RPCError as e:
            print(f"Error uploading {filename}: {e}")

    print("\nStarting history import process...")
    try:
        await client(functions.messages.StartHistoryImportRequest(
            peer=peer,
            import_id=import_id
        ))
        print("Import started successfully! It may take some time for Telegram to process the history.")
    except RPCError as e:
        print(f"Failed to start history import: {e}")

if __name__ == '__main__':
    asyncio.run(main())
