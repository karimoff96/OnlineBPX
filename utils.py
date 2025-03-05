import os
import time
import tempfile
import shutil
import tarfile
import requests
from datetime import datetime

from config import (
    LAST_CHECK_FILE, LAST_CALL_UUID_FILE, logger, 
    CALL_ICONS, HANGUP_CAUSES
)


def get_last_check_time():
    """
    Get the last time calls were checked
    
    Returns:
        int: Unix timestamp
    """
    try:
        if os.path.exists(LAST_CHECK_FILE):
            with open(LAST_CHECK_FILE, 'r') as f:
                timestamp = int(f.read().strip())
                logger.debug(f"Read last check time: {timestamp} ({datetime.fromtimestamp(timestamp)})")
                return timestamp
        else:
            # Default to 24 hours ago if file doesn't exist
            current_time = int(time.time())
            one_day_ago = current_time - (24 * 60 * 60)
            logger.debug(f"No last check time found, using 24 hours ago: {one_day_ago}")
            save_last_check_time(one_day_ago)
            return one_day_ago
    except Exception as e:
        logger.error(f"Error reading last check time: {e}", exc_info=True)
        current_time = int(time.time())
        save_last_check_time(current_time)
        return current_time


def save_last_check_time(timestamp):
    """
    Save the last time calls were checked
    
    Args:
        timestamp (int): Unix timestamp
    """
    try:
        with open(LAST_CHECK_FILE, 'w') as f:
            f.write(str(timestamp))
        logger.debug(f"Saved last check time: {timestamp} ({datetime.fromtimestamp(timestamp)})")
    except Exception as e:
        logger.error(f"Error saving last check time: {e}", exc_info=True)


def get_last_call_uuid():
    """
    Get the UUID of the last processed call
    
    Returns:
        str: UUID or empty string if not found
    """
    try:
        if os.path.exists(LAST_CALL_UUID_FILE):
            with open(LAST_CALL_UUID_FILE, 'r') as f:
                uuid = f.read().strip()
                logger.debug(f"Read last call UUID: {uuid}")
                return uuid
        else:
            logger.debug("No last call UUID found")
            return ""
    except Exception as e:
        logger.error(f"Error reading last call UUID: {e}", exc_info=True)
        return ""


def save_last_call_uuid(uuid):
    """
    Save the UUID of the last processed call
    
    Args:
        uuid (str): Call UUID
    """
    try:
        with open(LAST_CALL_UUID_FILE, 'w') as f:
            f.write(uuid)
        logger.debug(f"Saved last call UUID: {uuid}")
    except Exception as e:
        logger.error(f"Error saving last call UUID: {e}", exc_info=True)


def format_duration(seconds):
    """
    Format duration in seconds to a more readable format
    
    Args:
        seconds (int): Duration in seconds
        
    Returns:
        str: Formatted duration
    """
    if seconds < 60:
        return f"{seconds} sec"
    
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    
    if minutes < 60:
        return f"{minutes} min {remaining_seconds} sec"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    return f"{hours} hr {remaining_minutes} min {remaining_seconds} sec"


def format_call_details(call):
    """
    Format call details for Telegram message
    
    Args:
        call (dict): Call details
        
    Returns:
        str: Formatted message
    """
    # Get basic call details
    call_time = datetime.fromtimestamp(call.get('start_stamp', 0))
    formatted_time = call_time.strftime('%Y-%m-%d %H:%M:%S')
    
    # Get call direction icon
    account = call.get('accountcode', 'unknown')
    direction_icon = CALL_ICONS.get(account, CALL_ICONS['unknown'])
    
    # Format caller and destination
    caller = str(call.get('caller_id_number', 'Unknown')).replace('_', '\\_').replace('*', '\\*')
    destination = str(call.get('destination_number', 'Unknown')).replace('_', '\\_').replace('*', '\\*')
    
    # Format durations
    duration = call.get('duration', 0)
    formatted_duration = format_duration(duration)
    
    user_talk_time = call.get('user_talk_time', 0)
    formatted_talk_time = format_duration(user_talk_time)
    
    # Get status and other details
    hangup_cause = call.get('hangup_cause', 'Unknown')
    friendly_hangup = HANGUP_CAUSES.get(hangup_cause, hangup_cause.replace('_', ' ').title())
    
    gateway = str(call.get('gateway', 'Unknown')).replace('_', '\\_').replace('*', '\\*')
    contacted = "✅ Yes" if call.get('contacted', False) else "❌ No"
    
    # Build the message with improved styling
    message = (
        f"{direction_icon} <b>Call Record</b>\n\n"
        f"⏰ <b>Time:</b> {formatted_time}\n"
        f"📱 <b>From:</b> {caller}\n"
        f"📲 <b>To:</b> {destination}\n"
        f"🔀 <b>Gateway:</b> {gateway}\n"
        f"⏱ <b>Duration:</b> {formatted_duration}\n"
        f"💬 <b>Talk Time:</b> {formatted_talk_time}\n"
        f"💼 <b>Type:</b> {account.capitalize()}\n"
        f"📞 <b>Contacted:</b> {contacted}\n"
        f"📝 <b>Result:</b> {friendly_hangup}"
    )
    return message


def download_and_extract_audio_archive(url):
    """
    Download and extract audio files from a tar archive
    
    Args:
        url (str): Download URL
        
    Returns:
        tuple: (temp_dir, audio_files_dict) or (None, {})
    """
    temp_dir = None
    audio_files = {}
    
    try:
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()
        logger.debug(f"Created temp directory: {temp_dir}")
        tar_path = os.path.join(temp_dir, "calls.tar")
        
        # Download the tar file
        logger.info(f"Downloading audio archive from: {url}")
        response = requests.get(url, stream=True, timeout=180)
        response.raise_for_status()
        
        file_size = 0
        with open(tar_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                file_size += len(chunk)
        
        logger.debug(f"Download complete, file size: {file_size} bytes")
        
        # Check if file exists and has content
        if not os.path.exists(tar_path) or os.path.getsize(tar_path) == 0:
            logger.error(f"Downloaded file is empty or doesn't exist at {tar_path}")
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            return None, {}
        
        logger.info(f"Extracting archive: {tar_path}")
        
        # Extract the tar file
        try:
            with tarfile.open(tar_path) as tar:
                # List files in the archive before extraction
                file_list = tar.getnames()
                logger.debug(f"Files in archive: {len(file_list)}")
                
                # Extract the tar file
                tar.extractall(path=temp_dir)
                logger.info(f"Archive extracted to {temp_dir}")
                
                # Log the structure of the extracted directory
                for root, dirs, files in os.walk(temp_dir):
                    logger.debug(f"Directory: {root}")
                    for file in files:
                        file_path = os.path.join(root, file)
                        logger.debug(f"File: {file_path}, Size: {os.path.getsize(file_path)} bytes")
        except Exception as e:
            logger.error(f"Error extracting archive: {e}", exc_info=True)
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            return None, {}
        
        # Find all audio files
        for root, _, files in os.walk(temp_dir):
            for file in files:
                if file.endswith(('.wav', '.mp3')):
                    file_path = os.path.join(root, file)
                    if os.path.isfile(file_path) and os.access(file_path, os.R_OK):
                        audio_files[file] = file_path
                        logger.debug(f"Found audio file: {file}, size: {os.path.getsize(file_path)} bytes")
        
        logger.info(f"Found {len(audio_files)} audio files in archive")
        return temp_dir, audio_files
        
    except Exception as e:
        logger.error(f"Error downloading/extracting audio archive: {e}", exc_info=True)
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return None, {}