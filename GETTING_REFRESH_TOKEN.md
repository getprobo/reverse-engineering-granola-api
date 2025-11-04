# Obtaining Granola Refresh Token

Guide for extracting refresh tokens from Granola on macOS for API reverse engineering.

## Token Extraction Methods

### Method 1: Application Data Directory

Extract tokens directly from the Granola desktop application data.

**Location:**

```bash
~/Library/Application Support/Granola/
```

**Inspect application storage:**

```bash
cd ~/Library/Application\ Support/Granola/
find . -type f -name "*.json" -o -name "*.db"
```

**Common token storage locations:**

- `Local Storage/leveldb/*.ldb`
- `IndexedDB/`
- `tokens.json`
- `session.json`
- `auth.json`

**Extract token from LevelDB:**

```bash
strings Local\ Storage/leveldb/*.ldb | grep -E 'refresh_token|access_token'
```

### Method 2: Network Traffic Interception

Capture authentication requests using a proxy.

**Using mitmproxy:**

```bash
# Install mitmproxy
brew install mitmproxy

# Start proxy
mitmproxy -p 8080

# Configure system proxy
networksetup -setwebproxy Wi-Fi 127.0.0.1 8080
networksetup -setsecurewebproxy Wi-Fi 127.0.0.1 8080

# Launch Granola application
# Filter for authentication endpoint
# Target: api.workos.com/user_management/authenticate

# Disable proxy after capture
networksetup -setwebproxystate Wi-Fi off
networksetup -setsecurewebproxystate Wi-Fi off
```

**Using Charles Proxy:**

```bash
# Install Charles
brew install --cask charles

# Launch Charles and configure SSL proxying
# Enable macOS proxy in Charles (Proxy > macOS Proxy)
# Filter for: api.workos.com
# Launch Granola and authenticate
```

### Method 3: Browser Developer Tools

For web-based authentication flows.

**Chrome:**

```bash
# Open Chrome Developer Tools (Cmd+Option+I)
# Navigate to: https://app.granola.ai
# Network tab > Filter: authenticate or workos
# Locate authentication response containing tokens
```

## Configuration

**Create configuration file:**

```bash
cp config.json.template config.json
```

**Edit config.json:**

```json
{
  "refresh_token": "<refresh-token-value>",
  "client_id": "client_[identifier]"
}
```

**Extract client_id:**

- Found in authentication request payload
- Located in response alongside tokens
- Typically prefixed with `client_`

## Verification

**Test token validity:**

```bash
python main.py /path/to/output
```

**Expected output:**

```
Successfully obtained access token (expires in 3600 seconds)
```

## Token Lifecycle

- Refresh tokens are single-use and auto-rotated
- Application automatically updates `config.json` with new tokens
- Access tokens expire after 3600 seconds
- Refresh tokens trigger automatic renewal

## Common Issues

**Token already exchanged:**

- Extract new refresh token using methods above
- Update `config.json` with fresh token

**Invalid grant:**

- Token expired or revoked
- Re-authenticate and extract new token

**Missing client_id:**

- Verify `config.json` contains both `refresh_token` and `client_id`
- Extract from same authentication request

## Security

- Exclude `config.json` from version control
- Tokens grant full API access
- Revoke compromised tokens by logging out of Granola
