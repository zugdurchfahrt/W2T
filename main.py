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
    export_dir = args.export_dir or input("Enter path to unzipped WhatsApp export directory: ")

    if not os.path.isdir(export_dir):
        print(f"Error: Directory '{export_dir}' not found.")
        return

    # Find the _chat.txt or equivalent text file
    txt_files = [f for f in os.listdir(export_dir) if f.endswith('.txt')]
    if not txt_files:
        print("Error: No .txt file found in the export directory.")
        return
    chat_file = os.path.join(export_dir, txt_files[0])
    print(f"Found chat file: {chat_file}")

    client = TelegramClient('whatsapp_import_session', api_id, api_hash)
    try:
        await client.start()
    except ConnectionError:
        print("\n[!] Connection to Telegram failed.")
        print("[!] If you are in a region with restricted access to Telegram (e.g., Russia), the initial connection might be blocked by your ISP.")
        print("[!] Please turn on a VPN and try again.")
        return

    # Get target chat
    dialogs = await client.get_dialogs()
    
    # Filter out deactivated basic groups (which appear as duplicates when migrated to supergroups)
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
    
    # Automatically migrate basic groups to supergroups for import
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
            print(f"Failed to migrate group to supergroup: {e}. Please manually make the group history visible in Telegram settings.")
            return

    is_target_group = isinstance(peer, (types.InputPeerChat, types.InputPeerChannel))
    with open(chat_file, 'r', encoding='utf-8', errors='ignore') as f:
        original_content = f.read()
    
    head_str = original_content[:200]
    try:
        check_res = await client(functions.messages.CheckHistoryImportRequest(import_head=head_str))
        print("Initial parse result:", check_res)
    except RPCError as e:
        print(f"CheckHistoryImport failed: {e}")
        return
        
    upload_content_bytes = None
    
    if is_target_group and not getattr(check_res, 'group', False):
        print("\n[!] Mismatch: Trying to import a Private Chat export into a Telegram Group.")
        print("[!] Injecting fake group creation header to trick Telegram into accepting it...")
        fake_header = '01/01/2000, 00:00 - You created group "Imported"\n'
        modified_content = fake_header + original_content
        head_str = modified_content[:200]
        # Re-check to ensure it's valid
        check_res = await client(functions.messages.CheckHistoryImportRequest(import_head=head_str))
        print("Modified parse result:", check_res)
        upload_content_bytes = modified_content.encode('utf-8')
    elif not is_target_group and getattr(check_res, 'group', False):
        print("\n[!] Mismatch: Trying to import a Group Chat export into a Private Chat.")
        print("[!] Note: This is usually rejected by Telegram, but we will attempt it.")
        upload_content_bytes = original_content.encode('utf-8')
    else:
        upload_content_bytes = original_content.encode('utf-8')

    try:
        check_peer = await client(functions.messages.CheckHistoryImportPeerRequest(peer=peer))
        print("Peer check result:", check_peer)
    except RPCError as e:
        print(f"Target chat does not allow import or error occurred: {e}")
        return

    # Parse media files from the chat log
    media_pattern = re.compile(r'([A-Za-z0-9\-\_]+\.[a-zA-Z0-9]+)\s+\(file attached\)')
    media_files = list(set(media_pattern.findall(original_content)))
    print(f"\nFound {len(media_files)} attached media references in the log.")

    valid_media_files = [f for f in media_files if os.path.exists(os.path.join(export_dir, f))]
    print(f"Found {len(valid_media_files)} matching files in the directory.")

    print("\nUploading chat text file...")
    temp_chat_file = os.path.join(export_dir, '_telegram_import_temp.txt')
    with open(temp_chat_file, 'wb') as f:
        f.write(upload_content_bytes)
        
    uploaded_txt = await client.upload_file(temp_chat_file)
    os.remove(temp_chat_file)

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

    # Upload media files
    for idx, filename in enumerate(valid_media_files):
        filepath = os.path.join(export_dir, filename)
        print(f"Uploading media {idx+1}/{len(valid_media_files)}: {filename}...")
        uploaded_media = await client.upload_file(filepath)
        
        # Determine mime type roughly
        ext = filename.split('.')[-1].lower()
        mime_type = 'application/octet-stream'
        if ext in ['jpg', 'jpeg', 'png', 'webp']:
            mime_type = f'image/{ext}'
        elif ext in ['mp4', 'mov', 'avi']:
            mime_type = f'video/{ext}'
        elif ext in ['mp3', 'ogg', 'opus', 'wav']:
            mime_type = f'audio/{ext}'

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
        print("You can check the Telegram app to see the progress.")
    except RPCError as e:
        print(f"Failed to start history import: {e}")

if __name__ == '__main__':
    asyncio.run(main())
