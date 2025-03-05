import os
import time
import tempfile
import shutil
from datetime import datetime

import telebot
from telebot import types

from config import (
    TELEGRAM_CHANNEL_ID, logger
)
from api import OnlinePBXAPI
from utils import (
    get_last_check_time, save_last_check_time,
    get_last_call_uuid, save_last_call_uuid,
    format_call_details, download_and_extract_audio_archive
)


def process_new_calls(bot):
    """
    Check for new calls and send them to Telegram
    
    Args:
        bot (telebot.TeleBot): Telegram bot instance
        
    Returns:
        int: Number of processed calls
    """
    api = OnlinePBXAPI()
    if not api.authenticate():
        logger.error("Failed to authenticate with OnlinePBX API")
        return 0
    
    last_check = get_last_check_time()
    current_time = int(time.time())
    last_uuid = get_last_call_uuid()
    
    logger.info(f"Checking for new calls from {datetime.fromtimestamp(last_check)} to {datetime.fromtimestamp(current_time)}")
    
    # Get call details for the period since last check
    call_details = api.get_call_details(last_check, current_time)
    
    if not call_details:
        logger.info("No new calls found or error occurred")
        save_last_check_time(current_time)
        return 0
    
    # If there are new calls, download the recordings once
    if len(call_details) > 0:
        logger.info(f"Found {len(call_details)} new calls")
        download_url = api.download_call_records(last_check, current_time)
        
        # Create a temporary directory for extraction
        temp_dir = None
        audio_files = {}
        
        if download_url:
            temp_dir, audio_files = download_and_extract_audio_archive(download_url)
        
        # Sort calls by timestamp
        sorted_calls = sorted(call_details, key=lambda x: x.get('start_stamp', 0))
        
        # Process each call
        processed_count = 0
        found_last_call = False if last_uuid else True
        
        for call in sorted_calls:
            uuid = call.get('uuid', '')
            
            # Skip calls until we find the last processed UUID
            if not found_last_call:
                if uuid == last_uuid:
                    found_last_call = True
                continue
            
            try:
                call_time = call.get('start_stamp', 0)
                
                # Format and send message
                message = format_call_details(call)
                
                logger.debug(f"Processing call UUID: {uuid}")
                
                # Find the matching audio file
                audio_path = None
                if temp_dir and os.path.exists(temp_dir):
                    for filename, filepath in audio_files.items():
                        if uuid in filename and os.path.isfile(filepath):
                            audio_path = filepath
                            logger.debug(f"Found matching audio file: {filepath}")
                            break
                
                # Send the message with audio if available
                sent = False
                if audio_path and os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                    try:
                        logger.debug(f"Sending audio file: {audio_path} ({os.path.getsize(audio_path)} bytes)")
                        with open(audio_path, 'rb') as audio:
                            bot.send_audio(
                                TELEGRAM_CHANNEL_ID,
                                audio,
                                caption=message,
                                parse_mode='HTML'
                            )
                        logger.info(f"Successfully sent audio for call UUID: {uuid}")
                        sent = True
                    except Exception as audio_error:
                        logger.error(f"Error sending audio: {audio_error}", exc_info=True)
                
                # If audio sending failed or no audio was found, send text message only
                if not sent:
                    logger.debug(f"Sending text-only message for call UUID: {uuid}")
                    bot.send_message(
                        TELEGRAM_CHANNEL_ID,
                        message + "\n\n⚠️ <i>Recording couldn't be sent</i>",
                        parse_mode='HTML'
                    )
                    logger.info(f"Sent text-only notification for UUID: {uuid}")
                
                processed_count += 1
                
                # Update last check time and last call UUID
                save_last_check_time(call_time)
                save_last_call_uuid(uuid)
                
                # Add delay to avoid rate limiting
                time.sleep(1)
                
            except telebot.apihelper.ApiTelegramException as e:
                if "retry after" in str(e).lower():
                    retry_time = int(str(e).split("retry after ")[1])
                    logger.info(f"Rate limited. Waiting for {retry_time} seconds")
                    time.sleep(retry_time + 1)  # Wait the required time plus 1 second
                    # Try again with text-only message
                    try:
                        bot.send_message(
                            TELEGRAM_CHANNEL_ID,
                            message + "\n\n⚠️ <i>Recording couldn't be sent (rate limited)</i>",
                            parse_mode='HTML'
                        )
                        processed_count += 1
                        logger.info(f"Sent text-only notification after rate limit for UUID: {uuid}")
                        # Update last call UUID after successful retry
                        save_last_call_uuid(uuid)
                    except Exception as retry_error:
                        logger.error(f"Error after retry: {retry_error}", exc_info=True)
                else:
                    logger.error(f"Telegram API error: {e}", exc_info=True)
                    # Try to send text-only message as fallback
                    try:
                        bot.send_message(
                            TELEGRAM_CHANNEL_ID,
                            message + "\n\n⚠️ <i>Recording couldn't be sent (API error)</i>",
                            parse_mode='HTML'
                        )
                        logger.info(f"Sent fallback text-only notification for UUID: {uuid}")
                        processed_count += 1
                        # Update last call UUID after successful fallback
                        save_last_call_uuid(uuid)
                    except Exception:
                        logger.error(f"Failed to send fallback message", exc_info=True)
            except Exception as e:
                logger.error(f"Error processing call {uuid}: {e}", exc_info=True)
                # Try to send text-only message as fallback
                try:
                    bot.send_message(
                        TELEGRAM_CHANNEL_ID,
                        message + "\n\n⚠️ <i>Recording couldn't be sent (processing error)</i>",
                        parse_mode='HTML'
                    )
                    logger.info(f"Sent fallback text-only notification for UUID: {uuid}")
                    processed_count += 1
                    # Update last call UUID after successful fallback
                    save_last_call_uuid(uuid)
                except Exception:
                    logger.error(f"Failed to send fallback message", exc_info=True)
        
        # Clean up temporary directory
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                logger.debug(f"Cleaned up temp directory: {temp_dir}")
            except Exception as e:
                logger.error(f"Error cleaning up temp directory: {e}", exc_info=True)
        
        logger.info(f"Processed {processed_count} new calls")
        return processed_count
    
    # Update the last check time to current time
    save_last_check_time(current_time)
    return 0


