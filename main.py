import argparse
import logging
from pathlib import Path
import traceback
import json
import os
import requests
from datetime import datetime
from token_manager import TokenManager

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('granola_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def check_config_exists():
    """
    Check if config.json exists, if not provide helpful error message

    Returns:
        bool: True if config exists, False otherwise
    """
    config_path = Path('config.json')
    if not config_path.exists():
        logger.error("Config file 'config.json' not found!")
        logger.error("Please create config.json from config.json.template:")
        logger.error("  1. Copy config.json.template to config.json")
        logger.error("  2. Add your refresh_token and client_id")
        logger.error("  3. See GETTING_REFRESH_TOKEN.md for instructions on obtaining tokens")
        return False
    return True

def fetch_granola_documents(token):
    """
    Fetch documents from Granola API
    """
    url = "https://api.granola.ai/v2/get-documents"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "*/*",
        "User-Agent": "Granola/5.354.0",
        "X-Client-Version": "5.354.0"
    }
    data = {
        "limit": 100,
        "offset": 0,
        "include_last_viewed_panel": True
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching documents: {str(e)}")
        return None

def fetch_document_transcript(token, document_id):
    """
    Fetch transcript for a specific document

    Args:
        token: Access token
        document_id: Document ID to fetch transcript for

    Returns:
        dict: Transcript data or None if failed
    """
    url = "https://api.granola.ai/v1/get-document-transcript"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "*/*",
        "User-Agent": "Granola/5.354.0",
        "X-Client-Version": "5.354.0"
    }
    data = {
        "document_id": document_id
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            logger.debug(f"No transcript found for document {document_id}")
            return None
        else:
            logger.error(f"Error fetching transcript for {document_id}: {str(e)}")
            return None
    except Exception as e:
        logger.error(f"Error fetching transcript for {document_id}: {str(e)}")
        return None

def convert_prosemirror_to_markdown(content):
    """
    Convert ProseMirror JSON to Markdown
    """
    if not content or not isinstance(content, dict) or 'content' not in content:
        return ""
        
    markdown = []
    
    def process_node(node):
        if not isinstance(node, dict):
            return ""
            
        node_type = node.get('type', '')
        content = node.get('content', [])
        text = node.get('text', '')
        
        if node_type == 'heading':
            level = node.get('attrs', {}).get('level', 1)
            heading_text = ''.join(process_node(child) for child in content)
            return f"{'#' * level} {heading_text}\n\n"
            
        elif node_type == 'paragraph':
            para_text = ''.join(process_node(child) for child in content)
            return f"{para_text}\n\n"
            
        elif node_type == 'bulletList':
            items = []
            for item in content:
                if item.get('type') == 'listItem':
                    item_content = ''.join(process_node(child) for child in item.get('content', []))
                    items.append(f"- {item_content.strip()}")
            return '\n'.join(items) + '\n\n'
            
        elif node_type == 'text':
            return text
            
        return ''.join(process_node(child) for child in content)
    
    return process_node(content)

def convert_transcript_to_markdown(transcript_data):
    """
    Convert transcript JSON to formatted markdown
    
    Args:
        transcript_data: The transcript JSON response (list of utterances)
        
    Returns:
        str: Markdown formatted transcript
    """
    if not transcript_data or not isinstance(transcript_data, list):
        return "# Transcript\n\nNo transcript content available.\n"
    
    markdown = ["# Transcript\n\n"]
    
    for utterance in transcript_data:
        source = utterance.get('source', 'unknown')
        text = utterance.get('text', '')
        start_timestamp = utterance.get('start_timestamp', '')
        
        speaker = "Microphone" if source == "microphone" else "System"
        
        timestamp_str = ""
        if start_timestamp:
            try:
                dt = datetime.fromisoformat(start_timestamp.replace('Z', '+00:00'))
                timestamp_str = f"[{dt.strftime('%H:%M:%S')}]"
            except:
                timestamp_str = ""
        
        markdown.append(f"**{speaker}** {timestamp_str}\n\n{text}\n\n")
    
    return ''.join(markdown)

def sanitize_filename(title):
    """
    Convert a title to a valid filename
    """
    invalid_chars = '<>:"/\\|?*'
    filename = ''.join(c for c in title if c not in invalid_chars)
    filename = filename.replace(' ', '_')
    return filename

def main():
    logger.info("Starting Granola sync process")
    parser = argparse.ArgumentParser(description="Fetch Granola notes and save them as Markdown files in an Obsidian folder.")
    parser.add_argument("output_dir", type=str, help="The full path to the Obsidian subfolder where notes should be saved.")
    args = parser.parse_args()

    output_path = Path(args.output_dir)
    logger.info(f"Output directory set to: {output_path}")
    
    if not output_path.is_dir():
        logger.error(f"Output directory '{output_path}' does not exist or is not a directory.")
        logger.error("Please create it first.")
        return

    logger.info("Checking for config.json...")
    if not check_config_exists():
        return

    logger.info("Initializing token manager...")
    token_manager = TokenManager()

    logger.info("Obtaining access token...")
    access_token = token_manager.get_valid_token()
    if not access_token:
        logger.error("Failed to obtain access token. Exiting.")
        return

    logger.info("Access token obtained successfully. Fetching documents from Granola API...")
    api_response = fetch_granola_documents(access_token)

    if not api_response:
        logger.error("Failed to fetch documents - API response is empty")
        return
        
    if "docs" not in api_response:
        logger.error("API response format is unexpected - 'docs' key not found")
        logger.debug(f"API Response: {api_response}")
        return


    documents = api_response["docs"]
    logger.info(f"Successfully fetched {len(documents)} documents from Granola")
    
    if not documents:
        logger.warning("No documents found in the API response")
        return

    synced_count = 0
    for doc in documents:
        title = doc.get("title", "Untitled Granola Note")
        doc_id = doc.get("id", "unknown_id")
        logger.info(f"Processing document: {title} (ID: {doc_id})")
        
        doc_folder = output_path / doc_id
        doc_folder.mkdir(exist_ok=True)
        logger.debug(f"Created folder: {doc_folder}")
        
        try:
            document_json_path = doc_folder / "document.json"
            with open(document_json_path, 'w', encoding='utf-8') as f:
                json.dump(doc, f, indent=2)
            logger.debug(f"Saved raw document JSON to: {document_json_path}")
            
            transcript_data = fetch_document_transcript(access_token, doc_id)
            if transcript_data:
                transcript_json_path = doc_folder / "transcript.json"
                with open(transcript_json_path, 'w', encoding='utf-8') as f:
                    json.dump(transcript_data, f, indent=2)
                logger.debug(f"Saved raw transcript JSON to: {transcript_json_path}")
            
            metadata = {
                "document_id": doc_id,
                "title": title,
                "created_at": doc.get("created_at"),
                "updated_at": doc.get("updated_at"),
                "meeting_date": None,
                "sources": []
            }
            
            if transcript_data and isinstance(transcript_data, list) and len(transcript_data) > 0:
                sources = list(set(utterance.get('source', 'unknown') for utterance in transcript_data))
                metadata["sources"] = sources
                
                first_utterance = transcript_data[0]
                if first_utterance.get('start_timestamp'):
                    metadata["meeting_date"] = first_utterance['start_timestamp']
            
            metadata_path = doc_folder / "metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            logger.debug(f"Saved metadata to: {metadata_path}")
            
            content_to_parse = None
            if doc.get("last_viewed_panel") and \
               isinstance(doc["last_viewed_panel"], dict) and \
               doc["last_viewed_panel"].get("content") and \
               isinstance(doc["last_viewed_panel"]["content"], dict) and \
               doc["last_viewed_panel"]["content"].get("type") == "doc":
                content_to_parse = doc["last_viewed_panel"]["content"]
            
            if content_to_parse:
                logger.debug(f"Converting document to markdown: {title}")
                markdown_content = convert_prosemirror_to_markdown(content_to_parse)
                
                resume_path = doc_folder / "resume.md"
                with open(resume_path, 'w', encoding='utf-8') as f:
                    f.write(f"# {title}\n\n")
                    f.write(markdown_content)
                logger.debug(f"Saved resume to: {resume_path}")
            else:
                logger.warning(f"No content found for resume.md in document: {title}")
            
            if transcript_data:
                transcript_markdown = convert_transcript_to_markdown(transcript_data)
                transcript_md_path = doc_folder / "transcript.md"
                with open(transcript_md_path, 'w', encoding='utf-8') as f:
                    f.write(transcript_markdown)
                logger.debug(f"Saved transcript markdown to: {transcript_md_path}")
            else:
                logger.warning(f"No transcript available for document: {title}")
            
            logger.info(f"Successfully processed document: {title}")
            synced_count += 1
            
        except Exception as e:
            logger.error(f"Error processing document '{title}' (ID: {doc_id}): {str(e)}")
            logger.debug("Full traceback:", exc_info=True)

    logger.info(f"Sync complete. {synced_count} documents processed and saved to '{output_path}'")

if __name__ == "__main__":
    main()
