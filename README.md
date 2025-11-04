# Granola API Reverse Engineering

Reverse-engineered documentation of the Granola API, including authentication flow and endpoints.

## Credits

This work builds upon the initial reverse engineering research by Joseph Thacker:
- [Reverse Engineering Granola Notes](https://josephthacker.com/hacking/2025/05/08/reverse-engineering-granola-notes.html)

## Token Management

### OAuth 2.0 Refresh Token Flow

Granola uses WorkOS for authentication with refresh token rotation.

**Authentication Flow:**

1. **Initial Authentication**

   - Requires `refresh_token` from WorkOS authentication flow
   - Requires `client_id` to identify the application to WorkOS

2. **Access Token Exchange**

   - Refresh token is exchanged for short-lived `access_token` via WorkOS `/user_management/authenticate` endpoint
   - Request: `client_id`, `grant_type: "refresh_token"`, current `refresh_token`
   - Response: new `access_token`, rotated `refresh_token`, `expires_in` (3600 seconds)

3. **Token Rotation**
   - Each exchange invalidates the old refresh token and issues a new one
   - Refresh tokens are single-use (prevents token replay attacks)
   - Access tokens expire after 1 hour

## Implementation Files

- `main.py` - Document fetching and conversion logic
- `token_manager.py` - OAuth token management and refresh
- `GETTING_REFRESH_TOKEN.md` - Method to extract tokens from Granola app

## API Endpoints

### Authentication

#### Refresh Access Token

Exchanges a refresh token for a new access token using WorkOS authentication.

**Endpoint:** `POST https://api.workos.com/user_management/authenticate`

**Request Body:**

```json
{
  "client_id": "string", // WorkOS client ID
  "grant_type": "refresh_token", // OAuth 2.0 grant type
  "refresh_token": "string" // Current refresh token
}
```

**Response:**

```json
{
  "access_token": "string", // New JWT access token
  "refresh_token": "string", // New refresh token (rotated)
  "expires_in": 3600, // Token lifetime in seconds
  "token_type": "Bearer"
}
```

---

### Document Operations

#### Get Documents

Retrieves a paginated list of user's Granola documents.

**Endpoint:** `POST https://api.granola.ai/v2/get-documents`

**Headers:**

```
Authorization: Bearer {access_token}
Content-Type: application/json
User-Agent: Granola/5.354.0
X-Client-Version: 5.354.0
```

**Request Body:**

```json
{
  "limit": 100, // Number of documents to retrieve
  "offset": 0, // Pagination offset
  "include_last_viewed_panel": true // Include document content
}
```

**Response:**

```json
{
  "docs": [
    {
      "id": "string", // Document unique identifier
      "title": "string", // Document title
      "created_at": "ISO8601", // Creation timestamp
      "updated_at": "ISO8601", // Last update timestamp
      "last_viewed_panel": {
        "content": {
          "type": "doc", // ProseMirror document type
          "content": [] // ProseMirror content nodes
        }
      }
    }
  ]
}
```

---

#### Get Document Transcript

Retrieves the transcript (audio recording utterances) for a specific document.

**Endpoint:** `POST https://api.granola.ai/v1/get-document-transcript`

**Headers:**

```
Authorization: Bearer {access_token}
Content-Type: application/json
User-Agent: Granola/5.354.0
X-Client-Version: 5.354.0
```

**Request Body:**

```json
{
  "document_id": "string" // Document ID to fetch transcript for
}
```

**Response:**

```json
[
  {
    "source": "microphone|system", // Audio source type
    "text": "string", // Transcribed text
    "start_timestamp": "ISO8601", // Utterance start time
    "end_timestamp": "ISO8601", // Utterance end time
    "confidence": 0.95 // Transcription confidence
  }
]
```

**Notes:**

- Returns `404` if document has no associated transcript
- Transcripts are generated from meeting recordings

---

## Data Structure

### Document Format

Documents are converted from ProseMirror to Markdown with frontmatter metadata:

```markdown
---
granola_id: doc_123456
title: "My Meeting Notes"
created_at: 2025-01-15T10:30:00Z
updated_at: 2025-01-15T11:45:00Z
---

# Meeting Notes

[ProseMirror content converted to Markdown]
```