def get_period_calls(bot, chat_id, start_time, end_time, period_name):
    """
    Get and send calls for a specific period
    
    Args:
        bot (telebot.TeleBot): Telegram bot instance
        chat_id: Chat ID to send status messages to
        start_time (int): Start timestamp
        end_time (int): End timestamp
        period_name (str): Name of the period (e.g., "today", "month")
        
    Returns:
        int: Number of sent calls
    """
    logger.info(f"Getting {period_name} calls from {datetime.fromtimestamp(start_time)} to {datetime.fromtimestamp(end_time)}")
    
    # Get calls for the period
    api = OnlinePBXAPI()
    if not api.authenticate():
        bot.send_message(chat_id, f"Failed to authenticate with OnlinePBX API")
        return 0
    
    # Get call details
    call_details = api.get_call_details(start_time, end_time)
    
    if not call_details or len(call_details) == 0:
        bot.send_message(chat_id, f"No calls found for {period_name}")
        return 0
    
    bot.send_message(chat_id, f"Found {len(call_details)} calls for {period_name}. Sending to channel...")
    
    # Download recordings once
    download_url = api.download_call_records(start_time, end_time)
    temp_dir = None
    audio_files = {}
    
    if download_url:
        temp_dir, audio_files = download_and_extract_audio_archive(download_url)
    
    # Process and send each call
    sent_count = 0
    for call in sorted(call_details, key=lambda x: x.get('start_stamp', 0)):
        try:
            # Format message
            message_text = format_call_details(call)
            uuid = call.get('uuid', '')
            
            logger.debug(f"Processing call UUID: {uuid}")
            
            # Find the matching audio file
            audio_path = None
            if temp_dir and os.path.exists(temp_dir):
                for filename, filepath in audio_files.items():
                    if uuid in filename and os.path.isfile(filepath) and os.path.getsize(filepath) > 0:
                        audio_path = filepath
                        logger.debug(f"Found matching audio file: {filepath}")
                        break
            
            # Send with audio if available
            sent = False
            if audio_path and os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                try:
                    logger.debug(f"Sending audio file: {audio_path} ({os.path.getsize(audio_path)} bytes)")
                    with open(audio_path, 'rb') as audio:
                        bot.send_audio(
                            TELEGRAM_CHANNEL_ID,
                            audio,
                            caption=message_text,
                            parse_mode='HTML'
                        )
                    logger.info(f"Successfully sent audio for call UUID: {uuid}")
                    sent = True
                except Exception as audio_error:
                    logger.error(f"Error sending audio: {audio_error}", exc_info=True)
            
            # If audio sending failed or no audio was found, send text message only
            if not sent:
                logger.debug(f"Sending text-only message for call UUID: {uuid}")
                bot.send_message(
                    TELEGRAM_CHANNEL_ID,
                    message_text + "\n\n⚠️ <i>Recording couldn't be sent</i>",
                    parse_mode='HTML'
                )
                logger.info(f"Sent text-only notification for UUID: {uuid}")
            
            sent_count += 1
            
            # Add delay to avoid rate limiting
            time.sleep(1)
            
        except telebot.apihelper.ApiTelegramException as e:
            if "retry after" in str(e).lower():
                retry_time = int(str(e).split("retry after ")[1])
                logger.info(f"Rate limited. Waiting for {retry_time} seconds")
                time.sleep(retry_time + 1)
                # Try again with text-only message
                try:
                    bot.send_message(
                        TELEGRAM_CHANNEL_ID,
                        message_text + "\n\n⚠️ <i>Recording couldn't be sent (rate limited)</i>",
                        parse_mode='HTML'
                    )
                    sent_count += 1
                    logger.info(f"Sent text-only notification after rate limit for UUID: {uuid}")
                except Exception as retry_error:
                    logger.error(f"Error after retry: {retry_error}", exc_info=True)
            else:
                logger.error(f"Telegram API error: {e}", exc_info=True)
                # Try to send text-only message as fallback
                try:
                    bot.send_message(
                        TELEGRAM_CHANNEL_ID,
                        message_text + "\n\n⚠️ <i>Recording couldn't be sent (API error)</i>",
                        parse_mode='HTML'
                    )
                    logger.info(f"Sent fallback text-only notification for UUID: {uuid}")
                    sent_count += 1
                except Exception:
                    logger.error(f"Failed to send fallback message", exc_info=True)
        except Exception as e:
            logger.error(f"Error processing call {uuid}: {e}", exc_info=True)
            # Try to send text-only message as fallback
            try:
                bot.send_message(
                    TELEGRAM_CHANNEL_ID,
                    message_text + "\n\n⚠️ <i>Recording couldn't be sent (processing error)</i>",
                    parse_mode='HTML'
                )
                logger.info(f"Sent fallback text-only notification for UUID: {uuid}")
                sent_count += 1
            except Exception:
                logger.error(f"Failed to send fallback message", exc_info=True)
    
    # Clean up
    if temp_dir and os.path.exists(temp_dir):
        try:
            shutil.rmtree(temp_dir)
            logger.debug(f"Cleaned up temp directory: {temp_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up temp directory: {e}", exc_info=True)
    
    # Send completion message
    bot.send_message(chat_id, f"Sent {sent_count} calls to the channel")
    return sent_count


