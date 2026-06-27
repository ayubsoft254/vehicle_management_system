#!/bin/bash

CERT_FILE="${1:-SafaricomPublicKey.cer}"
ENV_FILE="${2:-.env}"

if [ ! -f "$CERT_FILE" ]; then
  echo "Certificate file not found: $CERT_FILE"
  echo "Usage: ./cr.sh [path/to/SafaricomPublicKey.cer] [path/to/.env]"
  exit 1
fi

read -s -p "Enter M-Pesa initiator password: " MPESA_PASSWORD
echo

if [ -z "$MPESA_PASSWORD" ]; then
  echo "Password cannot be empty."
  exit 1
fi

read -s -p "Confirm M-Pesa initiator password: " MPESA_PASSWORD_CONFIRM
echo

if [ "$MPESA_PASSWORD" != "$MPESA_PASSWORD_CONFIRM" ]; then
  echo "Passwords do not match."
  exit 1
fi

echo "Encrypting..."

SECURITY_CREDENTIAL=$(printf "%s" "$MPESA_PASSWORD" | openssl pkeyutl -encrypt -certin -inkey "$CERT_FILE" | base64 -w 0 2>/dev/null)

if [ $? -ne 0 ] || [ -z "$SECURITY_CREDENTIAL" ]; then
  echo "Trying older OpenSSL method..."
  SECURITY_CREDENTIAL=$(printf "%s" "$MPESA_PASSWORD" | openssl rsautl -encrypt -inkey "$CERT_FILE" -certin | base64 -w 0 2>/dev/null)
fi

if [ -z "$SECURITY_CREDENTIAL" ]; then
  echo "Encryption failed. Check that '$CERT_FILE' is a valid Safaricom public key certificate."
  exit 1
fi

echo
echo "MPESA_SECURITY_CREDENTIAL=$SECURITY_CREDENTIAL"
echo

# Save to .env file
if [ -f "$ENV_FILE" ]; then
  if grep -q "^MPESA_SECURITY_CREDENTIAL=" "$ENV_FILE"; then
    # Replace existing line in-place
    sed -i "s|^MPESA_SECURITY_CREDENTIAL=.*|MPESA_SECURITY_CREDENTIAL=$SECURITY_CREDENTIAL|" "$ENV_FILE"
    echo "Updated MPESA_SECURITY_CREDENTIAL in $ENV_FILE"
  else
    # Append it
    echo "MPESA_SECURITY_CREDENTIAL=$SECURITY_CREDENTIAL" >> "$ENV_FILE"
    echo "Appended MPESA_SECURITY_CREDENTIAL to $ENV_FILE"
  fi
else
  echo "MPESA_SECURITY_CREDENTIAL=$SECURITY_CREDENTIAL" > "$ENV_FILE"
  echo "Created $ENV_FILE with MPESA_SECURITY_CREDENTIAL"
fi