def create_test_audio_file():
    """
    Create a test audio file
    
    Returns:
        str: Path to test audio file or None on error
    """
    try:
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()
        test_file_path = os.path.join(temp_dir, "test_audio.wav")
        
        # Write a simple WAV file (1 second of silence)
        with open(test_file_path, 'wb') as f:
            # Simple WAV header for 8kHz mono 16-bit
            f.write(b'RIFF')
            f.write((36).to_bytes(4, byteorder='little'))  # ChunkSize
            f.write(b'WAVE')
            f.write(b'fmt ')
            f.write((16).to_bytes(4, byteorder='little'))  # Subchunk1Size
            f.write((1).to_bytes(2, byteorder='little'))   # AudioFormat (PCM)
            f.write((1).to_bytes(2, byteorder='little'))   # NumChannels
            f.write((8000).to_bytes(4, byteorder='little'))  # SampleRate
            f.write((16000).to_bytes(4, byteorder='little'))  # ByteRate
            f.write((2).to_bytes(2, byteorder='little'))   # BlockAlign
            f.write((16).to_bytes(2, byteorder='little'))  # BitsPerSample
            f.write(b'data')
            f.write((16000).to_bytes(4, byteorder='little'))  # Subchunk2Size
            # 1 second of silence (8000 samples * 2 bytes per sample)
            f.write(b'\x00' * 16000)
        
        logger.debug(f"Created test audio file: {test_file_path}, size: {os.path.getsize(test_file_path)} bytes")
        return test_file_path
    except Exception as e:
        logger.error(f"Error creating test audio file: {e}", exc_info=True)
        return None